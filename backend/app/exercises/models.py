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
    String,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.exercises.enums import BodyRegion, Difficulty, Equipment, MediaType, MuscleGroup


def enum_values(members: type[StrEnum]) -> list[str]:
    return [member.value for member in members]


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
            "json_typeof(safety_notes_en) = 'array' AND json_array_length(safety_notes_en) >= 1",
            name="ck_exercises_safety_notes_en_items",
        ),
        CheckConstraint(
            "json_typeof(safety_notes_fa) = 'array' AND json_array_length(safety_notes_fa) >= 1",
            name="ck_exercises_safety_notes_fa_items",
        ),
        Index("ix_exercises_body_region", "body_region"),
        Index("ix_exercises_primary_muscle", "primary_muscle"),
        Index("ix_exercises_difficulty", "difficulty"),
        Index("ix_exercises_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(160), nullable=False)
    body_region: Mapped[BodyRegion] = mapped_column(
        Enum(
            BodyRegion,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercises_body_region_values",
        ),
        nullable=False,
    )
    primary_muscle: Mapped[MuscleGroup] = mapped_column(
        Enum(
            MuscleGroup,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_exercises_primary_muscle_values",
        ),
        nullable=False,
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
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
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
