from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import User
from app.database.base import Base
from app.exercises.models import Exercise
from app.workout_cycles.enums import (
    WorkoutCycleStatus,
    WorkoutCycleWeeklyCheckInDifficulty,
    WorkoutCycleWeeklyCheckInRecovery,
    WorkoutExercisePreferenceType,
    WorkoutExerciseReplacementReason,
    WorkoutExerciseReplacementScope,
    WorkoutExerciseSafetySignalType,
)
from app.workouts.models import WorkoutPlan, WorkoutPlanExercise


def enum_values(members: type[StrEnum]) -> list[str]:
    return [member.value for member in members]


class WorkoutCycle(Base):
    __tablename__ = "workout_cycles"
    __table_args__ = (
        UniqueConstraint("workout_plan_id", name="uq_workout_cycles_workout_plan_id"),
        CheckConstraint(
            "duration_weeks IN (4, 6, 8)",
            name="ck_workout_cycles_duration_weeks_supported",
        ),
        CheckConstraint(
            "(status = 'active' AND completed_at IS NULL) "
            "OR (status = 'completed' AND completed_at IS NOT NULL)",
            name="ck_workout_cycles_completion_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workout_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_plans.id", ondelete="CASCADE"), nullable=False
    )
    duration_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[WorkoutCycleStatus] = mapped_column(
        Enum(
            WorkoutCycleStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_workout_cycles_status_values",
        ),
        default=WorkoutCycleStatus.ACTIVE,
        server_default=WorkoutCycleStatus.ACTIVE.value,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    workout_plan: Mapped[WorkoutPlan] = relationship()
    completion_feedback: Mapped[WorkoutCycleFeedback | None] = relationship(
        back_populates="cycle",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class WorkoutCycleFeedback(Base):
    __tablename__ = "workout_cycle_feedback"
    __table_args__ = (
        UniqueConstraint("cycle_id", name="uq_workout_cycle_feedback_cycle_id"),
        CheckConstraint(
            "adherence_percent IS NULL OR adherence_percent BETWEEN 0 AND 100",
            name="ck_workout_cycle_feedback_adherence_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cycle_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_cycles.id", ondelete="CASCADE"), nullable=False
    )
    adherence_percent: Mapped[int | None] = mapped_column(Integer)
    performance_changes: Mapped[str | None] = mapped_column(Text)
    pain_or_limitation_feedback: Mapped[str | None] = mapped_column(Text)
    measurements: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    cycle: Mapped[WorkoutCycle] = relationship(back_populates="completion_feedback")


class WorkoutCycleWeeklyCheckIn(Base):
    __tablename__ = "workout_cycle_weekly_check_ins"
    __table_args__ = (
        UniqueConstraint(
            "cycle_id",
            "week_number",
            name="uq_workout_cycle_weekly_checkins_cycle_week",
        ),
        CheckConstraint(
            "week_number >= 1",
            name="ck_workout_cycle_weekly_check_ins_week_positive",
        ),
        CheckConstraint(
            "week_number <= 8",
            name="ck_workout_cycle_weekly_check_ins_week_max",
        ),
        CheckConstraint(
            "sessions_completed >= 0",
            name="ck_weekly_check_ins_sessions_completed_nonnegative",
        ),
        CheckConstraint(
            "sessions_completed <= 7",
            name="ck_workout_cycle_weekly_check_ins_sessions_completed_max",
        ),
        CheckConstraint(
            "note_optional IS NULL OR char_length(note_optional) <= 2000",
            name="ck_workout_cycle_weekly_check_ins_note_length",
        ),
        Index(
            "ix_workout_cycle_weekly_check_ins_user_cycle",
            "user_id",
            "cycle_id",
        ),
        Index(
            "ix_workout_cycle_weekly_check_ins_cycle_week",
            "cycle_id",
            "week_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cycle_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_cycles.id", ondelete="RESTRICT"), nullable=False
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sessions_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    perceived_difficulty: Mapped[WorkoutCycleWeeklyCheckInDifficulty] = mapped_column(
        Enum(
            WorkoutCycleWeeklyCheckInDifficulty,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_workout_cycle_weekly_check_ins_difficulty_values",
        ),
        nullable=False,
    )
    recovery_rating: Mapped[WorkoutCycleWeeklyCheckInRecovery] = mapped_column(
        Enum(
            WorkoutCycleWeeklyCheckInRecovery,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_workout_cycle_weekly_check_ins_recovery_values",
        ),
        nullable=False,
    )
    has_pain_or_limitation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    note_optional: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship()
    cycle: Mapped[WorkoutCycle] = relationship()


class WorkoutExerciseReplacement(Base):
    __tablename__ = "workout_exercise_replacements"
    __table_args__ = (
        CheckConstraint(
            "original_exercise_id <> replacement_exercise_id",
            name="ck_workout_exercise_replacements_distinct_exercises",
        ),
        CheckConstraint(
            "week_number BETWEEN 1 AND 8",
            name="ck_workout_exercise_replacements_week_number_range",
        ),
        Index(
            "ix_workout_exercise_replacements_user_cycle",
            "user_id",
            "cycle_id",
        ),
        Index(
            "ix_workout_exercise_replacements_cycle_week",
            "cycle_id",
            "week_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cycle_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_cycles.id", ondelete="RESTRICT"), nullable=False
    )
    workout_plan_exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_plan_exercises.id", ondelete="RESTRICT"), nullable=False
    )
    original_exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False
    )
    replacement_exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[WorkoutExerciseReplacementReason] = mapped_column(
        Enum(
            WorkoutExerciseReplacementReason,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_workout_exercise_replacements_reason_values",
        ),
        nullable=False,
    )
    scope: Mapped[WorkoutExerciseReplacementScope] = mapped_column(
        Enum(
            WorkoutExerciseReplacementScope,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_workout_exercise_replacements_scope_values",
        ),
        nullable=False,
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()
    cycle: Mapped[WorkoutCycle] = relationship()
    workout_plan_exercise: Mapped[WorkoutPlanExercise] = relationship()
    original_exercise: Mapped[Exercise] = relationship(foreign_keys=[original_exercise_id])
    replacement_exercise: Mapped[Exercise] = relationship(foreign_keys=[replacement_exercise_id])


class WorkoutExercisePreference(Base):
    __tablename__ = "workout_exercise_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "exercise_id",
            "preference_type",
            name="uq_workout_exercise_preferences_user_exercise_type",
        ),
        Index("ix_workout_exercise_preferences_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False
    )
    preference_type: Mapped[WorkoutExercisePreferenceType] = mapped_column(
        Enum(
            WorkoutExercisePreferenceType,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_workout_exercise_preferences_type_values",
        ),
        nullable=False,
    )
    source_replacement_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_exercise_replacements.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()
    exercise: Mapped[Exercise] = relationship()
    source_replacement: Mapped[WorkoutExerciseReplacement] = relationship()


class WorkoutExerciseSafetySignal(Base):
    __tablename__ = "workout_exercise_safety_signals"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "cycle_id",
            "workout_plan_exercise_id",
            "replacement_exercise_id",
            "week_number",
            "signal_type",
            name="uq_workout_exercise_safety_signals_event",
        ),
        UniqueConstraint(
            "source_replacement_id",
            name="uq_workout_exercise_safety_signals_source_replacement",
        ),
        CheckConstraint(
            "week_number BETWEEN 1 AND 8",
            name="ck_workout_exercise_safety_signals_week_number_range",
        ),
        Index("ix_workout_exercise_safety_signals_user_cycle", "user_id", "cycle_id"),
        Index(
            "ix_workout_exercise_safety_signals_cycle_week",
            "cycle_id",
            "week_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cycle_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_cycles.id", ondelete="RESTRICT"), nullable=False
    )
    workout_plan_exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_plan_exercises.id", ondelete="RESTRICT"), nullable=False
    )
    original_exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False
    )
    replacement_exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False
    )
    signal_type: Mapped[WorkoutExerciseSafetySignalType] = mapped_column(
        Enum(
            WorkoutExerciseSafetySignalType,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_workout_exercise_safety_signals_type_values",
        ),
        nullable=False,
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_replacement_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_exercise_replacements.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()
    cycle: Mapped[WorkoutCycle] = relationship()
    workout_plan_exercise: Mapped[WorkoutPlanExercise] = relationship()
    original_exercise: Mapped[Exercise] = relationship(foreign_keys=[original_exercise_id])
    replacement_exercise: Mapped[Exercise] = relationship(foreign_keys=[replacement_exercise_id])
    source_replacement: Mapped[WorkoutExerciseReplacement] = relationship()
