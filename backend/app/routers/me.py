from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import local_date
from app.config import settings
from app.database import get_db
from app.deps import get_current_user, get_now
from app.models import DailyActivity, User
from app.schemas import DailyGoalOut, MeOut, RefillOut
from app.services import gamification

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("", response_model=MeOut)
def get_me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
):
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
    )


@router.post("/hearts/refill", response_model=RefillOut)
def refill_hearts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
):
    gamification.refill_hearts(user, now)
    db.commit()
    return RefillOut(hearts=user.hearts, gems=user.gems, next_heart_at=None)
