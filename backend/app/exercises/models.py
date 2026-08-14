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
    String,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseLabel,
    ExerciseType,
    MediaPresentation,
    MediaRole,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.taxonomy import FOCUSES_BY_MUSCLE


def enum_values(members: type[StrEnum]) -> list[str]:
    return [member.value for member in members]


def muscle_focus_compatibility_sql() -> str:
    compatible_pairs = []
    for muscle, focuses in FOCUSES_BY_MUSCLE.items():
        focus_values = ", ".join(f"'{focus.value}'" for focus in focuses)
        compatible_pairs.append(
            f"(primary_muscle = '{muscle.value}' AND muscle_focus IN ({focus_values}))"
        )
    muscle_values = ", ".join(f"'{muscle.value}'" for muscle in MuscleGroup)
    focus_values = ", ".join(f"'{focus.value}'" for focus in MuscleFocus)
    return (
        "(primary_muscle IS NULL AND muscle_focus IS NULL) OR "
        "(primary_muscle IS NOT NULL AND muscle_focus IS NOT NULL AND ("
        f"primary_muscle NOT IN ({muscle_values}) OR "
        f"muscle_focus NOT IN ({focus_values}) OR "
        f"{' OR '.join(compatible_pairs)}))"
    )


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_exercises_slug"),
        CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
            name="ck_exercises_slug_format",
        ),
        CheckConstraint(
            "char_length(btrim(name_en)) BETWEEN 2 AND 160",
            name="ck_exercises_name_en_length",
        ),
        CheckConstraint(
            "char_length(btrim(name_fa)) BETWEEN 2 AND 160",
            name="ck_exercises_name_fa_length",
        ),
        CheckConstraint(
            "json_typeof(instructions_en) = 'array' "
            "AND json_array_length(instructions_en) BETWEEN 3 AND 6",
            name="ck_exercises_instructions_en_steps",
        ),
        CheckConstraint(
            "json_typeof(instructions_fa) = 'array' "
            "AND json_array_length(instructions_fa) BETWEEN 3 AND 6",
            name="ck_exercises_instructions_fa_steps",
        ),
        CheckConstraint(
            "json_typeof(safety_notes_en) = 'array'",
            name="ck_exercises_safety_notes_en_items",
        ),
        CheckConstraint(
            "json_typeof(safety_notes_fa) = 'array'",
            name="ck_exercises_safety_notes_fa_items",
        ),
        UniqueConstraint("source", "source_id", name="uq_exercises_source_source_id"),
        CheckConstraint(
            muscle_focus_compatibility_sql(),
            name="ck_exercises_primary_muscle_focus_compatible",
        ),
        Index("ix_exercises_body_region", "body_region"),
        Index("ix_exercises_primary_muscle", "primary_muscle"),
        Index(
            "ix_exercises_primary_muscle_muscle_focus",
            "primary_muscle",
            "muscle_focus",
        ),
        Index("ix_exercises_difficulty", "difficulty"),
        Index("ix_exercises_is_active", "is_active"),
        Index("ix_exercises_is_programmable", "is_programmable"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(160), nullable=False)
    body_region: Mapped[BodyRegion | None] = mapped_column(
        Enum(
            BodyRegion,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercises_body_region_values",
        ),
        nullable=True,
    )
    primary_muscle: Mapped[MuscleGroup | None] = mapped_column(
        Enum(
            MuscleGroup,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercises_primary_muscle_values",
        ),
        nullable=True,
    )
    muscle_focus: Mapped[MuscleFocus | None] = mapped_column(
        Enum(
            MuscleFocus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercises_muscle_focus_values",
            length=40,
        ),
        nullable=True,
    )
    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(
            Difficulty,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercises_difficulty_values",
        ),
        nullable=False,
    )
    movement_pattern: Mapped[MovementPattern] = mapped_column(
        Enum(
            MovementPattern,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercises_movement_pattern_values",
        ),
        default=MovementPattern.OTHER,
        server_default=MovementPattern.OTHER.value,
        nullable=False,
    )
    exercise_type: Mapped[ExerciseType] = mapped_column(
        Enum(
            ExerciseType,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercises_exercise_type_values",
        ),
        default=ExerciseType.OTHER,
        server_default=ExerciseType.OTHER.value,
        nullable=False,
    )
    instructions_en: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    instructions_fa: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    safety_notes_en: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    safety_notes_fa: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    media_path: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(
        Enum(
            MediaType,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercises_media_type_values",
        ),
        nullable=False,
    )
    media_source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    media_license: Mapped[str | None] = mapped_column(String(120), nullable=True)
    media_attribution: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    aliases_en: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    short_description_en: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    steps_en: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    form_cues_en: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    common_mistakes_en: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    breathing_en: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_metadata_en: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )
    is_programmable: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    secondary_muscles: Mapped[list[ExerciseSecondaryMuscle]] = relationship(
        back_populates="exercise",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: ExerciseSecondaryMuscle.muscle,
    )
    equipment_items: Mapped[list[ExerciseEquipment]] = relationship(
        back_populates="exercise",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: ExerciseEquipment.equipment,
    )
    alternatives: Mapped[list[ExerciseAlternative]] = relationship(
        back_populates="exercise",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys=lambda: ExerciseAlternative.exercise_id,
    )
    caution_tag_items: Mapped[list[ExerciseCautionTagItem]] = relationship(
        back_populates="exercise",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: ExerciseCautionTagItem.caution_tag,
    )
    labels: Mapped[list[ExerciseLabelItem]] = relationship(
        back_populates="exercise",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: ExerciseLabelItem.label,
    )

    media_assets: Mapped[list[ExerciseMediaAsset]] = relationship(
        back_populates="exercise",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: (
            ExerciseMediaAsset.presentation,
            ExerciseMediaAsset.role,
            ExerciseMediaAsset.sort_order,
        ),
    )


