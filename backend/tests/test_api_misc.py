"""/api/me, refill, profile, leaderboard, achievements and the error format."""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.database import serialize_sqlite_writes
from app.deps import get_now
from app.main import app

from .conftest import FIXED_NOW
from .helpers import assert_error, finish, get_user, lesson_ids, set_user


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


# ── /api/me ──────────────────────────────────────────────────────────────────


def test_me_for_seeded_learner(api):
    me = api.get("/api/me").json()
    assert me["username"] == "arnav"
    assert me["xp"] == 45
    assert me["gems"] == 500
    assert me["hearts"] == 5 and me["max_hearts"] == 5
    assert me["next_heart_at"] is None
    assert me["heart_regen_minutes"] == 30
    assert me["refill_cost"] == 350
    assert me["streak"] == 3 and me["longest_streak"] == 3
    assert me["streak_extended_today"] is False
    assert me["daily_goal"] == {"goal": 20, "earned": 0, "met": False}
    assert me["today"] == "2026-01-15"


def test_me_applies_regen_on_read(api, seeded_db, clock):
    set_user(seeded_db, hearts=2, hearts_updated_at=FIXED_NOW)
    me = api.get("/api/me").json()
    assert me["hearts"] == 2
    assert me["next_heart_at"] == "2026-01-15T07:00:00Z"
    clock.advance(minutes=75)
    me = api.get("/api/me").json()
    assert me["hearts"] == 4
    assert me["next_heart_at"] == "2026-01-15T08:00:00Z"  # 15 of 30 minutes carried over


def test_unseeded_database(client):
    assert_error(client.get("/api/me"), 503, "NOT_SEEDED")
    assert_error(client.get("/api/course"), 503, "NOT_SEEDED")


# ── refill ───────────────────────────────────────────────────────────────────


def test_refill_with_gems(api, seeded_db):
    set_user(seeded_db, hearts=1, hearts_updated_at=FIXED_NOW)
    res = api.post("/api/me/hearts/refill")
    assert res.status_code == 200
    assert res.json() == {"hearts": 5, "gems": 150, "next_heart_at": None}
    user = get_user(seeded_db)
    assert (user.hearts, user.gems) == (5, 150)
    me = api.get("/api/me").json()
    assert me["hearts"] == 5 and me["gems"] == 150


def test_refill_without_enough_gems(api, seeded_db):
    set_user(seeded_db, hearts=0, gems=349, hearts_updated_at=FIXED_NOW)
    assert_error(api.post("/api/me/hearts/refill"), 400, "INSUFFICIENT_GEMS")
    user = get_user(seeded_db)
    assert (user.hearts, user.gems) == (0, 349)


def test_refill_when_full(api, seeded_db):
    assert_error(api.post("/api/me/hearts/refill"), 400, "HEARTS_FULL")
    assert get_user(seeded_db).gems == 500


def test_refill_twice_runs_out_of_gems(api, seeded_db):
    set_user(seeded_db, hearts=0, hearts_updated_at=FIXED_NOW)
    assert api.post("/api/me/hearts/refill").status_code == 200
    set_user(seeded_db, hearts=0, hearts_updated_at=FIXED_NOW)
    assert_error(api.post("/api/me/hearts/refill"), 400, "INSUFFICIENT_GEMS")
    assert get_user(seeded_db).gems == 150


# ── profile / leaderboard / achievements ─────────────────────────────────────


def test_profile(api):
    p = api.get("/api/profile").json()
    assert p["username"] == "arnav"
    assert p["total_xp"] == 45
    assert p["gems"] == 500
    assert p["streak"] == 3 and p["longest_streak"] == 3
    assert p["lessons_completed"] == 3
    assert p["skills_completed"] == 1 and p["skills_total"] == 9
    assert (p["course_title"], p["course_flag"]) == ("Spanish", "🇪🇸")
    assert p["joined_at"].endswith("Z")
    assert len(p["achievements"]) == 5
    assert sum(a["unlocked"] for a in p["achievements"]) == 2


def test_profile_updates_after_completion(api, seeded_db):
    finish(api, seeded_db, lesson_ids(seeded_db, 2)[1])
    p = api.get("/api/profile").json()
    assert p["total_xp"] == 60
    assert p["lessons_completed"] == 4
    assert p["skills_completed"] == 2
    assert p["streak"] == 4 and p["longest_streak"] == 4


