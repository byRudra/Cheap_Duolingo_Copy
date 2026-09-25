"""Skill/lesson state derivation and unlocking (§3.6).

State is derived from ``user_lesson_progress`` on every read so it can never
drift: the first skill (course-wide ``order_index``) is unlocked, each later
skill unlocks when the previous one is COMPLETED, and lessons inside a skill
unlock one after another.
"""

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError
from app.models import (
    AttemptStatus,
    Course,
    Lesson,
    LessonAttempt,
    Skill,
    Unit,
    User,
    UserLessonProgress,
    UserSkillProgress,
)
from app.schemas import CourseBrief, CourseOut, CourseSummary, LessonNode, SkillNode, UnitNode


@dataclass
class SkillView:
    skill: Skill
    state: str
    lessons_total: int
    lessons_completed: int
    lesson_status: dict[int, str] = field(default_factory=dict)

    @property
    def progress(self) -> int:
        if self.lessons_total == 0:
            return 0
        return round(100 * self.lessons_completed / self.lessons_total)

    @property
    def next_lesson_id(self) -> int | None:
        lessons = self.skill.lessons
        if self.state == "LOCKED" or not lessons:
            return None
        for lesson in lessons:
            if self.lesson_status[lesson.id] == "AVAILABLE":
                return lesson.id
        return lessons[0].id  # all done → practice from the start


def _course_query():
    return select(Course).options(
        selectinload(Course.units).selectinload(Unit.skills).selectinload(Skill.lessons)
    )


def get_course(db: Session, course_id: int | None = None) -> Course:
    """Load a course with its units, skills and lessons (the first course by default)."""
    query = _course_query().order_by(Course.id)
    if course_id is not None:
        query = query.where(Course.id == course_id)
    course = db.scalars(query).first()
    if course is None:
        if course_id is not None:
            raise AppError(404, "COURSE_NOT_FOUND", "That course doesn't exist.")
        raise AppError(503, "NOT_SEEDED", "No course found. Run `python -m app.seed`.")
    return course


def active_course(db: Session, user: User) -> Course:
    """The learner's selected course, falling back to the first one."""
    if user.active_course_id is not None:
        course = db.scalars(_course_query().where(Course.id == user.active_course_id)).first()
        if course is not None:
            return course
    return get_course(db)


def course_of_lesson(db: Session, lesson: Lesson) -> Course:
    return get_course(db, lesson.skill.unit.course_id)


def course_brief(course: Course) -> CourseBrief:
    return CourseBrief(
        id=course.id, title=course.title, language_code=course.language_code, flag_emoji=course.flag_emoji
    )


def ordered_skills(course: Course) -> list[Skill]:
    return sorted(
        (skill for unit in course.units for skill in unit.skills), key=lambda s: s.order_index
    )


def completed_lesson_ids(db: Session, user_id: int) -> set[int]:
    return set(
        db.scalars(
            select(UserLessonProgress.lesson_id).where(UserLessonProgress.user_id == user_id)
        )
    )


def derive_skill_views(skills: list[Skill], completed: set[int]) -> dict[int, SkillView]:
    """Pure derivation of every skill's state from the set of completed lessons."""
    views: dict[int, SkillView] = {}
    previous_completed = True  # the first skill is always unlocked
    for skill in skills:
        lessons = skill.lessons
        done = sum(1 for lesson in lessons if lesson.id in completed)
        unlocked = previous_completed
        if not unlocked:
            state = "LOCKED"
        elif lessons and done == len(lessons):
            state = "COMPLETED"
        elif done > 0:
            state = "IN_PROGRESS"
        else:
            state = "AVAILABLE"

        statuses: dict[int, str] = {}
        prior_done = True
        for lesson in lessons:
            if lesson.id in completed:
                statuses[lesson.id] = "COMPLETED"
            elif unlocked and prior_done:
                statuses[lesson.id] = "AVAILABLE"
            else:
                statuses[lesson.id] = "LOCKED"
            prior_done = lesson.id in completed

        views[skill.id] = SkillView(skill, state, len(lessons), done, statuses)
        previous_completed = state == "COMPLETED"
    return views


def skill_views_for_user(db: Session, user: User, course: Course) -> dict[int, SkillView]:
    return derive_skill_views(ordered_skills(course), completed_lesson_ids(db, user.id))


def lesson_status(db: Session, user: User, lesson: Lesson) -> str:
    views = skill_views_for_user(db, user, course_of_lesson(db, lesson))
    return views[lesson.skill_id].lesson_status[lesson.id]


