import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.models import Exercise, ExerciseCautionTagItem, ExerciseEquipment
from app.exercises.programming_metadata import (
    backfill_programming_metadata,
    infer_exercise_demands,
    infer_programming_metadata,
)
from app.workouts.program_engine.enums import (
    BodyPosition,
    ImpactLimit,
    LoadLimit,
    SkillDemand,
    StabilityDemand,
)


def make_exercise(slug: str) -> Exercise:
    return Exercise(
        slug=slug,
        name_en="Test Squat",
        name_fa="اسکوات آزمایشی",
        body_region=BodyRegion.LOWER_BODY,
        primary_muscle=MuscleGroup.QUADRICEPS,
        muscle_focus=None,
        difficulty=Difficulty.BEGINNER,
        movement_pattern=MovementPattern.SQUAT,
        exercise_type=ExerciseType.COMPOUND,
        instructions_en=["Brace.", "Lower.", "Stand."],
        instructions_fa=["آماده شو.", "پایین برو.", "بلند شو."],
        safety_notes_en=[],
        safety_notes_fa=[],
        media_path="/exercises/exercise-placeholder.svg",
        media_type=MediaType.PLACEHOLDER,
    )


def test_backfill_populates_supported_missing_metadata_and_reports_changes(db: Session) -> None:
    exercise = make_exercise("backfill-supported")
    exercise.equipment_items.append(ExerciseEquipment(equipment=Equipment.BODYWEIGHT))
    exercise.caution_tag_items.append(
        ExerciseCautionTagItem(caution_tag=ExerciseCautionTag.DEEP_KNEE_FLEXION)
    )
    db.add(exercise)
    db.flush()

    report = backfill_programming_metadata(db)
    db.expire_all()
    stored = db.scalar(select(Exercise).where(Exercise.slug == "backfill-supported"))

    assert stored is not None
    assert report.inspected == 1
    assert report.updated == 1
    assert report.skipped == 0
    assert stored.body_position is BodyPosition.STANDING
    assert stored.fatigue_cost == 3
    assert stored.setup_cost == 1
    assert stored.axial_loading_level is None
    assert stored.substitution_group == "squat_free_weight"
    assert stored.range_of_motion_profile == ["deep_knee_flexion"]


def test_backfill_never_overwrites_explicit_metadata(db: Session) -> None:
    exercise = make_exercise("backfill-explicit")
    exercise.body_position = BodyPosition.SUPPORTED
    exercise.fatigue_cost = 5
    exercise.axial_loading_level = LoadLimit.NONE
    exercise.substitution_group = "coach_curated_squat"
    db.add(exercise)
    db.flush()

    backfill_programming_metadata(db)
    db.expire_all()
    stored = db.scalar(select(Exercise).where(Exercise.slug == "backfill-explicit"))

    assert stored is not None
    assert stored.body_position is BodyPosition.SUPPORTED
    assert stored.fatigue_cost == 5
    assert stored.axial_loading_level is LoadLimit.NONE
    assert stored.substitution_group == "coach_curated_squat"


def test_bodyweight_push_up_is_supported_low_stability_unless_explicitly_cautioned() -> None:
    exercise = make_exercise("supported-push-up")
    exercise.name_en = "Incline Push-Up"
    exercise.primary_muscle = MuscleGroup.CHEST
    exercise.movement_pattern = MovementPattern.HORIZONTAL_PUSH
    exercise.equipment_items.append(ExerciseEquipment(equipment=Equipment.BODYWEIGHT))

    demands = infer_exercise_demands(exercise)
    metadata = infer_programming_metadata(exercise)

    assert demands.body_position is BodyPosition.SUPPORTED
    assert demands.stability_demand is StabilityDemand.LOW
    assert metadata["body_position"] is BodyPosition.SUPPORTED
    assert metadata["stability_demand"] is StabilityDemand.LOW

    exercise.caution_tag_items.append(
        ExerciseCautionTagItem(caution_tag=ExerciseCautionTag.BALANCE_DEMAND)
    )

    assert infer_exercise_demands(exercise).stability_demand is StabilityDemand.HIGH


