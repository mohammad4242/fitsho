from collections.abc import Mapping, Sequence
from statistics import median

from app.workouts.program_engine.constraint_classification import (
    ConstraintClass,
    classify_constraint,
)
from app.workouts.program_engine.duration_policy import (
    calculate_main_training_minutes,
    get_session_duration_policy,
)
from app.workouts.program_engine.program_selection import COACH_QUALITY_V2_SCHEMA_VERSION
from app.workouts.program_engine.recovery import (
    assess_recovery_spacing,
    recovery_quality_evidence,
)
from app.workouts.program_engine.repair_observability import (
    RepairObservability,
    collect_repair_observability,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ProgramGenerationRequest,
    ValidationReport,
    WorkoutProgram,
)


def build_coach_quality_metrics(
    program: WorkoutProgram,
    request: ProgramGenerationRequest,
    report: ValidationReport,
    ruleset: ProgramRuleset,
) -> dict[str, object]:
    priority_metrics = _mapping(program.aggregate_metrics.get("priority_metrics"))
    explicit = frozenset(muscle.value for muscle in request.priority_muscles)
    body_analysis = frozenset(str(key) for key in priority_metrics) - explicit
    duration_fit = _duration_fit(program, request, report, ruleset)
    recovery_evidence = recovery_quality_evidence(
        assess_recovery_spacing(program.weekly_schedule, ruleset)
    )
    recovery_margin = _number(recovery_evidence.get("recovery_margin"))
    coverage_quality = _coverage_quality(program.aggregate_metrics)
    repair_observation = collect_repair_observability(program.decision_trace)
    selection_quality = _build_selection_quality(
        priority_metrics=priority_metrics,
        explicit=explicit,
        body_analysis=body_analysis,
        aggregate_metrics=program.aggregate_metrics,
        coverage_quality=coverage_quality,
        recovery_margin=recovery_margin,
        duration_fit=duration_fit,
        report=report,
        trace=program.decision_trace,
        repair_observation=repair_observation,
    )
    return {
        "schema_version": COACH_QUALITY_V2_SCHEMA_VERSION,
        "template_preservation": _template_preservation(program.decision_trace),
        "priority_target_satisfaction": _target_satisfaction(priority_metrics, explicit),
        "body_analysis_target_satisfaction": _target_satisfaction(priority_metrics, body_analysis),
        "volume_fit": _volume_fit(program.aggregate_metrics),
        "duration_fit": duration_fit,
        "coverage_fit": metric_status(program.aggregate_metrics.get("weekly_coverage")),
        "recovery_fit": _ratio(recovery_margin, 100.0),
        "substitution_count": repair_observation.actual_substitution_count,
        "constraint_count": len(report.warnings),
        "hard_validation_status": report.status.value,
        "selection_quality": selection_quality,
    }


def _template_preservation(trace: Sequence[Mapping[str, object]]) -> dict[str, object]:
    entry = next((item for item in trace if item.get("stage") == "template_adaptation"), None)
    if entry is None:
        return _ratio(0.0, 0.0)
    return _ratio(
        _number(entry.get("retained_template_slot_count")),
        _number(entry.get("template_slot_count")),
    )


def _target_satisfaction(
    metrics: Mapping[str, object], muscles: frozenset[str]
) -> dict[str, object]:
    satisfied = 0.0
    total = 0.0
    for muscle in sorted(muscles):
        metric = _mapping(metrics.get(muscle))
        target = _number(metric.get("effective_target_sets"))
        actual = _number(metric.get("effective_sets"))
        if target <= 0:
            continue
        total += target
        satisfied += min(max(actual, 0.0), target)
    return _ratio(satisfied, total)


