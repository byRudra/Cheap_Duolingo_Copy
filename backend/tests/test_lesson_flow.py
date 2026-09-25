"""Lesson attempts end to end through the API (§3.2–§3.7)."""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select

from app.models import (
    AttemptAnswer,
    AttemptStatus,
    DailyActivity,
    ExerciseType,
    LessonAttempt,
    UserAchievement,
    UserLessonProgress,
    UserSkillProgress,
)
from app.services.answer_check import strip_accents

from .conftest import FIXED_NOW
from .helpers import (
    answer,
    assert_error,
    attempt,
    complete,
    correct_answer,
    exercises,
    finish,
    get_user,
    gradable,
    lesson_ids,
    play,
    set_user,
    skill_by_order,
    start,
    wrong_answer,
)

TODAY = date(2026, 1, 15)
ANSWER_KEYS = {"correct", "correct_answer", "explanation", "note", "hearts", "out_of_hearts"}
SUMMARY_KEYS = {
    "xp_earned",
    "perfect",
    "already_completed",
    "mistakes",
    "accuracy",
    "total_xp",
    "streak",
    "daily_goal",
    "skill",
    "newly_unlocked_skill",
    "new_achievements",
}


@pytest.fixture
def intro_2(seeded_db):
    """The seeded learner's next lesson (Introductions, lesson 2)."""
    return lesson_ids(seeded_db, 2)[1]


@pytest.fixture
def greet_1(seeded_db):
    """An already-completed lesson (practice replay)."""
    return lesson_ids(seeded_db, 1)[0]


def activity_today(db, day: date = TODAY) -> DailyActivity | None:
    db.expire_all()
    user = get_user(db)
    return db.scalars(
        select(DailyActivity).where(DailyActivity.user_id == user.id, DailyActivity.date == day)
    ).first()


def attempt_count(db) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(LessonAttempt))


# ── start ────────────────────────────────────────────────────────────────────


def test_start_creates_attempt_and_hides_solutions(api, seeded_db, intro_2):
    res = start(api, intro_2)
    assert res.status_code == 200
    body = res.json()
    assert body["hearts"] == 5 and body["max_hearts"] == 5
    assert body["lesson"]["id"] == intro_2
    assert body["lesson"]["status"] == "AVAILABLE"
    assert body["lesson"]["is_practice"] is False

    db_exercises = exercises(seeded_db, intro_2)
    assert [ex["id"] for ex in body["exercises"]] == [ex.id for ex in db_exercises]
    for sent, stored in zip(body["exercises"], db_exercises, strict=True):
        assert set(sent) == {"id", "type", "prompt", "payload"}
        assert "answer" not in sent["payload"] and "accepted" not in sent["payload"]
        assert sent["payload"] == stored.payload
    assert '"solution"' not in res.text
    assert '"accepted"' not in res.text

    row = attempt(seeded_db, body["attempt_id"])
    assert row.status == AttemptStatus.IN_PROGRESS
    assert row.mistakes == 0 and row.xp_awarded == 0
    assert row.started_at == FIXED_NOW


def test_type_answer_solutions_never_leak_in_start(api, seeded_db):
    for skill_order in (1, 2):
        for lesson_id in lesson_ids(seeded_db, skill_order):
            res = start(api, lesson_id)
            assert res.status_code == 200
            for ex in exercises(seeded_db, lesson_id):
                if ex.type == ExerciseType.TYPE_ANSWER:
                    sent = next(e for e in res.json()["exercises"] if e["id"] == ex.id)
                    for accepted in ex.solution["accepted"]:
                        assert accepted not in str(sent["payload"])


def test_lesson_meta(api, intro_2, greet_1):
    meta = api.get(f"/api/lessons/{intro_2}").json()
    assert meta["status"] == "AVAILABLE" and meta["is_practice"] is False
    assert meta["xp_reward"] == 10
    assert meta["skill_title"] == "Introductions"
    assert "solution" not in str(meta)
    practice = api.get(f"/api/lessons/{greet_1}").json()
    assert practice["status"] == "COMPLETED" and practice["is_practice"] is True
    assert practice["xp_reward"] == 5