class ExerciseMediaAsset(Base):
    __tablename__ = "exercise_media_assets"
    __table_args__ = (
        UniqueConstraint(
            "exercise_id",
            "presentation",
            "role",
            "sort_order",
            name="uq_exercise_media_assets_exercise_presentation_role_order",
        ),
        CheckConstraint("sort_order >= 0", name="ck_exercise_media_assets_sort_order"),
        CheckConstraint(
            "(role = 'video' AND media_type = 'video') "
            "OR (role = 'thumbnail' AND media_type = 'image')",
            name="ck_exercise_media_assets_role_media_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"),
        nullable=False,
    )
    presentation: Mapped[MediaPresentation] = mapped_column(
        Enum(
            MediaPresentation,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercise_media_assets_presentation_values",
        ),
        nullable=False,
    )
    role: Mapped[MediaRole] = mapped_column(
        Enum(
            MediaRole,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercise_media_assets_role_values",
        ),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    media_path: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(
        Enum(
            MediaType,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercise_media_assets_media_type_values",
        ),
        nullable=False,
    )
    media_source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    media_license: Mapped[str | None] = mapped_column(String(120), nullable=True)
    media_attribution: Mapped[str | None] = mapped_column(String(500), nullable=True)

    exercise: Mapped[Exercise] = relationship(back_populates="media_assets")


class ExerciseCautionTagItem(Base):
    __tablename__ = "exercise_caution_tags"
    __table_args__ = (Index("ix_exercise_caution_tags_caution_tag", "caution_tag"),)

    exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"),
        primary_key=True,
    )
    caution_tag: Mapped[ExerciseCautionTag] = mapped_column(
        Enum(
            ExerciseCautionTag,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercise_caution_tags_caution_tag_values",
        ),
        primary_key=True,
    )

    exercise: Mapped[Exercise] = relationship(back_populates="caution_tag_items")


class ExerciseLabelItem(Base):
    __tablename__ = "exercise_label_items"
    __table_args__ = (Index("ix_exercise_label_items_label", "label"),)

    exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"),
        primary_key=True,
    )
    label: Mapped[ExerciseLabel] = mapped_column(
        Enum(
            ExerciseLabel,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercise_label_items_label_values",
        ),
        primary_key=True,
    )

    exercise: Mapped[Exercise] = relationship(back_populates="labels")


class ExerciseSecondaryMuscle(Base):
    __tablename__ = "exercise_secondary_muscles"
    __table_args__ = (Index("ix_exercise_secondary_muscles_muscle", "muscle"),)

    exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"),
        primary_key=True,
    )
    muscle: Mapped[MuscleGroup] = mapped_column(
        Enum(
            MuscleGroup,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercise_secondary_muscles_muscle_values",
        ),
        primary_key=True,
    )

    exercise: Mapped[Exercise] = relationship(back_populates="secondary_muscles")


class ExerciseEquipment(Base):
    __tablename__ = "exercise_equipment"
    __table_args__ = (Index("ix_exercise_equipment_equipment", "equipment"),)

    exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"),
        primary_key=True,
    )
    equipment: Mapped[Equipment] = mapped_column(
        Enum(
            Equipment,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercise_equipment_equipment_values",
        ),
        primary_key=True,
    )

    exercise: Mapped[Exercise] = relationship(back_populates="equipment_items")


class ExerciseAlternative(Base):
    __tablename__ = "exercise_alternatives"
    __table_args__ = (
        CheckConstraint(
            "exercise_id <> alternative_exercise_id",
            name="ck_exercise_alternatives_distinct_exercises",
        ),
        Index("ix_exercise_alternatives_alternative_id", "alternative_exercise_id"),
    )

    exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"),
        primary_key=True,
    )
    alternative_exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"),
        primary_key=True,
    )
    reason_en: Mapped[str] = mapped_column(String(300), nullable=False)
    reason_fa: Mapped[str] = mapped_column(String(300), nullable=False)

    exercise: Mapped[Exercise] = relationship(
        back_populates="alternatives",
        foreign_keys=[exercise_id],
    )
    alternative_exercise: Mapped[Exercise] = relationship(
        foreign_keys=[alternative_exercise_id],
    )
