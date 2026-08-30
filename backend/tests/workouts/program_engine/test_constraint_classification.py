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
        "SESSION_DURATION_UNDER_TARGET",
        "SESSION_DURATION_EXCEEDED",
    )

    assert all(
        classify_constraint(reason) is ConstraintClass.REPAIRABLE for reason in repairable_reasons
    )
    assert all(
        classify_constraint(reason, repair_exhausted=True) is ConstraintClass.HARD
        for reason in repairable_reasons
    )


def test_classifies_quality_drift_as_soft_and_unknown_explicitly() -> None:
    assert classify_constraint("EFFECTIVE_VOLUME_BELOW_ACCEPTABLE_RANGE") is ConstraintClass.SOFT
    assert classify_constraint("SOFT_WEEKLY_VOLUME_EXCEEDED") is ConstraintClass.SOFT
    assert classify_constraint("MUSCLE_DIRECT_FREQUENCY_EXCEEDED") is ConstraintClass.SOFT
    assert classify_constraint("SEMANTIC_SLOT_MISMATCH_SELECTED") is ConstraintClass.SOFT
    assert classify_constraint("FUTURE_REASON_CODE") is None


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