def test_floor_bridge_is_lying_low_stability() -> None:
    exercise = make_exercise("supported-glute-bridge")
    exercise.name_en = "Glute Bridge"
    exercise.primary_muscle = MuscleGroup.GLUTES
    exercise.movement_pattern = MovementPattern.HIP_EXTENSION
    exercise.equipment_items.append(ExerciseEquipment(equipment=Equipment.BODYWEIGHT))

    demands = infer_exercise_demands(exercise)
    metadata = infer_programming_metadata(exercise)

    assert demands.body_position is BodyPosition.LYING
    assert demands.stability_demand is StabilityDemand.LOW
    assert metadata["body_position"] is BodyPosition.LYING
    assert metadata["stability_demand"] is StabilityDemand.LOW


def test_canonical_rear_decline_bridge_stability_override_wins_backfill(db: Session) -> None:
    exercise = make_exercise("fedb-0668-rear-decline-bridge")
    exercise.source = "free-exercise-db"
    exercise.source_id = "0668"
    exercise.name_en = "Rear Decline Bridge"
    exercise.primary_muscle = MuscleGroup.GLUTES
    exercise.muscle_focus = MuscleFocus.GLUTE_MAX
    exercise.movement_pattern = MovementPattern.HIP_EXTENSION
    exercise.stability_demand = StabilityDemand.HIGH
    db.add(exercise)
    db.flush()

    report = backfill_programming_metadata(db)
    db.expire_all()
    stored = db.scalar(select(Exercise).where(Exercise.id == exercise.id))

    assert stored is not None
    assert report.field_updates["stability_demand"] == 1
    assert stored.stability_demand is StabilityDemand.LOW


def test_infers_axial_loading_for_unsupported_rows_but_preserves_supported_rows() -> None:
    standing_row = make_exercise("standing-row")
    standing_row.name_en = "Standing Cable Row"
    standing_row.movement_pattern = MovementPattern.HORIZONTAL_PULL
    standing_row.equipment_items.append(ExerciseEquipment(equipment=Equipment.BODYWEIGHT))

    supported_row = make_exercise("supported-row")
    supported_row.name_en = "Chest-Supported Row"
    supported_row.movement_pattern = MovementPattern.HORIZONTAL_PULL
    supported_row.equipment_items.append(ExerciseEquipment(equipment=Equipment.BODYWEIGHT))

    assert infer_programming_metadata(standing_row)["axial_loading_level"] is LoadLimit.MODERATE
    assert infer_exercise_demands(supported_row).axial_loading_level is LoadLimit.LOW


def test_backfill_repairs_legacy_movement_pattern_substitution_group(db: Session) -> None:
    exercise = make_exercise("backfill-legacy-substitution-group")
    exercise.name_en = "Dumbbell Goblet Squat"
    exercise.substitution_group = MovementPattern.SQUAT.value
    db.add(exercise)
    db.flush()

    report = backfill_programming_metadata(db)
    db.expire_all()
    stored = db.scalar(
        select(Exercise).where(Exercise.slug == "backfill-legacy-substitution-group")
    )

    assert stored is not None
    assert stored.substitution_group == "squat_free_weight"
    assert report.field_updates["substitution_group"] == 1