def test_leaderboard(api):
    entries = api.get("/api/leaderboard").json()["entries"]
    assert [(e["rank"], e["display_name"], e["xp"]) for e in entries] == [
        (1, "Sofía", 140),
        (2, "Mateo", 95),
        (3, "Priya", 70),
        (4, "Arnav", 45),
        (5, "Liam", 38),
        (6, "Aisha", 20),
    ]
    assert [e["is_current_user"] for e in entries] == [False, False, False, True, False, False]


def test_leaderboard_moves_when_xp_is_earned(api, seeded_db):
    finish(api, seeded_db, lesson_ids(seeded_db, 2)[1])  # 60
    finish(api, seeded_db, lesson_ids(seeded_db, 3)[0])  # 75, passes Priya (70)
    entries = api.get("/api/leaderboard").json()["entries"]
    me = next(e for e in entries if e["is_current_user"])
    assert (me["rank"], me["xp"]) == (3, 75)
    assert [e["xp"] for e in entries] == sorted((e["xp"] for e in entries), reverse=True)


def test_achievements_list(api):
    items = api.get("/api/achievements").json()
    assert [a["code"] for a in items] == [
        "FIRST_LESSON", "PERFECT_LESSON", "XP_100", "STREAK_3", "LESSONS_5",
    ]
    for a in items:
        assert set(a) == {"code", "title", "description", "icon", "unlocked", "unlocked_at"}
        assert a["unlocked"] is (a["code"] in {"FIRST_LESSON", "STREAK_3"})
        assert (a["unlocked_at"] is not None) is a["unlocked"]
        if a["unlocked"]:
            assert a["unlocked_at"].endswith("Z")


def test_achievement_unlock_is_timestamped_with_the_clock(api, seeded_db, clock):
    clock.advance(hours=2)
    finish(api, seeded_db, lesson_ids(seeded_db, 2)[1])
    perfect = next(a for a in api.get("/api/achievements").json() if a["code"] == "PERFECT_LESSON")
    assert perfect["unlocked"] is True
    assert perfect["unlocked_at"] == "2026-01-15T08:30:00Z"


# ── error format ─────────────────────────────────────────────────────────────


def test_unknown_route_uses_error_format(client):
    assert_error(client.get("/api/nope"), 404, "NOT_FOUND")


def test_wrong_method_uses_error_format(client):
    assert_error(client.get("/api/me/hearts/refill"), 405, "HTTP_405")


def test_validation_errors_use_error_format(api):
    assert_error(api.get("/api/lessons/abc"), 422, "VALIDATION_ERROR")
    assert_error(api.post("/api/attempts/1/answer", json={}), 422, "VALIDATION_ERROR")
    assert_error(
        api.post("/api/attempts/1/answer", json={"exercise_id": 1, "answer": "Hola"}),
        422,
        "VALIDATION_ERROR",
    )
    res = api.post("/api/attempts/1/answer", content=b"not json",
                   headers={"Content-Type": "application/json"})
    assert_error(res, 422, "VALIDATION_ERROR")


def test_unexpected_errors_become_internal_error(api):
    def broken_clock():
        raise RuntimeError("secret stack detail")

    app.dependency_overrides[get_now] = broken_clock
    origin = settings.cors_origin_list[0]
    res = api.get("/api/me", headers={"Origin": origin})
    assert_error(res, 500, "INTERNAL_ERROR")
    assert "secret stack detail" not in res.text
    assert "Traceback" not in res.text
    assert res.headers.get("access-control-allow-origin") == origin


def test_cors_rejects_unknown_origins(client):
    res = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in res.headers


# ── SQLite write serialization (app.database) ────────────────────────────────


def test_serialize_sqlite_writes_takes_the_write_lock_at_begin(tmp_path):
    eng = create_engine(f"sqlite:///{(tmp_path / 'lock.db').as_posix()}",
                        connect_args={"timeout": 0})
    serialize_sqlite_writes(eng)
    try:
        with eng.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE t (x INTEGER)")
        with eng.connect() as first:
            first.exec_driver_sql("SELECT count(*) FROM t")  # BEGIN IMMEDIATE
            with eng.connect() as second:
                with pytest.raises(OperationalError, match="locked"):
                    second.exec_driver_sql("SELECT count(*) FROM t")
            first.rollback()
        with eng.connect() as third:  # lock released
            assert third.exec_driver_sql("SELECT count(*) FROM t").scalar() == 0
    finally:
        eng.dispose()


def test_clock_override_is_used_for_dates(api, clock):
    clock.advance(days=3, hours=1)
    assert api.get("/api/me").json()["today"] == str((FIXED_NOW + timedelta(days=3, hours=1)).date())
