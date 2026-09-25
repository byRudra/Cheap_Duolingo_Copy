from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import CourseOut
from app.services import progress_service

router = APIRouter(prefix="/api", tags=["course"])


@router.get("/course", response_model=CourseOut)
def get_course(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The whole learning path in one call, with per-user skill/lesson state."""
    return progress_service.build_course_tree(db, user)
