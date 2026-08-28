from uuid import NAMESPACE_URL, uuid5

import pytest

from app.exercises.enums import (
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.exercise_semantics import ExerciseRoleSignature
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    NormalizedProgramRequest,
    ProgrammedExercise,
    WorkoutDay,
)
from app.workouts.program_engine.session_structure import (
    finalize_session_structure,
    session_structure_errors,
)
from tests.workouts.program_engine.golden_fixtures import request


def _programmed(
    slug: str,
    *,
    pattern: MovementPattern,
    muscle: MuscleGroup,
    order: int,
    substitution_group: str,
    exercise_type: ExerciseType = ExerciseType.COMPOUND,
    caution_tags: frozenset[ExerciseCautionTag] = frozenset(),
) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=uuid5(NAMESPACE_URL, f"https://fitsho.test/task-d/{slug}"),
        exercise_name=slug,
        order=order,
        sets=3,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=75,
        estimated_minutes=6,
        reason_codes=("TEST",),
        movement_pattern=pattern,
        primary_muscle=muscle,
        equipment=frozenset({Equipment.BODYWEIGHT}),
        caution_tags=caution_tags,
        exercise_type=exercise_type,
        substitution_group=substitution_group,
    )


def _day(focus: str, exercises: tuple[ProgrammedExercise, ...]) -> WorkoutDay:
    return WorkoutDay(
        day_index=1,
        weekday=0,
        title="Test",
        focus=focus,
        estimated_duration_minutes=5 + sum(item.estimated_minutes for item in exercises),
        exercises=exercises,
    )


def _normalized(**overrides: object) -> NormalizedProgramRequest:
    return normalize_request(request(**overrides), RULESET)


def _families(day: WorkoutDay) -> tuple[str, ...]:
    return tuple(
        ExerciseRoleSignature.from_candidate(item).canonical_family for item in day.exercises
    )


def test_push_up_family_is_the_first_working_exercise_in_chest_session() -> None:
    push_up = _programmed(
        "push-up",
        pattern=MovementPattern.HORIZONTAL_PUSH,
        muscle=MuscleGroup.CHEST,
        order=3,
        substitution_group="horizontal_press_push_up",
    )
    bench = _programmed(
        "flat-press",
        pattern=MovementPattern.HORIZONTAL_PUSH,
        muscle=MuscleGroup.CHEST,
        order=1,
        substitution_group="horizontal_press_flat",
    )
    shoulder = _programmed(
        "shoulder-press",
        pattern=MovementPattern.VERTICAL_PUSH,
        muscle=MuscleGroup.SHOULDERS,
        order=2,
        substitution_group="vertical_press_shoulder",
    )

    finalized = finalize_session_structure(
        (_day("upper", (bench, shoulder, push_up)),), _normalized(), RULESET
    )[0]

    assert _families(finalized) == (
        "horizontal_push_push_up",
        "horizontal_press_flat",
        "vertical_press_shoulder",
    )


def test_pull_up_family_is_the_first_working_exercise_in_back_session() -> None:
    pull_up = _programmed(
        "pull-up",
        pattern=MovementPattern.VERTICAL_PULL,
        muscle=MuscleGroup.BACK,
        order=3,
        substitution_group="vertical_pull_bodyweight",
    )
    row = _programmed(
        "row",
        pattern=MovementPattern.HORIZONTAL_PULL,
        muscle=MuscleGroup.BACK,
        order=1,
        substitution_group="horizontal_pull_row_unsupported",
    )
    curl = _programmed(
        "curl",
        pattern=MovementPattern.ELBOW_FLEXION,
        muscle=MuscleGroup.BICEPS,
        order=2,
        substitution_group="elbow_flexion_supinated",
        exercise_type=ExerciseType.ISOLATION,
    )

    finalized = finalize_session_structure(
        (_day("upper", (row, curl, pull_up)),), _normalized(), RULESET
    )[0]

    assert _families(finalized)[0] == "vertical_pull_bodyweight"


def test_safe_leg_extension_primer_precedes_squat_family() -> None:
    squat = _programmed(
        "squat",
        pattern=MovementPattern.SQUAT,
        muscle=MuscleGroup.QUADRICEPS,
        order=1,
        substitution_group="squat_free_weight",
    )
    leg_extension = _programmed(
        "leg-extension",
        pattern=MovementPattern.KNEE_EXTENSION,
        muscle=MuscleGroup.QUADRICEPS,
        order=2,
        substitution_group="knee_extension",
        exercise_type=ExerciseType.ISOLATION,
    )

    finalized = finalize_session_structure(
        (_day("legs", (squat, leg_extension)),), _normalized(), RULESET
    )[0]

    assert _families(finalized) == ("knee_extension:quadriceps:isolation", "squat_primary")


