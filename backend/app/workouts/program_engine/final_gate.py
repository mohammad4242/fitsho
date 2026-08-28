from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.workouts.program_engine.enums import SplitType
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ProgramGenerationRequest,
    ValidationReport,
    WorkoutDay,
    WorkoutProgram,
)
from app.workouts.program_engine.split_selector import (
    LOWER_REGION_MUSCLES,
    UPPER_REGION_MUSCLES,
    classify_template_region,
)

FINAL_GATE_SCHEMA_VERSION = "final_quality_gate_v1"
_FULL_BODY_SPLITS = frozenset(item for item in SplitType if item.value.startswith("full_body"))
_DURATION_CODES = frozenset(
    "SESSION_EXERCISE_COUNT_OUT_OF_RANGE SESSION_DURATION_UNDER_TARGET "
    "SESSION_DURATION_TARGET_UNSATISFIED SESSION_DURATION_EXCEEDED "
    "SESSION_DURATION_OVER_TARGET".split()
)
_DURATION_CONSTRAINTS = frozenset(
    "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS "
    "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE "
    "VOLUME_REDUCED_FOR_DURATION_CAPACITY DURATION_PLANNED_REDUCED_EXERCISE_COUNT".split()
)
_DURATION_OUTCOME_CODES = frozenset(_DURATION_CODES - {"SESSION_EXERCISE_COUNT_OUT_OF_RANGE"})


class FinalGateStatus(StrEnum):
    ACCEPTED = "accepted"
    ACCEPTED_WITH_CONSTRAINTS = "accepted_with_constraints"
    REJECTED = "rejected"


@dataclass(frozen=True)
class FinalGateResult:
    status: FinalGateStatus
    reason_codes: tuple[str, ...]
    constraint_reason_codes: tuple[str, ...]
    metrics: dict[str, object]
    validation_report: ValidationReport
    schema_version: str = FINAL_GATE_SCHEMA_VERSION

    @property
    def is_accepted(self) -> bool:
        return self.status is not FinalGateStatus.REJECTED

    def decision_trace(self) -> dict[str, object]:
        return {
            "stage": "final_quality_gate",
            "schema_version": self.schema_version,
            "status": self.status.value,
            "reason_codes": self.reason_codes,
            "constraint_reason_codes": self.constraint_reason_codes,
            "metrics": self.metrics,
            "checks": self.metrics["checks"],
        }