def _priority_quality_floor(metrics: Mapping[str, object], muscles: frozenset[str]) -> float | None:
    """Return the weakest applicable direct/effective/frequency ratio."""

    ratios: list[float] = []
    for muscle in sorted(muscles):
        metric = _mapping(metrics.get(muscle))
        dimensions = (
            ("target_sets", "direct_sets"),
            ("effective_target_sets", "effective_sets"),
            ("preferred_frequency", "session_frequency"),
        )
        for target_key, actual_key in dimensions:
            target = _number(metric.get(target_key))
            if target <= 0:
                continue
            actual = max(_number(metric.get(actual_key)), 0.0)
            ratios.append(min(actual / target * 100.0, 100.0))
    return round(min(ratios), 1) if ratios else None


def _volume_fit(metrics: Mapping[str, object]) -> dict[str, object]:
    ranges = _mapping(metrics.get("volume_ranges_by_muscle"))
    satisfied = 0.0
    total = 0.0
    for muscle in sorted(str(key) for key in ranges):
        values = _mapping(ranges.get(muscle))
        actual = _number(
            values.get(
                "actual_constraint_volume",
                values.get("actual_effective_volume"),
            )
        )
        minimum = _number(values.get("acceptable_minimum"))
        maximum = _number(values.get("acceptable_maximum"))
        total += 1
        if minimum <= actual <= maximum:
            satisfied += 1
    return _ratio(satisfied, total)


def _coverage_quality(metrics: Mapping[str, object]) -> dict[str, object]:
    weekly_coverage = _mapping(metrics.get("weekly_coverage"))
    coverage_status = weekly_coverage.get("status")
    if isinstance(coverage_status, str) and coverage_status != "not_applicable":
        required = _string_values(weekly_coverage.get("major_muscles"))
        covered_muscles = set(_string_values(weekly_coverage.get("covered_major_muscles")))
        if required:
            percentage = round(
                len(covered_muscles.intersection(required)) / len(required) * 100.0,
                1,
            )
        else:
            percentage = 100.0 if coverage_status == "satisfied" else 0.0
        return {
            "coverage_state": (
                "satisfied" if coverage_status == "satisfied" else "proven_constrained"
            ),
            "coverage_percentage": percentage,
        }

    ranges = _mapping(metrics.get("volume_ranges_by_muscle"))
    required_ranges: list[Mapping[str, object]] = []
    for muscle in sorted(str(key) for key in ranges):
        values = _mapping(ranges.get(muscle))
        minimum = _number(values.get("acceptable_minimum"))
        required_flag = values.get("minimum_coverage_required")
        if required_flag is True or (required_flag is not False and minimum > 0):
            required_ranges.append(values)
    if not required_ranges:
        return {"coverage_state": "satisfied", "coverage_percentage": None}
    covered_count = sum(
        _number(
            values.get(
                "actual_constraint_volume",
                values.get("actual_effective_volume"),
            )
        )
        >= _number(values.get("acceptable_minimum"))
        for values in required_ranges
    )
    return {
        "coverage_state": (
            "satisfied" if covered_count == len(required_ranges) else "proven_constrained"
        ),
        "coverage_percentage": round(covered_count / len(required_ranges) * 100.0, 1),
    }


def _build_selection_quality(
    *,
    priority_metrics: Mapping[str, object],
    explicit: frozenset[str],
    body_analysis: frozenset[str],
    aggregate_metrics: Mapping[str, object],
    coverage_quality: Mapping[str, object],
    recovery_margin: float,
    duration_fit: Mapping[str, object],
    report: ValidationReport,
    trace: Sequence[Mapping[str, object]],
    repair_observation: RepairObservability,
) -> dict[str, object]:
    explicit_floor = _priority_quality_floor(priority_metrics, explicit)
    body_floor = _priority_quality_floor(priority_metrics, body_analysis)
    volume_scores = _volume_quality_scores(aggregate_metrics)
    volume_floor = round(min(volume_scores), 1) if volume_scores else None
    volume_median = round(float(median(volume_scores)), 1) if volume_scores else None
    duration_percentage = _optional_number(duration_fit.get("percentage"))
    observation = repair_observation
    warning_burden = _warning_burden(report.warnings)
    repair_burden = {
        "structural": observation.structural_repair_burden,
        "workload": observation.workload_repair_burden,
        "scheduling": observation.scheduling_repair_burden,
        "total": observation.total_repair_burden,
    }
    return {
        "schema_version": COACH_QUALITY_V2_SCHEMA_VERSION,
        "critical_dimensions": {
            "explicit_priority": explicit_floor,
            "body_analysis_priority": body_floor,
            "volume": volume_floor,
        },
        "coverage_state": coverage_quality.get("coverage_state", "satisfied"),
        "coverage_percentage": coverage_quality.get("coverage_percentage"),
        "volume_floor": volume_floor,
        "volume_median": volume_median,
        "explicit_priority_floor": explicit_floor,
        "body_analysis_priority_floor": body_floor,
        "recovery_margin": round(recovery_margin, 1),
        "duration_fit": duration_percentage,
        "semantic_degradation": _semantic_degradation(trace),
        "warning_burden": warning_burden,
        "repair_burden": repair_burden,
        "actual_substitution_count": observation.actual_substitution_count,
    }


