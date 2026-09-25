"""Pure game rules: hearts, streak, XP, daily goal, achievements, clock (§3)."""

from datetime import date, datetime, timedelta

import pytest

from app.clock import local_date
from app.config import Settings, settings
from app.errors import AppError
from app.models import User
from app.services import gamification as g
from app.services.gamification import AchievementStats

from .conftest import FIXED_NOW
from .helpers import achievement_codes, get_user

T0 = FIXED_NOW
MAX = 5
REGEN = 30


def minutes(n: float) -> timedelta:
    return timedelta(minutes=n)


def make_user(hearts: int, updated_at: datetime = T0, gems: int = 500) -> User:
    return User(hearts=hearts, hearts_updated_at=updated_at, gems=gems)


def test_pinned_constants():
    assert settings.MAX_HEARTS == 5
    assert settings.HEART_REGEN_MINUTES == 30
    assert settings.HEART_REFILL_GEM_COST == 350
    assert settings.BASE_LESSON_XP == 10
    assert settings.PERFECT_BONUS_XP == 5
    assert settings.PRACTICE_XP == 5
    assert settings.DEFAULT_DAILY_GOAL_XP == 20


# ── clock ────────────────────────────────────────────────────────────────────


def test_local_date_uses_app_timezone():
    assert local_date(FIXED_NOW) == date(2026, 1, 15)
    # IST is UTC+05:30: the local day starts at 18:30 UTC the previous day.
    assert local_date(datetime(2026, 1, 14, 18, 29)) == date(2026, 1, 14)
    assert local_date(datetime(2026, 1, 14, 18, 30)) == date(2026, 1, 15)
    assert local_date(datetime(2026, 1, 14, 18, 30), "UTC") == date(2026, 1, 14)


# ── hearts: lazy regeneration ────────────────────────────────────────────────


def test_regen_full_hearts_unchanged():
    assert g.regenerate_hearts(5, T0, T0 + minutes(500), MAX, REGEN) == (5, T0)


def test_regen_before_first_interval_changes_nothing():
    assert g.regenerate_hearts(2, T0, T0 + minutes(29), MAX, REGEN) == (2, T0)


def test_regen_exactly_one_interval():
    assert g.regenerate_hearts(2, T0, T0 + minutes(30), MAX, REGEN) == (3, T0 + minutes(30))


def test_regen_keeps_partial_interval_progress():
    # 45 min: one heart; the clock advances by the consumed 30 min only,
    # so the 15 min toward the next heart are kept.
    hearts, clock = g.regenerate_hearts(2, T0, T0 + minutes(45), MAX, REGEN)
    assert hearts == 3
    assert clock == T0 + minutes(30)
    # 15 more minutes completes the next heart.
    assert g.regenerate_hearts(hearts, clock, T0 + minutes(60), MAX, REGEN) == (
        4,
        T0 + minutes(60),
    )


def test_regen_multiple_intervals():
    assert g.regenerate_hearts(0, T0, T0 + minutes(100), MAX, REGEN) == (3, T0 + minutes(90))


def test_regen_caps_at_max():
    hearts, clock = g.regenerate_hearts(1, T0, T0 + timedelta(days=2), MAX, REGEN)
    assert hearts == MAX
    assert clock == T0 + timedelta(days=2)


def test_regen_above_max_is_clamped():
    assert g.regenerate_hearts(7, T0, T0, MAX, REGEN)[0] == MAX


def test_next_heart_at():
    assert g.next_heart_at(5, T0, MAX, REGEN) is None
    assert g.next_heart_at(3, T0, MAX, REGEN) == T0 + minutes(30)
    assert g.next_heart_at(0, T0, MAX, REGEN) == T0 + minutes(30)


def test_effective_hearts_does_not_mutate_user():
    user = make_user(2)
    assert g.effective_hearts(user, T0 + minutes(60)) == (4, T0 + minutes(60))
    assert user.hearts == 2 and user.hearts_updated_at == T0


# ── hearts: deduction ────────────────────────────────────────────────────────


def test_lose_heart_from_full_starts_the_regen_clock():
    user = make_user(5, updated_at=T0 - timedelta(days=3))
    g.lose_heart(user, T0)
    assert user.hearts == 4
    assert user.hearts_updated_at == T0
    assert g.next_heart_at(user.hearts, user.hearts_updated_at, MAX, REGEN) == T0 + minutes(30)


def test_lose_heart_floors_at_zero():
    user = make_user(0)
    g.lose_heart(user, T0 + minutes(10))
    assert user.hearts == 0
    user = make_user(1)
    g.lose_heart(user, T0)
    g.lose_heart(user, T0)
    assert user.hearts == 0


def test_lose_heart_applies_regen_first_and_keeps_partial_progress():
    user = make_user(3, updated_at=T0)
    g.lose_heart(user, T0 + minutes(45))  # regen to 4 (clock T0+30), then lose one
    assert user.hearts == 3
    assert user.hearts_updated_at == T0 + minutes(30)


def test_lose_heart_after_regen_to_full_resets_clock():
    user = make_user(4, updated_at=T0)
    g.lose_heart(user, T0 + minutes(40))  # regen to 5, so the clock restarts now
    assert user.hearts == 4
    assert user.hearts_updated_at == T0 + minutes(40)


def test_zero_hearts_regenerate_after_an_interval():
    user = make_user(0)
    g.apply_heart_regen(user, T0 + minutes(30))
    assert user.hearts == 1


# ── hearts: refill ───────────────────────────────────────────────────────────