def evaluate_final_program(
    program: WorkoutProgram,
    request: ProgramGenerationRequest,
    report: ValidationReport,
    ruleset: ProgramRuleset,
) -> FinalGateResult:
    """Check final authoritative metrics and validation output after all repairs."""
    reasons = list(report.errors)
    constraints = [code for code in report.warnings if code not in _DURATION_OUTCOME_CODES]
    checks: dict[str, object] = {
        "validation": {
            "status": "rejected" if report.errors else "passed",
            "reason_codes": report.errors,
            "warning_codes": report.warnings,
        },
        "duration": {"status": "passed", "reason_codes": ()},
        "coverage": {"status": "not_applicable", "reason_codes": ()},
        "distribution": {"status": "missing", "reason_codes": ()},
        "recovery": {"status": "passed", "reason_codes": ()},
        "safety": {"status": "passed", "reason_codes": ()},
        "day_count": {"status": "passed", "reason_codes": ()},
        "upper_priority_topology": {"status": "not_applicable", "reason_codes": ()},
    }

    duration_codes = tuple(
        code for code in (*report.errors, *report.warnings) if code in _DURATION_CODES
    )
    duration_evidence = _trace_reason_codes(program).intersection(_DURATION_CONSTRAINTS)
    if duration_codes:
        checks["duration"] = {
            "status": "constrained" if duration_evidence and not report.errors else "rejected",
            "reason_codes": tuple(dict.fromkeys((*duration_evidence, *duration_codes))),
        }
        if report.errors or not duration_evidence:
            reasons.extend(duration_codes)
            if not duration_evidence:
                reasons.append("SESSION_DURATION_CONSTRAINT_UNEXPLAINED")
        else:
            constraints.extend(duration_evidence)

    coverage = _mapping(program.aggregate_metrics.get("weekly_coverage"))
    if _full_body_claim(program):
        if not coverage:
            reasons.append("WEEKLY_COVERAGE_EVIDENCE_MISSING")
            checks["coverage"] = {"status": "rejected", "reason_codes": reasons[-1:]}
        else:
            coverage_status = coverage.get("status")
            coverage_reasons = _string_values(coverage.get("reason_codes"))
            checks["coverage"] = {"status": coverage_status, "reason_codes": coverage_reasons}
            if coverage_status == "unsatisfied":
                missing_muscles = set(_string_values(coverage.get("missing_major_muscles")))
                unavailable_muscles = set(
                    _string_values(program.aggregate_metrics.get("unavailable_muscle_coverage"))
                )
                if coverage_reasons and missing_muscles and missing_muscles <= unavailable_muscles:
                    constraints.extend((*coverage_reasons, "FULL_BODY_COVERAGE_CONSTRAINED"))
                else:
                    reasons.extend((*coverage_reasons, "FULL_BODY_COVERAGE_UNSATISFIED"))
            elif coverage_status == "constrained":
                if _coverage_constraint_is_proven(coverage):
                    constraints.extend(coverage_reasons)
                else:
                    reasons.append("FULL_BODY_COVERAGE_CONSTRAINT_UNEXPLAINED")
            elif coverage_status != "satisfied":
                reasons.append("WEEKLY_COVERAGE_STATUS_UNEXPLAINED")

    distribution = _mapping(program.aggregate_metrics.get("weekly_distribution"))
    distribution_reasons = _string_values(distribution.get("reason_codes"))
    checks["distribution"] = {
        "status": distribution.get("status", "missing"),
        "reason_codes": distribution_reasons,
    }
    actual_counts = tuple(len(day.exercises) for day in program.weekly_schedule)
    after_counts = _int_tuple(distribution.get("after_exercise_counts"))
    if not distribution:
        reasons.append("WEEKLY_DISTRIBUTION_EVIDENCE_MISSING")
    elif not after_counts:
        reasons.append("WEEKLY_DISTRIBUTION_EVIDENCE_INCOMPLETE")
    elif after_counts != actual_counts:
        reasons.append("WEEKLY_DISTRIBUTION_METRICS_STALE")
    elif distribution.get("status") == "constrained":
        if distribution_reasons == ("WEEKLY_REDISTRIBUTION_NO_SAFE_IMPROVING_MOVE",):
            constraints.extend(distribution_reasons)
        else:
            reasons.append("WEEKLY_DISTRIBUTION_CONSTRAINT_UNEXPLAINED")
    elif distribution.get("status") == "unsatisfied":
        reasons.append("WEEKLY_DISTRIBUTION_UNSATISFIED")
    elif distribution.get("status") == "applied":
        if "WEEKLY_REDISTRIBUTION_APPLIED" not in distribution_reasons:
            reasons.append("WEEKLY_DISTRIBUTION_STATUS_UNEXPLAINED")
    elif distribution.get("status") == "not_needed":
        if "WEEKLY_REDISTRIBUTION_ALREADY_BALANCED" not in distribution_reasons:
            reasons.append("WEEKLY_DISTRIBUTION_STATUS_UNEXPLAINED")
    else:
        reasons.append("WEEKLY_DISTRIBUTION_STATUS_UNEXPLAINED")

    expected_days = min(request.available_training_days, ruleset.max_resistance_days)
    if (
        len(program.weekly_schedule) != expected_days
        or len(program.split.day_focuses) != expected_days
    ):
        reasons.append("REQUESTED_TRAINING_DAYS_UNSATISFIED")
        checks["day_count"] = {"status": "rejected"}
    if "RECOVERY_SPACING_INVALID" in report.errors:
        reasons.append("RECOVERY_SPACING_INVALID")
        checks["recovery"] = {
            "status": "rejected",
            "reason_codes": ("RECOVERY_SPACING_INVALID",),
        }
    safety_errors = tuple(
        code
        for code in report.errors
        if code
        in {
            "SAFETY_STATUS_DISALLOWS_GENERATION",
            "BLOCKED_CAUTION_TAG_SELECTED",
            "UNAVAILABLE_EQUIPMENT_SELECTED",
        }
    )
    if safety_errors:
        reasons.extend(safety_errors)
        checks["safety"] = {"status": "rejected", "reason_codes": safety_errors}

    topology_status, topology_reasons = _upper_priority_topology(program, request)
    checks["upper_priority_topology"] = {
        "status": topology_status,
        "reason_codes": topology_reasons,
    }
    reasons.extend(topology_reasons)

    unique_reasons = tuple(dict.fromkeys(reasons))
    unique_constraints = tuple(dict.fromkeys(constraints))
    status = (
        FinalGateStatus.REJECTED
        if unique_reasons
        else FinalGateStatus.ACCEPTED_WITH_CONSTRAINTS
        if unique_constraints
        else FinalGateStatus.ACCEPTED
    )
    metrics: dict[str, object] = {
        "schema_version": FINAL_GATE_SCHEMA_VERSION,
        "status": status.value,
        "reason_codes": unique_reasons,
        "constraint_reason_codes": unique_constraints,
        "checks": checks,
    }
    return FinalGateResult(
        status=status,
        reason_codes=unique_reasons,
        constraint_reason_codes=unique_constraints,
        metrics=metrics,
        validation_report=report,
    )


