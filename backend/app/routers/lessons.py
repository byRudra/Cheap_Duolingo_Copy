from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_now
from app.models import User
from app.schemas import AnswerIn, AnswerOut, AttemptStartOut, CompletionSummary, LessonMetaOut
from app.services import lesson_service

router = APIRouter(prefix="/api", tags=["lessons"])


@router.get("/lessons/{lesson_id}", response_model=LessonMetaOut)
def get_lesson(
    lesson_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return lesson_service.lesson_meta(db, user, lesson_id)


@router.post("/lessons/{lesson_id}/start", response_model=AttemptStartOut)
def start_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
):
    return lesson_service.start_attempt(db, user, lesson_id, now)


@router.post("/attempts/{attempt_id}/answer", response_model=AnswerOut)
def answer_exercise(
    attempt_id: int,
    body: AnswerIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
):
    return lesson_service.submit_answer(db, user, attempt_id, body.exercise_id, body.answer, now)


@router.post("/attempts/{attempt_id}/complete", response_model=CompletionSummary)
def complete_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
):
    return lesson_service.complete_attempt(db, user, attempt_id, now)


@router.post("/practice/start", response_model=AttemptStartOut)
def start_practice(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
):
    """Heart practice: works at 0 hearts, mistakes are free, finishing restores a heart."""
    return lesson_service.start_practice(db, user, now)