def test_refill_with_enough_gems():
    user = make_user(1, gems=500)
    g.refill_hearts(user, T0)
    assert user.hearts == MAX
    assert user.gems == 150
    assert user.hearts_updated_at == T0


def test_refill_with_exact_cost():
    user = make_user(0, gems=350)
    g.refill_hearts(user, T0)
    assert user.hearts == MAX and user.gems == 0


def test_refill_without_enough_gems():
    user = make_user(1, gems=349)
    with pytest.raises(AppError) as info:
        g.refill_hearts(user, T0)
    assert (info.value.status_code, info.value.code) == (400, "INSUFFICIENT_GEMS")
    assert user.hearts == 1 and user.gems == 349


def test_refill_when_full():
    user = make_user(5)
    with pytest.raises(AppError) as info:
        g.refill_hearts(user, T0)
    assert (info.value.status_code, info.value.code) == (400, "HEARTS_FULL")
    assert user.gems == 500


def test_refill_when_regen_already_filled_hearts():
    user = make_user(4, updated_at=T0)
    with pytest.raises(AppError) as info:
        g.refill_hearts(user, T0 + minutes(30))
    assert info.value.code == "HEARTS_FULL"
    assert user.gems == 500


# ── streak ───────────────────────────────────────────────────────────────────

TODAY = date(2026, 1, 15)
YESTERDAY = TODAY - timedelta(days=1)


def test_streak_first_activity():
    assert g.next_streak(0, None, TODAY) == 1


def test_streak_consecutive_day():
    assert g.next_streak(3, YESTERDAY, TODAY) == 4


def test_streak_same_day_unchanged():
    assert g.next_streak(4, TODAY, TODAY) == 4


def test_streak_gap_resets():
    assert g.next_streak(9, TODAY - timedelta(days=2), TODAY) == 1
    assert g.next_streak(9, TODAY - timedelta(days=30), TODAY) == 1


def test_display_streak():
    assert g.display_streak(0, None, TODAY) == 0
    assert g.display_streak(4, TODAY, TODAY) == 4
    assert g.display_streak(3, YESTERDAY, TODAY) == 3  # still alive until today ends
    assert g.display_streak(3, TODAY - timedelta(days=2), TODAY) == 0  # broken


# ── XP and daily goal ────────────────────────────────────────────────────────


def test_lesson_xp():
    assert g.lesson_xp(first_completion=True, mistakes=0) == 15  # base + perfect bonus
    assert g.lesson_xp(first_completion=True, mistakes=2) == 10  # base only
    assert g.lesson_xp(first_completion=False, mistakes=0) == 5  # practice
    assert g.lesson_xp(first_completion=False, mistakes=3) == 5


def test_practice_xp_can_be_disabled():
    cfg = Settings(PRACTICE_XP=0)
    assert g.lesson_xp(first_completion=False, mistakes=0, cfg=cfg) == 0
    assert g.lesson_xp(first_completion=True, mistakes=0, cfg=cfg) == 15


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        (0, 15, False),  # still below
        (15, 20, True),  # lands exactly on the goal
        (10, 35, True),  # jumps over it
        (0, 20, True),
        (20, 25, False),  # already met earlier: never fires twice
        (25, 30, False),
        (19, 19, False),
    ],
)
def test_daily_goal_just_met(before, after, expected):
    assert g.daily_goal_just_met(before, after, 20) is expected


# ── achievements ─────────────────────────────────────────────────────────────


def stats(lessons=0, xp=0, streak=0, perfect=False) -> AchievementStats:
    return AchievementStats(
        distinct_lessons_completed=lessons, total_xp=xp, streak=streak, perfect_lesson=perfect
    )


def test_earned_achievement_codes():
    assert g.earned_achievement_codes(stats()) == set()
    assert g.earned_achievement_codes(stats(lessons=1)) == {"FIRST_LESSON"}
    assert g.earned_achievement_codes(stats(lessons=1, perfect=True)) == {
        "FIRST_LESSON",
        "PERFECT_LESSON",
    }
    assert "XP_100" not in g.earned_achievement_codes(stats(xp=99))
    assert "XP_100" in g.earned_achievement_codes(stats(xp=100))
    assert "STREAK_3" not in g.earned_achievement_codes(stats(streak=2))
    assert "STREAK_3" in g.earned_achievement_codes(stats(streak=3))
    assert "LESSONS_5" not in g.earned_achievement_codes(stats(lessons=4))
    assert g.earned_achievement_codes(stats(lessons=5, xp=100, streak=3, perfect=True)) == {
        "FIRST_LESSON",
        "PERFECT_LESSON",
        "XP_100",
        "STREAK_3",
        "LESSONS_5",
    }


def test_award_achievements_unlocks_each_once(seeded_db):
    db = seeded_db
    user = get_user(db)
    assert achievement_codes(db) == ["FIRST_LESSON", "STREAK_3"]

    everything = stats(lessons=5, xp=100, streak=3, perfect=True)
    new = g.award_achievements(db, user, everything, T0)
    db.commit()
    assert sorted(a.code for a in new) == ["LESSONS_5", "PERFECT_LESSON", "XP_100"]

    again = g.award_achievements(db, get_user(db), everything, T0 + minutes(5))
    db.commit()
    assert again == []
    assert achievement_codes(db) == [
        "FIRST_LESSON",
        "LESSONS_5",
        "PERFECT_LESSON",
        "STREAK_3",
        "XP_100",
    ]