def test_curated_groups_separate_structurally_distinct_same_region_movements() -> None:
    flat_press = make_exercise("flat-press")
    flat_press.name_en = "Dumbbell Bench Press"
    flat_press.primary_muscle = MuscleGroup.CHEST
    flat_press.movement_pattern = MovementPattern.HORIZONTAL_PUSH
    incline_press = make_exercise("incline-press")
    incline_press.name_en = "Dumbbell Incline Bench Press"
    incline_press.primary_muscle = MuscleGroup.CHEST
    incline_press.movement_pattern = MovementPattern.HORIZONTAL_PUSH
    romanian_deadlift = make_exercise("romanian-deadlift")
    romanian_deadlift.name_en = "Dumbbell Romanian Deadlift"
    romanian_deadlift.primary_muscle = MuscleGroup.HAMSTRINGS
    romanian_deadlift.movement_pattern = MovementPattern.HIP_HINGE
    leg_curl = make_exercise("leg-curl")
    leg_curl.name_en = "Dumbbell Lying Leg Curl"
    leg_curl.primary_muscle = MuscleGroup.HAMSTRINGS
    leg_curl.movement_pattern = MovementPattern.KNEE_FLEXION
    leg_curl.exercise_type = ExerciseType.ISOLATION

    groups = {
        item.name_en: infer_programming_metadata(item)["substitution_group"]
        for item in (flat_press, incline_press, romanian_deadlift, leg_curl)
    }

    assert groups == {
        "Dumbbell Bench Press": "horizontal_press_flat",
        "Dumbbell Incline Bench Press": "horizontal_press_incline",
        "Dumbbell Romanian Deadlift": "hip_hinge_romanian_deadlift",
        "Dumbbell Lying Leg Curl": "knee_flexion_leg_curl",
    }


@pytest.mark.parametrize(
    ("name", "pattern", "muscle", "exercise_type", "expected"),
    [
        (
            "Barbell Incline Bench Press",
            MovementPattern.HORIZONTAL_PUSH,
            MuscleGroup.CHEST,
            ExerciseType.COMPOUND,
            "horizontal_press_incline",
        ),
        (
            "Barbell Bent-Over Row",
            MovementPattern.HORIZONTAL_PULL,
            MuscleGroup.BACK,
            ExerciseType.COMPOUND,
            "horizontal_pull_row_unsupported",
        ),
        (
            "Seated Cable Row",
            MovementPattern.HORIZONTAL_PULL,
            MuscleGroup.BACK,
            ExerciseType.COMPOUND,
            "horizontal_pull_row_supported",
        ),
        (
            "Lat Pulldown",
            MovementPattern.VERTICAL_PULL,
            MuscleGroup.BACK,
            ExerciseType.COMPOUND,
            "vertical_pull_pulldown",
        ),
        (
            "Pull-Up (Wide Grip)",
            MovementPattern.VERTICAL_PULL,
            MuscleGroup.BACK,
            ExerciseType.COMPOUND,
            "vertical_pull_bodyweight",
        ),
        (
            "Seated Dumbbell Shoulder Press",
            MovementPattern.VERTICAL_PUSH,
            MuscleGroup.SHOULDERS,
            ExerciseType.COMPOUND,
            "vertical_press_shoulder",
        ),
        (
            "Hack Squat",
            MovementPattern.SQUAT,
            MuscleGroup.QUADRICEPS,
            ExerciseType.COMPOUND,
            "squat_supported_machine",
        ),
        (
            "Lever Horizontal Leg Press",
            MovementPattern.KNEE_EXTENSION,
            MuscleGroup.QUADRICEPS,
            ExerciseType.ISOLATION,
            "leg_press_knee_dominant",
        ),
        (
            "Barbell Hip Thrust",
            MovementPattern.HIP_EXTENSION,
            MuscleGroup.GLUTES,
            ExerciseType.COMPOUND,
            "hip_extension_bridge",
        ),
        (
            "Lever Seated Leg Curl",
            MovementPattern.KNEE_FLEXION,
            MuscleGroup.HAMSTRINGS,
            ExerciseType.ISOLATION,
            "knee_flexion_leg_curl",
        ),
        (
            "Lever Leg Extension",
            MovementPattern.KNEE_EXTENSION,
            MuscleGroup.QUADRICEPS,
            ExerciseType.ISOLATION,
            "knee_extension",
        ),
        (
            "Dumbbell Cross Body Hammer Curl",
            MovementPattern.ELBOW_FLEXION,
            MuscleGroup.BICEPS,
            ExerciseType.ISOLATION,
            "elbow_flexion_neutral",
        ),
        (
            "Cable Rope Overhead Triceps Extension",
            MovementPattern.ELBOW_EXTENSION,
            MuscleGroup.TRICEPS,
            ExerciseType.ISOLATION,
            "elbow_extension_overhead",
        ),
        (
            "Dumbbell Lateral Raise",
            MovementPattern.SHOULDER_ABDUCTION,
            MuscleGroup.SHOULDERS,
            ExerciseType.ISOLATION,
            "shoulder_raise_lateral",
        ),
        (
            "Dumbbell Seated Calf Raise",
            MovementPattern.CALF_RAISE,
            MuscleGroup.CALVES,
            ExerciseType.ISOLATION,
            "calf_raise_seated",
        ),
        (
            "Pallof Press",
            MovementPattern.CORE_ANTI_ROTATION,
            MuscleGroup.OBLIQUES,
            ExerciseType.CORE,
            "core_anti_rotation",
        ),
        (
            "Dumbbell Kickback",
            MovementPattern.HIP_EXTENSION,
            MuscleGroup.TRICEPS,
            ExerciseType.COMPOUND,
            None,
        ),
    ],
)
def test_catalog_curated_substitution_group_audit(
    name: str,
    pattern: MovementPattern,
    muscle: MuscleGroup,
    exercise_type: ExerciseType,
    expected: str | None,
) -> None:
    exercise = make_exercise("catalog-substitution-audit")
    exercise.name_en = name
    exercise.movement_pattern = pattern
    exercise.primary_muscle = muscle
    exercise.exercise_type = exercise_type

    assert infer_programming_metadata(exercise).get("substitution_group") == expected


