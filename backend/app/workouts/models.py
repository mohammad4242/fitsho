from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.exercises.enums import PrescriptionMode
from app.exercises.models import Exercise
from app.workouts.enums import WorkoutGenerationStatus, WorkoutPlanStatus

if TYPE_CHECKING:
    from app.workout_reviews.models import WorkoutPlanReview


def enum_values(members: type[StrEnum]) -> list[str]:
    return [member.value for member in members]


class WorkoutPlan(Base):
    __tablename__ = "workout_plans"
    __table_args__ = (
        CheckConstraint(
            "char_length(generation_signature) = 64",
            name="ck_workout_plans_generation_signature_length",
        ),
        CheckConstraint(
            "char_length(candidate_set_hash) = 64",
            name="ck_workout_plans_candidate_set_hash_length",
        ),
        Index("ix_workout_plans_user_id", "user_id"),
        Index(
            "uq_workout_plans_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[WorkoutPlanStatus] = mapped_column(
        Enum(
            WorkoutPlanStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_workout_plans_status_values",
        ),
        default=WorkoutPlanStatus.GENERATING,
        server_default=WorkoutPlanStatus.GENERATING.value,
        nullable=False,
    )
    generation_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_method: Mapped[str] = mapped_column(String(30), nullable=False)
    engine_version: Mapped[str] = mapped_column(
        String(64), default="legacy_ai", server_default="legacy_ai", nullable=False
    )
    ruleset_version: Mapped[str] = mapped_column(
        String(64), default="legacy", server_default="legacy", nullable=False
    )
    primary_goal: Mapped[str] = mapped_column(
        String(40), default="general_fitness", server_default="general_fitness", nullable=False
    )
    secondary_goal: Mapped[str | None] = mapped_column(String(40))
    training_status: Mapped[str] = mapped_column(
        String(40), default="novice", server_default="novice", nullable=False
    )
    safety_status: Mapped[str] = mapped_column(
        String(50), default="clear", server_default="clear", nullable=False
    )
    seed: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", nullable=False)
    exercise_catalog_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'::json"), nullable=False
    )
    assumptions: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'::json"), nullable=False
    )
    warnings: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'::json"), nullable=False
    )
    validation_report: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'::json"), nullable=False
    )
    aggregate_metrics: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'::json"), nullable=False
    )
    decision_trace: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, default=list, server_default=text("'[]'::json"), nullable=False
    )
    body_analysis_provenance: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'::json"), nullable=False
    )
    ai_coach_template_slug: Mapped[str | None] = mapped_column(String(120))
    ai_coach_program_explanation_fa: Mapped[str | None] = mapped_column(Text)
    progression_policy: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'::json"), nullable=False
    )
    previous_program_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workout_plans.id", ondelete="SET NULL")
    )
    regeneration_reason: Mapped[str | None] = mapped_column(String(160))
    difference_summary: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'::json"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    days: Mapped[list[WorkoutDay]] = relationship(
        back_populates="workout_plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: WorkoutDay.day_number,
    )
    generation_records: Mapped[list[WorkoutPlanGeneration]] = relationship(
        back_populates="workout_plan"
    )
    source_review: Mapped[WorkoutPlanReview | None] = relationship(
        foreign_keys="WorkoutPlanReview.source_plan_id",
        back_populates="source_plan",
        uselist=False,
    )
    approval_review: Mapped[WorkoutPlanReview | None] = relationship(
        foreign_keys="WorkoutPlanReview.approved_plan_id",
        back_populates="approved_plan",
        uselist=False,
    )


class WorkoutDay(Base):
    __tablename__ = "workout_days"
    __table_args__ = (
        UniqueConstraint("workout_plan_id", "day_number", name="uq_workout_days_plan_day"),
        CheckConstraint("day_number >= 1", name="ck_workout_days_day_number_positive"),
        CheckConstraint(
            "estimated_duration_minutes BETWEEN 1 AND 180",
            name="ck_workout_days_estimated_duration_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workout_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_plans.id", ondelete="CASCADE"), nullable=False
    )
    day_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title_en: Mapped[str] = mapped_column(String(120), nullable=False)
    title_fa: Mapped[str] = mapped_column(String(120), nullable=False)
    estimated_duration_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    weekday: Mapped[int | None] = mapped_column(SmallInteger)
    focus: Mapped[str] = mapped_column(
        String(80), default="legacy", server_default="legacy", nullable=False
    )
    cardio: Mapped[dict[str, object] | None] = mapped_column(JSON)
    ai_coach_explanation_fa: Mapped[str | None] = mapped_column(Text)

    workout_plan: Mapped[WorkoutPlan] = relationship(back_populates="days")
    exercises: Mapped[list[WorkoutPlanExercise]] = relationship(
        back_populates="workout_day",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: WorkoutPlanExercise.order_index,
    )


