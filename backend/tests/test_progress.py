"""Skill state derivation, progress % and unlocking (§3.6)."""

from types import SimpleNamespace

from sqlalchemy import select

from app.models import Lesson, UserLessonProgress, UserSkillProgress
from app.services import progress_service as ps
from app.services.progress_service import derive_skill_views

from .conftest import FIXED_NOW
from .helpers import finish, get_user, lesson_ids, skill_by_order, start


def make_skills(*lesson_counts: int) -> list[SimpleNamespace]:
    """Skills 1..n with sequential lesson ids: (2, 2) → skill 1: [11, 12], skill 2: [21, 22]."""
    return [
        SimpleNamespace(
            id=s,
            lessons=[SimpleNamespace(id=s * 10 + i) for i in range(1, count + 1)],
        )
        for s, count in enumerate(lesson_counts, start=1)
    ]


# ── pure derivation ──────────────────────────────────────────────────────────


def test_fresh_learner_first_skill_available_rest_locked():
    views = derive_skill_views(make_skills(2, 2, 2), set())
    assert [views[s].state for s in (1, 2, 3)] == ["AVAILABLE", "LOCKED", "LOCKED"]
    assert views[1].progress == 0
    assert views[1].lesson_status == {11: "AVAILABLE", 12: "LOCKED"}
    assert views[2].lesson_status == {21: "LOCKED", 22: "LOCKED"}
    assert views[1].next_lesson_id == 11
    assert views[2].next_lesson_id is None


def test_in_progress_and_lesson_within_skill_unlock():
    views = derive_skill_views(make_skills(2, 2), {11})
    assert views[1].state == "IN_PROGRESS"
    assert views[1].progress == 50
    assert views[1].lessons_completed == 1 and views[1].lessons_total == 2
    assert views[1].lesson_status == {11: "COMPLETED", 12: "AVAILABLE"}
    assert views[1].next_lesson_id == 12
    assert views[2].state == "LOCKED"


def test_completed_skill_unlocks_the_next_one():
    views = derive_skill_views(make_skills(2, 2, 2), {11, 12})
    assert views[1].state == "COMPLETED"
    assert views[1].progress == 100
    assert views[1].next_lesson_id == 11  # practice from the start
    assert views[2].state == "AVAILABLE"
    assert views[2].lesson_status == {21: "AVAILABLE", 22: "LOCKED"}
    assert views[3].state == "LOCKED"


def test_unlocking_is_strictly_sequential():
    # Skill 3 stays locked while skill 2 is only half done.
    views = derive_skill_views(make_skills(2, 2, 2), {11, 12, 21})
    assert [views[s].state for s in (1, 2, 3)] == ["COMPLETED", "IN_PROGRESS", "LOCKED"]


def test_all_completed():
    views = derive_skill_views(make_skills(2, 2), {11, 12, 21, 22})
    assert {v.state for v in views.values()} == {"COMPLETED"}


def test_progress_rounds_to_whole_percent():
    views = derive_skill_views(make_skills(3), {11})
    assert views[1].progress == 33
    views = derive_skill_views(make_skills(3), {11, 12})
    assert views[1].progress == 67


def test_derivation_is_pure_and_repeatable():
    skills = make_skills(2, 2)
    completed = {11}
    first = derive_skill_views(skills, completed)
    second = derive_skill_views(skills, completed)
    assert completed == {11}
    assert {k: (v.state, v.lesson_status) for k, v in first.items()} == {
        k: (v.state, v.lesson_status) for k, v in second.items()
    }


# ── DB-level progress recording ──────────────────────────────────────────────


def test_ordered_skills_is_course_wide(seeded_db):
    skills = ps.ordered_skills(ps.get_course(seeded_db))
    assert [s.order_index for s in skills] == list(range(1, 10))
    assert [s.title for s in skills[:4]] == ["Greetings", "Introductions", "Common Words", "Food"]


def test_record_completion_unlocks_next_skill(seeded_db):
    db = seeded_db
    user = get_user(db)
    intro_2 = db.get(Lesson, lesson_ids(db, 2)[1])
    update = ps.record_lesson_completion(db, user, intro_2, mistakes=0, now=FIXED_NOW)
    db.commit()
    assert update.first_completion
    assert update.skill_view.state == "COMPLETED" and update.skill_view.progress == 100
    assert update.newly_unlocked_skill.title == "Common Words"
    assert update.distinct_lessons_completed == 4

    common = skill_by_order(db, 3)
    row = db.scalars(
        select(UserSkillProgress).where(
            UserSkillProgress.user_id == user.id, UserSkillProgress.skill_id == common.id
        )
    ).one()
    assert row.unlocked_at == FIXED_NOW and row.lessons_completed == 0