def test_cannot_start_locked_lesson(api, seeded_db):
    before = attempt_count(seeded_db)
    locked = lesson_ids(seeded_db, 3)[0]  # Common Words is locked
    assert_error(start(api, locked), 403, "LESSON_LOCKED")
    assert_error(start(api, lesson_ids(seeded_db, 9)[1]), 403, "LESSON_LOCKED")
    assert attempt_count(seeded_db) == before


def test_cannot_start_with_zero_hearts(api, seeded_db, intro_2):
    set_user(seeded_db, hearts=0, hearts_updated_at=FIXED_NOW)
    before = attempt_count(seeded_db)
    assert_error(start(api, intro_2), 409, "OUT_OF_HEARTS")
    assert attempt_count(seeded_db) == before


def test_start_applies_heart_regen_before_the_zero_check(api, seeded_db, clock, intro_2):
    set_user(seeded_db, hearts=0, hearts_updated_at=FIXED_NOW)
    clock.advance(minutes=29)
    assert_error(start(api, intro_2), 409, "OUT_OF_HEARTS")
    clock.advance(minutes=1)
    res = start(api, intro_2)
    assert res.status_code == 200
    assert res.json()["hearts"] == 1


def test_start_unknown_lesson(api):
    assert_error(start(api, 99999), 404, "LESSON_NOT_FOUND")
    assert_error(api.get("/api/lessons/99999"), 404, "LESSON_NOT_FOUND")


def test_can_replay_a_completed_lesson(api, greet_1):
    res = start(api, greet_1)
    assert res.status_code == 200
    assert res.json()["lesson"]["is_practice"] is True


# ── answer ───────────────────────────────────────────────────────────────────


def test_correct_answer_keeps_hearts(api, seeded_db, intro_2):
    attempt_id = start(api, intro_2).json()["attempt_id"]
    ex = gradable(seeded_db, intro_2)[0]
    res = answer(api, attempt_id, ex.id, correct_answer(ex))
    assert res.status_code == 200
    body = res.json()
    assert set(body) == ANSWER_KEYS
    assert body["correct"] is True
    assert body["hearts"] == 5
    assert body["out_of_hearts"] is False
    assert body["explanation"] == ex.explanation
    assert get_user(seeded_db).hearts == 5


def test_wrong_answer_costs_one_heart_and_counts_a_mistake(api, seeded_db, intro_2):
    attempt_id = start(api, intro_2).json()["attempt_id"]
    ex = gradable(seeded_db, intro_2)[0]
    body = answer(api, attempt_id, ex.id, wrong_answer(ex)).json()
    assert body["correct"] is False
    assert body["hearts"] == 4
    assert body["out_of_hearts"] is False
    expected = ex.solution.get("answer") or ex.solution["accepted"][0]
    assert body["correct_answer"] == expected
    user = get_user(seeded_db)
    assert user.hearts == 4
    assert user.hearts_updated_at == FIXED_NOW  # regen clock starts at the first loss
    assert attempt(seeded_db, attempt_id).mistakes == 1
    me = api.get("/api/me").json()
    assert me["hearts"] == 4
    assert me["next_heart_at"] == "2026-01-15T07:00:00Z"


def test_duplicate_answer_does_not_deduct_twice(api, seeded_db, intro_2):
    attempt_id = start(api, intro_2).json()["attempt_id"]
    ex = gradable(seeded_db, intro_2)[0]
    first = answer(api, attempt_id, ex.id, wrong_answer(ex)).json()
    second = answer(api, attempt_id, ex.id, wrong_answer(ex)).json()
    # Even a now-correct resubmission returns the stored (wrong) result.
    third = answer(api, attempt_id, ex.id, correct_answer(ex)).json()
    assert first == second == third
    assert first["hearts"] == 4
    assert get_user(seeded_db).hearts == 4
    assert attempt(seeded_db, attempt_id).mistakes == 1
    seeded_db.expire_all()
    stored = seeded_db.scalars(
        select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt_id)
    ).all()
    assert len(stored) == 1 and stored[0].is_correct is False