def test_knee_contraindication_does_not_promote_leg_extension_primer() -> None:
    squat = _programmed(
        "squat",
        pattern=MovementPattern.SQUAT,
        muscle=MuscleGroup.QUADRICEPS,
        order=1,
        substitution_group="squat_free_weight",
    )
    leg_extension = _programmed(
        "leg-extension",
        pattern=MovementPattern.KNEE_EXTENSION,
        muscle=MuscleGroup.QUADRICEPS,
        order=2,
        substitution_group="knee_extension",
        exercise_type=ExerciseType.ISOLATION,
        caution_tags=frozenset({ExerciseCautionTag.DEEP_KNEE_FLEXION}),
    )

    finalized = finalize_session_structure(
        (_day("legs", (squat, leg_extension)),),
        _normalized(blocked_caution_tags={ExerciseCautionTag.DEEP_KNEE_FLEXION}),
        RULESET,
    )[0]

    assert _families(finalized) == ("squat_primary", "knee_extension:quadriceps:isolation")


@pytest.mark.parametrize(
    ("focus", "items", "expected_error"),
    [
        (
            "upper",
            (
                _programmed(
                    "press",
                    pattern=MovementPattern.HORIZONTAL_PUSH,
                    muscle=MuscleGroup.CHEST,
                    order=1,
                    substitution_group="horizontal_press_flat",
                ),
                _programmed(
                    "push-up",
                    pattern=MovementPattern.HORIZONTAL_PUSH,
                    muscle=MuscleGroup.CHEST,
                    order=2,
                    substitution_group="horizontal_press_push_up",
                ),
            ),
            "PUSH_UP_OPENER_ORDER_INVALID",
        ),
        (
            "upper",
            (
                _programmed(
                    "row",
                    pattern=MovementPattern.HORIZONTAL_PULL,
                    muscle=MuscleGroup.BACK,
                    order=1,
                    substitution_group="horizontal_pull_row_unsupported",
                ),
                _programmed(
                    "pull-up",
                    pattern=MovementPattern.VERTICAL_PULL,
                    muscle=MuscleGroup.BACK,
                    order=2,
                    substitution_group="vertical_pull_bodyweight",
                ),
            ),
            "PULL_UP_OPENER_ORDER_INVALID",
        ),
        (
            "legs",
            (
                _programmed(
                    "squat",
                    pattern=MovementPattern.SQUAT,
                    muscle=MuscleGroup.QUADRICEPS,
                    order=1,
                    substitution_group="squat_free_weight",
                ),
                _programmed(
                    "leg-extension",
                    pattern=MovementPattern.KNEE_EXTENSION,
                    muscle=MuscleGroup.QUADRICEPS,
                    order=2,
                    substitution_group="knee_extension",
                    exercise_type=ExerciseType.ISOLATION,
                ),
            ),
            "LEG_EXTENSION_PRIMER_ORDER_INVALID",
        ),
    ],
)
def test_final_structure_validator_rejects_late_opener_mutations(
    focus: str,
    items: tuple[ProgrammedExercise, ...],
    expected_error: str,
) -> None:
    assert expected_error in session_structure_errors(_day(focus, items), Goal.HYPERTROPHY)


def test_batch2_profiles_2_and_9_keep_selected_push_up_as_chest_opener(monkeypatch) -> None:
    import scripts.generate_e2e_report_batch2 as batch2

    captured = []
    original_generate = batch2.generate_program

    def capture_generate(*args, **kwargs):
        result = original_generate(*args, **kwargs)
        captured.append(result)
        return result

    monkeypatch.setattr(batch2, "generate_program", capture_generate)
    monkeypatch.setattr(
        batch2,
        "TEST_PROFILES_BATCH2",
        [item for item in batch2.TEST_PROFILES_BATCH2 if item["num"] in {2, 9}],
    )

    results = batch2.run_batch2_profiles()

    assert {profile["num"] for profile, _result in results} == {2, 9}
    assert len(captured) == 2
    for generation in captured:
        assert generation.program is not None
        for day in generation.program.weekly_schedule:
            push_ups = [
                item
                for item in day.exercises
                if ExerciseRoleSignature.from_candidate(item).canonical_family
                == "horizontal_push_push_up"
            ]
            if push_ups and any(item.primary_muscle is MuscleGroup.CHEST for item in day.exercises):
                assert push_ups[0] is day.exercises[0]
