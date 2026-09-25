"""SQLAlchemy models (§4).

JSON columns are used only for type-specific exercise content and the raw
submitted answer; all user state lives in typed, constrained columns.
"""

import enum
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.clock import utc_now
from app.database import Base


class ExerciseType(str, enum.Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    WORD_BANK = "WORD_BANK"
    MATCH_PAIRS = "MATCH_PAIRS"
    FILL_BLANK = "FILL_BLANK"
    TYPE_ANSWER = "TYPE_ANSWER"


class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AttemptMode(str, enum.Enum):
    LESSON = "LESSON"  # normal play: mistakes cost hearts, completion earns XP
    PRACTICE = "PRACTICE"  # heart practice: no heart cost, earns +1 heart, no XP


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    avatar_color: Mapped[str] = mapped_column(String(9))
    xp: Mapped[int] = mapped_column(Integer, default=0)
    gems: Mapped[int] = mapped_column(Integer, default=0)
    hearts: Mapped[int] = mapped_column(Integer)
    hearts_updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    daily_goal_xp: Mapped[int] = mapped_column(Integer)
    active_course_id: Mapped[int | None] = mapped_column(
        ForeignKey("courses.id"), nullable=True, index=True
    )
    # Settings (edited via PATCH /api/me/settings)
    sound_effects: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_reminder: Mapped[bool] = mapped_column(Boolean, default=True)
    achievement_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    language_code: Mapped[str] = mapped_column(String(10), unique=True)
    flag_emoji: Mapped[str] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(String(255), default="")

    units: Mapped[list["Unit"]] = relationship(
        back_populates="course", order_by="Unit.order_index"
    )


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("course_id", "order_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    order_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))
    color: Mapped[str] = mapped_column(String(9))

    course: Mapped[Course] = relationship(back_populates="units")
    skills: Mapped[list["Skill"]] = relationship(
        back_populates="unit", order_by="Skill.order_index"
    )


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), index=True)
    # Course-wide order (unique within a course): drives sequential unlocking
    # across units.
    order_index: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(100))
    icon: Mapped[str] = mapped_column(String(16))

    unit: Mapped[Unit] = relationship(back_populates="skills")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="skill", order_by="Lesson.order_index"
    )


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("skill_id", "order_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), index=True)
    order_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(100))

    skill: Mapped[Skill] = relationship(back_populates="lessons")
    exercises: Mapped[list["Exercise"]] = relationship(
        back_populates="lesson", order_by="Exercise.order_index"
    )


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (UniqueConstraint("lesson_id", "order_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), index=True)
    order_index: Mapped[int] = mapped_column(Integer)
    type: Mapped[ExerciseType] = mapped_column(Enum(ExerciseType, native_enum=False))
    prompt: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    # Never serialized to clients (MATCH_PAIRS has no solution; see §5).
    solution: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    lesson: Mapped[Lesson] = relationship(back_populates="exercises")


class LessonAttempt(Base):
    __tablename__ = "lesson_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), index=True)
    status: Mapped[AttemptStatus] = mapped_column(
        Enum(AttemptStatus, native_enum=False), default=AttemptStatus.IN_PROGRESS
    )
    mode: Mapped[AttemptMode] = mapped_column(
        Enum(AttemptMode, native_enum=False), default=AttemptMode.LESSON
    )
    mistakes: Mapped[int] = mapped_column(Integer, default=0)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    lesson: Mapped[Lesson] = relationship()


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"
    # One stored result per exercise per attempt: retries can't cost two hearts.
    __table_args__ = (UniqueConstraint("attempt_id", "exercise_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("lesson_attempts.id"), index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"), index=True)
    submitted: Mapped[dict[str, Any]] = mapped_column(JSON)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class UserLessonProgress(Base):
    __tablename__ = "user_lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime)
    best_mistakes: Mapped[int] = mapped_column(Integer)


class UserSkillProgress(Base):
    __tablename__ = "user_skill_progress"
    __table_args__ = (UniqueConstraint("user_id", "skill_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), index=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime)
    lessons_completed: Mapped[int] = mapped_column(Integer, default=0)


class DailyActivity(Base):
    __tablename__ = "daily_activity"
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0)
    lessons_completed: Mapped[int] = mapped_column(Integer, default=0)


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))
    icon: Mapped[str] = mapped_column(String(16))


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id"), index=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime)

    achievement: Mapped[Achievement] = relationship()
