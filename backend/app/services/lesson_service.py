"""Lesson attempts: the integrity backbone (§3.2).

start → answer (one stored result per exercise) → complete (one transaction,
idempotent). The client never sends XP; everything is computed here.
"""

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import local_date
from app.config import Settings, settings
from app.errors import AppError, not_found
from app.models import (
    AttemptAnswer,
    AttemptStatus,
    DailyActivity,
    Exercise,
    Lesson,
    LessonAttempt,
    User,
)
from app.schemas import (
    AchievementBrief,
    AnswerOut,
    AttemptStartOut,
    CompletionSummary,
    DailyGoalChange,
    ExerciseOut,
    LessonMetaOut,
    SkillProgressOut,
    StreakChange,
    UnlockedSkillOut,
)
from app.services import gamification, progress_service
from app.services.answer_check import check_answer


def _get_lesson(db: Session, lesson_id: int) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise not_found("LESSON_NOT_FOUND", "That lesson doesn't exist.")
    return lesson


def _get_attempt(db: Session, user: User, attempt_id: int) -> LessonAttempt:
    attempt = db.get(LessonAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise not_found("ATTEMPT_NOT_FOUND", "That lesson attempt doesn't exist.")
    return attempt


def lesson_meta(db: Session, user: User, lesson_id: int, cfg: Settings = settings) -> LessonMetaOut:
    lesson = _get_lesson(db, lesson_id)
    status = progress_service.lesson_status(db, user, lesson)
    skill = lesson.skill
    is_practice = status == "COMPLETED"
    return LessonMetaOut(
        id=lesson.id,
        title=lesson.title,
        order_index=lesson.order_index,
        lessons_in_skill=len(skill.lessons),
        exercise_count=len(lesson.exercises),
        status=status,  # type: ignore[arg-type]
        is_practice=is_practice,
        skill_id=skill.id,
        skill_title=skill.title,
        skill_icon=skill.icon,
        unit_title=skill.unit.title,
        unit_color=skill.unit.color,
        xp_reward=cfg.PRACTICE_XP if is_practice else cfg.BASE_LESSON_XP,
    )


def start_attempt(
    db: Session, user: User, lesson_id: int, now: datetime, cfg: Settings = settings
) -> AttemptStartOut:
    meta = lesson_meta(db, user, lesson_id, cfg)
    if meta.status == "LOCKED":
        raise AppError(403, "LESSON_LOCKED", "Complete the previous lessons to unlock this one.")

    gamification.apply_heart_regen(user, now, cfg)
    if user.hearts <= 0:
        raise AppError(409, "OUT_OF_HEARTS", "You're out of hearts.")

    attempt = LessonAttempt(user_id=user.id, lesson_id=lesson_id, started_at=now)
    db.add(attempt)
    db.commit()

    lesson = _get_lesson(db, lesson_id)
    return AttemptStartOut(
        attempt_id=attempt.id,
        lesson=meta,
        exercises=[
            ExerciseOut(id=ex.id, type=ex.type, prompt=ex.prompt, payload=ex.payload)
            for ex in lesson.exercises
        ],
        hearts=user.hearts,
        max_hearts=cfg.MAX_HEARTS,
    )


def _answer_response(
    exercise: Exercise, is_correct: bool, note: str | None, hearts: int, attempt: LessonAttempt
) -> AnswerOut:
    correct_answer: str | None = None
    if exercise.solution is not None:
        solution = exercise.solution
        correct_answer = solution["answer"] if "answer" in solution else solution["accepted"][0]
    return AnswerOut(
        correct=is_correct,
        correct_answer=correct_answer,
        explanation=exercise.explanation,
        note=note,
        hearts=hearts,
        out_of_hearts=attempt.status == AttemptStatus.FAILED,
    )


def _stored_answer(db: Session, attempt_id: int, exercise_id: int) -> AttemptAnswer | None:
    return db.scalars(
        select(AttemptAnswer).where(
            AttemptAnswer.attempt_id == attempt_id, AttemptAnswer.exercise_id == exercise_id
        )
    ).first()


def submit_answer(
    db: Session,
    user: User,
    attempt_id: int,
    exercise_id: int,
    answer: dict,
    now: datetime,
    cfg: Settings = settings,
) -> AnswerOut:
    attempt = _get_attempt(db, user, attempt_id)
    exercise = db.get(Exercise, exercise_id)
    if exercise is None or exercise.lesson_id != attempt.lesson_id:
        raise AppError(400, "EXERCISE_NOT_IN_LESSON", "That exercise isn't part of this lesson.")

    # Idempotent retry: return the stored result, never charge a second heart.
    stored = _stored_answer(db, attempt.id, exercise.id)
    if stored is not None:
        hearts, _ = gamification.effective_hearts(user, now, cfg)
        return _answer_response(exercise, stored.is_correct, stored.note, hearts, attempt)

    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise AppError(409, "ATTEMPT_NOT_IN_PROGRESS", "This lesson attempt has already ended.")

    result = check_answer(exercise.type, exercise.solution, answer)

    gamification.apply_heart_regen(user, now, cfg)
    if not result.correct:
        attempt.mistakes += 1
        gamification.lose_heart(user, now, cfg)
        if user.hearts == 0:
            attempt.status = AttemptStatus.FAILED
            attempt.completed_at = now

    db.add(
        AttemptAnswer(
            attempt_id=attempt.id,
            exercise_id=exercise.id,
            submitted=answer,
            is_correct=result.correct,
            note=result.note,
            created_at=now,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        # A concurrent duplicate won the race; its result (and heart) stands.
        db.rollback()
        stored = _stored_answer(db, attempt.id, exercise.id)
        assert stored is not None
        db.refresh(user)
        db.refresh(attempt)
        hearts, _ = gamification.effective_hearts(user, now, cfg)
        return _answer_response(exercise, stored.is_correct, stored.note, hearts, attempt)

    return _answer_response(exercise, result.correct, result.note, user.hearts, attempt)


def _accuracy(total: int, mistakes: int) -> int:
    if total == 0:
        return 100
    return round(100 * (total - mistakes) / total)


def _today_activity(db: Session, user: User, today) -> DailyActivity | None:
    return db.scalars(
        select(DailyActivity).where(DailyActivity.user_id == user.id, DailyActivity.date == today)
    ).first()


def _already_completed_summary(
    db: Session, user: User, attempt: LessonAttempt, now: datetime
) -> CompletionSummary:
    """Replay of /complete: report the stored result, award nothing new."""
    today = local_date(now)
    streak = gamification.display_streak(user.streak, user.last_activity_date, today)
    activity = _today_activity(db, user, today)
    view = progress_service.skill_views_for_user(db, user, progress_service.get_course(db))[
        attempt.lesson.skill_id
    ]
    total = len(attempt.lesson.exercises)
    return CompletionSummary(
        attempt_id=attempt.id,
        status=attempt.status,
        xp_earned=attempt.xp_awarded,
        perfect=attempt.mistakes == 0,
        already_completed=True,
        mistakes=attempt.mistakes,
        accuracy=_accuracy(total, attempt.mistakes),
        total_xp=user.xp,
        streak=StreakChange(before=streak, after=streak, extended=False),
        daily_goal=DailyGoalChange(
            earned=activity.xp_earned if activity else 0, goal=user.daily_goal_xp, just_met=False
        ),
        skill=SkillProgressOut(
            id=view.skill.id, title=view.skill.title, progress=view.progress, state=view.state  # type: ignore[arg-type]
        ),
        newly_unlocked_skill=None,
        new_achievements=[],
    )


def complete_attempt(
    db: Session, user: User, attempt_id: int, now: datetime, cfg: Settings = settings
) -> CompletionSummary:
    attempt = _get_attempt(db, user, attempt_id)
    if attempt.status == AttemptStatus.COMPLETED:
        return _already_completed_summary(db, user, attempt, now)
    if attempt.status == AttemptStatus.FAILED:
        raise AppError(409, "ATTEMPT_FAILED", "This attempt ended when you ran out of hearts.")

    lesson = attempt.lesson
    total = len(lesson.exercises)
    answered = db.scalar(
        select(func.count()).select_from(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id)
    )
    if answered != total:
        raise AppError(
            409, "INCOMPLETE_ATTEMPT", f"Answer every exercise first ({answered}/{total} done)."
        )

    # Claim the attempt atomically so a double-submit can't award XP twice.
    claimed = db.execute(
        update(LessonAttempt)
        .where(LessonAttempt.id == attempt.id, LessonAttempt.status == AttemptStatus.IN_PROGRESS)
        .values(status=AttemptStatus.COMPLETED, completed_at=now)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:  # type: ignore[attr-defined]
        db.rollback()
        db.refresh(attempt)
        db.refresh(user)
        if attempt.status == AttemptStatus.COMPLETED:
            return _already_completed_summary(db, user, attempt, now)
        raise AppError(409, "ATTEMPT_NOT_IN_PROGRESS", "This lesson attempt has already ended.")
    db.refresh(attempt)

    today = local_date(now)

    # Progress + unlocks
    update_info = progress_service.record_lesson_completion(db, user, lesson, attempt.mistakes, now)
    xp = gamification.lesson_xp(update_info.first_completion, attempt.mistakes, cfg)

    # Streak
    streak_before = gamification.display_streak(user.streak, user.last_activity_date, today)
    user.streak = gamification.next_streak(user.streak, user.last_activity_date, today)
    user.longest_streak = max(user.longest_streak, user.streak)
    user.last_activity_date = today

    # Daily goal
    activity = _today_activity(db, user, today)
    if activity is None:
        activity = DailyActivity(user_id=user.id, date=today, xp_earned=0, lessons_completed=0)
        db.add(activity)
    xp_before_today = activity.xp_earned
    activity.xp_earned += xp
    activity.lessons_completed += 1

    # XP
    user.xp += xp
    attempt.xp_awarded = xp

    # Achievements (same transaction)
    db.flush()
    new_achievements = gamification.award_achievements(
        db,
        user,
        gamification.AchievementStats(
            distinct_lessons_completed=update_info.distinct_lessons_completed,
            total_xp=user.xp,
            streak=user.streak,
            perfect_lesson=attempt.mistakes == 0,
        ),
        now,
    )

    db.commit()

    view = update_info.skill_view
    unlocked = update_info.newly_unlocked_skill
    return CompletionSummary(
        attempt_id=attempt.id,
        status=attempt.status,
        xp_earned=xp,
        perfect=attempt.mistakes == 0,
        already_completed=False,
        mistakes=attempt.mistakes,
        accuracy=_accuracy(total, attempt.mistakes),
        total_xp=user.xp,
        streak=StreakChange(
            before=streak_before, after=user.streak, extended=user.streak > streak_before
        ),
        daily_goal=DailyGoalChange(
            earned=activity.xp_earned,
            goal=user.daily_goal_xp,
            just_met=gamification.daily_goal_just_met(
                xp_before_today, activity.xp_earned, user.daily_goal_xp
            ),
        ),
        skill=SkillProgressOut(
            id=view.skill.id, title=view.skill.title, progress=view.progress, state=view.state  # type: ignore[arg-type]
        ),
        newly_unlocked_skill=UnlockedSkillOut(id=unlocked.id, title=unlocked.title)
        if unlocked
        else None,
        new_achievements=[
            AchievementBrief(code=a.code, title=a.title, icon=a.icon) for a in new_achievements
        ],
    )