def test_duplicate_correct_answer_is_stable(api, seeded_db, intro_2):
    attempt_id = start(api, intro_2).json()["attempt_id"]
    ex = gradable(seeded_db, intro_2)[0]
    first = answer(api, attempt_id, ex.id, correct_answer(ex)).json()
    second = answer(api, attempt_id, ex.id, wrong_answer(ex)).json()
    assert first == second and first["correct"] is True
    assert get_user(seeded_db).hearts == 5


def test_hearts_regenerate_lazily_between_answers(api, seeded_db, clock, intro_2):
    set_user(seeded_db, hearts=3, hearts_updated_at=FIXED_NOW - timedelta(minutes=45))
    res = start(api, intro_2)
    assert res.json()["hearts"] == 4  # one interval consumed, 15 min carried over
    attempt_id = res.json()["attempt_id"]

    ex = gradable(seeded_db, intro_2)[0]
    assert answer(api, attempt_id, ex.id, wrong_answer(ex)).json()["hearts"] == 3
    user = get_user(seeded_db)
    assert user.hearts_updated_at == FIXED_NOW - timedelta(minutes=15)
    assert api.get("/api/me").json()["next_heart_at"] == "2026-01-15T06:45:00Z"

    clock.advance(minutes=15)
    me = api.get("/api/me").json()
    assert me["hearts"] == 4
    assert me["next_heart_at"] == "2026-01-15T07:15:00Z"

    clock.advance(hours=5)
    me = api.get("/api/me").json()
    assert me["hearts"] == 5  # capped at max
    assert me["next_heart_at"] is None


def test_running_out_of_hearts_fails_the_attempt(api, seeded_db, intro_2):
    set_user(seeded_db, hearts=1, hearts_updated_at=FIXED_NOW)
    attempt_id = start(api, intro_2).json()["attempt_id"]
    first, second = gradable(seeded_db, intro_2)[:2]

    body = answer(api, attempt_id, first.id, wrong_answer(first)).json()
    assert body["correct"] is False
    assert body["hearts"] == 0
    assert body["out_of_hearts"] is True
    row = attempt(seeded_db, attempt_id)
    assert row.status == AttemptStatus.FAILED
    assert row.mistakes == 1

    # Retrying the same exercise returns the stored result and stays at 0 (floor).
    again = answer(api, attempt_id, first.id, wrong_answer(first)).json()
    assert again == body
    # The attempt is over: no more answers, no completion, no new attempt.
    assert_error(answer(api, attempt_id, second.id, correct_answer(second)), 409,
                 "ATTEMPT_NOT_IN_PROGRESS")
    assert_error(complete(api, attempt_id), 409, "ATTEMPT_FAILED")
    assert_error(start(api, intro_2), 409, "OUT_OF_HEARTS")
    assert get_user(seeded_db).hearts == 0
    assert api.get("/api/me").json()["hearts"] == 0


def test_hearts_floor_at_zero_on_a_parallel_attempt(api, seeded_db, intro_2, greet_1):
    set_user(seeded_db, hearts=1, hearts_updated_at=FIXED_NOW)
    a = start(api, intro_2).json()["attempt_id"]
    b = start(api, greet_1).json()["attempt_id"]
    ex_a = gradable(seeded_db, intro_2)[0]
    ex_b = gradable(seeded_db, greet_1)[0]
    assert answer(api, a, ex_a.id, wrong_answer(ex_a)).json()["hearts"] == 0
    body = answer(api, b, ex_b.id, wrong_answer(ex_b)).json()
    assert body["hearts"] == 0 and body["out_of_hearts"] is True
    assert get_user(seeded_db).hearts == 0
    assert attempt(seeded_db, b).status == AttemptStatus.FAILED


