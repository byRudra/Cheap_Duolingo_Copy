"""Test helpers: look up seeded content and drive lessons through the API."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Achievement,
    Exercise,
    ExerciseType,
    Lesson,
    LessonAttempt,
    Skill,
    User,
    UserAchievement,
)

DEMO = "arnav"


def get_user(db: Session, username: str = DEMO) -> User:
    db.expire_all()  # requests commit through their own sessions
    return db.scalars(select(User).where(User.username == username)).one()


def set_user(db: Session, username: str = DEMO, **fields: Any) -> User:
    user = get_user(db, username)
    for key, value in fields.items():
        setattr(user, key, value)
    db.commit()
    return user


def skill_by_order(db: Session, order_index: int) -> Skill:
    return db.scalars(select(Skill).where(Skill.order_index == order_index)).one()


def lesson_ids(db: Session, skill_order: int) -> list[int]:
    return [lesson.id for lesson in skill_by_order(db, skill_order).lessons]


def exercises(db: Session, lesson_id: int) -> list[Exercise]:
    return db.get(Lesson, lesson_id).exercises


def attempt(db: Session, attempt_id: int) -> LessonAttempt:
    db.expire_all()
    return db.get(LessonAttempt, attempt_id)


def achievement_codes(db: Session, username: str = DEMO) -> list[str]:
    user = get_user(db, username)
    return sorted(
        db.scalars(
            select(Achievement.code)
            .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
            .where(UserAchievement.user_id == user.id)
        )
    )


def correct_answer(ex: Exercise) -> dict[str, Any]:
    """Build a correct submission from the server-side solution."""
    match ex.type:
        case ExerciseType.MULTIPLE_CHOICE | ExerciseType.FILL_BLANK:
            return {"answer": ex.solution["answer"]}
        case ExerciseType.WORD_BANK:
            return {"tiles": ex.solution["accepted"][0].split()}
        case ExerciseType.TYPE_ANSWER:
            return {"text": ex.solution["accepted"][0]}
        case ExerciseType.MATCH_PAIRS:
            return {"completed": True}
    raise AssertionError(ex.type)


def wrong_answer(ex: Exercise) -> dict[str, Any]:
    match ex.type:
        case ExerciseType.MULTIPLE_CHOICE | ExerciseType.FILL_BLANK:
            return {"answer": "definitely not it"}
        case ExerciseType.WORD_BANK:
            return {"tiles": ["zzz", "qqq"]}
        case ExerciseType.TYPE_ANSWER:
            return {"text": "zzz"}
    raise AssertionError(f"{ex.type} cannot be answered wrong on the server")


def gradable(db: Session, lesson_id: int) -> list[Exercise]:
    """Exercises that can be answered wrong (everything but MATCH_PAIRS)."""
    return [ex for ex in exercises(db, lesson_id) if ex.type != ExerciseType.MATCH_PAIRS]


def start(client, lesson_id: int):
    return client.post(f"/api/lessons/{lesson_id}/start")


def answer(client, attempt_id: int, exercise_id: int, payload: dict[str, Any]):
    return client.post(
        f"/api/attempts/{attempt_id}/answer", json={"exercise_id": exercise_id, "answer": payload}
    )


def complete(client, attempt_id: int):
    return client.post(f"/api/attempts/{attempt_id}/complete")


def play(client, db: Session, lesson_id: int, wrong: int = 0) -> int:
    """Start a lesson and answer every exercise; the first ``wrong`` gradable ones wrong.

    Returns the attempt id (not completed yet).
    """
    res = start(client, lesson_id)
    assert res.status_code == 200, res.json()
    attempt_id = res.json()["attempt_id"]
    wrong_ids = {ex.id for ex in gradable(db, lesson_id)[:wrong]}
    assert len(wrong_ids) == wrong
    for ex in exercises(db, lesson_id):
        payload = wrong_answer(ex) if ex.id in wrong_ids else correct_answer(ex)
        res = answer(client, attempt_id, ex.id, payload)
        assert res.status_code == 200, res.json()
        assert res.json()["correct"] is (ex.id not in wrong_ids)
    return attempt_id


def finish(client, db: Session, lesson_id: int, wrong: int = 0) -> dict[str, Any]:
    """Play and complete a lesson; returns the completion summary."""
    attempt_id = play(client, db, lesson_id, wrong)
    res = complete(client, attempt_id)
    assert res.status_code == 200, res.json()
    return res.json()


def assert_error(res, status: int, code: str) -> None:
    assert res.status_code == status, res.json()
    body = res.json()
    assert set(body) == {"detail"}
    assert set(body["detail"]) == {"code", "message"}
    assert body["detail"]["code"] == code
    assert isinstance(body["detail"]["message"], str) and body["detail"]["message"]
