"""End-to-end API smoke test (§9.2) against a running server on a fresh seed.

    python -m app.seed --reset
    uvicorn app.main:app --port 8000        # in another terminal
    python scripts/smoke_test.py            # from backend/

Solutions are read straight from the seeded SQLite file (test-only knowledge;
the API never exposes them) so the script can answer correctly.
"""

import os
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Exercise, ExerciseType  # noqa: E402

BASE_URL = os.environ.get("API_URL", "http://localhost:8000")

# Windows consoles default to cp1252; the output contains arrows and accents.
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


def check(condition: bool, message: str) -> None:
    if not condition:
        print(f"FAIL: {message}")
        sys.exit(1)
    print(f"  ok  {message}")


def correct_answer(ex: Exercise) -> dict[str, Any]:
    solution = ex.solution or {}
    match ex.type:
        case ExerciseType.MULTIPLE_CHOICE | ExerciseType.FILL_BLANK:
            return {"answer": solution["answer"]}
        case ExerciseType.WORD_BANK:
            return {"tiles": solution["accepted"][0].split()}
        case ExerciseType.TYPE_ANSWER:
            return {"text": solution["accepted"][0]}
        case ExerciseType.MATCH_PAIRS:
            return {"completed": True}


def wrong_answer(ex: Exercise) -> dict[str, Any]:
    match ex.type:
        case ExerciseType.MULTIPLE_CHOICE | ExerciseType.FILL_BLANK:
            return {"answer": "definitely wrong"}
        case ExerciseType.WORD_BANK:
            return {"tiles": ["definitely", "wrong"]}
        case ExerciseType.TYPE_ANSWER:
            return {"text": "definitely wrong"}
    raise ValueError("match pairs cannot be answered wrong server-side")


def main() -> None:
    client = httpx.Client(base_url=BASE_URL, timeout=10)
    print(f"Smoke test against {BASE_URL}")

    check(client.get("/api/health").json() == {"status": "ok"}, "health endpoint responds")

    me = client.get("/api/me").json()
    check(me["xp"] == 45 and me["hearts"] == 5 and me["streak"] == 3,
          f"seeded learner: 45 XP, 5 hearts, streak 3 (got {me['xp']}, {me['hearts']}, {me['streak']})")

    course = client.get("/api/course").json()
    skills = [s for u in course["units"] for s in u["skills"]]
    states = {s["title"]: s["state"] for s in skills}
    check(states["Greetings"] == "COMPLETED" and states["Introductions"] == "IN_PROGRESS"
          and states["Common Words"] == "LOCKED", f"initial skill states {states}")
    intro = next(s for s in skills if s["title"] == "Introductions")
    lesson_id = intro["next_lesson_id"]

    locked_lesson = next(s for s in skills if s["title"] == "Common Words")["lessons"][0]["id"]
    locked = client.post(f"/api/lessons/{locked_lesson}/start")
    check(locked.status_code == 403 and locked.json()["detail"]["code"] == "LESSON_LOCKED",
          "starting a locked lesson returns 403 LESSON_LOCKED")

    start = client.post(f"/api/lessons/{lesson_id}/start")
    check(start.status_code == 200, "started the in-progress lesson")
    body = start.json()
    attempt_id = body["attempt_id"]
    check(all("solution" not in ex for ex in body["exercises"]), "no solutions sent to the client")

    with SessionLocal() as db:
        exercises = {ex.id: ex for ex in db.query(Exercise).filter(Exercise.lesson_id == lesson_id)}

    first = next(ex for ex in exercises.values() if ex.type != ExerciseType.MATCH_PAIRS)
    wrong = client.post(f"/api/attempts/{attempt_id}/answer",
                        json={"exercise_id": first.id, "answer": wrong_answer(first)}).json()
    check(wrong["correct"] is False and wrong["hearts"] == 4, "wrong answer costs exactly one heart")

    again = client.post(f"/api/attempts/{attempt_id}/answer",
                        json={"exercise_id": first.id, "answer": correct_answer(first)}).json()
    check(again["correct"] is False and again["hearts"] == 4,
          "duplicate submission returns the stored result without another heart")

    early = client.post(f"/api/attempts/{attempt_id}/complete")
    check(early.status_code == 409 and early.json()["detail"]["code"] == "INCOMPLETE_ATTEMPT",
          "cannot complete with unanswered exercises")

    for ex in exercises.values():
        if ex.id == first.id:
            continue
        res = client.post(f"/api/attempts/{attempt_id}/answer",
                          json={"exercise_id": ex.id, "answer": correct_answer(ex)}).json()
        check(res["correct"] is True, f"exercise {ex.id} ({ex.type.value}) answered correctly")

    summary = client.post(f"/api/attempts/{attempt_id}/complete").json()
    check(summary["xp_earned"] == 10 and summary["perfect"] is False, "10 XP, no perfect bonus")
    check(summary["total_xp"] == 55, f"total XP 55 (got {summary['total_xp']})")
    check(summary["streak"] == {"before": 3, "after": 4, "extended": True}, "streak extended 3 → 4")
    check(summary["skill"]["state"] == "COMPLETED" and summary["skill"]["progress"] == 100,
          "Introductions is now COMPLETED at 100%")
    check((summary["newly_unlocked_skill"] or {}).get("title") == "Common Words", "Common Words unlocked")

    replay = client.post(f"/api/attempts/{attempt_id}/complete").json()
    check(replay["already_completed"] is True and replay["total_xp"] == 55,
          "second /complete is idempotent (no extra XP)")

    me = client.get("/api/me").json()
    check(me["xp"] == 55 and me["streak"] == 4 and me["hearts"] == 4,
          f"state persisted: 55 XP, streak 4, 4 hearts (got {me['xp']}, {me['streak']}, {me['hearts']})")
    course = client.get("/api/course").json()
    states = {s["title"]: s["state"] for u in course["units"] for s in u["skills"]}
    check(states["Common Words"] == "AVAILABLE", "path shows Common Words AVAILABLE")

    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
