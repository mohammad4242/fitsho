from app.workouts.program_engine.progression import deload_policy, double_progression_policy


def test_double_progression_remains_the_default_progression_contract() -> None:
    policy = double_progression_policy()

    assert policy["type"] == "double_progression"
    assert policy["qualifying_sessions"] == 2
    assert policy["conditions"] == (
        "top_of_rep_range_for_all_working_sets",
        "within_target_rir",
        "acceptable_technique",
    )
    assert policy["use_smallest_available_increment"] is True
    assert policy["increase_volume_and_load_together"] is False


def test_progression_does_not_enable_runtime_workout_log_rewrites() -> None:
    policy = double_progression_policy()

    assert policy["runtime_workout_log_adaptation"] is False


def test_deload_is_reactive_first_with_planned_checkpoint_eligibility() -> None:
    policy = deload_policy()

    assert policy["mode"] == "hybrid"
    assert policy["reactive_is_primary"] is True
    assert policy["trigger_requires_multiple_signals"] is True
    assert policy["planned_checkpoint_eligible"] is True
    assert policy["planned_checkpoint_requires_long_or_high_fatigue_block"] is True
    assert policy["planned_checkpoint_is_automatic"] is False
    assert policy["mandatory_schedule_weeks"] is None


def test_deload_preserves_patterns_and_uses_bounded_reductions() -> None:
    policy = deload_policy()

    assert policy["volume_reduction_percent"] == (30, 50)
    assert policy["load_reduction_percent"] == (5, 10)
    assert policy["maintain_main_movement_patterns"] is True
    assert policy["never_override_safety_referral"] is True
