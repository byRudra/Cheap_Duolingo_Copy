"""Heart practice (POST /api/practice/start): free mistakes, +1 heart, no rewards."""

from datetime import timedelta

from sqlalchemy import func, select

from app.content import COURSES
from app.models import (
    Course,
    DailyActivity,
    UserAchievement,
    UserLessonProgress,
    UserSkillProgress,
)

from .conftest import FIXED_NOW
from .helpers import (
    answer,
    assert_error,
    attempt,
    complete,
    correct_answer,
    exercises,
    get_user,
    gradable,
    lesson_ids,
    set_user,
    skill_by_order,
    wrong_answer,
)

OTHER = COURSES[1]["language_code"]


def start_practice(api):
    res = api.post("/api/practice/start")
    assert res.status_code == 200, res.json()
    return res.json()


def play_practice(api, db, wrong: int = 0) -> tuple[int, int]:
    """Start practice and answer everything (first ``wrong`` gradable ones wrong)."""
    body = start_practice(api)
    attempt_id, lesson_id = body["attempt_id"], body["lesson"]["id"]
    wrong_ids = {ex.id for ex in gradable(db, lesson_id)[:wrong]}
    for ex in exercises(db, lesson_id):
        payload = wrong_answer(ex) if ex.id in wrong_ids else correct_answer(ex)
        res = answer(api, attempt_id, ex.id, payload)
        assert res.status_code == 200, res.json()
        assert res.json()["correct"] is (ex.id not in wrong_ids)
    return attempt_id, lesson_id


def side_effect_snapshot(db) -> dict:
    user = get_user(db)
    count = lambda model: db.scalar(  # noqa: E731
        select(func.count()).select_from(model).where(model.user_id == user.id)
    )
    return {
        "xp": user.xp,
        "streak": user.streak,
        "longest": user.longest_streak,
        "last_activity": user.last_activity_date,
        "gems": user.gems,
        "activity": [(a.date, a.xp_earned, a.lessons_completed) for a in db.scalars(
            select(DailyActivity).where(DailyActivity.user_id == user.id).order_by(DailyActivity.date)
        )],
        "lesson_progress": sorted(
            (p.lesson_id, p.best_mistakes, p.completed_at) for p in db.scalars(
                select(UserLessonProgress).where(UserLessonProgress.user_id == user.id)
            )
        ),
        "skill_progress": sorted(
            (p.skill_id, p.lessons_completed) for p in db.scalars(
                select(UserSkillProgress).where(UserSkillProgress.user_id == user.id)
            )
        ),
        "achievements": count(UserAchievement),
    }


# ── start ────────────────────────────────────────────────────────────────────


def test_practice_start_shape(api, seeded_db):
    body = start_practice(api)
    assert body["mode"] == "PRACTICE"
    assert body["hearts"] == 5 and body["max_hearts"] == 5
    assert body["exercises"]
    assert all("solution" not in ex for ex in body["exercises"])
    assert attempt(seeded_db, body["attempt_id"]).mode.value == "PRACTICE"


def test_normal_attempts_are_lesson_mode(api, seeded_db):
    res = api.post(f"/api/lessons/{lesson_ids(seeded_db, 2)[1]}/start")
    assert res.json()["mode"] == "LESSON"
    assert attempt(seeded_db, res.json()["attempt_id"]).mode.value == "LESSON"


def test_practice_starts_at_zero_hearts(api, seeded_db):
    set_user(seeded_db, hearts=0, hearts_updated_at=FIXED_NOW)
    # A normal lesson is refused...
    assert_error(api.post(f"/api/lessons/{lesson_ids(seeded_db, 2)[1]}/start"), 409, "OUT_OF_HEARTS")
    # ...but heart practice is allowed.
    body = start_practice(api)
    assert body["hearts"] == 0


def test_practice_picks_oldest_lesson_among_equal_mistakes(api, seeded_db):
    # Seed: three lessons, each best_mistakes=1; Greetings lesson 1 was completed first.
    assert start_practice(api)["lesson"]["id"] == lesson_ids(seeded_db, 1)[0]


def test_practice_picks_the_lesson_with_most_mistakes(api, seeded_db):
    db = seeded_db
    user = get_user(db)
    target = lesson_ids(db, 2)[0]  # most recently completed, but now the weakest
    row = db.scalars(select(UserLessonProgress).where(
        UserLessonProgress.user_id == user.id, UserLessonProgress.lesson_id == target
    )).one()
    row.best_mistakes = 4
    db.commit()
    assert start_practice(api)["lesson"]["id"] == target


def test_practice_uses_the_active_course(api, seeded_db):
    db = seeded_db
    other_id = db.scalars(select(Course.id).where(Course.language_code == OTHER)).one()
    api.post("/api/me/course", json={"course_id": other_id})
    body = start_practice(api)
    # Nothing completed there yet → falls back to the course's first lesson.
    assert body["lesson"]["id"] == skill_by_order(db, 1, OTHER).lessons[0].id
    assert body["lesson"]["language_code"] == OTHER


def test_practice_prefers_completed_lessons_in_the_active_course(api, seeded_db):
    db = seeded_db
    other_id = db.scalars(select(Course.id).where(Course.language_code == OTHER)).one()
    api.post("/api/me/course", json={"course_id": other_id})
    first, second = skill_by_order(db, 1, OTHER).lessons
    user = get_user(db)
    db.add(UserLessonProgress(user_id=user.id, lesson_id=second.id,
                              completed_at=FIXED_NOW - timedelta(days=1), best_mistakes=2))
    db.commit()
    # Spanish lessons (more mistakes elsewhere would not matter) are ignored.
    assert start_practice(api)["lesson"]["id"] == second.id


