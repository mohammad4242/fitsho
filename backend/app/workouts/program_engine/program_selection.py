from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.workouts.program_engine.constraint_classification import (
    ConstraintClass,
    classify_constraint,
)
from app.workouts.program_engine.schemas import ProgramGenerationResult


class CandidateSource(StrEnum):
    TEMPLATE = "template"
    CANONICAL_SPLIT = "canonical_split"
    DYNAMIC_FALLBACK = "dynamic_fallback"


class CoverageState(StrEnum):
    SATISFIED = "satisfied"
    PROVEN_CONSTRAINED = "proven_constrained"


COACH_QUALITY_V2_SCHEMA_VERSION = "coach_quality_v2"
_ACCEPTED_GATE_STATUSES = frozenset({"accepted", "accepted_with_constraints"})


@dataclass(frozen=True, slots=True)
class ProgramQualityView:
    critical_dimensions: tuple[tuple[str, float | None], ...] = ()
    coverage_state: str = "satisfied"
    explicit_priority_floor: float | None = None
    body_analysis_priority_floor: float | None = None
    volume_floor: float | None = None
    volume_median: float | None = None
    coverage_percentage: float | None = None
    recovery_margin: float | None = None
    semantic_degradation: float | None = None
    repairable_warning_burden: int = 0
    soft_warning_burden: int = 0
    structural_repair_burden: int = 0
    workload_repair_burden: int = 0
    scheduling_repair_burden: int = 0
    total_repair_burden: int = 0
    actual_substitution_count: int = 0
    duration_fit: float | None = None
    evidence_complete: bool = True
    schema_version: str = COACH_QUALITY_V2_SCHEMA_VERSION

    @classmethod
    def from_selection_quality(
        cls,
        selection_quality: Mapping[str, object],
    ) -> ProgramQualityView:
        """Normalize the internal v2 selection evidence without inventing zeros."""

        required_fields = (
            "critical_dimensions",
            "coverage_state",
            "coverage_percentage",
            "volume_floor",
            "volume_median",
            "explicit_priority_floor",
            "body_analysis_priority_floor",
            "recovery_margin",
            "duration_fit",
            "semantic_degradation",
        )
        dimensions = _normalize_critical_dimensions(selection_quality.get("critical_dimensions"))
        warning_burden = _mapping(selection_quality.get("warning_burden"))
        repair_burden = _mapping(selection_quality.get("repair_burden"))
        schema_version = selection_quality.get("schema_version", COACH_QUALITY_V2_SCHEMA_VERSION)
        return cls(
            critical_dimensions=dimensions,
            coverage_state=str(
                selection_quality.get("coverage_state", CoverageState.SATISFIED.value)
            ),
            explicit_priority_floor=_optional_number(
                selection_quality.get("explicit_priority_floor")
            ),
            body_analysis_priority_floor=_optional_number(
                selection_quality.get("body_analysis_priority_floor")
            ),
            volume_floor=_optional_number(selection_quality.get("volume_floor")),
            volume_median=_optional_number(selection_quality.get("volume_median")),
            coverage_percentage=_optional_number(selection_quality.get("coverage_percentage")),
            recovery_margin=_optional_number(selection_quality.get("recovery_margin")),
            semantic_degradation=_optional_number(selection_quality.get("semantic_degradation")),
            repairable_warning_burden=_integer(
                warning_burden.get(
                    "repairable",
                    selection_quality.get("repairable_warning_burden", 0),
                )
            ),
            soft_warning_burden=_integer(
                warning_burden.get("soft", selection_quality.get("soft_warning_burden", 0))
            ),
            structural_repair_burden=_integer(
                repair_burden.get(
                    "structural",
                    selection_quality.get("structural_repair_burden", 0),
                )
            ),
            workload_repair_burden=_integer(
                repair_burden.get("workload", selection_quality.get("workload_repair_burden", 0))
            ),
            scheduling_repair_burden=_integer(
                repair_burden.get(
                    "scheduling",
                    selection_quality.get("scheduling_repair_burden", 0),
                )
            ),
            total_repair_burden=_integer(
                repair_burden.get(
                    "total",
                    selection_quality.get("total_repair_burden", 0),
                )
            ),
            actual_substitution_count=_integer(
                selection_quality.get("actual_substitution_count", 0)
            ),
            duration_fit=_optional_number(selection_quality.get("duration_fit")),
            evidence_complete=all(field in selection_quality for field in required_fields)
            and isinstance(schema_version, str),
            schema_version=str(schema_version),
        )

    @classmethod
    def from_mapping(cls, selection_quality: Mapping[str, object]) -> ProgramQualityView:
        """Compatibility alias for callers that hold a generic quality mapping."""

        return cls.from_selection_quality(selection_quality)


