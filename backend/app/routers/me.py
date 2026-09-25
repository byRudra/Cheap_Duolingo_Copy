from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import local_date
from app.config import settings
from app.database import get_db
from app.deps import get_current_user, get_now
from app.errors import AppError
from app.models import DailyActivity, User
from app.schemas import (
    DailyGoalOut,
    MeOut,
    RefillOut,
    ResetIn,
    ResetOut,
    SetCourseIn,
    SettingsIn,
    SettingsOut,
)
from app.services import gamification, progress_service

router = APIRouter(prefix="/api/me", tags=["me"])


def build_me(db: Session, user: User, now: datetime) -> MeOut:
    """Current learner stats. Hearts regen and streak breaks are applied on read."""
    today = local_date(now)
    hearts, clock = gamification.effective_hearts(user, now)
    activity = db.scalars(
        select(DailyActivity).where(DailyActivity.user_id == user.id, DailyActivity.date == today)
    ).first()
    earned = activity.xp_earned if activity else 0
    return MeOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        avatar_color=user.avatar_color,
        xp=user.xp,
        gems=user.gems,
        hearts=hearts,
        max_hearts=settings.MAX_HEARTS,
        next_heart_at=gamification.next_heart_at(
            hearts, clock, settings.MAX_HEARTS, settings.HEART_REGEN_MINUTES
        ),
        heart_regen_minutes=settings.HEART_REGEN_MINUTES,
        refill_cost=settings.HEART_REFILL_GEM_COST,
        streak=gamification.display_streak(user.streak, user.last_activity_date, today),
        longest_streak=user.longest_streak,
        streak_extended_today=user.last_activity_date == today,
        daily_goal=DailyGoalOut(
            goal=user.daily_goal_xp, earned=earned, met=earned >= user.daily_goal_xp
        ),
        today=today,
        active_course=progress_service.course_brief(progress_service.active_course(db, user)),
        settings=SettingsOut(
            display_name=user.display_name,
            avatar_color=user.avatar_color,
            daily_goal_xp=user.daily_goal_xp,
            sound_effects=user.sound_effects,
            daily_reminder=user.daily_reminder,
            achievement_alerts=user.achievement_alerts,
        ),
    )


@router.get("", response_model=MeOut)
def get_me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
):
    return build_me(db, user, now)


@router.post("/hearts/refill", response_model=RefillOut)
def refill_hearts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
):
    gamification.refill_hearts(user, now)
    db.commit()
    return RefillOut(hearts=user.hearts, gems=user.gems, next_heart_at=None)


@router.patch("/settings", response_model=MeOut)
def update_settings(
    body: SettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
):
    """Partial update of profile and preference fields."""
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user, field, value)
    db.commit()
    return build_me(db, user, now)


@router.post("/course", response_model=MeOut)
def set_course(
    body: SetCourseIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
):
    """Switch the learner's active course. Progress in every course is kept."""
    course = progress_service.get_course(db, body.course_id)
    user.active_course_id = course.id
    db.commit()
    return build_me(db, user, now)


@router.post("/reset", response_model=ResetOut)
def reset(
    body: ResetIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
):
    """`course`: forget progress in the active course. `demo`: restore the seeded demo."""
    if body.scope == "course":
        course = progress_service.active_course(db, user)
        progress_service.reset_course_progress(db, user, course, now)
        db.commit()
        return ResetOut(scope="course", message=f"Your {course.title} progress was reset.")

    if not settings.ALLOW_DEMO_RESET:
        raise AppError(403, "DEMO_RESET_DISABLED", "Restoring the demo is turned off on this server.")

    from app.seed import restore_demo

    restore_demo(db, now)
    return ResetOut(scope="demo", message="Demo data restored.")
