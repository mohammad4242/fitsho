from __future__ import annotations

from dataclasses import replace

from app.workouts.program_engine.enums import GenerationErrorCode
from app.workouts.program_engine.program_selection import (
    CandidateSource,
    ProgramCandidate,
    ProgramQualityView,
    select_best_program,
)
from app.workouts.program_engine.schemas import ProgramGenerationResult


def _quality(
    critical: tuple[tuple[str, float | None], ...] = (("volume", 90.0),),
    **overrides: object,
) -> ProgramQualityView:
    return ProgramQualityView(critical_dimensions=critical, **overrides)


def _candidate(
    identifier: str,
    quality: ProgramQualityView | None = None,
    *,
    source: CandidateSource = CandidateSource.CANONICAL_SPLIT,
    rank: int = 1,
    result: ProgramGenerationResult | None = None,
) -> ProgramCandidate:
    if result is None:
        result = ProgramGenerationResult(
            program=object(),
            decision_trace=(
                {
                    "stage": "final_quality_gate",
                    "status": "accepted",
                    "reason_codes": (),
                    "constraint_reason_codes": (),
                },
            ),
        )
    return ProgramCandidate(
        source=source,
        identifier=identifier,
        preconstruction_rank=rank,
        preconstruction_score=50.0,
        result=result,
        quality=quality or _quality(),
    )


def test_hard_invalid_candidate_never_wins_over_a_valid_candidate() -> None:
    invalid = _candidate(
        "invalid-high-quality",
        _quality(critical=(("volume", 100.0), ("priority", 100.0))),
        result=ProgramGenerationResult(
            program=None,
            error_code=GenerationErrorCode.UNSATISFIED_CONSTRAINT,
        ),
    )
    valid = _candidate("valid-lower-quality", _quality(critical=(("volume", 70.0),)))

    decision = select_best_program((invalid, valid))

    assert decision.selected is valid
    assert decision.comparisons[0].admitted is False


def test_balanced_candidate_beats_high_average_candidate_with_one_weak_dimension() -> None:
    high_average = _candidate(
        "high-average",
        _quality(critical=(("a", 100.0), ("b", 70.0), ("c", 100.0), ("d", 100.0))),
    )
    balanced = _candidate(
        "balanced",
        _quality(critical=(("a", 94.0), ("b", 94.0), ("c", 93.0), ("d", 100.0))),
    )

    assert select_best_program((high_average, balanced)).selected is balanced


def test_not_applicable_dimension_is_not_converted_to_zero() -> None:
    not_applicable = _candidate(
        "not-applicable",
        _quality(critical=(("priority", 80.0), ("volume", None))),
    )
    low_applicable = _candidate(
        "low-applicable",
        _quality(critical=(("priority", 80.0), ("volume", 1.0))),
    )

    assert select_best_program((low_applicable, not_applicable)).selected is not_applicable


def test_quality_mapping_normalizes_burdens_and_preserves_not_applicable_values() -> None:
    quality = ProgramQualityView.from_mapping(
        {
            "critical_dimensions": {"volume": None, "priority": 80},
            "coverage_state": "proven_constrained",
            "coverage_percentage": None,
            "volume_floor": 70,
            "volume_median": 85,
            "explicit_priority_floor": None,
            "body_analysis_priority_floor": 75,
            "recovery_margin": 20,
            "duration_fit": 90,
            "semantic_degradation": 0,
            "warning_burden": {"repairable": 2, "soft": 1},
            "repair_burden": {
                "structural": 1,
                "workload": 2,
                "scheduling": 3,
                "total": 6,
            },
        }
    )

    assert quality.evidence_complete is True
    assert quality.critical_dimensions == (("priority", 80.0), ("volume", None))
    assert quality.coverage_state == "proven_constrained"
    assert quality.repairable_warning_burden == 2
    assert quality.soft_warning_burden == 1
    assert quality.total_repair_burden == 6


def test_missing_selection_evidence_fails_closed() -> None:
    missing_gate = _candidate(
        "missing-gate",
        _quality(critical=(("volume", 100.0),)),
        result=ProgramGenerationResult(program=object(), decision_trace=()),
    )

    decision = select_best_program((missing_gate,))

    assert decision.selected is None
    assert decision.comparisons[0].reason_codes == ("PROGRAM_SELECTION_EVIDENCE_MISSING",)


def test_selection_critical_unknown_constraint_excludes_candidate() -> None:
    unknown_constraint = _candidate(
        "unknown-constraint",
        _quality(critical=(("volume", 100.0),)),
        result=ProgramGenerationResult(
            program=object(),
            decision_trace=(
                {
                    "stage": "final_quality_gate",
                    "status": "accepted_with_constraints",
                    "reason_codes": (),
                    "constraint_reason_codes": ("UNKNOWN_SELECTION_CONSTRAINT",),
                },
            ),
        ),
    )
    known_valid = _candidate("known-valid", _quality(critical=(("volume", 70.0),)))

    decision = select_best_program((unknown_constraint, known_valid))

    assert decision.selected is known_valid
    assert decision.comparisons[0].reason_codes == ("PROGRAM_SELECTION_UNKNOWN_CONSTRAINT",)


