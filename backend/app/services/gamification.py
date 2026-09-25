"""Game rules: hearts, streak, XP, daily goal and achievements (§3).

Rule functions are pure and take ``now``/``today`` as arguments so they can be
tested with a fixed clock. The few functions that touch the DB (achievement
awarding) only add rows; committing is the caller's job.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.errors import AppError
from app.models import Achievement, User, UserAchievement

# ── Hearts (§3.3) ────────────────────────────────────────────────────────────


def regenerate_hearts(
    stored: int, updated_at: datetime, now: datetime, max_hearts: int, regen_minutes: int
) -> tuple[int, datetime]:
    """Lazy regeneration: ``min(max, stored + floor(elapsed / interval))``.

    Returns the effective hearts and the new clock origin. The origin only
    advances by whole intervals, so progress toward the next heart is kept.
    """
    if stored >= max_hearts:
        return max_hearts, updated_at
    if regen_minutes <= 0:
        return max_hearts, now
    interval = timedelta(minutes=regen_minutes)
    elapsed = now - updated_at
    if elapsed < interval:
        return stored, updated_at
    gained = elapsed // interval
    hearts = min(max_hearts, stored + gained)
    if hearts >= max_hearts:
        return max_hearts, now
    return hearts, updated_at + gained * interval


def next_heart_at(
    hearts: int, updated_at: datetime, max_hearts: int, regen_minutes: int
) -> datetime | None:
    if hearts >= max_hearts:
        return None
    return updated_at + timedelta(minutes=regen_minutes)


def effective_hearts(user: User, now: datetime, cfg: Settings = settings) -> tuple[int, datetime]:
    return regenerate_hearts(
        user.hearts, user.hearts_updated_at, now, cfg.MAX_HEARTS, cfg.HEART_REGEN_MINUTES
    )


def apply_heart_regen(user: User, now: datetime, cfg: Settings = settings) -> None:
    user.hearts, user.hearts_updated_at = effective_hearts(user, now, cfg)


def lose_heart(user: User, now: datetime, cfg: Settings = settings) -> None:
    """Deduct one heart (floor 0), regenerating first."""
    apply_heart_regen(user, now, cfg)
    if user.hearts >= cfg.MAX_HEARTS:
        user.hearts_updated_at = now  # the regen clock starts at the first loss
    user.hearts = max(0, user.hearts - 1)


def refill_hearts(user: User, now: datetime, cfg: Settings = settings) -> None:
    apply_heart_regen(user, now, cfg)
    if user.hearts >= cfg.MAX_HEARTS:
        raise AppError(400, "HEARTS_FULL", "Your hearts are already full.")
    if user.gems < cfg.HEART_REFILL_GEM_COST:
        raise AppError(
            400, "INSUFFICIENT_GEMS", f"You need {cfg.HEART_REFILL_GEM_COST} gems to refill."
        )
    user.gems -= cfg.HEART_REFILL_GEM_COST
    user.hearts = cfg.MAX_HEARTS
    user.hearts_updated_at = now


# ── Streak (§3.4) ────────────────────────────────────────────────────────────


def next_streak(current: int, last_activity: date | None, today: date) -> int:
    """Streak after completing a lesson ``today``."""
    if last_activity is not None and last_activity >= today:
        return current
    if last_activity == today - timedelta(days=1):
        return current + 1
    return 1


def display_streak(current: int, last_activity: date | None, today: date) -> int:
    """A streak whose last activity is before yesterday is shown as broken (0)."""
    if last_activity is None or last_activity < today - timedelta(days=1):
        return 0
    return current


# ── XP and daily goal (§3.2, §3.5) ───────────────────────────────────────────


def lesson_xp(first_completion: bool, mistakes: int, cfg: Settings = settings) -> int:
    if not first_completion:
        return cfg.PRACTICE_XP
    return cfg.BASE_LESSON_XP + (cfg.PERFECT_BONUS_XP if mistakes == 0 else 0)


def daily_goal_just_met(xp_before: int, xp_after: int, goal: int) -> bool:
    return xp_before < goal <= xp_after


# ── Achievements (§3.7) ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class AchievementStats:
    distinct_lessons_completed: int
    total_xp: int
    streak: int
    perfect_lesson: bool


def earned_achievement_codes(stats: AchievementStats) -> set[str]:
    earned: set[str] = set()
    if stats.distinct_lessons_completed >= 1:
        earned.add("FIRST_LESSON")
    if stats.perfect_lesson:
        earned.add("PERFECT_LESSON")
    if stats.total_xp >= 100:
        earned.add("XP_100")
    if stats.streak >= 3:
        earned.add("STREAK_3")
    if stats.distinct_lessons_completed >= 5:
        earned.add("LESSONS_5")
    return earned


def award_achievements(
    db: Session, user: User, stats: AchievementStats, now: datetime
) -> list[Achievement]:
    """Persist newly earned achievements; each unlocks at most once."""
    codes = earned_achievement_codes(stats)
    if not codes:
        return []
    owned = set(
        db.scalars(
            select(UserAchievement.achievement_id).where(UserAchievement.user_id == user.id)
        )
    )
    candidates = db.scalars(
        select(Achievement).where(Achievement.code.in_(codes)).order_by(Achievement.id)
    ).all()
    new = [a for a in candidates if a.id not in owned]
    for achievement in new:
        db.add(UserAchievement(user_id=user.id, achievement_id=achievement.id, unlocked_at=now))
    return new
