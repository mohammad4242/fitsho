from collections import Counter

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


def test_phase11_population_covers_every_supported_cell_with_five_profiles() -> None:
    profiles = benchmark_profiles()

    assert len(profiles) == 75
    assert Counter((item.experience_level.value, item.resistance_days) for item in profiles) == {
        cell: 5 for cell in SUPPORTED_MATRIX
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