def test_backfill_is_idempotent(db: Session) -> None:
    exercise = make_exercise("backfill-idempotent")
    db.add(exercise)
    db.flush()

    first = backfill_programming_metadata(db)
    db.expire_all()
    second = backfill_programming_metadata(db)

    assert first.updated == 1
    assert second.updated == 0
    assert second.skipped == 1
    assert infer_programming_metadata(exercise)["skill_demand"] is SkillDemand.LOW


def test_backfill_leaves_uncertain_metadata_unset(db: Session) -> None:
    exercise = make_exercise("backfill-uncertain")
    exercise.name_en = "Unspecified movement"
    exercise.movement_pattern = MovementPattern.OTHER
    exercise.exercise_type = ExerciseType.OTHER
    exercise.equipment_items.clear()
    db.add(exercise)
    db.flush()

    report = backfill_programming_metadata(db)
    db.expire_all()
    stored = db.scalar(select(Exercise).where(Exercise.slug == "backfill-uncertain"))

    assert stored is not None
    assert report.updated == 1
    assert report.skipped == 0
    assert stored.skill_demand is SkillDemand.LOW
    assert stored.body_position is None
    assert stored.fatigue_cost is None
    assert stored.setup_cost is None
    assert stored.laterality is None


def test_backfill_dry_run_reports_without_persisting_values(db: Session) -> None:
    exercise = make_exercise("backfill-dry-run")
    db.add(exercise)
    db.flush()

    report = backfill_programming_metadata(db, dry_run=True)
    db.expire_all()
    stored = db.scalar(select(Exercise).where(Exercise.slug == "backfill-dry-run"))

    assert stored is not None
    assert report.updated == 1
    assert report.field_updates["body_position"] == 1
    assert stored.body_position is None
    assert stored.fatigue_cost is None


def test_generic_cardio_is_not_inferred_as_low_impact() -> None:
    exercise = make_exercise("generic-cardio")
    exercise.name_en = "Cardio Exercise"
    exercise.movement_pattern = MovementPattern.OTHER
    exercise.exercise_type = ExerciseType.OTHER

    demands = infer_exercise_demands(exercise)

    assert demands.impact_level is ImpactLimit.MODERATE
    assert demands.fatigue_cost >= 3