@dataclass(frozen=True, slots=True)
class ProgramCandidate:
    source: CandidateSource
    identifier: str
    preconstruction_rank: int
    preconstruction_score: float | None
    result: ProgramGenerationResult
    quality: ProgramQualityView | None = None
    actual_substitution_count: int = 0
    source_metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CandidateComparison:
    candidate: ProgramCandidate
    admitted: bool
    reason_codes: tuple[str, ...]
    quality_view: ProgramQualityView | None = None
    diagnostic_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProgramSelectionDecision:
    selected: ProgramCandidate | None
    comparisons: tuple[CandidateComparison, ...]
    admitted_candidates: tuple[ProgramCandidate, ...] = ()
    reason_codes: tuple[str, ...] = ()
    diagnostic_codes: tuple[str, ...] = ()


def select_best_program(
    candidates: Sequence[ProgramCandidate],
) -> ProgramSelectionDecision:
    comparisons = tuple(_compare_admission(candidate) for candidate in candidates)
    admitted = tuple(item.candidate for item in comparisons if item.admitted)
    selected: ProgramCandidate | None = None
    for candidate in admitted:
        if selected is None or _compare_preference(candidate, selected) > 0:
            selected = candidate
    return ProgramSelectionDecision(
        selected=selected,
        comparisons=comparisons,
        admitted_candidates=admitted,
        reason_codes=tuple(
            dict.fromkeys(
                reason for comparison in comparisons for reason in comparison.reason_codes
            )
        ),
        diagnostic_codes=tuple(
            dict.fromkeys(
                diagnostic
                for comparison in comparisons
                for diagnostic in comparison.diagnostic_codes
            )
        ),
    )


def _compare_admission(candidate: ProgramCandidate) -> CandidateComparison:
    reasons: list[str] = []
    diagnostics: list[str] = []
    result = candidate.result
    if not result.is_success or result.program is None:
        reasons.append("PROGRAM_SELECTION_RESULT_INVALID")

    trace = _candidate_trace(result)
    final_gate = next(
        (entry for entry in reversed(trace) if entry.get("stage") == "final_quality_gate"),
        None,
    )
    if final_gate is None:
        reasons.append("PROGRAM_SELECTION_EVIDENCE_MISSING")
    else:
        status = final_gate.get("status")
        if status not in _ACCEPTED_GATE_STATUSES:
            reasons.append("PROGRAM_SELECTION_HARD_CONSTRAINT")
        for code in _string_values(final_gate.get("reason_codes")):
            reasons.append(_admission_reason_for_constraint(code, repair_exhausted=True))
        for code in _string_values(final_gate.get("constraint_reason_codes")):
            constraint_class = classify_constraint(code, repair_exhausted=True)
            if constraint_class is None:
                reasons.append("PROGRAM_SELECTION_UNKNOWN_CONSTRAINT")
            elif constraint_class is ConstraintClass.HARD:
                reasons.append("PROGRAM_SELECTION_HARD_CONSTRAINT")

    for entry in trace:
        if entry.get("stage") in {"final_quality_gate", "validation", "coach_quality"}:
            continue
        for field_name in ("reason_codes", "reasons"):
            for code in _string_values(entry.get(field_name)):
                if classify_constraint(code) is None:
                    diagnostics.append("PROGRAM_SELECTION_UNKNOWN_INFORMATIONAL_TRACE")

    validation_report = getattr(result.program, "validation_report", None)
    for code in _string_values(getattr(validation_report, "errors", ())):
        reasons.append(_admission_reason_for_constraint(code, repair_exhausted=True))

    quality = candidate.quality
    if (
        quality is None
        or quality.schema_version != COACH_QUALITY_V2_SCHEMA_VERSION
        or not quality.evidence_complete
    ):
        reasons.append("PROGRAM_SELECTION_EVIDENCE_MISSING")

    unique_reasons = tuple(dict.fromkeys(reasons))
    return CandidateComparison(
        candidate=candidate,
        admitted=not unique_reasons,
        reason_codes=unique_reasons,
        quality_view=quality,
        diagnostic_codes=tuple(dict.fromkeys(diagnostics)),
    )


def _admission_reason_for_constraint(code: str, *, repair_exhausted: bool) -> str:
    constraint_class = classify_constraint(code, repair_exhausted=repair_exhausted)
    return (
        "PROGRAM_SELECTION_UNKNOWN_CONSTRAINT"
        if constraint_class is None
        else "PROGRAM_SELECTION_HARD_CONSTRAINT"
    )


