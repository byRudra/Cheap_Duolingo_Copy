"""Pydantic v2 response/request schemas. ``frontend/lib/types.ts`` mirrors these."""

from datetime import date, datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, PlainSerializer

from app.models import AttemptStatus, ExerciseType


def _utc_iso(value: datetime) -> str:
    """Stored datetimes are naive UTC; send them with an explicit ``Z``."""
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


UTCDateTime = Annotated[datetime, PlainSerializer(_utc_iso, return_type=str)]

SkillState = Literal["LOCKED", "AVAILABLE", "IN_PROGRESS", "COMPLETED"]
LessonStatus = Literal["LOCKED", "AVAILABLE", "COMPLETED"]


# ── /api/me ──────────────────────────────────────────────────────────────────


class DailyGoalOut(BaseModel):
    goal: int
    earned: int
    met: bool


class MeOut(BaseModel):
    id: int
    username: str
    display_name: str
    avatar_color: str
    xp: int
    gems: int
    hearts: int
    max_hearts: int
    next_heart_at: UTCDateTime | None
    heart_regen_minutes: int
    refill_cost: int
    streak: int
    longest_streak: int
    streak_extended_today: bool
    daily_goal: DailyGoalOut
    today: date


class RefillOut(BaseModel):
    hearts: int
    gems: int
    next_heart_at: UTCDateTime | None


# ── /api/course ──────────────────────────────────────────────────────────────


class LessonNode(BaseModel):
    id: int
    title: str
    order_index: int
    status: LessonStatus


class SkillNode(BaseModel):
    id: int
    title: str
    icon: str
    order_index: int
    state: SkillState
    progress: int = Field(description="Completed lessons as a percentage (0-100).")
    lessons_completed: int
    lessons_total: int
    next_lesson_id: int | None = Field(
        description="Lesson the Start button opens: first uncompleted, else lesson 1 (practice)."
    )
    lessons: list[LessonNode]


class UnitNode(BaseModel):
    id: int
    title: str
    description: str
    color: str
    order_index: int
    skills: list[SkillNode]


class CourseOut(BaseModel):
    id: int
    title: str
    language_code: str
    flag_emoji: str
    current_skill_id: int | None
    units: list[UnitNode]


# ── Lessons and attempts ─────────────────────────────────────────────────────


class LessonMetaOut(BaseModel):
    id: int
    title: str
    order_index: int
    lessons_in_skill: int
    exercise_count: int
    status: LessonStatus
    is_practice: bool
    skill_id: int
    skill_title: str
    skill_icon: str
    unit_title: str
    unit_color: str
    xp_reward: int


class ExerciseOut(BaseModel):
    """Exercise as sent to the client: ``payload`` only, never ``solution``."""

    id: int
    type: ExerciseType
    prompt: str
    payload: dict[str, Any]


class AttemptStartOut(BaseModel):
    attempt_id: int
    lesson: LessonMetaOut
    exercises: list[ExerciseOut]
    hearts: int
    max_hearts: int


class AnswerIn(BaseModel):
    exercise_id: int
    answer: dict[str, Any]


class AnswerOut(BaseModel):
    correct: bool
    correct_answer: str | None
    explanation: str | None
    note: str | None
    hearts: int
    out_of_hearts: bool


class StreakChange(BaseModel):
    before: int
    after: int
    extended: bool


class DailyGoalChange(BaseModel):
    earned: int
    goal: int
    just_met: bool


class SkillProgressOut(BaseModel):
    id: int
    title: str
    progress: int
    state: SkillState


class UnlockedSkillOut(BaseModel):
    id: int
    title: str


class AchievementBrief(BaseModel):
    code: str
    title: str
    icon: str


class CompletionSummary(BaseModel):
    attempt_id: int
    status: AttemptStatus
    xp_earned: int
    perfect: bool
    already_completed: bool
    mistakes: int
    accuracy: int
    total_xp: int
    streak: StreakChange
    daily_goal: DailyGoalChange
    skill: SkillProgressOut
    newly_unlocked_skill: UnlockedSkillOut | None
    new_achievements: list[AchievementBrief]


# ── Social ───────────────────────────────────────────────────────────────────


class AchievementOut(BaseModel):
    code: str
    title: str
    description: str
    icon: str
    unlocked: bool
    unlocked_at: UTCDateTime | None


class ProfileOut(BaseModel):
    id: int
    username: str
    display_name: str
    avatar_color: str
    joined_at: UTCDateTime
    total_xp: int
    gems: int
    streak: int
    longest_streak: int
    lessons_completed: int
    skills_completed: int
    skills_total: int
    course_title: str
    course_flag: str
    course_language_code: str
    achievements: list[AchievementOut]


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    display_name: str
    avatar_color: str
    xp: int
    is_current_user: bool


class LeaderboardOut(BaseModel):
    entries: list[LeaderboardEntry]