# ── answers ──────────────────────────────────────────────────────────────────


def test_wrong_answers_cost_no_hearts_and_never_fail(api, seeded_db):
    db = seeded_db
    set_user(db, hearts=1, hearts_updated_at=FIXED_NOW)
    body = start_practice(api)
    attempt_id, lesson_id = body["attempt_id"], body["lesson"]["id"]
    wrong = gradable(db, lesson_id)
    assert len(wrong) >= 2
    for ex in wrong:
        res = answer(api, attempt_id, ex.id, wrong_answer(ex)).json()
        assert res["correct"] is False
        assert res["hearts"] == 1
        assert res["out_of_hearts"] is False
    row = attempt(db, attempt_id)
    assert row.status.value == "IN_PROGRESS"
    assert row.mistakes == len(wrong)
    assert get_user(db).hearts == 1


def test_practice_works_from_zero_hearts_to_completion(api, seeded_db):
    db = seeded_db
    set_user(db, hearts=0, hearts_updated_at=FIXED_NOW)
    attempt_id, _ = play_practice(api, db, wrong=2)
    res = complete(api, attempt_id)
    assert res.status_code == 200, res.json()
    summary = res.json()
    assert summary["mode"] == "PRACTICE"
    assert summary["status"] == "COMPLETED"
    assert summary["hearts_restored"] == 1
    assert summary["hearts"] == 1
    assert summary["mistakes"] == 2
    assert summary["perfect"] is False
    assert get_user(db).hearts == 1
    assert api.get("/api/me").json()["hearts"] == 1


# ── completion ───────────────────────────────────────────────────────────────


def test_practice_completion_restores_one_heart_and_awards_nothing(api, seeded_db):
    db = seeded_db
    set_user(db, hearts=3, hearts_updated_at=FIXED_NOW)
    before = side_effect_snapshot(db)
    attempt_id, lesson_id = play_practice(api, db)
    summary = complete(api, attempt_id).json()

    assert summary["mode"] == "PRACTICE"
    assert summary["hearts_restored"] == 1 and summary["hearts"] == 4
    assert summary["xp_earned"] == 0
    assert summary["total_xp"] == 45
    assert summary["perfect"] is True
    assert summary["already_completed"] is False
    assert summary["streak"] == {"before": 3, "after": 3, "extended": False}
    assert summary["daily_goal"]["just_met"] is False
    assert summary["daily_goal"]["earned"] == 0
    assert summary["newly_unlocked_skill"] is None
    assert summary["new_achievements"] == []  # PERFECT_LESSON is NOT unlocked by practice
    assert attempt(db, attempt_id).xp_awarded == 0

    assert side_effect_snapshot(db) == before
    assert get_user(db).hearts == 4
    me = api.get("/api/me").json()
    assert me["streak_extended_today"] is False
    assert me["daily_goal"]["earned"] == 0


def test_practice_on_uncompleted_lesson_records_no_progress(api, seeded_db):
    db = seeded_db
    other_id = db.scalars(select(Course.id).where(Course.language_code == OTHER)).one()
    api.post("/api/me/course", json={"course_id": other_id})
    before = side_effect_snapshot(db)
    attempt_id, lesson_id = play_practice(api, db)
    summary = complete(api, attempt_id).json()
    assert summary["skill"]["state"] == "AVAILABLE"
    assert summary["skill"]["progress"] == 0
    assert side_effect_snapshot(db) == before
    meta = api.get(f"/api/lessons/{lesson_id}").json()
    assert meta["status"] == "AVAILABLE"


def test_practice_restores_nothing_when_hearts_are_full(api, seeded_db):
    attempt_id, _ = play_practice(api, seeded_db)
    summary = complete(api, attempt_id).json()
    assert summary["hearts_restored"] == 0
    assert summary["hearts"] == 5
    assert get_user(seeded_db).hearts == 5


def test_practice_heart_is_capped_after_regen(api, seeded_db, clock):
    # 4 stored hearts + one regenerated during the practice = full; no overflow.
    set_user(seeded_db, hearts=4, hearts_updated_at=FIXED_NOW)
    attempt_id, _ = play_practice(api, seeded_db)
    clock.advance(minutes=31)
    summary = complete(api, attempt_id).json()
    assert summary["hearts"] == 5
    assert summary["hearts_restored"] == 0
    assert get_user(seeded_db).hearts == 5


def test_repeated_practice_complete_is_idempotent(api, seeded_db):
    db = seeded_db
    set_user(db, hearts=2, hearts_updated_at=FIXED_NOW)
    attempt_id, _ = play_practice(api, db)
    first = complete(api, attempt_id).json()
    assert first["hearts_restored"] == 1 and first["hearts"] == 3
    snapshot = side_effect_snapshot(db)

    again = complete(api, attempt_id)
    assert again.status_code == 200
    body = again.json()
    assert body["already_completed"] is True
    assert body["hearts_restored"] == 0
    assert body["hearts"] == 3
    assert body["xp_earned"] == 0
    assert body["mode"] == "PRACTICE"
    assert get_user(db).hearts == 3
    assert side_effect_snapshot(db) == snapshot


def test_practice_complete_requires_every_answer(api, seeded_db):
    body = start_practice(api)
    first = exercises(seeded_db, body["lesson"]["id"])[0]
    answer(api, body["attempt_id"], first.id, correct_answer(first))
    assert_error(complete(api, body["attempt_id"]), 409, "INCOMPLETE_ATTEMPT")
    assert get_user(seeded_db).hearts == 5