def test_invalid_answer_payload_is_rejected_without_cost(api, seeded_db, intro_2):
    attempt_id = start(api, intro_2).json()["attempt_id"]
    ex = next(e for e in exercises(seeded_db, intro_2) if e.type == ExerciseType.MULTIPLE_CHOICE)
    assert_error(answer(api, attempt_id, ex.id, {"answer": 42}), 422, "INVALID_ANSWER")
    assert_error(answer(api, attempt_id, ex.id, {"tiles": ["x"]}), 422, "INVALID_ANSWER")
    assert get_user(seeded_db).hearts == 5
    assert attempt(seeded_db, attempt_id).mistakes == 0
    # Nothing was stored, so a proper answer still counts.
    assert answer(api, attempt_id, ex.id, correct_answer(ex)).json()["correct"] is True


def test_match_pairs_answer(api, seeded_db, intro_2, greet_1):
    for lesson_id in (intro_2, greet_1):
        pairs = [e for e in exercises(seeded_db, lesson_id) if e.type == ExerciseType.MATCH_PAIRS]
        if pairs:
            break
    else:
        pytest.skip("no MATCH_PAIRS exercise in the chosen lessons")
    attempt_id = start(api, lesson_id).json()["attempt_id"]
    assert_error(answer(api, attempt_id, pairs[0].id, {"completed": False}), 422, "INVALID_ANSWER")
    body = answer(api, attempt_id, pairs[0].id, {"completed": True}).json()
    assert body["correct"] is True and body["correct_answer"] is None
    assert body["hearts"] == 5


def test_accent_note_through_the_api(api, seeded_db):
    candidates = [
        (lesson_id, ex)
        for skill_order in (1, 2)
        for lesson_id in lesson_ids(seeded_db, skill_order)
        for ex in exercises(seeded_db, lesson_id)
        if ex.type == ExerciseType.TYPE_ANSWER
        and strip_accents(ex.solution["accepted"][0]) != ex.solution["accepted"][0]
    ]
    if not candidates:
        pytest.skip("no accented TYPE_ANSWER exercise in unlocked lessons")
    lesson_id, ex = candidates[0]
    attempt_id = start(api, lesson_id).json()["attempt_id"]
    target = ex.solution["accepted"][0]
    body = answer(api, attempt_id, ex.id, {"text": strip_accents(target).upper()}).json()
    assert body["correct"] is True
    assert body["note"] == f"Watch your accents: {target}"
    assert body["hearts"] == 5


def test_answer_exercise_from_another_lesson(api, seeded_db, intro_2, greet_1):
    attempt_id = start(api, intro_2).json()["attempt_id"]
    foreign = exercises(seeded_db, greet_1)[0]
    assert_error(answer(api, attempt_id, foreign.id, correct_answer(foreign)), 400,
                 "EXERCISE_NOT_IN_LESSON")
    assert_error(answer(api, attempt_id, 99999, {"answer": "x"}), 400, "EXERCISE_NOT_IN_LESSON")


def test_answer_unknown_or_foreign_attempt(api, seeded_db, intro_2):
    ex = exercises(seeded_db, intro_2)[0]
    assert_error(answer(api, 99999, ex.id, correct_answer(ex)), 404, "ATTEMPT_NOT_FOUND")
    rival = get_user(seeded_db, "sofia")
    other = LessonAttempt(user_id=rival.id, lesson_id=intro_2, started_at=FIXED_NOW)
    seeded_db.add(other)
    seeded_db.commit()
    assert_error(answer(api, other.id, ex.id, correct_answer(ex)), 404, "ATTEMPT_NOT_FOUND")
    assert_error(complete(api, other.id), 404, "ATTEMPT_NOT_FOUND")


# ── complete: XP ─────────────────────────────────────────────────────────────


