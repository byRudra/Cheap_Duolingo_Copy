"""Seed the demo courses and learners (§7).

    python -m app.seed           # seed only if the database is empty
    python -m app.seed --reset   # drop everything and reseed

Both forms are idempotent. Dates are relative to "today" in APP_TIMEZONE at
the moment the seed runs, so re-seed before a demo to keep the streak alive.
"""

import argparse
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import local_date, utc_now
from app.config import settings
from app.content import COURSES
from app.content.builders import validate_course
from app.database import Base, SessionLocal, engine
from app.models import (
    Achievement,
    AttemptMode,
    AttemptStatus,
    Course,
    DailyActivity,
    Exercise,
    Lesson,
    LessonAttempt,
    Skill,
    Unit,
    User,
    UserAchievement,
    UserLessonProgress,
    UserSkillProgress,
)


ACHIEVEMENTS = [
    ("FIRST_LESSON", "First Steps", "Complete your first lesson.", "🏆"),
    ("PERFECT_LESSON", "Flawless", "Complete a lesson with no mistakes.", "🎯"),
    ("XP_100", "XP Hunter", "Earn 100 total XP.", "⭐"),
    ("STREAK_3", "On Fire", "Reach a 3-day streak.", "🔥"),
    ("LESSONS_5", "Dedicated", "Complete 5 different lessons.", "📚"),
]

LEADERBOARD_RIVALS = [
    ("sofia", "Sofía", "#EC4899", 140),
    ("mateo", "Mateo", "#0EA5E9", 95),
    ("priya", "Priya", "#F97316", 70),
    ("liam", "Liam", "#14B8A6", 38),
    ("aisha", "Aisha", "#A855F7", 20),
]


def _utc_at_local_noon(day, tz_name: str) -> datetime:
    """Naive-UTC timestamp for midday on ``day`` in the app timezone."""
    local = datetime.combine(day, time(12, 0), tzinfo=ZoneInfo(tz_name))
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def _add_course(db: Session, data: dict[str, Any]) -> tuple[Course, list[Skill]]:
    """Insert one course tree; skill order_index runs course-wide from 1."""
    validate_course(data)
    course = Course(
        title=data["title"],
        language_code=data["language_code"],
        flag_emoji=data["flag_emoji"],
        description=data["description"],
    )
    db.add(course)
    skills: list[Skill] = []
    for unit_index, unit_data in enumerate(data["units"], start=1):
        unit = Unit(
            course=course,
            order_index=unit_index,
            title=unit_data["title"],
            description=unit_data["description"],
            color=unit_data["color"],
        )
        db.add(unit)
        for skill_data in unit_data["skills"]:
            skill = Skill(
                unit=unit, order_index=len(skills) + 1, title=skill_data["title"], icon=skill_data["icon"]
            )
            db.add(skill)
            skills.append(skill)
            for lesson_index, (lesson_title, exercises) in enumerate(skill_data["lessons"], start=1):
                lesson = Lesson(skill=skill, order_index=lesson_index, title=lesson_title)
                db.add(lesson)
                for ex_index, ex in enumerate(exercises, start=1):
                    db.add(Exercise(lesson=lesson, order_index=ex_index, **ex))
    db.flush()
    return course, skills


def is_seeded(db: Session) -> bool:
    return db.scalars(select(Course.id)).first() is not None


