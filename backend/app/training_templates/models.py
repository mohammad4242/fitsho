from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.exercises.enums import MovementPattern
from app.exercises.models import Exercise, enum_values
from app.profile.enums import FitnessGoal


class TrainingTemplateMethod(StrEnum):
    STANDARD = "standard"
    SUPERSET = "superset"
    DROP_SET = "drop_set"


class TrainingTemplateSlotPriority(StrEnum):
    CORE = "core"
    ACCESSORY = "accessory"
    OPTIONAL = "optional"


class TrainingProgramTemplate(Base):
    __tablename__ = "training_program_templates"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_training_program_templates_slug"),
        CheckConstraint(
            "days_per_week BETWEEN 2 AND 6",
            name="ck_training_program_templates_days_per_week",
        ),
        CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
            name="ck_training_program_templates_slug_format",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(160), nullable=False)
    description_en: Mapped[str] = mapped_column(String(1000), nullable=False)
    description_fa: Mapped[str] = mapped_column(String(1000), nullable=False)
    days_per_week: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    supported_levels: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    fitness_goal: Mapped[FitnessGoal] = mapped_column(
        Enum(
            FitnessGoal,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_training_program_templates_fitness_goal_values",
        ),
        nullable=False,
    )
    focus_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    intensity_methods: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    programming_rationale: Mapped[list[dict[str, str]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("'[]'::json"),
    )
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    days: Mapped[list[TrainingProgramTemplateDay]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: TrainingProgramTemplateDay.day_number,
    )


class TrainingProgramTemplateDay(Base):
    __tablename__ = "training_program_template_days"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "day_number", name="uq_training_program_template_days_template_day"
        ),
        CheckConstraint("day_number >= 1", name="ck_training_program_template_days_day_number"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("training_program_templates.id", ondelete="CASCADE"), nullable=False
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title_en: Mapped[str] = mapped_column(String(160), nullable=False)
    title_fa: Mapped[str] = mapped_column(String(160), nullable=False)
    structure_focus: Mapped[str] = mapped_column(
        String(100), nullable=False, default="full_body", server_default="full_body"
    )
    direct_target_muscles: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    template: Mapped[TrainingProgramTemplate] = relationship(back_populates="days")
    slots: Mapped[list[TrainingProgramTemplateSlot]] = relationship(
        back_populates="day",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: TrainingProgramTemplateSlot.slot_order,
    )


class TrainingProgramTemplateSlot(Base):
    __tablename__ = "training_program_template_slots"
    __table_args__ = (
        UniqueConstraint(
            "template_day_id", "slot_order", name="uq_training_program_template_slots_day_order"
        ),
        CheckConstraint("slot_order >= 1", name="ck_training_program_template_slots_slot_order"),
        CheckConstraint("sets BETWEEN 1 AND 10", name="ck_training_program_template_slots_sets"),
        CheckConstraint(
            "rep_min BETWEEN 1 AND rep_max", name="ck_training_program_template_slots_reps"
        ),
        CheckConstraint(
            "target_rir BETWEEN 0 AND 6", name="ck_training_program_template_slots_rir"
        ),
        CheckConstraint(
            "rest_seconds BETWEEN 0 AND 600", name="ck_training_program_template_slots_rest"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    template_day_id: Mapped[UUID] = mapped_column(
        ForeignKey("training_program_template_days.id", ondelete="CASCADE"), nullable=False
    )
    slot_order: Mapped[int] = mapped_column(Integer, nullable=False)
    exercise_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("exercises.id", ondelete="SET NULL"), nullable=True, index=True
    )
    exercise_slug_hint: Mapped[str] = mapped_column(String(120), nullable=False)
    placeholder_name_en: Mapped[str | None] = mapped_column(String(160), nullable=True)
    placeholder_name_fa: Mapped[str | None] = mapped_column(String(160), nullable=True)
    target_muscles: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    movement_pattern: Mapped[MovementPattern] = mapped_column(
        Enum(
            MovementPattern,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_training_program_template_slots_pattern_values",
        ),
        nullable=False,
    )
    intensity_method: Mapped[TrainingTemplateMethod] = mapped_column(
        Enum(
            TrainingTemplateMethod,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_training_program_template_slots_method_values",
        ),
        nullable=False,
        default=TrainingTemplateMethod.STANDARD,
    )
    adaptation_priority: Mapped[TrainingTemplateSlotPriority] = mapped_column(
        Enum(
            TrainingTemplateSlotPriority,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_training_program_template_slots_priority_values",
        ),
        nullable=False,
        default=TrainingTemplateSlotPriority.ACCESSORY,
        server_default=TrainingTemplateSlotPriority.ACCESSORY.value,
    )
    superset_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    rep_min: Mapped[int] = mapped_column(Integer, nullable=False)
    rep_max: Mapped[int] = mapped_column(Integer, nullable=False)
    target_rir: Mapped[int] = mapped_column(Integer, nullable=False)
    rest_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    day: Mapped[TrainingProgramTemplateDay] = relationship(back_populates="slots")
    exercise: Mapped[Exercise | None] = relationship()
