import pytest

from app.exercises.enums import ExerciseType, PrescriptionMode
from app.workouts.program_engine.enums import Goal, TrainingStatus
from app.workouts.program_engine.prescription import prescription_for
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.strength_programming import (
    APPROVED_PRIMARY_STRENGTH_LIFT_SLUGS,
    StrengthExerciseRole,
    is_strength_set_cap_authorized,
)


def test_hypertrophy_rir_depends_on_role_and_experience() -> None:
    novice_compound = prescription_for(
        Goal.HYPERTROPHY, ExerciseType.COMPOUND, TrainingStatus.NOVICE, RULESET
    )
    novice_isolation = prescription_for(
        Goal.HYPERTROPHY, ExerciseType.ISOLATION, TrainingStatus.NOVICE, RULESET
    )
    advanced_compound = prescription_for(
        Goal.HYPERTROPHY, ExerciseType.COMPOUND, TrainingStatus.ADVANCED, RULESET
    )
    advanced_isolation = prescription_for(
        Goal.HYPERTROPHY, ExerciseType.ISOLATION, TrainingStatus.ADVANCED, RULESET
    )

    assert novice_compound.target_rir == 3
    assert novice_isolation.target_rir == 2
    assert advanced_compound.target_rir == 1
    assert advanced_isolation.target_rir == 1


def test_strength_rir_depends_on_role_and_experience() -> None:
    novice_primary = prescription_for(
        Goal.STRENGTH,
        ExerciseType.COMPOUND,
        TrainingStatus.NOVICE,
        RULESET,
        strength_role=StrengthExerciseRole.PRIMARY_STRENGTH,
    )
    advanced_primary = prescription_for(
        Goal.STRENGTH,
        ExerciseType.COMPOUND,
        TrainingStatus.ADVANCED,
        RULESET,
        strength_role=StrengthExerciseRole.PRIMARY_STRENGTH,
    )
    advanced_secondary = prescription_for(
        Goal.STRENGTH,
        ExerciseType.COMPOUND,
        TrainingStatus.ADVANCED,
        RULESET,
        strength_role=StrengthExerciseRole.SECONDARY_COMPOUND,
    )
    advanced_isolation = prescription_for(
        Goal.STRENGTH,
        ExerciseType.ISOLATION,
        TrainingStatus.ADVANCED,
        RULESET,
        strength_role=StrengthExerciseRole.ACCESSORY,
    )

    assert novice_primary.target_rir == 3
    assert advanced_primary.target_rir == 2
    assert advanced_secondary.target_rir == 2
    assert advanced_isolation.target_rir == 1


@pytest.mark.parametrize("goal", tuple(Goal))
@pytest.mark.parametrize("status", tuple(TrainingStatus))
@pytest.mark.parametrize(
    "exercise_type",
    (ExerciseType.COMPOUND, ExerciseType.ISOLATION, ExerciseType.CORE),
)
def test_prescription_never_assigns_indiscriminate_failure(
    goal: Goal,
    status: TrainingStatus,
    exercise_type: ExerciseType,
) -> None:
    prescription = prescription_for(goal, exercise_type, status, RULESET)

    assert prescription.target_rir is not None
    assert prescription.target_rir >= 1


