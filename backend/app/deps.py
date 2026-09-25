"""Request dependencies.

``get_current_user`` is the single auth seam: it returns the seeded learner
today; swapping in JWT/session auth means changing only this function.
``get_now`` lets tests freeze the clock via ``app.dependency_overrides``.
"""

from datetime import datetime

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.config import settings
from app.database import get_db
from app.errors import AppError
from app.models import User


def get_now() -> datetime:
    return utc_now()


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.scalars(select(User).where(User.username == settings.DEMO_USERNAME)).first()
    if user is None:
        raise AppError(503, "NOT_SEEDED", "Demo learner not found. Run `python -m app.seed`.")
    return user