def _coverage_constraint_is_proven(coverage: Mapping[str, object]) -> bool:
    reasons = set(_string_values(coverage.get("reason_codes"))) - {"FULL_BODY_COVERAGE_CONSTRAINED"}
    if not reasons or not all(
        reason.startswith(("FULL_BODY_COVERAGE_UNAVAILABLE:", "FULL_BODY_PATTERN_UNAVAILABLE:"))
        for reason in reasons
    ):
        return False
    evidence = _mapping(coverage.get("availability_evidence"))
    return any(
        isinstance(value, Mapping) and value.get("unavailable") is True
        for category in ("patterns", "muscles")
        for value in _mapping(evidence.get(category)).values()
    )


def _upper_priority_topology(
    program: WorkoutProgram,
    request: ProgramGenerationRequest,
) -> tuple[str, tuple[str, ...]]:
    priorities = frozenset(request.priority_muscles)
    supported = (
        request.available_training_days == 4
        and program.split.split_type is SplitType.UPPER_LOWER_SPECIALIZATION
        and len(priorities.intersection(UPPER_REGION_MUSCLES)) >= 2
        and not priorities.intersection(LOWER_REGION_MUSCLES)
        and classify_template_region(priorities) == "upper"
    )
    if not supported:
        return "not_applicable", ()
    regions = tuple(_final_session_region(day) for day in program.weekly_schedule)
    if len(regions) == 4 and regions.count("upper") == 3 and regions.count("lower") == 1:
        return "passed", ()
    return "rejected", ("UPPER_PRIORITY_TOPOLOGY_INVALID",)


def _final_session_region(day: WorkoutDay) -> str | None:
    primary_muscles = tuple(
        item.primary_muscle for item in day.exercises if item.primary_muscle is not None
    )
    region = classify_template_region(primary_muscles)
    if region is not None:
        return region
    target_region = classify_template_region(day.template_target_muscles)
    if target_region is None:
        return None
    has_target_evidence = any(
        classify_template_region((muscle,)) == target_region for muscle in primary_muscles
    )
    return target_region if has_target_evidence else None


def _trace_reason_codes(program: WorkoutProgram) -> set[str]:
    return {
        code
        for entry in program.decision_trace
        for key in ("reason_codes", "reasons")
        for code in _string_values(entry.get(key))
    }


def _full_body_claim(program: WorkoutProgram) -> bool:
    return program.split.split_type in _FULL_BODY_SPLITS or any(
        day.focus.startswith("full_body") for day in program.weekly_schedule
    )


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, (tuple, list, set, frozenset)):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _int_tuple(value: object) -> tuple[int, ...]:
    if isinstance(value, (tuple, list)) and all(isinstance(item, int) for item in value):
        return tuple(value)
    return ()