def seed(db: Session, now: datetime | None = None) -> None:
    now = now or utc_now()
    today = local_date(now)
    tz = settings.APP_TIMEZONE

    # Course content: the first registered course is the demo learner's.
    courses = [_add_course(db, data) for data in COURSES]
    spanish, all_skills = courses[0]

    achievements = {code: Achievement(code=code, title=title, description=desc, icon=icon)
                    for code, title, desc, icon in ACHIEVEMENTS}
    db.add_all(achievements.values())
    db.flush()

    # Demo learner: Greetings done, Introductions half done, 3-day streak ending yesterday.
    day = [today - timedelta(days=offset) for offset in (3, 2, 1)]
    arnav = User(
        username=settings.DEMO_USERNAME,
        display_name="Arnav",
        avatar_color="#22C55E",
        xp=45,
        gems=500,
        hearts=settings.MAX_HEARTS,
        hearts_updated_at=now,
        streak=3,
        longest_streak=3,
        last_activity_date=day[2],
        daily_goal_xp=settings.DEFAULT_DAILY_GOAL_XP,
        active_course_id=spanish.id,
        created_at=_utc_at_local_noon(today - timedelta(days=10), tz),
    )
    db.add(arnav)
    db.flush()

    greetings, introductions = all_skills[0], all_skills[1]
    completed = [(greetings.lessons[0], day[0]), (greetings.lessons[1], day[1]),
                 (introductions.lessons[0], day[2])]
    for lesson, when in completed:
        # One mistake each: consistent with PERFECT_LESSON still being locked.
        db.add(UserLessonProgress(user_id=arnav.id, lesson_id=lesson.id,
                                  completed_at=_utc_at_local_noon(when, tz), best_mistakes=1))
    db.add(UserSkillProgress(user_id=arnav.id, skill_id=greetings.id,
                             unlocked_at=_utc_at_local_noon(day[0], tz), lessons_completed=2))
    db.add(UserSkillProgress(user_id=arnav.id, skill_id=introductions.id,
                             unlocked_at=_utc_at_local_noon(day[1], tz), lessons_completed=1))
    # 45 XP = three first completions (10 each) + three practice replays (5 each).
    # The attempt history backs the XP and keeps a course reset from re-paying first-completion XP.
    replays = [greetings.lessons[0], greetings.lessons[0], greetings.lessons[1]]
    for (lesson, when), replay in zip(completed, replays):
        for offset, played, xp in ((0, lesson, settings.BASE_LESSON_XP), (30, replay, settings.PRACTICE_XP)):
            finished = _utc_at_local_noon(when, tz) + timedelta(minutes=offset)
            db.add(LessonAttempt(user_id=arnav.id, lesson_id=played.id, mode=AttemptMode.LESSON,
                                 status=AttemptStatus.COMPLETED, mistakes=1, xp_awarded=xp,
                                 started_at=finished - timedelta(minutes=5), completed_at=finished))
    for when in day:
        db.add(DailyActivity(user_id=arnav.id, date=when, xp_earned=15, lessons_completed=2))
    db.add(UserAchievement(user_id=arnav.id, achievement_id=achievements["FIRST_LESSON"].id,
                           unlocked_at=_utc_at_local_noon(day[0], tz)))
    db.add(UserAchievement(user_id=arnav.id, achievement_id=achievements["STREAK_3"].id,
                           unlocked_at=_utc_at_local_noon(day[2], tz)))

    for username, name, color, xp in LEADERBOARD_RIVALS:
        db.add(User(username=username, display_name=name, avatar_color=color, xp=xp, gems=500,
                    hearts=settings.MAX_HEARTS, hearts_updated_at=now, streak=0, longest_streak=0,
                    last_activity_date=None, daily_goal_xp=settings.DEFAULT_DAILY_GOAL_XP,
                    created_at=_utc_at_local_noon(today - timedelta(days=30), tz)))

    db.commit()


def restore_demo(db: Session, now: datetime | None = None) -> None:
    """Wipe every row and reseed in the caller's session (used by POST /api/me/reset)."""
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.flush()
    db.expunge_all()  # drop ORM objects for the rows just deleted
    seed(db, now)


def reset_database() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Seed the {settings.APP_NAME} demo database.")
    parser.add_argument("--reset", action="store_true", help="drop all tables and reseed")
    args = parser.parse_args()

    if args.reset:
        reset_database()
    else:
        Base.metadata.create_all(engine)

    with SessionLocal() as db:
        if is_seeded(db):
            print("Database already seeded; nothing to do (use --reset to start over).")
            return
        seed(db)
        for course in db.scalars(select(Course).order_by(Course.id)):
            units = len(course.units)
            skills = sum(len(u.skills) for u in course.units)
            exercises = sum(len(l.exercises) for u in course.units for s in u.skills for l in s.lessons)
            print(f"Seeded {course.title} course: {units} units, {skills} skills, {exercises} exercises")
        print(f"Learner '{settings.DEMO_USERNAME}' + {len(LEADERBOARD_RIVALS)} rivals.")


if __name__ == "__main__":
    main()
