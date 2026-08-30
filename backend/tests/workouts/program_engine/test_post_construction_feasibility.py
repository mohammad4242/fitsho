from app.workouts.program_engine.template_survival import (
    CandidateSurvivalStatus,
    assess_candidate_survival,
    candidate_survival_sort_key,
)


def test_unmodified_success_is_comfortably_feasible() -> None:
    assessment = assess_candidate_survival(
        is_success=True,
        reason_codes=(),
        repair_events=(),
    )

    assert assessment.status is CandidateSurvivalStatus.COMFORTABLY_FEASIBLE
    assert assessment.repair_cost == 0
    assert assessment.hard_reason_codes == ()


def test_legitimate_adaptation_is_repairable_with_bounded_cost() -> None:
    assessment = assess_candidate_survival(
        is_success=True,
        reason_codes=(),
        repair_events=(
            "TEMPLATE_TARGETED_ACCESSORY_ADDED",
            "SESSION_DURATION_REPAIR_APPLIED",
            "RECOVERY_WEEKDAYS_REARRANGED_FOR_EXPOSURE_LOAD",
        ),
    )

    assert assessment.status is CandidateSurvivalStatus.REPAIRABLE
    assert assessment.repair_cost == 3


def test_failed_hard_candidate_is_provably_infeasible() -> None:
    assessment = assess_candidate_survival(
        is_success=False,
        reason_codes=("BLOCKED_CAUTION_TAG_SELECTED",),
        repair_events=("SESSION_DURATION_REPAIR_APPLIED",),
    )

    assert assessment.status is CandidateSurvivalStatus.PROVABLY_INFEASIBLE
    assert assessment.hard_reason_codes == ("BLOCKED_CAUTION_TAG_SELECTED",)


def test_professional_small_repair_beats_generic_unmodified_candidate() -> None:
    professional = assess_candidate_survival(
        is_success=True,
        reason_codes=(),
        repair_events=("SESSION_DURATION_REPAIR_APPLIED",),
    )
    generic = assess_candidate_survival(
        is_success=True,
        reason_codes=(),
        repair_events=(),
    )

    assert candidate_survival_sort_key(professional, product_score=50) > (
        candidate_survival_sort_key(generic, product_score=0)
    )


def test_infeasible_professional_never_bypasses_valid_generic_candidate() -> None:
    professional = assess_candidate_survival(
        is_success=False,
        reason_codes=("WEEKLY_MUSCLE_VOLUME_EXCEEDED",),
        repair_events=(),
    )
    generic = assess_candidate_survival(
        is_success=True,
        reason_codes=(),
        repair_events=(),
    )

    assert candidate_survival_sort_key(professional, product_score=50) < (
        candidate_survival_sort_key(generic, product_score=0)
    )


def test_survival_trace_includes_constraint_class_and_repair_cost() -> None:
    assessment = assess_candidate_survival(
        is_success=False,
        reason_codes=("SESSION_DURATION_UNDER_TARGET",),
        repair_events=("SESSION_DURATION_REPAIR_APPLIED",),
    )

    assert assessment.decision_trace() == {
        "status": "provably_infeasible",
        "repair_cost": 1,
        "repair_events": ("SESSION_DURATION_REPAIR_APPLIED",),
        "reason_codes": ("SESSION_DURATION_UNDER_TARGET",),
        "hard_reason_codes": ("SESSION_DURATION_UNDER_TARGET",),
        "constraints": (
            {
                "reason_code": "SESSION_DURATION_UNDER_TARGET",
                "constraint_class": "hard",
            },
        ),
    }
