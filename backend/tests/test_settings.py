"""PATCH /api/me/settings: partial updates, validation and persistence."""

import pytest

from .helpers import assert_error, finish, get_user, lesson_ids

DEFAULTS = {
    "display_name": "Arnav",
    "avatar_color": "#22C55E",
    "daily_goal_xp": 20,
    "sound_effects": True,
    "daily_reminder": True,
    "achievement_alerts": True,
}


def patch(api, **body):
    return api.patch("/api/me/settings", json=body)


def test_me_exposes_settings(api):
    assert api.get("/api/me").json()["settings"] == DEFAULTS


def test_empty_patch_changes_nothing(api):
    res = patch(api)
    assert res.status_code == 200
    assert res.json()["settings"] == DEFAULTS


def test_patch_every_field_returns_me_and_persists(api, seeded_db):
    changes = {
        "display_name": "Arnav G",
        "avatar_color": "#0ea5e9",
        "daily_goal_xp": 50,
        "sound_effects": False,
        "daily_reminder": False,
        "achievement_alerts": False,
    }
    res = patch(api, **changes)
    assert res.status_code == 200, res.json()
    me = res.json()
    assert me["username"] == "arnav" and "active_course" in me  # full MeOut
    assert me["settings"] == changes
    assert me["display_name"] == "Arnav G"
    assert me["avatar_color"] == "#0ea5e9"
    assert me["daily_goal"]["goal"] == 50

    assert api.get("/api/me").json()["settings"] == changes
    user = get_user(seeded_db)
    assert (user.display_name, user.avatar_color, user.daily_goal_xp) == ("Arnav G", "#0ea5e9", 50)
    assert (user.sound_effects, user.daily_reminder, user.achievement_alerts) == (False, False, False)


def test_patch_is_partial(api):
    me = patch(api, sound_effects=False).json()
    assert me["settings"] == {**DEFAULTS, "sound_effects": False}
    me = patch(api, daily_goal_xp=10).json()
    assert me["settings"] == {**DEFAULTS, "sound_effects": False, "daily_goal_xp": 10}


def test_explicit_null_leaves_field_unchanged(api):
    res = patch(api, display_name=None, daily_goal_xp=None, sound_effects=None)
    assert res.status_code == 200
    assert res.json()["settings"] == DEFAULTS


def test_display_name_is_stripped(api):
    assert patch(api, display_name="  Ana  ").json()["settings"]["display_name"] == "Ana"


@pytest.mark.parametrize("goal", [10, 20, 30, 50])
def test_allowed_daily_goals(api, goal):
    res = patch(api, daily_goal_xp=goal)
    assert res.status_code == 200
    assert res.json()["daily_goal"]["goal"] == goal


def test_display_name_boundaries(api):
    assert patch(api, display_name="A").status_code == 200
    assert patch(api, display_name="x" * 30).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"display_name": ""},
        {"display_name": "   "},
        {"display_name": "x" * 31},
        {"avatar_color": "red"},
        {"avatar_color": "#12345"},
        {"avatar_color": "#1234567"},
        {"avatar_color": "#GGGGGG"},
        {"avatar_color": "22C55E"},
        {"daily_goal_xp": 0},
        {"daily_goal_xp": 25},
        {"daily_goal_xp": 100},
        {"daily_goal_xp": "lots"},
        {"sound_effects": "maybe"},
    ],
)
def test_invalid_settings_are_rejected(api, seeded_db, body):
    assert_error(patch(api, **body), 422, "VALIDATION_ERROR")
    assert api.get("/api/me").json()["settings"] == DEFAULTS


def test_invalid_field_rejects_the_whole_patch(api):
    assert_error(patch(api, sound_effects=False, daily_goal_xp=15), 422, "VALIDATION_ERROR")
    assert api.get("/api/me").json()["settings"]["sound_effects"] is True


def test_new_daily_goal_drives_goal_tracking(api, seeded_db):
    patch(api, daily_goal_xp=10)
    summary = finish(api, seeded_db, lesson_ids(seeded_db, 2)[1])
    assert summary["daily_goal"] == {"earned": 15, "goal": 10, "just_met": True}
    me = api.get("/api/me").json()
    assert me["daily_goal"] == {"goal": 10, "earned": 15, "met": True}
    # Raising the goal afterwards un-meets it without touching earned XP.
    me = patch(api, daily_goal_xp=30).json()
    assert me["daily_goal"] == {"goal": 30, "earned": 15, "met": False}


def test_cors_allows_patch(client):
    res = client.options(
        "/api/me/settings",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert res.status_code == 200
    assert "PATCH" in res.headers["access-control-allow-methods"]
    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_patch_ignores_protected_fields(api, seeded_db):
    before = api.get("/api/me").json()
    res = patch(api, display_name="Hacker", xp=99999, hearts=0, gems=99999, streak=365,
                longest_streak=365, active_course_id=2, max_hearts=50)
    assert res.status_code == 200, res.json()
    after = api.get("/api/me").json()
    assert after["settings"]["display_name"] == "Hacker"
    for field in ("xp", "hearts", "gems", "streak", "longest_streak", "max_hearts", "active_course"):
        assert after[field] == before[field], field
    user = get_user(seeded_db)
    assert (user.xp, user.gems, user.hearts) == (before["xp"], before["gems"], before["hearts"])
