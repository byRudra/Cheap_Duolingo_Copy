"""Multiple courses: listing, switching, the active tree and per-course progress."""

from sqlalchemy import select

from app.content import COURSES
from app.models import Course, UserLessonProgress

from .helpers import assert_error, finish, get_user, lesson_ids, skill_by_order

SPANISH = COURSES[0]["language_code"]


def course_ids(db) -> dict[str, int]:
    """language_code → course id, in registry order."""
    return {c.language_code: c.id for c in db.scalars(select(Course).order_by(Course.id))}


def other_codes() -> list[str]:
    return [c["language_code"] for c in COURSES[1:]]


def first_lesson_id(db, code: str) -> int:
    return skill_by_order(db, 1, code).lessons[0].id


def summaries(api) -> dict[str, dict]:
    res = api.get("/api/courses")
    assert res.status_code == 200
    return {c["language_code"]: c for c in res.json()}


# ── GET /api/courses ─────────────────────────────────────────────────────────


def test_list_courses(api, seeded_db):
    res = api.get("/api/courses")
    assert res.status_code == 200
    body = res.json()
    assert [c["language_code"] for c in body] == [c["language_code"] for c in COURSES]
    for item, data in zip(body, COURSES):
        assert set(item) == {
            "id", "title", "language_code", "flag_emoji", "description",
            "is_active", "lessons_completed", "lessons_total", "progress",
        }
        assert (item["title"], item["flag_emoji"], item["description"]) == (
            data["title"], data["flag_emoji"], data["description"]
        )
        expected_total = sum(len(s["lessons"]) for u in data["units"] for s in u["skills"])
        assert item["lessons_total"] == expected_total
    assert [c["is_active"] for c in body] == [True] + [False] * (len(COURSES) - 1)


def test_list_courses_reports_seeded_progress(api):
    by_code = summaries(api)
    spanish = by_code[SPANISH]
    assert spanish["lessons_completed"] == 3
    assert spanish["progress"] == round(100 * 3 / spanish["lessons_total"])
    for code in other_codes():
        assert by_code[code]["lessons_completed"] == 0
        assert by_code[code]["progress"] == 0


# ── POST /api/me/course ──────────────────────────────────────────────────────


def test_me_reports_active_course(api, seeded_db):
    active = api.get("/api/me").json()["active_course"]
    assert active == {
        "id": course_ids(seeded_db)[SPANISH],
        "title": COURSES[0]["title"],
        "language_code": SPANISH,
        "flag_emoji": COURSES[0]["flag_emoji"],
    }


def test_switch_course(api, seeded_db):
    ids = course_ids(seeded_db)
    for code in other_codes() + [SPANISH]:
        res = api.post("/api/me/course", json={"course_id": ids[code]})
        assert res.status_code == 200, res.json()
        assert res.json()["active_course"]["language_code"] == code
        assert get_user(seeded_db).active_course_id == ids[code]
        assert api.get("/api/me").json()["active_course"]["id"] == ids[code]
        by_code = summaries(api)
        assert [c for c, s in by_code.items() if s["is_active"]] == [code]


def test_switch_to_unknown_course(api, seeded_db):
    before = get_user(seeded_db).active_course_id
    assert_error(api.post("/api/me/course", json={"course_id": 99999}), 404, "COURSE_NOT_FOUND")
    assert get_user(seeded_db).active_course_id == before


def test_switch_course_validation(api):
    assert_error(api.post("/api/me/course", json={}), 422, "VALIDATION_ERROR")
    assert_error(api.post("/api/me/course", json={"course_id": "abc"}), 422, "VALIDATION_ERROR")


# ── /api/course follows the active course ────────────────────────────────────


def test_course_tree_is_the_active_course(api, seeded_db):
    ids = course_ids(seeded_db)
    for data in COURSES[1:]:
        code = data["language_code"]
        api.post("/api/me/course", json={"course_id": ids[code]})
        tree = api.get("/api/course").json()
        assert (tree["id"], tree["title"], tree["language_code"]) == (ids[code], data["title"], code)
        assert [u["title"] for u in tree["units"]] == [u["title"] for u in data["units"]]
        skills = [s for u in tree["units"] for s in u["skills"]]
        assert [s["order_index"] for s in skills] == list(range(1, len(skills) + 1))
        assert skills[0]["state"] == "AVAILABLE"
        assert {s["state"] for s in skills[1:]} <= {"LOCKED"}
        assert tree["current_skill_id"] == skills[0]["id"]