def test_first_perfect_completion(api, seeded_db, intro_2):
    attempt_id = play(api, seeded_db, intro_2)
    res = complete(api, attempt_id)
    assert res.status_code == 200
    s = res.json()
    assert SUMMARY_KEYS <= set(s)
    assert s["xp_earned"] == 15  # base 10 + perfect 5
    assert s["perfect"] is True
    assert s["already_completed"] is False
    assert s["mistakes"] == 0
    assert s["accuracy"] == 100
    assert s["total_xp"] == 60
    assert s["streak"] == {"before": 3, "after": 4, "extended": True}
    assert s["daily_goal"] == {"earned": 15, "goal": 20, "just_met": False}
    assert s["skill"]["state"] == "COMPLETED" and s["skill"]["progress"] == 100
    assert s["newly_unlocked_skill"]["title"] == "Common Words"
    assert [a["code"] for a in s["new_achievements"]] == ["PERFECT_LESSON"]

    user = get_user(seeded_db)
    assert (user.xp, user.streak, user.longest_streak) == (60, 4, 4)
    assert user.last_activity_date == TODAY
    row = attempt(seeded_db, attempt_id)
    assert row.status == AttemptStatus.COMPLETED
    assert row.xp_awarded == 15
    assert row.completed_at == FIXED_NOW
    today = activity_today(seeded_db)
    assert (today.xp_earned, today.lessons_completed) == (15, 1)


def test_first_completion_with_mistakes_gets_base_xp_only(api, seeded_db, intro_2):
    total = len(exercises(seeded_db, intro_2))
    s = finish(api, seeded_db, intro_2, wrong=2)
    assert s["xp_earned"] == 10
    assert s["perfect"] is False
    assert s["mistakes"] == 2
    assert s["accuracy"] == round(100 * (total - 2) / total)
    assert s["total_xp"] == 55
    assert s["new_achievements"] == []
    assert get_user(seeded_db).hearts == 3


def test_practice_replay_earns_practice_xp(api, seeded_db, greet_1):
    s = finish(api, seeded_db, greet_1)
    assert s["xp_earned"] == 5
    assert s["total_xp"] == 50
    assert s["perfect"] is True
    s = finish(api, seeded_db, greet_1, wrong=1)
    assert s["xp_earned"] == 5
    assert s["total_xp"] == 55
    seeded_db.expire_all()
    rows = seeded_db.scalars(
        select(UserLessonProgress).where(UserLessonProgress.lesson_id == greet_1)
    ).all()
    assert len(rows) == 1


def test_practice_xp_can_be_disabled(api, seeded_db, greet_1, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "PRACTICE_XP", 0)
    s = finish(api, seeded_db, greet_1)
    assert s["xp_earned"] == 0
    assert s["total_xp"] == 45


# ── complete: guards and idempotency ─────────────────────────────────────────


def test_completion_is_idempotent(api, seeded_db, intro_2):
    attempt_id = play(api, seeded_db, intro_2)
    first = complete(api, attempt_id).json()
    user_before = get_user(seeded_db)
    xp, streak = user_before.xp, user_before.streak

    for _ in range(2):
        res = complete(api, attempt_id)
        assert res.status_code == 200
        again = res.json()
        assert again["already_completed"] is True
        assert again["total_xp"] == first["total_xp"] == 60
        assert again["xp_earned"] == first["xp_earned"]  # the stored award, not a new one
        assert again["new_achievements"] == []
        assert again["newly_unlocked_skill"] is None
        assert again["daily_goal"]["just_met"] is False
        assert again["streak"]["before"] == again["streak"]["after"] == 4
        assert again["streak"]["extended"] is False

    user = get_user(seeded_db)
    assert (user.xp, user.streak) == (xp, streak)
    assert activity_today(seeded_db).xp_earned == 15
    assert activity_today(seeded_db).lessons_completed == 1
    seeded_db.expire_all()
    assert seeded_db.scalar(
        select(func.count()).select_from(UserAchievement).where(UserAchievement.user_id == user.id)
    ) == 3


def test_answers_after_completion_return_stored_results(api, seeded_db, intro_2):
    attempt_id = play(api, seeded_db, intro_2)
    complete(api, attempt_id)
    ex = gradable(seeded_db, intro_2)[0]
    body = answer(api, attempt_id, ex.id, wrong_answer(ex)).json()
    assert body["correct"] is True
    assert get_user(seeded_db).hearts == 5


