"""POST /api/me/reset: forget one course's progress, or restore the whole demo."""

import pytest
from sqlalchemy import func, select

import app.seed as seed_module
from app.content import COURSES
from app.models import (
    Course,
    DailyActivity,
    LessonAttempt,
    User,
    UserAchievement,
    UserLessonProgress,
    UserSkillProgress,
)

from .helpers import (
    achievement_codes,
    assert_error,
    complete,
    finish,
    get_user,
    lesson_ids,
    play,
    set_user,
    skill_by_order,
)

SPANISH = COURSES[0]["language_code"]
OTHER = COURSES[1]["language_code"]


def course_id(db, code: str) -> int:
    return db.scalars(select(Course.id).where(Course.language_code == code)).one()


def skill_states(api) -> list[str]:
    return [s["state"] for u in api.get("/api/course").json()["units"] for s in u["skills"]]


def lessons_done(api) -> dict[str, int]:
    return {c["language_code"]: c["lessons_completed"] for c in api.get("/api/courses").json()}


def reset(api, scope: str):
    return api.post("/api/me/reset", json={"scope": scope})


# ── validation ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("body", [{}, {"scope": "everything"}, {"scope": None}])
def test_reset_validation(api, body):
    assert_error(api.post("/api/me/reset", json=body), 422, "VALIDATION_ERROR")


# ── scope: course ────────────────────────────────────────────────────────────


def test_course_reset_forgets_active_course_progress_only(api, seeded_db):
    db = seeded_db
    # Progress in another course first (played while Spanish is active).
    finish(api, db, skill_by_order(db, 1, OTHER).lessons[0].id)
    user = get_user(db)
    xp, streak, longest = user.xp, user.streak, user.longest_streak
    achievements = achievement_codes(db)
    activity_rows = db.scalar(select(func.count()).select_from(DailyActivity))

    res = reset(api, "course")
    assert res.status_code == 200, res.json()
    assert res.json()["scope"] == "course"
    assert COURSES[0]["title"] in res.json()["message"]

    states = skill_states(api)
    assert states[0] == "AVAILABLE" and set(states[1:]) == {"LOCKED"}
    assert lessons_done(api)[SPANISH] == 0
    assert lessons_done(api)[OTHER] == 1  # other course untouched

    user = get_user(db)
    assert (user.xp, user.streak, user.longest_streak) == (xp, streak, longest)
    assert achievement_codes(db) == achievements
    assert db.scalar(select(func.count()).select_from(DailyActivity)) == activity_rows
    me = api.get("/api/me").json()
    assert me["xp"] == xp and me["streak"] == streak

    spanish_skill_ids = {s.id for s in (skill_by_order(db, i, SPANISH) for i in (1, 2))}
    rows = db.scalars(select(UserSkillProgress.skill_id).where(UserSkillProgress.user_id == user.id)).all()
    assert not spanish_skill_ids & set(rows)
    assert skill_by_order(db, 1, OTHER).id in rows


def test_course_reset_applies_to_the_active_course(api, seeded_db):
    db = seeded_db
    finish(api, db, skill_by_order(db, 1, OTHER).lessons[0].id)
    api.post("/api/me/course", json={"course_id": course_id(db, OTHER)})
    assert reset(api, "course").status_code == 200
    done = lessons_done(api)
    assert done[OTHER] == 0
    assert done[SPANISH] == 3


def test_course_reset_then_replay_counts_as_first_completion(api, seeded_db):
    db = seeded_db
    reset(api, "course")
    first = lesson_ids(db, 1)[0]
    summary = finish(api, db, first)
    assert summary["xp_earned"] == 15  # first completion again (base + perfect)
    assert summary["skill"]["state"] == "IN_PROGRESS"
    # Lessons after the reset point are locked again.
    assert_error(api.post(f"/api/lessons/{lesson_ids(db, 2)[1]}/start"), 403, "LESSON_LOCKED")


def test_in_flight_attempt_cannot_complete_a_lesson_locked_by_a_reset(api, seeded_db):
    db = seeded_db
    locked_after_reset = lesson_ids(db, 2)[1]
    attempt_id = play(api, db, locked_after_reset)
    reset(api, "course")
    res = complete(api, attempt_id)
    assert res.status_code == 409, res.json()
    user = get_user(db)
    assert user.xp == 45
    assert not db.scalars(select(UserLessonProgress).where(
        UserLessonProgress.user_id == user.id, UserLessonProgress.lesson_id == locked_after_reset
    )).all()


def test_course_reset_leaves_other_users_alone(api, seeded_db):
    db = seeded_db
    rival = db.scalars(select(User).where(User.username == "sofia")).one()
    lesson = lesson_ids(db, 1)[0]
    db.add(UserLessonProgress(user_id=rival.id, lesson_id=lesson,
                              completed_at=get_user(db).created_at, best_mistakes=0))
    db.commit()
    reset(api, "course")
    rows = db.scalars(select(UserLessonProgress).where(UserLessonProgress.user_id == rival.id)).all()
    assert [r.lesson_id for r in rows] == [lesson]


# ── scope: demo ──────────────────────────────────────────────────────────────


def table_snapshot(db) -> dict[str, int]:
    db.expire_all()
    return {
        model.__name__: db.scalar(select(func.count()).select_from(model))
        for model in (User, Course, DailyActivity, UserAchievement, UserLessonProgress,
                      UserSkillProgress, LessonAttempt)
    }


@pytest.fixture
def pinned_seed_clock(monkeypatch, clock):
    """restore_demo() reseeds with the real clock; pin it to the test clock."""
    monkeypatch.setattr(seed_module, "utc_now", lambda: clock.now)


def test_demo_reset_restores_a_fresh_seed(api, seeded_db, pinned_seed_clock):
    db = seeded_db
    fresh_me = api.get("/api/me").json()
    fresh_course = api.get("/api/course").json()
    fresh_courses = api.get("/api/courses").json()
    fresh_profile = api.get("/api/profile").json()
    fresh_board = api.get("/api/leaderboard").json()
    fresh_counts = table_snapshot(db)

    # Mess everything up: progress, XP, settings, active course, hearts, gems.
    finish(api, db, lesson_ids(db, 2)[1])
    finish(api, db, skill_by_order(db, 1, OTHER).lessons[0].id)
    api.patch("/api/me/settings", json={"display_name": "Changed", "daily_goal_xp": 50,
                                        "sound_effects": False})
    api.post("/api/me/course", json={"course_id": course_id(db, OTHER)})
    set_user(db, hearts=1, gems=10)
    assert api.get("/api/me").json() != fresh_me

    res = reset(api, "demo")
    assert res.status_code == 200, res.json()
    assert res.json()["scope"] == "demo"

    assert api.get("/api/me").json() == fresh_me
    assert api.get("/api/course").json() == fresh_course
    assert api.get("/api/courses").json() == fresh_courses
    assert api.get("/api/profile").json() == fresh_profile
    assert api.get("/api/leaderboard").json() == fresh_board
    assert table_snapshot(db) == {**fresh_counts, "LessonAttempt": 0}
    assert achievement_codes(db) == ["FIRST_LESSON", "STREAK_3"]


def test_demo_reset_is_repeatable(api, seeded_db, pinned_seed_clock):
    assert reset(api, "demo").status_code == 200
    first = table_snapshot(seeded_db)
    assert reset(api, "demo").status_code == 200
    assert table_snapshot(seeded_db) == first
    assert get_user(seeded_db).xp == 45
