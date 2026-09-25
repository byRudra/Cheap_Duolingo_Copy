"""Seed data invariants (§7) and seed idempotency."""

import sys
from collections import Counter
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import func, select

import app.seed as seed_module
from app.models import (
    Achievement,
    Course,
    DailyActivity,
    Exercise,
    ExerciseType,
    Lesson,
    Skill,
    Unit,
    User,
    UserLessonProgress,
    UserSkillProgress,
)
from app.seed import is_seeded, seed
from app.services import progress_service as ps
from app.services.answer_check import normalize

from .conftest import FIXED_NOW
from .helpers import achievement_codes, get_user

TODAY = date(2026, 1, 15)
ALL_TYPES = set(ExerciseType)


def all_lessons(db) -> list[Lesson]:
    return db.scalars(select(Lesson).order_by(Lesson.id)).all()


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# ── course structure ─────────────────────────────────────────────────────────


def test_course_structure(seeded_db):
    db = seeded_db
    course = db.scalars(select(Course)).one()
    assert (course.title, course.language_code, course.flag_emoji) == ("Spanish", "es", "🇪🇸")
    assert [u.title for u in course.units] == ["Basics", "Food", "Everyday Life"]
    skills = ps.ordered_skills(course)
    assert [s.title for s in skills] == [
        "Greetings", "Introductions", "Common Words",
        "Food", "Drinks", "Restaurants",
        "Family", "Daily Routine", "Places",
    ]
    assert [s.order_index for s in skills] == list(range(1, 10))
    for unit in course.units:
        assert len(unit.skills) == 3
    for skill in skills:
        assert len(skill.lessons) == 2
        assert [lesson.order_index for lesson in skill.lessons] == [1, 2]


def test_every_lesson_has_5_to_7_exercises_with_at_least_3_types(seeded_db):
    for lesson in all_lessons(seeded_db):
        exs = lesson.exercises
        assert 5 <= len(exs) <= 7, lesson.title
        assert len({ex.type for ex in exs}) >= 3, lesson.title
        assert [ex.order_index for ex in exs] == list(range(1, len(exs) + 1))


def test_unit_1_uses_every_exercise_type(seeded_db):
    unit_1 = seeded_db.scalars(select(Unit).where(Unit.order_index == 1)).one()
    types = {ex.type for skill in unit_1.skills for lesson in skill.lessons for ex in lesson.exercises}
    assert types == ALL_TYPES


def test_exercise_content_is_answerable(seeded_db):
    for ex in seeded_db.scalars(select(Exercise)).all():
        label = f"exercise {ex.id} ({ex.type.value}): {ex.prompt}"
        assert ex.prompt.strip(), label
        match ex.type:
            case ExerciseType.MULTIPLE_CHOICE:
                options = ex.payload["options"]
                assert len(options) >= 2 and len(set(options)) == len(options), label
                assert ex.solution["answer"] in options, label
            case ExerciseType.FILL_BLANK:
                assert ex.payload["sentence"].count("___") == 1, label
                assert ex.solution["answer"] in ex.payload["options"], label
            case ExerciseType.WORD_BANK:
                tiles = Counter(normalize(t) for t in ex.payload["tiles"])
                words = Counter(normalize(ex.solution["accepted"][0]).split())
                assert not words - tiles, f"{label}: primary answer not buildable from tiles"
                distractors = sum(tiles.values()) - sum(words.values())
                assert 1 <= distractors <= 3, f"{label}: {distractors} distractors"
            case ExerciseType.TYPE_ANSWER:
                accepted = ex.solution["accepted"]
                assert accepted and all(a.strip() for a in accepted), label
            case ExerciseType.MATCH_PAIRS:
                assert ex.solution is None, label
                pairs = ex.payload["pairs"]
                assert len(pairs) >= 2, label
                assert all(p["left"] and p["right"] for p in pairs), label


def test_some_exercises_accept_multiple_answers(seeded_db):
    multi = [
        ex for ex in seeded_db.scalars(select(Exercise)).all()
        if ex.solution and len(ex.solution.get("accepted", [])) >= 2
    ]
    assert multi


def test_achievements_catalogue(seeded_db):
    rows = seeded_db.scalars(select(Achievement).order_by(Achievement.id)).all()
    assert [(a.code, a.title, a.icon) for a in rows] == [
        ("FIRST_LESSON", "First Steps", "🏆"),
        ("PERFECT_LESSON", "Flawless", "🎯"),
        ("XP_100", "XP Hunter", "⭐"),
        ("STREAK_3", "On Fire", "🔥"),
        ("LESSONS_5", "Dedicated", "📚"),
    ]


# ── the demo learner ─────────────────────────────────────────────────────────