class WorkoutPlanExercise(Base):
    __tablename__ = "workout_plan_exercises"
    __table_args__ = (
        UniqueConstraint(
            "workout_day_id", "order_index", name="uq_workout_plan_exercises_day_order"
        ),
        UniqueConstraint(
            "workout_day_id", "exercise_id", name="uq_workout_plan_exercises_day_exercise"
        ),
        CheckConstraint("order_index >= 1", name="ck_workout_plan_exercises_order_positive"),
        CheckConstraint("sets BETWEEN 1 AND 10", name="ck_workout_plan_exercises_sets_range"),
        CheckConstraint(
            "reps_min BETWEEN 1 AND 100 AND reps_max BETWEEN 1 AND 100 AND reps_min <= reps_max",
            name="ck_workout_plan_exercises_reps_range",
        ),
        CheckConstraint(
            "(prescription_mode = 'reps' "
            "AND reps_min BETWEEN 1 AND 100 "
            "AND reps_max BETWEEN 1 AND 100 "
            "AND reps_min <= reps_max "
            "AND duration_min_seconds IS NULL "
            "AND duration_max_seconds IS NULL "
            "AND rir BETWEEN 0 AND 5) OR "
            "(prescription_mode = 'duration' "
            "AND duration_min_seconds BETWEEN 1 AND 3600 "
            "AND duration_max_seconds BETWEEN 1 AND 3600 "
            "AND duration_min_seconds <= duration_max_seconds "
            "AND reps_min IS NULL "
            "AND reps_max IS NULL "
            "AND rir IS NULL)",
            name="ck_workout_plan_exercises_prescription_contract",
        ),
        CheckConstraint(
            "rest_seconds BETWEEN 0 AND 600",
            name="ck_workout_plan_exercises_rest_range",
        ),
        CheckConstraint("rir BETWEEN 0 AND 5", name="ck_workout_plan_exercises_rir_range"),
        CheckConstraint(
            "estimated_minutes BETWEEN 1 AND 90",
            name="ck_workout_plan_exercises_estimated_minutes_range",
        ),
        CheckConstraint(
            "notes_en IS NULL OR char_length(notes_en) <= 1000",
            name="ck_workout_plan_exercises_notes_en_length",
        ),
        CheckConstraint(
            "notes_fa IS NULL OR char_length(notes_fa) <= 1000",
            name="ck_workout_plan_exercises_notes_fa_length",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workout_day_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_days.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sets: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    prescription_mode: Mapped[PrescriptionMode] = mapped_column(
        Enum(
            PrescriptionMode,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_workout_plan_exercises_prescription_mode_values",
        ),
        default=PrescriptionMode.REPS,
        server_default=PrescriptionMode.REPS.value,
        nullable=False,
    )
    reps_min: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    reps_max: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    duration_min_seconds: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    duration_max_seconds: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    rest_seconds: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rir: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    estimated_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    notes_en: Mapped[str | None] = mapped_column(Text)
    notes_fa: Mapped[str | None] = mapped_column(Text)
    exercise_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'::json"), nullable=False
    )
    reason_codes: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'::json"), nullable=False
    )
    substitution_exercise_ids: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'::json"), nullable=False
    )
    warmup_sets: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0", nullable=False
    )
    load_guidance: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    progression_rule: Mapped[str] = mapped_column(
        String(80), default="legacy", server_default="legacy", nullable=False
    )

    workout_day: Mapped[WorkoutDay] = relationship(back_populates="exercises")
    exercise: Mapped[Exercise] = relationship()


class WorkoutPlanGeneration(Base):
    __tablename__ = "workout_plan_generations"
    __table_args__ = (
        CheckConstraint(
            "candidate_count BETWEEN 0 AND 5000",
            name="ck_workout_plan_generations_candidate_count_range",
        ),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_workout_plan_generations_input_tokens_nonnegative",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_workout_plan_generations_output_tokens_nonnegative",
        ),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_workout_plan_generations_latency_nonnegative",
        ),
        Index("ix_workout_plan_generations_user_id", "user_id"),
        Index(
            "uq_workout_plan_generations_one_running_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'generating'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workout_plan_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workout_plans.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[WorkoutGenerationStatus] = mapped_column(
        Enum(
            WorkoutGenerationStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_workout_plan_generations_status_values",
        ),
        default=WorkoutGenerationStatus.GENERATING,
        server_default=WorkoutGenerationStatus.GENERATING.value,
        nullable=False,
    )
    candidate_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    validation_diagnostics: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workout_plan: Mapped[WorkoutPlan | None] = relationship(back_populates="generation_records")