def build_course_tree(db: Session, user: User) -> CourseOut:
    course = active_course(db, user)
    views = skill_views_for_user(db, user, course)

    current_skill_id: int | None = None
    for skill in ordered_skills(course):
        if views[skill.id].state in ("AVAILABLE", "IN_PROGRESS"):
            current_skill_id = skill.id
            break

    units = []
    for unit in course.units:
        skills = []
        for skill in unit.skills:
            view = views[skill.id]
            skills.append(
                SkillNode(
                    id=skill.id,
                    title=skill.title,
                    icon=skill.icon,
                    order_index=skill.order_index,
                    state=view.state,  # type: ignore[arg-type]
                    progress=view.progress,
                    lessons_completed=view.lessons_completed,
                    lessons_total=view.lessons_total,
                    next_lesson_id=view.next_lesson_id,
                    lessons=[
                        LessonNode(
                            id=lesson.id,
                            title=lesson.title,
                            order_index=lesson.order_index,
                            status=view.lesson_status[lesson.id],  # type: ignore[arg-type]
                        )
                        for lesson in skill.lessons
                    ],
                )
            )
        units.append(
            UnitNode(
                id=unit.id,
                title=unit.title,
                description=unit.description,
                color=unit.color,
                order_index=unit.order_index,
                skills=skills,
            )
        )

    return CourseOut(
        id=course.id,
        title=course.title,
        language_code=course.language_code,
        flag_emoji=course.flag_emoji,
        current_skill_id=current_skill_id,
        units=units,
    )


@dataclass
class ProgressUpdate:
    first_completion: bool
    skill_view: SkillView
    newly_unlocked_skill: Skill | None
    distinct_lessons_completed: int


def record_lesson_completion(
    db: Session, user: User, lesson: Lesson, mistakes: int, now: datetime
) -> ProgressUpdate:
    """Update lesson/skill progress and unlock the next skill. Caller commits."""
    course = course_of_lesson(db, lesson)
    skills = ordered_skills(course)
    completed_before = completed_lesson_ids(db, user.id)
    views_before = derive_skill_views(skills, completed_before)

    progress = db.scalars(
        select(UserLessonProgress).where(
            UserLessonProgress.user_id == user.id, UserLessonProgress.lesson_id == lesson.id
        )
    ).first()
    first_completion = progress is None
    if progress is None:
        db.add(
            UserLessonProgress(
                user_id=user.id, lesson_id=lesson.id, completed_at=now, best_mistakes=mistakes
            )
        )
    else:
        progress.best_mistakes = min(progress.best_mistakes, mistakes)

    completed_after = completed_before | {lesson.id}
    views_after = derive_skill_views(skills, completed_after)
    view = views_after[lesson.skill_id]

    skill_progress = _skill_progress_row(db, user.id, lesson.skill_id, now)
    skill_progress.lessons_completed = view.lessons_completed

    newly_unlocked: Skill | None = None
    for skill in skills:
        if views_before[skill.id].state == "LOCKED" and views_after[skill.id].state != "LOCKED":
            newly_unlocked = skill
            _skill_progress_row(db, user.id, skill.id, now)
            break

    return ProgressUpdate(first_completion, view, newly_unlocked, len(completed_after))


def _skill_progress_row(db: Session, user_id: int, skill_id: int, now: datetime) -> UserSkillProgress:
    row = db.scalars(
        select(UserSkillProgress).where(
            UserSkillProgress.user_id == user_id, UserSkillProgress.skill_id == skill_id
        )
    ).first()
    if row is None:
        row = UserSkillProgress(
            user_id=user_id, skill_id=skill_id, unlocked_at=now, lessons_completed=0
        )
        db.add(row)
    return row


def count_completed_skills(db: Session, user: User, course: Course) -> tuple[int, int]:
    views = skill_views_for_user(db, user, course)
    done = sum(1 for v in views.values() if v.state == "COMPLETED")
    return done, len(views)


def count_completed_lessons(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count()).select_from(UserLessonProgress).where(
            UserLessonProgress.user_id == user.id
        )
    ) or 0


def course_summaries(db: Session, user: User) -> list[CourseSummary]:
    """Every course with the learner's progress, for the course switcher."""
    completed = completed_lesson_ids(db, user.id)
    active_id = active_course(db, user).id
    summaries = []
    for course in db.scalars(_course_query().order_by(Course.id)):
        lesson_ids = [l.id for u in course.units for s in u.skills for l in s.lessons]
        done = sum(1 for lesson_id in lesson_ids if lesson_id in completed)
        summaries.append(
            CourseSummary(
                **course_brief(course).model_dump(),
                description=course.description,
                is_active=course.id == active_id,
                lessons_completed=done,
                lessons_total=len(lesson_ids),
                progress=round(100 * done / len(lesson_ids)) if lesson_ids else 0,
            )
        )
    return summaries


def reset_course_progress(db: Session, user: User, course: Course, now: datetime) -> None:
    """Forget the learner's lesson/skill progress in one course. XP and streak stay.

    Open attempts in the course are failed, so one started before the reset
    can't complete a lesson the reset just locked again.
    """
    lesson_ids = [l.id for u in course.units for s in u.skills for l in s.lessons]
    skill_ids = [s.id for u in course.units for s in u.skills]
    db.execute(
        update(LessonAttempt)
        .where(
            LessonAttempt.user_id == user.id,
            LessonAttempt.lesson_id.in_(lesson_ids),
            LessonAttempt.status == AttemptStatus.IN_PROGRESS,
        )
        .values(status=AttemptStatus.FAILED, completed_at=now)
        .execution_options(synchronize_session=False)
    )
    db.execute(
        delete(UserLessonProgress).where(
            UserLessonProgress.user_id == user.id, UserLessonProgress.lesson_id.in_(lesson_ids)
        )
    )
    db.execute(
        delete(UserSkillProgress).where(
            UserSkillProgress.user_id == user.id, UserSkillProgress.skill_id.in_(skill_ids)
        )
    )