def test_cannot_complete_with_unanswered_exercises(api, seeded_db, intro_2):
    attempt_id = start(api, intro_2).json()["attempt_id"]
    assert_error(complete(api, attempt_id), 409, "INCOMPLETE_ATTEMPT")
    all_but_last = exercises(seeded_db, intro_2)[:-1]
    for ex in all_but_last:
        answer(api, attempt_id, ex.id, correct_answer(ex))
    assert_error(complete(api, attempt_id), 409, "INCOMPLETE_ATTEMPT")
    assert get_user(seeded_db).xp == 45
    assert attempt(seeded_db, attempt_id).status == AttemptStatus.IN_PROGRESS
    last = exercises(seeded_db, intro_2)[-1]
    answer(api, attempt_id, last.id, correct_answer(last))
    assert complete(api, attempt_id).status_code == 200


def test_complete_unknown_attempt(api):
    assert_error(complete(api, 99999), 404, "ATTEMPT_NOT_FOUND")


# ── daily goal ───────────────────────────────────────────────────────────────


def test_daily_goal_accumulates_and_just_met_fires_once(api, seeded_db, intro_2, greet_1):
    greet_2 = lesson_ids(seeded_db, 1)[1]
    assert api.get("/api/me").json()["daily_goal"] == {"goal": 20, "earned": 0, "met": False}

    s1 = finish(api, seeded_db, intro_2)  # +15
    assert s1["daily_goal"] == {"earned": 15, "goal": 20, "just_met": False}
    s2 = finish(api, seeded_db, greet_1)  # +5 → exactly 20
    assert s2["daily_goal"] == {"earned": 20, "goal": 20, "just_met": True}
    s3 = finish(api, seeded_db, greet_2)  # +5 → 25, already met
    assert s3["daily_goal"] == {"earned": 25, "goal": 20, "just_met": False}

    assert api.get("/api/me").json()["daily_goal"] == {"goal": 20, "earned": 25, "met": True}
    today = activity_today(seeded_db)
    assert (today.xp_earned, today.lessons_completed) == (25, 3)
    seeded_db.expire_all()
    assert seeded_db.scalar(select(func.count()).select_from(DailyActivity)) == 4


def test_daily_goal_resets_on_a_new_local_day(api, seeded_db, clock, intro_2, greet_1):
    finish(api, seeded_db, intro_2)
    finish(api, seeded_db, greet_1)
    clock.advance(days=1)
    assert api.get("/api/me").json()["daily_goal"] == {"goal": 20, "earned": 0, "met": False}
    s = finish(api, seeded_db, lesson_ids(seeded_db, 3)[0])  # Common Words 1, +15
    assert s["daily_goal"] == {"earned": 15, "goal": 20, "just_met": False}
    s = finish(api, seeded_db, greet_1)  # +5 → crosses today's goal once more
    assert s["daily_goal"]["just_met"] is True


# ── streak ───────────────────────────────────────────────────────────────────


def test_streak_extends_once_per_day(api, seeded_db, clock, intro_2, greet_1):
    s = finish(api, seeded_db, intro_2)
    assert s["streak"] == {"before": 3, "after": 4, "extended": True}
    s = finish(api, seeded_db, greet_1)
    assert s["streak"] == {"before": 4, "after": 4, "extended": False}
    me = api.get("/api/me").json()
    assert me["streak"] == 4 and me["streak_extended_today"] is True

    clock.advance(days=1)
    me = api.get("/api/me").json()
    assert me["streak"] == 4 and me["streak_extended_today"] is False
    s = finish(api, seeded_db, greet_1)
    assert s["streak"] == {"before": 4, "after": 5, "extended": True}
    user = get_user(seeded_db)
    assert (user.streak, user.longest_streak) == (5, 5)


def test_streak_follows_the_app_timezone_day(api, seeded_db, clock, greet_1):
    clock.set(datetime(2026, 1, 15, 18, 29))  # 23:59 IST on the 15th
    assert finish(api, seeded_db, greet_1)["streak"]["after"] == 4
    clock.set(datetime(2026, 1, 15, 18, 31))  # 00:01 IST on the 16th
    assert finish(api, seeded_db, greet_1)["streak"] == {"before": 4, "after": 5, "extended": True}