def test_informational_unknown_trace_token_does_not_reject_candidate() -> None:
    candidate = _candidate(
        "informational-token",
        _quality(critical=(("volume", 90.0),)),
        result=ProgramGenerationResult(
            program=object(),
            decision_trace=(
                {
                    "stage": "final_quality_gate",
                    "status": "accepted",
                    "reason_codes": (),
                    "constraint_reason_codes": (),
                },
                {"stage": "observability", "reason_codes": ("UNKNOWN_INFO_TOKEN",)},
            ),
        ),
    )

    decision = select_best_program((candidate,))

    assert decision.selected is candidate
    assert decision.comparisons[0].admitted is True
    assert decision.comparisons[0].diagnostic_codes == (
        "PROGRAM_SELECTION_UNKNOWN_INFORMATIONAL_TRACE",
    )


def test_warning_burden_is_used_only_after_stronger_quality_dimensions_tie() -> None:
    better_quality = _candidate(
        "better-quality-more-warnings",
        _quality(critical=(("volume", 91.0),), repairable_warning_burden=10),
    )
    fewer_warnings = _candidate(
        "fewer-warnings",
        _quality(critical=(("volume", 90.0),), repairable_warning_burden=0),
    )
    tied_quality_more_warnings = _candidate(
        "tied-quality-more-warnings",
        _quality(critical=(("volume", 90.0),), repairable_warning_burden=2),
    )

    assert select_best_program((fewer_warnings, better_quality)).selected is better_quality
    assert (
        select_best_program((tied_quality_more_warnings, fewer_warnings)).selected is fewer_warnings
    )


def test_repair_burden_is_used_only_after_warning_burden_ties() -> None:
    fewer_warnings = _candidate(
        "more-repairs-fewer-warnings",
        _quality(critical=(("volume", 90.0),), repairable_warning_burden=0, total_repair_burden=5),
    )
    fewer_repairs = _candidate(
        "fewer-repairs",
        _quality(critical=(("volume", 90.0),), repairable_warning_burden=0, total_repair_burden=1),
    )

    assert select_best_program((fewer_warnings, fewer_repairs)).selected is fewer_repairs


def test_actual_substitutions_are_used_after_repair_burden_ties() -> None:
    more_substitutions = _candidate(
        "more-substitutions",
        _quality(critical=(("volume", 90.0),)),
    )
    more_substitutions = replace(more_substitutions, actual_substitution_count=3)
    fewer_substitutions = replace(
        more_substitutions, identifier="fewer-substitutions", actual_substitution_count=0
    )

    assert (
        select_best_program((more_substitutions, fewer_substitutions)).selected
        is fewer_substitutions
    )


def test_duration_is_a_soft_late_tie_break() -> None:
    better_quality_shorter = _candidate(
        "better-quality-shorter",
        _quality(critical=(("volume", 91.0),), duration_fit=20.0),
    )
    worse_quality_longer = _candidate(
        "worse-quality-longer",
        _quality(critical=(("volume", 90.0),), duration_fit=100.0),
    )
    tied_quality_longer = _candidate(
        "tied-quality-longer",
        _quality(critical=(("volume", 90.0),), duration_fit=100.0),
    )
    tied_quality_shorter = _candidate(
        "tied-quality-shorter",
        _quality(critical=(("volume", 90.0),), duration_fit=20.0),
    )

    assert (
        select_best_program((worse_quality_longer, better_quality_shorter)).selected
        is better_quality_shorter
    )
    assert (
        select_best_program((tied_quality_shorter, tied_quality_longer)).selected
        is tied_quality_longer
    )


def test_template_preference_applies_only_in_a_true_quality_tie() -> None:
    canonical_better = _candidate(
        "canonical-better",
        _quality(critical=(("volume", 91.0),)),
        source=CandidateSource.CANONICAL_SPLIT,
    )
    template_worse = _candidate(
        "curated-template-worse",
        _quality(critical=(("volume", 90.0),)),
        source=CandidateSource.TEMPLATE,
    )
    canonical_tie = _candidate(
        "canonical-tie",
        _quality(critical=(("volume", 90.0),)),
        source=CandidateSource.CANONICAL_SPLIT,
    )
    template_tie = _candidate(
        "curated-template-tie",
        _quality(critical=(("volume", 90.0),)),
        source=CandidateSource.TEMPLATE,
    )

    assert select_best_program((template_worse, canonical_better)).selected is canonical_better
    assert select_best_program((canonical_tie, template_tie)).selected is template_tie


def test_selection_is_independent_of_input_order_and_uses_stable_identifier_tie_break() -> None:
    candidates = (
        _candidate("candidate-c", _quality(critical=(("volume", 90.0),)), rank=2),
        _candidate("candidate-b", _quality(critical=(("volume", 90.0),)), rank=1),
        _candidate("candidate-a", _quality(critical=(("volume", 90.0),)), rank=1),
    )

    first = select_best_program(candidates)
    second = select_best_program(tuple(reversed(candidates)))

    assert first.selected is not None
    assert second.selected is not None
    assert first.selected.identifier == "candidate-a"
    assert second.selected.identifier == "candidate-a"
