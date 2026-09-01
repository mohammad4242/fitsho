from app.workouts.program_engine.constraint_classification import (
    ConstraintClass,
    classify_constraint,
    constraint_trace,
)


def test_classifies_stable_hard_safety_and_contract_reasons() -> None:
    hard_reasons = (
        "BLOCKED_CAUTION_TAG_SELECTED",
        "UNAVAILABLE_EQUIPMENT_SELECTED",
        "REQUIRED_MOVEMENT_PATTERN_MISSING",
        "TEMPLATE_CORE_SLOT_UNRESOLVABLE",
        "REQUESTED_TRAINING_DAYS_UNSATISFIED",
        "WEEKLY_MUSCLE_VOLUME_EXCEEDED",
        "PER_SESSION_MUSCLE_VOLUME_EXCEEDED",
        "PER_EXERCISE_SET_CAP_EXCEEDED",
        "RECOVERY_DIRECT_HIGH_UNSAFE",
    )

    assert all(classify_constraint(reason) is ConstraintClass.HARD for reason in hard_reasons)


def test_repairable_contracts_become_hard_only_after_exhaustion() -> None:
    repairable_reasons = (
        "RECOVERY_SPACING_INVALID",
        "SESSION_EXERCISE_COUNT_OUT_OF_RANGE",
        "SESSION_DURATION_EXCEEDED",
    )

    assert all(
        classify_constraint(reason) is ConstraintClass.REPAIRABLE for reason in repairable_reasons
    )
    assert all(
        classify_constraint(reason, repair_exhausted=True) is ConstraintClass.HARD
        for reason in repairable_reasons
    )
    assert classify_constraint("SESSION_DURATION_UNDER_TARGET") is ConstraintClass.SOFT
    assert (
        classify_constraint("SESSION_DURATION_UNDER_TARGET", repair_exhausted=True)
        is ConstraintClass.SOFT
    )


def test_classifies_quality_drift_as_soft_and_unknown_explicitly() -> None:
    assert classify_constraint("EFFECTIVE_VOLUME_BELOW_ACCEPTABLE_RANGE") is ConstraintClass.SOFT
    assert classify_constraint("SOFT_WEEKLY_VOLUME_EXCEEDED") is ConstraintClass.SOFT
    assert classify_constraint("MUSCLE_DIRECT_FREQUENCY_EXCEEDED") is ConstraintClass.SOFT
    assert classify_constraint("SEMANTIC_SLOT_MISMATCH_SELECTED") is ConstraintClass.SOFT
    assert classify_constraint("FUTURE_REASON_CODE") is None


def test_classifies_current_final_quality_constraints_explicitly() -> None:
    final_quality_constraints = (
        "WEEKLY_VOLUME_CONSTRAINED",
        "DIRECT_VOLUME_BELOW_SOFT_TARGET",
        "PRIORITY_TARGET_PARTIALLY_SATISFIED",
        "PRIORITY_TARGET_CONSTRAINED",
        "RECOVERY_REPAIRABLE_OVERLAP_REMAINS",
        "MINIMUM_DIRECT_MUSCLE_COVERAGE_UNSATISFIED:shoulders",
        "MINIMUM_MUSCLE_COVERAGE_UNSATISFIED:shoulders",
        "DURATION_CAPACITY_LIMITED_VOLUME",
    )

    classifications = tuple(classify_constraint(reason) for reason in final_quality_constraints)
    assert classifications == (ConstraintClass.SOFT,) * len(final_quality_constraints)


def test_structured_reason_suffix_uses_the_stable_base_code() -> None:
    assert (
        classify_constraint("REQUESTED_TRAINING_DAYS_MISMATCH:expected=6:actual=5")
        is ConstraintClass.HARD
    )


def test_constraint_trace_preserves_reason_and_metadata() -> None:
    trace = constraint_trace("RECOVERY_SPACING_INVALID", {"muscle": "shoulders"})

    assert trace.reason_code == "RECOVERY_SPACING_INVALID"
    assert trace.constraint_class is ConstraintClass.REPAIRABLE
    assert trace.metadata == {"muscle": "shoulders"}
    assert trace.as_trace() == {
        "reason_code": "RECOVERY_SPACING_INVALID",
        "constraint_class": "repairable",
        "metadata": {"muscle": "shoulders"},
    }


def test_validation_and_construction_reason_inventory_is_classified() -> None:
    hard = (
        "INVALID_EXERCISE_PRESCRIPTION",
        "SEMANTIC_NEAR_DUPLICATE_EXERCISE",
        "UNJUSTIFIED_DUPLICATE_EXERCISE",
        "REQUIRED_SLOT_HARD_IMPOSSIBILITY:horizontal_push",
        "PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED",
        "SAFETY_STATUS_DISALLOWS_GENERATION",
        "RESISTANCE_WORK_EXCLUDED_FROM_VOLUME",
        "FULL_BODY_COVERAGE_UNSATISFIED",
        "FULL_BODY_PATTERN_MISSING:pull",
        "NO_SAFE_EXERCISE_FOR_PATTERN",
        "VOLUME_REPAIR_HARD_MINIMUM_UNSATISFIED",
    )
    repairable = (
        "INITIAL_TEMPLATE_REJECTED_UNFILLABLE",
        "TEMPLATE_MAIN_COUNT_OUT_OF_RANGE",
        "RECOVERY_WEEKDAY_REPAIR_UNAVAILABLE",
        "RECOVERY_OPTIONAL_ISOLATION_REDISTRIBUTION_UNAVAILABLE",
        "UNSAFE_SUPERSET_PAIR",
    )

    assert all(classify_constraint(code) is ConstraintClass.HARD for code in hard)
    assert all(classify_constraint(code) is ConstraintClass.REPAIRABLE for code in repairable)
    assert (
        classify_constraint("INITIAL_TEMPLATE_REJECTED_UNFILLABLE", repair_exhausted=True)
        is ConstraintClass.HARD
    )
