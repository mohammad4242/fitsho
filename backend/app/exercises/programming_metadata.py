"""Deterministic exercise programming metadata inference and backfill."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MovementPattern,
)
from app.exercises.models import Exercise
from app.workouts.program_engine.enums import (
    BodyPosition,
    ImpactLimit,
    Laterality,
    LoadLimit,
    SkillDemand,
    StabilityDemand,
)

PROGRAMMING_METADATA_FIELDS = (
    "body_position",
    "stability_demand",
    "skill_demand",
    "impact_level",
    "axial_loading_level",
    "fatigue_cost",
    "setup_cost",
    "laterality",
    "substitution_group",
    "range_of_motion_profile",
)

_STANDING_PATTERNS = frozenset(
    {
        MovementPattern.SQUAT,
        MovementPattern.HIP_HINGE,
        MovementPattern.LUNGE,
        MovementPattern.HIP_EXTENSION,
        MovementPattern.HIP_ABDUCTION,
        MovementPattern.HIP_ADDUCTION,
        MovementPattern.CALF_RAISE,
        MovementPattern.SHRUG,
    }
)
_FATIGUE_BY_TYPE: dict[ExerciseType, int] = {
    ExerciseType.COMPOUND: 3,
    ExerciseType.ISOLATION: 1,
    ExerciseType.CORE: 1,
    ExerciseType.MOBILITY: 1,
}
_ROM_BY_CAUTION: tuple[tuple[ExerciseCautionTag, str], ...] = (
    (ExerciseCautionTag.DEEP_KNEE_FLEXION, "deep_knee_flexion"),
    (ExerciseCautionTag.SPINAL_FLEXION, "spinal_flexion"),
)


@dataclass(frozen=True)
class ProgrammingMetadataBackfillReport:
    inspected: int = 0
    updated: int = 0
    skipped: int = 0
    field_updates: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class InferredExerciseDemands:
    body_position: BodyPosition
    stability_demand: StabilityDemand
    skill_demand: SkillDemand
    impact_level: ImpactLimit
    fatigue_cost: int
    setup_cost: int


def _values(items: Iterable[object]) -> set[object]:
    return set(items)


def _name_tokens(exercise: Exercise) -> str:
    return exercise.name_en.lower().replace("-", " ")


def _infer_body_position(exercise: Exercise) -> BodyPosition | None:
    name = _name_tokens(exercise)
    if any(token in name for token in ("seated", "sitting", "chair")):
        return BodyPosition.SEATED
    if any(token in name for token in ("lying", "floor", "supine", "prone", "plank")):
        return BodyPosition.LYING
    if "supported" in name:
        return BodyPosition.SUPPORTED
    if exercise.movement_pattern in _STANDING_PATTERNS:
        return BodyPosition.STANDING
    return None


def _infer_stability_demand(
    exercise: Exercise,
    body_position: BodyPosition | None,
) -> StabilityDemand | None:
    cautions = _values(item.caution_tag for item in exercise.caution_tag_items)
    if ExerciseCautionTag.BALANCE_DEMAND in cautions:
        return StabilityDemand.HIGH
    if body_position in {
        BodyPosition.SEATED,
        BodyPosition.LYING,
        BodyPosition.SUPPORTED,
    }:
        return StabilityDemand.LOW
    return None


def _infer_skill_demand(exercise: Exercise) -> SkillDemand:
    return {
        Difficulty.BEGINNER: SkillDemand.LOW,
        Difficulty.INTERMEDIATE: SkillDemand.MODERATE,
        Difficulty.ADVANCED: SkillDemand.HIGH,
    }[exercise.difficulty]


def _infer_axial_loading(exercise: Exercise) -> LoadLimit | None:
    cautions = _values(item.caution_tag for item in exercise.caution_tag_items)
    equipment = _values(item.equipment for item in exercise.equipment_items)
    if Equipment.BARBELL in equipment and exercise.movement_pattern in {
        MovementPattern.SQUAT,
        MovementPattern.HIP_HINGE,
    }:
        return LoadLimit.HIGH
    if ExerciseCautionTag.LOWER_BACK_LOADING in cautions:
        return LoadLimit.MODERATE
    return None


def _infer_laterality(exercise: Exercise) -> Laterality | None:
    name = _name_tokens(exercise)
    if any(
        token in name
        for token in ("single", "one arm", "one leg", "unilateral", "alternating", "split squat")
    ):
        return Laterality.UNILATERAL
    return None


def _infer_range_of_motion_profile(exercise: Exercise) -> list[str] | None:
    cautions = _values(item.caution_tag for item in exercise.caution_tag_items)
    profile = [value for caution, value in _ROM_BY_CAUTION if caution in cautions]
    return profile or None


def infer_exercise_demands(exercise: Exercise) -> InferredExerciseDemands:
    """Infer conservative demand signals for catalog rows with incomplete metadata."""

    name = _name_tokens(exercise)
    equipment = _values(item.equipment for item in exercise.equipment_items)
    body_position = _infer_body_position(exercise) or BodyPosition.STANDING
    stability = _infer_stability_demand(exercise, body_position) or StabilityDemand.MODERATE
    skill = _infer_skill_demand(exercise)
    impact = ImpactLimit.LOW
    fatigue = _FATIGUE_BY_TYPE.get(exercise.exercise_type, 2)
    setup = 1 if equipment == {Equipment.BODYWEIGHT} else 2

    if any(
        token in name
        for token in (
            "between chairs",
            "plyometric",
            "plank pike",
            "with straps",
            "ring ",
        )
    ):
        stability = StabilityDemand.HIGH
    if any(
        token in name
        for token in (
            "dip",
            "between chairs",
            "plyometric",
            "plank pike",
            "bench pull up",
            "with straps",
            "ring ",
        )
    ):
        skill = SkillDemand.HIGH
    if "cardio exercise" in name or "cardio machine" in name:
        impact = ImpactLimit.MODERATE
        fatigue = max(fatigue, 3)
    if any(
        token in name
        for token in (
            "plyometric",
            "jump",
            "burpee",
            "bound",
            "running",
            "mountain climber",
        )
    ):
        impact = ImpactLimit.HIGH
        fatigue = max(fatigue, 3)
    if any(token in name for token in ("dip", "plyometric", "burpee", "plank pike")):
        fatigue = max(fatigue, 4)
    if any(token in name for token in ("between chairs", "with straps", "ring ")):
        setup = 4
    elif "bench pull up" in name:
        setup = 3
    elif "dip" in name:
        setup = max(setup, 2)

    return InferredExerciseDemands(
        body_position=body_position,
        stability_demand=stability,
        skill_demand=skill,
        impact_level=impact,
        fatigue_cost=fatigue,
        setup_cost=setup,
    )


def infer_programming_metadata(exercise: Exercise) -> dict[str, object]:
    """Return only conservative values supported by existing catalog data."""

    body_position = _infer_body_position(exercise)
    metadata: dict[str, object] = {}
    if body_position is not None:
        metadata["body_position"] = body_position

    stability_demand = _infer_stability_demand(exercise, body_position)
    if stability_demand is not None:
        metadata["stability_demand"] = stability_demand

    metadata["skill_demand"] = _infer_skill_demand(exercise)
    if exercise.exercise_type is ExerciseType.MOBILITY:
        metadata["impact_level"] = ImpactLimit.LOW

    axial_loading_level = _infer_axial_loading(exercise)
    if axial_loading_level is not None:
        metadata["axial_loading_level"] = axial_loading_level

    fatigue_cost = _FATIGUE_BY_TYPE.get(exercise.exercise_type)
    if fatigue_cost is not None:
        metadata["fatigue_cost"] = fatigue_cost

    if _values(item.equipment for item in exercise.equipment_items) == {Equipment.BODYWEIGHT}:
        metadata["setup_cost"] = 1

    laterality = _infer_laterality(exercise)
    if laterality is not None:
        metadata["laterality"] = laterality

    if exercise.movement_pattern is not MovementPattern.OTHER:
        metadata["substitution_group"] = exercise.movement_pattern.value

    range_of_motion_profile = _infer_range_of_motion_profile(exercise)
    if range_of_motion_profile is not None:
        metadata["range_of_motion_profile"] = range_of_motion_profile
    return metadata


def backfill_programming_metadata(
    db: Session,
    *,
    dry_run: bool = False,
) -> ProgrammingMetadataBackfillReport:
    """Fill missing fields only; explicit values always remain authoritative."""

    inspected = 0
    updated = 0
    skipped = 0
    field_updates = {field_name: 0 for field_name in PROGRAMMING_METADATA_FIELDS}
    try:
        exercises = db.scalars(
            select(Exercise)
            .options(
                selectinload(Exercise.equipment_items),
                selectinload(Exercise.caution_tag_items),
            )
            .order_by(Exercise.id)
        )
        for exercise in exercises:
            inspected += 1
            inferred = infer_programming_metadata(exercise)
            changes = {
                field_name: value
                for field_name, value in inferred.items()
                if getattr(exercise, field_name) is None
            }
            if not changes:
                skipped += 1
                continue
            updated += 1
            for field_name, value in changes.items():
                field_updates[field_name] += 1
                if not dry_run:
                    setattr(exercise, field_name, value)
        if not dry_run:
            db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return ProgrammingMetadataBackfillReport(
        inspected=inspected,
        updated=updated,
        skipped=skipped,
        field_updates={name: count for name, count in field_updates.items() if count},
    )
