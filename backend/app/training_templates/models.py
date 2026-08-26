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


class StructureFamily(StrEnum):
    UPPER_LOWER = "upper_lower"
    SPLIT = "split"


class StructureSplitType(StrEnum):
    PPL = "ppl"
    BODY_PART = "body_part"


class TrainingProgramStructure(Base):
    """Admin-manageable weekly training split skeleton.

    Stores the ordered identity of each training day (e.g. Push / Pull / Legs).
    Programs reference exactly one compatible Structure (same days_per_week).
    """

    __tablename__ = "training_program_structures"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_training_program_structures_slug"),
        CheckConstraint(
            "days_per_week BETWEEN 2 AND 6",
            name="ck_training_program_structures_days_per_week",
        ),
        CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
            name="ck_training_program_structures_slug_format",
        ),
        CheckConstraint(
            "(days_per_week BETWEEN 2 AND 3 AND family IS NULL AND split_type IS NULL) OR "
            "(days_per_week BETWEEN 4 AND 6 AND "
            "((family = 'upper_lower' AND split_type IS NULL) OR "
            "(family = 'split' AND split_type IN ('ppl', 'body_part'))))",
            name="ck_training_program_structures_family_classification",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(160), nullable=False)
    days_per_week: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    family: Mapped[StructureFamily | None] = mapped_column(
        Enum(
            StructureFamily,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_training_program_structures_family_values",
        ),
        nullable=True,
    )
    split_type: Mapped[StructureSplitType | None] = mapped_column(
        Enum(
            StructureSplitType,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_training_program_structures_split_type_values",
        ),
        nullable=True,
    )
    description_en: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description_fa: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    structure_days: Mapped[list[TrainingProgramStructureDay]] = relationship(
        back_populates="structure",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: TrainingProgramStructureDay.day_number,
    )
    templates: Mapped[list[TrainingProgramTemplate]] = relationship(
        back_populates="structure",
        foreign_keys="TrainingProgramTemplate.structure_id",
    )


class TrainingProgramStructureDay(Base):
    """One ordered day in a TrainingProgramStructure (e.g. day 2 = Pull)."""

    __tablename__ = "training_program_structure_days"
    __table_args__ = (
        UniqueConstraint(
            "structure_id",
            "day_number",
            name="uq_training_program_structure_days_structure_day",
        ),
        CheckConstraint(
            "day_number >= 1",
            name="ck_training_program_structure_days_day_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    structure_id: Mapped[UUID] = mapped_column(
        ForeignKey("training_program_structures.id", ondelete="CASCADE"), nullable=False
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label_en: Mapped[str] = mapped_column(String(120), nullable=False)
    label_fa: Mapped[str] = mapped_column(String(120), nullable=False)
    # Optional stable day-type key for programmatic use (e.g. "upper", "lower", "push")
    day_type: Mapped[str | None] = mapped_column(String(60), nullable=True)

    structure: Mapped[TrainingProgramStructure] = relationship(back_populates="structure_days")



class TrainingTemplateMethod(StrEnum):
    STANDARD = "standard"
    SUPERSET = "superset"
    DROP_SET = "drop_set"


class TrainingTemplateSlotPriority(StrEnum):
    CORE = "core"
    ACCESSORY = "accessory"
    OPTIONAL = "optional"


class TrainingTemplateCatalogState(Base):
    __tablename__ = "training_template_catalog_state"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    catalog_revision: Mapped[int] = mapped_column(Integer, nullable=False)


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
    # Nullable: existing admin-created programs may not have a structure assigned yet.
    # New programs should always set structure_id to a compatible structure.
    structure_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("training_program_structures.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    days: Mapped[list[TrainingProgramTemplateDay]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: TrainingProgramTemplateDay.day_number,
    )
    structure: Mapped[TrainingProgramStructure | None] = relationship(
        back_populates="templates",
        foreign_keys=[structure_id],
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
        CheckConstraint(
            "(intensity_method = 'superset' AND superset_exercise_id IS NOT NULL AND exercise_id != superset_exercise_id AND superset_exercise_slug_hint IS NOT NULL) OR (intensity_method != 'superset' AND superset_exercise_id IS NULL AND superset_exercise_slug_hint IS NULL)",
            name="ck_training_program_template_slots_superset_validity"
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
    superset_exercise_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("exercises.id", ondelete="SET NULL"), nullable=True, index=True
    )
    superset_exercise_slug_hint: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    rep_min: Mapped[int] = mapped_column(Integer, nullable=False)
    rep_max: Mapped[int] = mapped_column(Integer, nullable=False)
    target_rir: Mapped[int] = mapped_column(Integer, nullable=False)
    rest_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    day: Mapped[TrainingProgramTemplateDay] = relationship(back_populates="slots")
    exercise: Mapped[Exercise | None] = relationship(foreign_keys=[exercise_id])
    superset_exercise: Mapped[Exercise | None] = relationship(foreign_keys=[superset_exercise_id])
