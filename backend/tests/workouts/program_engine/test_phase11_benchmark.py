from collections import Counter
from types import SimpleNamespace
from uuid import uuid4

import tests.workouts.program_engine.phase11_benchmark as benchmark
from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import full_catalog
from tests.workouts.program_engine.phase11_benchmark import (
    NEGATIVE_PROFILES,
    SUPPORTED_MATRIX,
    benchmark_profiles,
    canonical_fingerprint,
    profile_to_request,
)


def _successful_result(*, warnings: tuple[str, ...] = ()) -> SimpleNamespace:
    return SimpleNamespace(
        program=SimpleNamespace(
            validation_report=SimpleNamespace(warnings=warnings),
        )
    )


def test_phase11_population_covers_every_supported_cell_with_five_profiles() -> None:
    profiles = benchmark_profiles()

    assert len(profiles) == 375
    assert Counter((item.experience_level.value, item.resistance_days) for item in profiles) == {
        cell: 25 for cell in SUPPORTED_MATRIX
    }
    assert len({item.goal.value for item in profiles}) >= 5
    assert len({item.equipment_label for item in profiles}) >= 4
    assert len({item.duration_minutes for item in profiles}) >= 5


def test_phase11_negative_profiles_reject_unsupported_days() -> None:
    for profile in NEGATIVE_PROFILES:
        result = generate_program(
            profile_to_request(profile, enforce_matrix=False), full_catalog(), RULESET
        )

        assert result.program is None
        assert result.error_code is not None
        assert result.error_code.value == "UNSUPPORTED_RESISTANCE_TRAINING_DAYS"


def test_phase11_representative_output_has_an_identical_determinism_fingerprint() -> None:
    profile = benchmark_profiles()[37]
    request = profile_to_request(profile)
    first = generate_program(request, full_catalog(), RULESET)
    second = generate_program(request, full_catalog(), RULESET)

    assert canonical_fingerprint(first) == canonical_fingerprint(second)


def test_fallback_construction_does_not_replace_quality_outcome() -> None:
    result = _successful_result()

    assert benchmark._category(result, {"fallback_succeeded": True}, ()) == "PASS"
    assert benchmark._construction_path(result, {"succeeded": False}) == "FALLBACK"


def test_legitimate_constraint_finding_is_pass_with_constraints() -> None:
    result = _successful_result(warnings=("BODY_ANALYSIS_PRIORITY_PARTIAL",))

    category = benchmark._category(
        result,
        {"fallback_succeeded": False},
        (
            {
                "code": "BODY_ANALYSIS_PRIORITY_PARTIAL",
                "severity": "constraint",
                "message": "hamstrings",
            },
        ),
    )

    assert category == "PASS_WITH_CONSTRAINTS"


def test_weekly_pattern_frequency_is_not_automatically_redundant() -> None:
    repeated_pattern_days = tuple(
        SimpleNamespace(
            exercises=(
                SimpleNamespace(
                    exercise_id=uuid4(),
                    primary_muscle="chest",
                    movement_pattern="horizontal_push",
                    exercise_type="compound",
                    equipment=frozenset({"dumbbell"}),
                ),
            )
        )
        for _ in range(4)
    )

    detector = getattr(benchmark, "_has_redundant_near_identical_movements", None)

    assert callable(detector)
    assert detector(repeated_pattern_days) is False


def test_same_session_exact_duplicate_is_redundant() -> None:
    exercise_id = uuid4()
    duplicated_day = SimpleNamespace(
        exercises=tuple(
            SimpleNamespace(
                exercise_id=exercise_id,
                primary_muscle="chest",
                movement_pattern="horizontal_push",
                exercise_type="compound",
                equipment=frozenset({"dumbbell"}),
            )
            for _ in range(2)
        )
    )

    detector = getattr(benchmark, "_has_redundant_near_identical_movements", None)

    assert callable(detector)
    assert detector((duplicated_day,)) is True


def test_two_similar_same_session_movements_are_not_automatically_redundant() -> None:
    similar_day = SimpleNamespace(
        exercises=tuple(
            SimpleNamespace(
                exercise_id=uuid4(),
                primary_muscle="chest",
                movement_pattern="horizontal_push",
                exercise_type="compound",
                equipment=frozenset({"dumbbell"}),
            )
            for _ in range(2)
        )
    )

    assert benchmark._has_redundant_near_identical_movements((similar_day,)) is False


def test_major_coverage_uses_the_canonical_profile_minimum_not_two_sets() -> None:
    ranges = {
        muscle.value: {
            "minimum_coverage_required": True,
            "minimum_effective_sets": 1,
            "actual_effective_volume": 1.0,
        }
        for muscle in benchmark.MAJOR_MUSCLES
    }

    assert benchmark._missing_major_muscle_coverage(ranges) == ()


def test_supplemental_abs_absence_is_not_a_major_coverage_miss() -> None:
    ranges = {
        MuscleGroup.ABS.value: {
            "minimum_coverage_required": True,
            "minimum_effective_sets": 1,
            "actual_effective_volume": 0.0,
        }
    }

    assert benchmark._missing_major_muscle_coverage(ranges) == ()