def test_record_replay_does_not_double_count(seeded_db):
    db = seeded_db
    user = get_user(db)
    greet_1 = db.get(Lesson, lesson_ids(db, 1)[0])
    update = ps.record_lesson_completion(db, user, greet_1, mistakes=0, now=FIXED_NOW)
    db.commit()
    assert not update.first_completion
    assert update.newly_unlocked_skill is None
    assert update.skill_view.lessons_completed == 2
    assert update.distinct_lessons_completed == 3
    progress = db.scalars(
        select(UserLessonProgress).where(
            UserLessonProgress.user_id == user.id, UserLessonProgress.lesson_id == greet_1.id
        )
    ).all()
    assert len(progress) == 1
    assert progress[0].best_mistakes == 0  # improved from the seeded 1
    assert ps.count_completed_lessons(db, user) == 3


# ── /api/course reflects progress ────────────────────────────────────────────


def skills_by_title(course: dict) -> dict[str, dict]:
    return {s["title"]: s for u in course["units"] for s in u["skills"]}


def test_course_tree_for_seeded_learner(api, seeded_db):
    course = api.get("/api/course").json()
    skills = skills_by_title(course)
    assert len(course["units"]) == 3 and len(skills) == 9
    assert skills["Greetings"]["state"] == "COMPLETED"
    assert skills["Greetings"]["progress"] == 100
    assert skills["Introductions"]["state"] == "IN_PROGRESS"
    assert skills["Introductions"]["progress"] == 50
    assert [lesson["status"] for lesson in skills["Introductions"]["lessons"]] == [
        "COMPLETED",
        "AVAILABLE",
    ]
    assert skills["Introductions"]["next_lesson_id"] == lesson_ids(seeded_db, 2)[1]
    assert course["current_skill_id"] == skills["Introductions"]["id"]
    for title in ("Common Words", "Food", "Drinks", "Restaurants", "Family", "Daily Routine", "Places"):
        assert skills[title]["state"] == "LOCKED"
        assert skills[title]["progress"] == 0
        assert {lesson["status"] for lesson in skills[title]["lessons"]} == {"LOCKED"}


def test_finishing_a_skill_unlocks_the_next_via_api(api, seeded_db):
    db = seeded_db
    summary = finish(api, db, lesson_ids(db, 2)[1])
    common = skill_by_order(db, 3)
    assert summary["skill"]["state"] == "COMPLETED"
    assert summary["skill"]["progress"] == 100
    assert summary["newly_unlocked_skill"] == {"id": common.id, "title": "Common Words"}

    skills = skills_by_title(api.get("/api/course").json())
    assert skills["Introductions"]["state"] == "COMPLETED"
    assert skills["Common Words"]["state"] == "AVAILABLE"
    assert [lesson["status"] for lesson in skills["Common Words"]["lessons"]] == [
        "AVAILABLE",
        "LOCKED",
    ]
    assert skills["Food"]["state"] == "LOCKED"


def test_lesson_within_skill_unlocks_via_api(api, seeded_db):
    db = seeded_db
    finish(api, db, lesson_ids(db, 2)[1])
    cw_1, cw_2 = lesson_ids(db, 3)
    assert start(api, cw_2).status_code == 403  # lesson 2 waits for lesson 1

    summary = finish(api, db, cw_1)
    assert summary["skill"]["state"] == "IN_PROGRESS"
    assert summary["skill"]["progress"] == 50
    assert summary["newly_unlocked_skill"] is None

    skills = skills_by_title(api.get("/api/course").json())
    assert [lesson["status"] for lesson in skills["Common Words"]["lessons"]] == [
        "COMPLETED",
        "AVAILABLE",
    ]
    assert start(api, cw_2).status_code == 200


def test_replay_does_not_change_skill_progress(api, seeded_db):
    db = seeded_db
    summary = finish(api, db, lesson_ids(db, 1)[0])
    assert summary["skill"] == {
        "id": skill_by_order(db, 1).id,
        "title": "Greetings",
        "progress": 100,
        "state": "COMPLETED",
    }
    assert summary["newly_unlocked_skill"] is None
    skills = skills_by_title(api.get("/api/course").json())
    assert skills["Greetings"]["lessons_completed"] == 2
    assert skills["Introductions"]["state"] == "IN_PROGRESS"