def test_demo_learner_stats(seeded_db):
    arnav = get_user(seeded_db)
    assert arnav.display_name == "Arnav"
    assert arnav.xp == 45
    assert arnav.gems == 500
    assert arnav.hearts == 5
    assert arnav.daily_goal_xp == 20
    assert arnav.streak == 3 and arnav.longest_streak == 3
    assert arnav.last_activity_date == TODAY - timedelta(days=1)


def test_demo_learner_activity_is_the_previous_three_days(seeded_db):
    arnav = get_user(seeded_db)
    rows = seeded_db.scalars(
        select(DailyActivity).where(DailyActivity.user_id == arnav.id).order_by(DailyActivity.date)
    ).all()
    assert [r.date for r in rows] == [TODAY - timedelta(days=d) for d in (3, 2, 1)]
    assert sum(r.xp_earned for r in rows) == arnav.xp == 45


def test_demo_learner_progress(seeded_db):
    db = seeded_db
    arnav = get_user(db)
    views = ps.skill_views_for_user(db, arnav, ps.get_course(db))
    by_title = {v.skill.title: v for v in views.values()}
    assert by_title["Greetings"].state == "COMPLETED"
    assert by_title["Greetings"].lessons_completed == 2
    assert by_title["Introductions"].state == "IN_PROGRESS"
    assert by_title["Introductions"].lessons_completed == 1
    others = {t: v.state for t, v in by_title.items() if t not in ("Greetings", "Introductions")}
    assert set(others.values()) == {"LOCKED"} and len(others) == 7

    # Stored skill progress agrees with the derived state.
    stored = {
        db.get(Skill, row.skill_id).title: row.lessons_completed
        for row in db.scalars(select(UserSkillProgress).where(UserSkillProgress.user_id == arnav.id))
    }
    assert stored == {"Greetings": 2, "Introductions": 1}

    # Seeded history has mistakes, consistent with PERFECT_LESSON still locked.
    progress = db.scalars(select(UserLessonProgress).where(UserLessonProgress.user_id == arnav.id)).all()
    assert len(progress) == 3
    assert all(p.best_mistakes >= 1 for p in progress)


def test_demo_learner_achievements(seeded_db):
    assert achievement_codes(seeded_db) == ["FIRST_LESSON", "STREAK_3"]


def test_leaderboard_rivals(seeded_db):
    rivals = seeded_db.scalars(
        select(User).where(User.username != "arnav").order_by(User.xp.desc())
    ).all()
    assert [u.xp for u in rivals] == [140, 95, 70, 38, 20]
    assert all(u.last_activity_date is None and u.streak == 0 for u in rivals)


def test_seed_dates_are_relative_to_now_in_app_timezone(db):
    # 20:00 UTC on 1 March is 01:30 on 2 March in Asia/Kolkata.
    seed(db, now=datetime(2026, 3, 1, 20, 0))
    arnav = get_user(db)
    assert arnav.last_activity_date == date(2026, 3, 1)
    dates = sorted(db.scalars(select(DailyActivity.date).where(DailyActivity.user_id == arnav.id)))
    assert dates == [date(2026, 2, 27), date(2026, 2, 28), date(2026, 3, 1)]


# ── idempotency ──────────────────────────────────────────────────────────────


def test_is_seeded(db):
    assert is_seeded(db) is False
    seed(db, now=FIXED_NOW)
    assert is_seeded(db) is True


@pytest.fixture
def seed_cli(engine, session_factory, monkeypatch):
    """Run ``python -m app.seed`` against the in-memory test engine."""
    monkeypatch.setattr(seed_module, "engine", engine)
    monkeypatch.setattr(seed_module, "SessionLocal", session_factory)

    def run(*args: str) -> None:
        monkeypatch.setattr(sys, "argv", ["app.seed", *args])
        seed_module.main()

    return run


def snapshot(db) -> dict[str, int]:
    db.expire_all()
    return {
        model.__name__: count(db, model)
        for model in (Course, Unit, Skill, Lesson, Exercise, User, Achievement, DailyActivity)
    }


def test_seed_cli_is_idempotent(db, seed_cli, capsys):
    seed_cli()
    first = snapshot(db)
    assert first["Course"] == 1 and first["User"] == 6 and first["Skill"] == 9
    seed_cli()
    assert snapshot(db) == first
    assert "already seeded" in capsys.readouterr().out


def test_seed_cli_reset_rebuilds_the_same_data(db, seed_cli):
    seed_cli()
    first = snapshot(db)
    get_user(db).xp = 999
    db.commit()
    seed_cli("--reset")
    assert snapshot(db) == first
    assert get_user(db).xp == 45
