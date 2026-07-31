def double_progression_policy() -> dict[str, object]:
    return {
        "type": "double_progression",
        "qualifying_sessions": 2,
        "conditions": (
            "top_of_rep_range_for_all_working_sets",
            "within_target_rir",
            "acceptable_technique",
        ),
        "upper_body_load_increase_percent": (2.5, 5.0),
        "lower_body_load_increase_percent": (5.0, 10.0),
        "use_smallest_available_increment": True,
        "increase_volume_and_load_together": False,
        "regression_actions": (
            "reduce_load",
            "remove_one_low_priority_set",
            "increase_target_rir",
            "use_eligible_regression",
            "review_recovery",
        ),
    }


def deload_policy() -> dict[str, object]:
    return {
        "trigger_requires_multiple_signals": True,
        "volume_reduction_percent": (30, 50),
        "load_reduction_percent": (5, 10),
        "maintain_main_movement_patterns": True,
        "never_override_safety_referral": True,
    }