def _volume_quality_scores(metrics: Mapping[str, object]) -> tuple[float, ...]:
    ranges = _mapping(metrics.get("volume_ranges_by_muscle"))
    scores: list[float] = []
    for muscle in sorted(str(key) for key in ranges):
        values = _mapping(ranges.get(muscle))
        minimum = _number(values.get("acceptable_minimum"))
        maximum = _number(values.get("acceptable_maximum"))
        if minimum <= 0 or maximum <= 0:
            continue
        actual = max(
            0.0,
            _number(
                values.get(
                    "actual_constraint_volume",
                    values.get("actual_effective_volume"),
                )
            ),
        )
        if actual < minimum:
            score = actual / minimum * 100.0
        elif actual <= maximum:
            score = 100.0
        else:
            score = maximum / actual * 100.0
        scores.append(min(max(score, 0.0), 100.0))
    return tuple(scores)


def _warning_burden(warnings: Sequence[str]) -> dict[str, int]:
    repairable = 0
    soft = 0
    for reason in warnings:
        classification = classify_constraint(reason)
        if classification is ConstraintClass.REPAIRABLE:
            repairable += 1
        elif classification is ConstraintClass.SOFT:
            soft += 1
    return {"repairable": repairable, "soft": soft}


def _semantic_degradation(trace: Sequence[Mapping[str, object]]) -> int:
    codes = frozenset(
        {
            "SEMANTIC_SLOT_MISMATCH_SELECTED",
            "SUBSTITUTION_ROLE_PRESERVED_FOCUS_DEGRADED",
        }
    )
    return sum(
        code in codes
        for entry in trace
        for field in ("reason_codes", "reasons")
        for code in _string_values(entry.get(field))
    )


def _duration_fit(
    program: WorkoutProgram,
    request: ProgramGenerationRequest,
    report: ValidationReport,
    ruleset: ProgramRuleset,
) -> dict[str, object]:
    policy = get_session_duration_policy(request.session_duration_minutes)
    satisfied = 0.0
    for day in program.weekly_schedule:
        # This remains a preferred-range quality metric; a lower-bound miss is
        # intentionally not a generation failure.
        if policy.within_preferred_range(calculate_main_training_minutes(day)):
            satisfied += 1
    return _ratio(satisfied, float(len(program.weekly_schedule)))


def _substitution_count(trace: Sequence[Mapping[str, object]]) -> int:
    return collect_repair_observability(trace).actual_substitution_count


def _ratio(satisfied: float, total: float) -> dict[str, object]:
    return {
        "satisfied": round(satisfied, 1),
        "total": round(total, 1),
        "percentage": round(satisfied / total * 100, 1) if total > 0 else None,
    }


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def metric_status(value: object) -> str:
    status = _mapping(value).get("status")
    return status if isinstance(status, str) else "not_applicable"


def _number(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _optional_number(value: object) -> float | None:
    if value is None:
        return None
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _string_values(value: object) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list, set, frozenset)):
        return ()
    return tuple(item for item in value if isinstance(item, str))