def test_switching_keeps_progress_in_every_course(api, seeded_db):
    db = seeded_db
    ids = course_ids(db)
    code = other_codes()[0]
    api.post("/api/me/course", json={"course_id": ids[code]})
    summary = finish(api, db, first_lesson_id(db, code))
    assert summary["xp_earned"] == 15  # first completion + perfect bonus

    # Back to Spanish: its seeded path is untouched.
    api.post("/api/me/course", json={"course_id": ids[SPANISH]})
    skills = [s for u in api.get("/api/course").json()["units"] for s in u["skills"]]
    assert [s["state"] for s in skills[:3]] == ["COMPLETED", "IN_PROGRESS", "LOCKED"]

    # And the other course still remembers its completed lesson.
    api.post("/api/me/course", json={"course_id": ids[code]})
    skills = [s for u in api.get("/api/course").json()["units"] for s in u["skills"]]
    assert skills[0]["lessons_completed"] == 1
    assert skills[0]["lessons"][0]["status"] == "COMPLETED"
    assert summaries(api)[code]["lessons_completed"] == 1
    assert summaries(api)[SPANISH]["lessons_completed"] == 3


# ── lessons in a non-active course ───────────────────────────────────────────


def test_lesson_meta_reports_its_own_course(api, seeded_db):
    db = seeded_db
    ids = course_ids(db)
    for data in COURSES:
        code = data["language_code"]
        meta = api.get(f"/api/lessons/{first_lesson_id(db, code)}").json()
        assert (meta["course_id"], meta["course_title"], meta["language_code"]) == (
            ids[code], data["title"], code
        )
        expected = "COMPLETED" if code == SPANISH else "AVAILABLE"
        assert meta["status"] == expected


def test_lesson_in_non_active_course_can_be_played(api, seeded_db):
    db = seeded_db
    code = other_codes()[-1]
    lesson_id = first_lesson_id(db, code)
    # Spanish stays active; the lesson is judged by its own course's unlocks.
    summary = finish(api, db, lesson_id)
    assert summary["already_completed"] is False
    assert summary["xp_earned"] == 15
    skill = skill_by_order(db, 1, code)
    assert summary["skill"]["id"] == skill.id
    assert summary["skill"]["state"] == "IN_PROGRESS"
    assert summary["streak"] == {"before": 3, "after": 4, "extended": True}  # streak is global

    user = get_user(db)
    assert user.active_course_id == course_ids(db)[SPANISH]
    progress = db.scalars(
        select(UserLessonProgress.lesson_id).where(UserLessonProgress.user_id == user.id)
    ).all()
    assert lesson_id in progress
    assert summaries(api)[code]["lessons_completed"] == 1
    # Spanish path unchanged.
    assert summaries(api)[SPANISH]["lessons_completed"] == 3


def test_locked_lesson_in_non_active_course(api, seeded_db):
    db = seeded_db
    code = other_codes()[0]
    locked = skill_by_order(db, 2, code).lessons[0].id
    assert_error(api.post(f"/api/lessons/{locked}/start"), 403, "LESSON_LOCKED")
    second = skill_by_order(db, 1, code).lessons[1].id
    assert_error(api.post(f"/api/lessons/{second}/start"), 403, "LESSON_LOCKED")


def test_unlocks_are_per_course(api, seeded_db):
    """Finishing another course's first skill unlocks its skill 2, not Spanish's skill 3."""
    db = seeded_db
    code = other_codes()[0]
    first_skill = skill_by_order(db, 1, code)
    summaries_ = [finish(api, db, lesson.id) for lesson in first_skill.lessons]
    unlocked = summaries_[-1]["newly_unlocked_skill"]
    assert unlocked is not None and unlocked["id"] == skill_by_order(db, 2, code).id
    spanish_skill_3 = skill_by_order(db, 3, SPANISH)
    tree = api.get("/api/course").json()  # Spanish is active
    states = {s["id"]: s["state"] for u in tree["units"] for s in u["skills"]}
    assert states[spanish_skill_3.id] == "LOCKED"


def test_profile_lists_courses(api, seeded_db):
    ids = course_ids(seeded_db)
    profile = api.get("/api/profile").json()
    assert [c["language_code"] for c in profile["courses"]] == [c["language_code"] for c in COURSES]
    assert profile["course_language_code"] == SPANISH
    assert profile["skills_completed"] == 1
    code = other_codes()[0]
    api.post("/api/me/course", json={"course_id": ids[code]})
    profile = api.get("/api/profile").json()
    assert profile["course_language_code"] == code
    assert profile["course_title"] == COURSES[1]["title"]
    assert profile["skills_completed"] == 0
    assert profile["skills_total"] == sum(len(u["skills"]) for u in COURSES[1]["units"])
    assert [c["is_active"] for c in profile["courses"]] == [False, True] + [False] * (len(COURSES) - 2)


def test_spanish_helpers_still_resolve(seeded_db):
    # Sanity: lesson_ids() is Spanish-scoped even though other courses reuse order_index.
    assert len(lesson_ids(seeded_db, 1)) == 2