def test_broken_streak_displays_zero_then_restarts(api, seeded_db, clock, greet_1):
    set_user(seeded_db, longest_streak=7)
    clock.advance(days=1)  # the 15th was skipped entirely
    me = api.get("/api/me").json()
    assert me["streak"] == 0
    assert me["longest_streak"] == 7
    assert api.get("/api/profile").json()["streak"] == 0

    s = finish(api, seeded_db, greet_1)
    assert s["streak"] == {"before": 0, "after": 1, "extended": True}
    user = get_user(seeded_db)
    assert (user.streak, user.longest_streak) == (1, 7)  # longest is kept
    assert api.get("/api/me").json()["streak"] == 1


# ── achievements ─────────────────────────────────────────────────────────────


def codes(summary: dict) -> list[str]:
    return [a["code"] for a in summary["new_achievements"]]


def test_perfect_lesson_unlocks_once(api, seeded_db, intro_2, greet_1):
    assert codes(finish(api, seeded_db, intro_2, wrong=1)) == []
    first = finish(api, seeded_db, greet_1)
    assert first["new_achievements"] == [
        {"code": "PERFECT_LESSON", "title": "Flawless", "icon": "🎯"}
    ]
    assert codes(finish(api, seeded_db, lesson_ids(seeded_db, 1)[1])) == []  # perfect again
    unlocked = {a["code"] for a in api.get("/api/achievements").json() if a["unlocked"]}
    assert unlocked == {"FIRST_LESSON", "STREAK_3", "PERFECT_LESSON"}


def test_xp_100_unlocks_at_threshold(api, seeded_db, intro_2, greet_1):
    set_user(seeded_db, xp=85)
    assert "XP_100" in codes(finish(api, seeded_db, intro_2))  # 85 + 15 = 100
    assert "XP_100" not in codes(finish(api, seeded_db, greet_1))


def test_lessons_5_counts_distinct_lessons_only(api, seeded_db, intro_2, greet_1):
    for _ in range(3):  # replays don't add distinct lessons
        assert "LESSONS_5" not in codes(finish(api, seeded_db, greet_1))
    assert "LESSONS_5" not in codes(finish(api, seeded_db, intro_2))  # 4 distinct
    assert "LESSONS_5" in codes(finish(api, seeded_db, lesson_ids(seeded_db, 3)[0]))  # 5
    assert "LESSONS_5" not in codes(finish(api, seeded_db, lesson_ids(seeded_db, 3)[1]))


def test_fresh_learner_first_lesson(api, seeded_db, greet_1):
    """A learner with no history: streak starts at 1, FIRST_LESSON + PERFECT_LESSON."""
    user = set_user(seeded_db, xp=0, streak=0, longest_streak=0, last_activity_date=None)
    for model in (UserAchievement, UserLessonProgress, UserSkillProgress, DailyActivity):
        seeded_db.execute(delete(model).where(model.user_id == user.id))
    seeded_db.commit()

    course = api.get("/api/course").json()
    states = [s["state"] for u in course["units"] for s in u["skills"]]
    assert states == ["AVAILABLE"] + ["LOCKED"] * 8
    assert_error(start(api, lesson_ids(seeded_db, 1)[1]), 403, "LESSON_LOCKED")

    s = finish(api, seeded_db, greet_1)
    assert s["xp_earned"] == 15
    assert s["total_xp"] == 15
    assert s["streak"] == {"before": 0, "after": 1, "extended": True}
    assert s["skill"]["state"] == "IN_PROGRESS" and s["skill"]["progress"] == 50
    assert s["newly_unlocked_skill"] is None
    assert sorted(codes(s)) == ["FIRST_LESSON", "PERFECT_LESSON"]
    assert codes(finish(api, seeded_db, lesson_ids(seeded_db, 1)[1])) == []
