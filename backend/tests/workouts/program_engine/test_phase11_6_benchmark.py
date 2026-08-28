from collections import Counter

import tests.workouts.program_engine.phase11_benchmark as phase11
from tests.workouts.program_engine.phase11_6_benchmark import (
    _duration_diagnostics,
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
    assert all(len(item.priority_muscles) <= 1 for item in profiles)
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


def test_phase11_6_duration_diagnostics_use_workout_minutes_and_repair_trace() -> None:
    records = [
        {
            "input": {
                "duration_minutes": 30,
                "goal": "strength",
                "experience_level": "intermediate",
                "resistance_days": 2,
            },
            "construction_path": "TEMPLATE",
            "final_program": {
                "days": (
                    {"estimated_duration_minutes": 35},
                    {"estimated_duration_minutes": 50},
                ),
                "validation": {"warnings": ("SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD",)},
                "trace": (
                    {
                        "stage": "session_duration",
                        "repair_classification": "minor",
                    },
                    {
                        "stage": "template_selection",
                        "hard_rejections": (
                            {"reason_codes": ("REQUIRED_CORE_DURATION_INFEASIBLE",)},
                        ),
                    },
                ),
            },
        }
    ]

    diagnostics = _duration_diagnostics(records)

    assert diagnostics["sessions"] == 2
    assert diagnostics["within_target_count"] == 1
    assert diagnostics["over_target_count"] == 1
    assert diagnostics["average_absolute_deviation_minutes"] == 7.5
    assert diagnostics["late_duration_repair_percentage"] == 100.0
    assert diagnostics["major_late_repair_percentage"] == 0.0
    assert diagnostics["proven_duration_template_rejections"] == 1
    assert (
        diagnostics["breakdowns"]["requested_duration"]["30"][  # type: ignore
            "duration_fit_percentage"
        ]
        == 50.0
    )


def test_phase11_6_generates_40_minute_legacy_case() -> None:
    import tests.workouts.program_engine.phase11_benchmark as phase11
    from app.workouts.program_engine.engine import generate_program
    from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
    from tests.workouts.program_engine.golden_fixtures import full_catalog

    profiles = holdout_profiles()
    profile = next(p for p in profiles if p.duration_minutes == 40)
    request = phase11.profile_to_request(profile)
    assert request.session_duration_minutes == 40  # type: ignore

    res = generate_program(request, full_catalog(), RULESET)
    assert res.is_success
