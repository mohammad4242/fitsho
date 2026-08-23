from collections import Counter

import tests.workouts.program_engine.phase11_benchmark as phase11
from tests.workouts.program_engine.phase11_6_benchmark import (
    holdout_profiles,
    input_fingerprint,
    negative_profiles,
)


def test_phase11_6_is_a_new_ten_per_cell_holdout() -> None:
    profiles = holdout_profiles()

    assert len(profiles) == 150
    assert len({input_fingerprint(profile) for profile in profiles}) == 150
    assert not {input_fingerprint(profile) for profile in profiles}.intersection(
        input_fingerprint(profile) for profile in phase11.benchmark_profiles()
    )
    assert Counter((item.experience_level.value, item.resistance_days) for item in profiles) == {
        cell: 10 for cell in phase11.SUPPORTED_MATRIX
    }


def test_phase11_6_profile_diversity_is_realistic_and_broad() -> None:
    profiles = holdout_profiles()

    assert {item.goal.value for item in profiles} == {
        "strength",
        "hypertrophy",
        "body_recomposition",
        "fat_loss",
        "general_fitness",
    }
    assert {item.duration_minutes for item in profiles} >= {30, 40, 45, 60, 75, 90, 120}
    assert {item.equipment_label for item in profiles} >= {
        "full_gym",
        "limited_gym",
        "dumbbells_bench",
        "dumbbells_only",
        "bands_bodyweight",
        "home_limited",
    }
    assert {item.sex for item in profiles} >= {None}
    assert any(item.priority_muscles for item in profiles)
    assert any(len(item.priority_muscles) > 1 for item in profiles)
    assert any(item.body_analysis_priorities for item in profiles)
    assert any(len(item.body_analysis_priorities) > 1 for item in profiles)
    assert any(item.priority_muscles and item.body_analysis_priorities for item in profiles)
    assert any(item.training_cautions for item in profiles)
    assert any(item.recent_recovery_problems for item in profiles)


def test_phase11_6_negative_profiles_keep_unsupported_matrix_rejections() -> None:
    profiles = negative_profiles()

    assert len(profiles) == 4
    assert {(item.experience_level.value, item.resistance_days) for item in profiles} == {
        ("first_month", 5),
        ("beginner", 5),
        ("intermediate", 7),
        ("advanced", 2),
    }
