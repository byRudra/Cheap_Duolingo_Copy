from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import local_date
from app.database import get_db
from app.deps import get_current_user, get_now
from app.models import Achievement, User, UserAchievement
from app.schemas import AchievementOut, LeaderboardEntry, LeaderboardOut, ProfileOut
from app.services import gamification, progress_service

router = APIRouter(prefix="/api", tags=["social"])


def _achievements(db: Session, user: User) -> list[AchievementOut]:
    unlocked = {
        ua.achievement_id: ua.unlocked_at
        for ua in db.scalars(select(UserAchievement).where(UserAchievement.user_id == user.id))
    }
    return [
        AchievementOut(
            code=a.code,
            title=a.title,
            description=a.description,
            icon=a.icon,
            unlocked=a.id in unlocked,
            unlocked_at=unlocked.get(a.id),
        )
        for a in db.scalars(select(Achievement).order_by(Achievement.id))
    ]


@router.get("/profile", response_model=ProfileOut)
def get_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
):
    course = progress_service.get_course(db)
    skills_done, skills_total = progress_service.count_completed_skills(db, user)
    return ProfileOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        avatar_color=user.avatar_color,
        joined_at=user.created_at,
        total_xp=user.xp,
        gems=user.gems,
        streak=gamification.display_streak(user.streak, user.last_activity_date, local_date(now)),
        longest_streak=user.longest_streak,
        lessons_completed=progress_service.count_completed_lessons(db, user),
        skills_completed=skills_done,
        skills_total=skills_total,
        course_title=course.title,
        course_flag=course.flag_emoji,
        course_language_code=course.language_code,
        achievements=_achievements(db, user),
    )


@router.get("/leaderboard", response_model=LeaderboardOut)
def get_leaderboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    users = db.scalars(select(User).order_by(User.xp.desc(), User.id)).all()
    return LeaderboardOut(
        entries=[
            LeaderboardEntry(
                rank=i,
                user_id=u.id,
                display_name=u.display_name,
                avatar_color=u.avatar_color,
                xp=u.xp,
                is_current_user=u.id == user.id,
            )
            for i, u in enumerate(users, start=1)
        ]
    )


@router.get("/achievements", response_model=list[AchievementOut])
def get_achievements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _achievements(db, user)