def test_role_specific_rep_ranges_and_practical_rest_ranges() -> None:
    strength_primary = prescription_for(
        Goal.STRENGTH,
        ExerciseType.COMPOUND,
        TrainingStatus.ADVANCED,
        RULESET,
        strength_role=StrengthExerciseRole.PRIMARY_STRENGTH,
    )
    strength_secondary = prescription_for(
        Goal.STRENGTH,
        ExerciseType.COMPOUND,
        TrainingStatus.ADVANCED,
        RULESET,
        strength_role=StrengthExerciseRole.SECONDARY_COMPOUND,
    )
    strength_isolation = prescription_for(
        Goal.STRENGTH,
        ExerciseType.ISOLATION,
        TrainingStatus.ADVANCED,
        RULESET,
        strength_role=StrengthExerciseRole.ACCESSORY,
    )
    hypertrophy_compound = prescription_for(
        Goal.HYPERTROPHY, ExerciseType.COMPOUND, TrainingStatus.INTERMEDIATE, RULESET
    )
    hypertrophy_isolation = prescription_for(
        Goal.HYPERTROPHY, ExerciseType.ISOLATION, TrainingStatus.INTERMEDIATE, RULESET
    )
    hypertrophy_core = prescription_for(
        Goal.HYPERTROPHY, ExerciseType.CORE, TrainingStatus.INTERMEDIATE, RULESET
    )

    assert (strength_primary.rep_min, strength_primary.rep_max) == (3, 6)
    assert (strength_primary.minimum_rest_seconds, strength_primary.rest_seconds) == (150, 180)
    assert strength_primary.maximum_rest_seconds == 180
    assert (strength_secondary.rep_min, strength_secondary.rep_max) == (5, 10)
    assert (strength_secondary.minimum_rest_seconds, strength_secondary.rest_seconds) == (120, 135)
    assert strength_secondary.maximum_rest_seconds == 150
    assert (strength_isolation.rep_min, strength_isolation.rep_max) == (8, 15)
    assert 75 <= strength_isolation.rest_seconds <= 120
    assert (hypertrophy_compound.rep_min, hypertrophy_compound.rep_max) == (6, 12)
    assert 90 <= hypertrophy_compound.rest_seconds <= 150
    assert (hypertrophy_isolation.rep_min, hypertrophy_isolation.rep_max) == (10, 20)
    assert 60 <= hypertrophy_isolation.rest_seconds <= 90
    assert (hypertrophy_core.rep_min, hypertrophy_core.rep_max) == (8, 20)
    assert 45 <= hypertrophy_core.rest_seconds <= 90


def test_high_fatigue_strength_work_uses_upper_range_without_five_minute_rest() -> None:
    prescription = prescription_for(
        Goal.STRENGTH,
        ExerciseType.COMPOUND,
        TrainingStatus.ADVANCED,
        RULESET,
        strength_role=StrengthExerciseRole.SECONDARY_COMPOUND,
        fatigue_cost=RULESET.strength_high_fatigue_cost,
    )

    assert prescription.rest_seconds == prescription.maximum_rest_seconds == 150
    assert prescription.rest_seconds < 300


@pytest.mark.parametrize("exercise_slug", sorted(APPROVED_PRIMARY_STRENGTH_LIFT_SLUGS))
def test_strength_compound_set_cap_bonus_authorizes_only_approved_lifts(
    exercise_slug: str,
) -> None:
    assert is_strength_set_cap_authorized(
        goal=Goal.STRENGTH,
        exercise_type=ExerciseType.COMPOUND,
        exercise_slug=exercise_slug,
        is_primary_strength=True,
    )
    cap = RULESET.max_working_sets_for_exercise(
        training_status=TrainingStatus.ADVANCED,
        goal=Goal.STRENGTH,
        exercise_type=ExerciseType.COMPOUND,
        is_priority=True,
        weekly_exposure_count=1,
        is_primary_strength=True,
        is_approved_primary_strength_lift=True,
    )

    assert cap == 5


def test_strength_compound_set_cap_bonus_keeps_unrelated_context_at_four_sets() -> None:
    common = {
        "training_status": TrainingStatus.ADVANCED,
        "exercise_type": ExerciseType.COMPOUND,
        "is_priority": True,
        "weekly_exposure_count": 1,
        "is_primary_strength": True,
        "is_approved_primary_strength_lift": True,
    }

    assert RULESET.max_working_sets_for_exercise(goal=Goal.HYPERTROPHY, **common) == 4
    assert (
        RULESET.max_working_sets_for_exercise(
            goal=Goal.STRENGTH,
            exercise_type=ExerciseType.ISOLATION,
            **{key: value for key, value in common.items() if key != "exercise_type"},
        )
        == 4
    )
    assert (
        RULESET.max_working_sets_for_exercise(
            goal=Goal.STRENGTH,
            is_approved_primary_strength_lift=False,
            **{
                key: value
                for key, value in common.items()
                if key != "is_approved_primary_strength_lift"
            },
        )
        == 4
    )


def test_duration_core_preserves_metadata_without_fake_rep_or_rir_values() -> None:
    prescription = prescription_for(
        Goal.HYPERTROPHY,
        ExerciseType.CORE,
        TrainingStatus.INTERMEDIATE,
        RULESET,
        prescription_mode=PrescriptionMode.DURATION,
        duration_min_seconds=30,
        duration_max_seconds=45,
    )

    assert prescription.rep_min is None
    assert prescription.rep_max is None
    assert prescription.target_rir is None
    assert (prescription.duration_min_seconds, prescription.duration_max_seconds) == (30, 45)