def _candidate_trace(result: ProgramGenerationResult) -> tuple[Mapping[str, object], ...]:
    program_trace = getattr(result.program, "decision_trace", ())
    trace = (
        program_trace
        if isinstance(program_trace, (tuple, list)) and program_trace
        else result.decision_trace
    )
    return tuple(item for item in trace if isinstance(item, Mapping))


def _compare_preference(left: ProgramCandidate, right: ProgramCandidate) -> int:
    quality_comparison = _compare_quality(left.quality, right.quality)
    if quality_comparison:
        return quality_comparison

    comparison = _compare_low(
        left.actual_substitution_count,
        right.actual_substitution_count,
    )
    if comparison:
        return comparison

    comparison = _compare_high(
        left.quality.duration_fit if left.quality else None,
        right.quality.duration_fit if right.quality else None,
    )
    if comparison:
        return comparison

    if left.source is CandidateSource.TEMPLATE or right.source is CandidateSource.TEMPLATE:
        if left.source is CandidateSource.TEMPLATE and right.source is not CandidateSource.TEMPLATE:
            return 1
        if right.source is CandidateSource.TEMPLATE and left.source is not CandidateSource.TEMPLATE:
            return -1

    if left.source is right.source and left.preconstruction_rank != right.preconstruction_rank:
        return 1 if left.preconstruction_rank < right.preconstruction_rank else -1

    left_identity = (left.identifier, left.source.value)
    right_identity = (right.identifier, right.source.value)
    if left_identity == right_identity:
        return 0
    return 1 if left_identity < right_identity else -1


def _compare_quality(
    left: ProgramQualityView | None,
    right: ProgramQualityView | None,
) -> int:
    if left is None or right is None:
        return 0
    comparison = _compare_high(
        _coverage_rank(left.coverage_state), _coverage_rank(right.coverage_state)
    )
    if comparison:
        return comparison

    comparison = _compare_high(_critical_floor(left), _critical_floor(right))
    if comparison:
        return comparison
    comparison = _compare_sequence_high(_critical_vector(left), _critical_vector(right))
    if comparison:
        return comparison

    for left_value, right_value in (
        (left.explicit_priority_floor, right.explicit_priority_floor),
        (left.body_analysis_priority_floor, right.body_analysis_priority_floor),
        (left.volume_floor, right.volume_floor),
        (left.volume_median, right.volume_median),
        (left.coverage_percentage, right.coverage_percentage),
        (left.recovery_margin, right.recovery_margin),
    ):
        comparison = _compare_high(left_value, right_value)
        if comparison:
            return comparison

    comparison = _compare_low(left.semantic_degradation, right.semantic_degradation)
    if comparison:
        return comparison

    for left_value, right_value in (
        (left.repairable_warning_burden, right.repairable_warning_burden),
        (left.soft_warning_burden, right.soft_warning_burden),
        (left.structural_repair_burden, right.structural_repair_burden),
        (left.workload_repair_burden, right.workload_repair_burden),
        (left.scheduling_repair_burden, right.scheduling_repair_burden),
        (left.total_repair_burden, right.total_repair_burden),
    ):
        comparison = _compare_low(left_value, right_value)
        if comparison:
            return comparison

    return 0


def _coverage_rank(value: str) -> int:
    return 1 if value == CoverageState.SATISFIED.value else 0


def _critical_floor(quality: ProgramQualityView) -> float | None:
    values = [value for _, value in quality.critical_dimensions if value is not None]
    return min(values) if values else None


def _critical_vector(quality: ProgramQualityView) -> tuple[float, ...]:
    return tuple(sorted(value for _, value in quality.critical_dimensions if value is not None))


def _compare_sequence_high(left: Sequence[float], right: Sequence[float]) -> int:
    for left_value, right_value in zip(left, right, strict=False):
        comparison = _compare_high(left_value, right_value)
        if comparison:
            return comparison
    return 0


def _compare_high(left: float | int | None, right: float | int | None) -> int:
    if left is None or right is None:
        return 0
    return (left > right) - (left < right)


def _compare_low(left: float | int | None, right: float | int | None) -> int:
    comparison = _compare_high(left, right)
    return -comparison


def _normalize_critical_dimensions(value: object) -> tuple[tuple[str, float | None], ...]:
    if not isinstance(value, Mapping):
        return ()
    return tuple(
        (str(name), _optional_number(item))
        for name, item in sorted(value.items(), key=lambda pair: str(pair[0]))
    )


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _string_values(value: object) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list, set, frozenset)):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _optional_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _integer(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return 0
