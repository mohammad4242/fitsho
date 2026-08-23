from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET, ProgramRuleset


def double_progression_policy(ruleset: ProgramRuleset = RULESET) -> dict[str, object]:
    return {
        "type": "double_progression",
        "qualifying_sessions": ruleset.double_progression_qualifying_sessions,
        "conditions": (
            "top_of_rep_range_for_all_working_sets",
            "within_target_rir",
            "acceptable_technique",
        ),
        "upper_body_load_increase_percent": ruleset.upper_body_load_increase_percent,
        "lower_body_load_increase_percent": ruleset.lower_body_load_increase_percent,
        "use_smallest_available_increment": True,
        "increase_volume_and_load_together": False,
        "runtime_workout_log_adaptation": False,
        "regression_actions": (
            "reduce_load",
            "remove_one_low_priority_set",
            "increase_target_rir",
            "use_eligible_regression",
            "review_recovery",
        ),
    }


def deload_policy(ruleset: ProgramRuleset = RULESET) -> dict[str, object]:
    return {
        "mode": "hybrid",
        "reactive_is_primary": True,
        "trigger_requires_multiple_signals": True,
        "planned_checkpoint_eligible": True,
        "planned_checkpoint_requires_long_or_high_fatigue_block": True,
        "planned_checkpoint_is_automatic": False,
        "mandatory_schedule_weeks": None,
        "volume_reduction_percent": ruleset.deload_volume_reduction_percent,
        "load_reduction_percent": ruleset.deload_load_reduction_percent,
        "maintain_main_movement_patterns": True,
        "never_override_safety_referral": True,
    }
