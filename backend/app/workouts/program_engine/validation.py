from collections import Counter

from app.exercises.enums import MovementPattern, MuscleGroup, PrescriptionMode
from app.workouts.program_engine.duration_policy import get_session_duration_policy
from app.workouts.program_engine.effective_volume import (
    calculate_effective_volume,
    complete_tracked_metrics,
)
from app.workouts.program_engine.enums import SafetyStatus
from app.workouts.program_engine.equipment import effective_required_equipment
from app.workouts.program_engine.recovery import recovery_spacing_is_valid
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.safety import effective_caution_tags
from app.workouts.program_engine.schemas import (
    ProgramGenerationRequest,
    ValidationReport,
    WorkoutProgram,
)


def validate_program(
    program: WorkoutProgram,
    request: ProgramGenerationRequest,
    ruleset: ProgramRuleset,
) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    if program.body_analysis_provenance.get("provisional") is True:
        warnings.append("BODY_ANALYSIS_NOT_FULLY_REVIEWED")
    constraints = request
    patterns: Counter[MovementPattern] = Counter()
    exercise_usage: Counter[object] = Counter()
    direct_sets: Counter[str] = Counter()
    direct_session_frequency: Counter[str] = Counter()
    volume_ranges = program.aggregate_metrics.get("volume_ranges_by_muscle", {})
    priority_muscles = set(request.priority_muscles)
    duration_policy = get_session_duration_policy(request.session_duration_minutes, ruleset)
    if isinstance(volume_ranges, dict):
        priority_muscles.update(
            MuscleGroup(muscle)
            for muscle, values in volume_ranges.items()
            if isinstance(values, dict)
            and values.get("direct_minimum_required") is True
            and muscle in {item.value for item in MuscleGroup}
        )
    weekly_exposures: Counter[MuscleGroup] = Counter()
    for day in program.weekly_schedule:
        weekly_exposures.update(
            {
                item.primary_muscle
                for item in day.exercises
                if item.primary_muscle is not None and item.counts_toward_volume
            }
        )
    for day in program.weekly_schedule:
        if (
            not ruleset.minimum_exercises_per_session
            <= len(day.exercises)
            <= (ruleset.max_exercises_per_session)
        ):
            errors.append("SESSION_EXERCISE_COUNT_OUT_OF_RANGE")
        if day.estimated_duration_minutes < duration_policy.minimum_minutes:
            errors.append("SESSION_DURATION_UNDER_TARGET")
            errors.append("SESSION_DURATION_TARGET_UNSATISFIED")
        if day.estimated_duration_minutes > duration_policy.maximum_minutes:
            errors.append("SESSION_DURATION_EXCEEDED")
            errors.append("SESSION_DURATION_OVER_TARGET")
            errors.append("SESSION_DURATION_TARGET_UNSATISFIED")
        per_session: Counter[str] = Counter()
        for item in day.exercises:
            patterns[item.movement_pattern] += 1
            exercise_usage[item.exercise_id] += 1
            if not item.is_active:
                errors.append("INACTIVE_EXERCISE_SELECTED")
            if not item.is_programmable:
                errors.append("NONPROGRAMMABLE_EXERCISE_SELECTED")
            if item.needs_review:
                errors.append("REVIEW_PENDING_EXERCISE_SELECTED")
            if item.exercise_id in constraints.blocked_exercises:
                errors.append("BLOCKED_EXERCISE_SELECTED")
            if item.movement_pattern in constraints.blocked_movement_patterns:
                errors.append("BLOCKED_MOVEMENT_PATTERN_SELECTED")
            if effective_caution_tags(item).intersection(constraints.blocked_caution_tags):
                errors.append("BLOCKED_CAUTION_TAG_SELECTED")
            if not effective_required_equipment(item.equipment, item.movement_pattern).issubset(
                constraints.available_equipment
            ):
                errors.append("UNAVAILABLE_EQUIPMENT_SELECTED")
            if item.sets < 1:
                errors.append("INVALID_EXERCISE_PRESCRIPTION")
            if (
                item.primary_muscle is not None
                and item.sets
                > ruleset.max_working_sets_for_exercise(
                    training_status=program.training_status,
                    goal=request.primary_goal,
                    exercise_type=item.exercise_type,
                    is_priority=item.primary_muscle in priority_muscles,
                    weekly_exposure_count=weekly_exposures[item.primary_muscle],
                )
            ):
                errors.append("PER_EXERCISE_SET_CAP_EXCEEDED")
            if item.prescription_mode is PrescriptionMode.REPS:
                if (
                    item.rep_min is None
                    or item.rep_max is None
                    or not 1 <= item.rep_min <= item.rep_max <= 100
                    or item.duration_min_seconds is not None
                    or item.duration_max_seconds is not None
                    or item.target_rir is None
                ):
                    errors.append("INVALID_EXERCISE_PRESCRIPTION")
            elif item.prescription_mode is PrescriptionMode.DURATION:
                if (
                    item.duration_min_seconds is None
                    or item.duration_max_seconds is None
                    or not 1
                    <= item.duration_min_seconds
                    <= item.duration_max_seconds
                    <= 3600
                    or item.rep_min is not None
                    or item.rep_max is not None
                    or item.target_rir is not None
                ):
                    errors.append("INVALID_EXERCISE_PRESCRIPTION")
            else:
                errors.append("INVALID_EXERCISE_PRESCRIPTION")
            if (
                item.rest_seconds < ruleset.minimum_rest_seconds
                or (
                    item.target_rir is not None
                    and not 0 <= item.target_rir <= ruleset.maximum_target_rir
                )
            ):
                errors.append("INVALID_EXERCISE_PRESCRIPTION")
            if not item.reason_codes:
                errors.append("MISSING_SELECTION_REASON")
            if item.primary_muscle is not None and item.counts_toward_volume:
                key = item.primary_muscle.value
                direct_sets[key] += item.sets
                per_session[key] += item.sets
        for muscle in per_session:
            direct_session_frequency[muscle] += 1
        configured_limit = program.aggregate_metrics.get(
            "reference_max_sets_per_muscle_per_session",
            ruleset.max_sets_per_muscle_per_session,
        )
        per_session_limit = (
            configured_limit
            if isinstance(configured_limit, int)
            else ruleset.max_sets_per_muscle_per_session
        )
        if any(value > per_session_limit for value in per_session.values()):
            errors.append("PER_SESSION_MUSCLE_VOLUME_EXCEEDED")
        if (
            day.cardio
            and day.cardio.intensity.value == "vigorous"
            and day.focus
            in {
                "lower",
                "legs",
            }
        ):
            errors.append("CARDIO_LOWER_BODY_RECOVERY_CONFLICT")

    if len(program.weekly_schedule) != len(program.split.day_focuses):
        errors.append("TRAINING_DAY_COUNT_MISMATCH")
    expected_training_days = min(request.available_training_days, ruleset.max_resistance_days)
    if len(program.weekly_schedule) != expected_training_days:
        errors.append("REQUESTED_TRAINING_DAYS_UNSATISFIED")
        errors.append(
            f"REQUESTED_TRAINING_DAYS_MISMATCH:expected={expected_training_days}:"
            f"actual={len(program.weekly_schedule)}"
        )
    if len(program.weekly_schedule) >= 4 and any(
        frequency > ruleset.maximum_direct_sessions_per_muscle_per_week
        for frequency in direct_session_frequency.values()
    ):
        errors.append("MUSCLE_DIRECT_FREQUENCY_EXCEEDED")
    if not recovery_spacing_is_valid(program.weekly_schedule, ruleset):
        errors.append("RECOVERY_SPACING_INVALID")
    if program.safety_status not in {
        SafetyStatus.CLEAR,
        SafetyStatus.CLEAR_WITH_MODIFICATIONS,
    }:
        errors.append("SAFETY_STATUS_DISALLOWS_GENERATION")
    relaxed_pattern_groups = {
        frozenset(group)
        for group in _sequence_metric(
            program.aggregate_metrics.get("relaxed_required_pattern_groups", ())
        )
        if isinstance(group, (tuple, list, set, frozenset))
    }
    for group in (
        {MovementPattern.HORIZONTAL_PUSH, MovementPattern.VERTICAL_PUSH},
        {MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL},
        {MovementPattern.SQUAT, MovementPattern.LUNGE, MovementPattern.KNEE_EXTENSION},
        {MovementPattern.HIP_HINGE, MovementPattern.HIP_EXTENSION},
        {
            MovementPattern.CORE_ANTI_EXTENSION,
            MovementPattern.CORE_ANTI_ROTATION,
            MovementPattern.CORE_ANTI_LATERAL_FLEXION,
        },
    ):
        if frozenset(pattern.value for pattern in group) in relaxed_pattern_groups:
            continue
        if not any(patterns[pattern] for pattern in group):
            errors.append("REQUIRED_MOVEMENT_PATTERN_MISSING")
    for exercise_id, count in exercise_usage.items():
        if count > 1:
            occurrences = [
                item
                for day in program.weekly_schedule
                for item in day.exercises
                if item.exercise_id == exercise_id
            ]
            if not all(
                "CORE_MOVEMENT_REPEATED_FOR_PROGRESSION" in item.reason_codes
                for item in occurrences[1:]
            ):
                errors.append("UNJUSTIFIED_DUPLICATE_EXERCISE")
    planned = program.aggregate_metrics.get("planned_direct_sets_by_muscle", {})
    ranges = program.aggregate_metrics.get("volume_ranges_by_muscle", {})
    effective_volume = calculate_effective_volume(
        (item for day in program.weekly_schedule for item in day.exercises),
        ruleset,
    )
    effective_sets = effective_volume.effective_sets_by_muscle
    if isinstance(ranges, dict):
        for muscle, range_values in ranges.items():
            if not isinstance(range_values, dict):
                continue
            muscle_key = str(muscle)
            actual_effective = effective_sets.get(muscle_key, 0)
            effective_maximum_hard = _int_metric(
                range_values.get("effective_maximum_hard"),
                ruleset.maximum_sets[program.training_status],
            )
            if actual_effective > effective_maximum_hard:
                errors.append("WEEKLY_MUSCLE_VOLUME_EXCEEDED")
            if actual_effective > _int_metric(
                range_values.get("effective_maximum_soft", range_values.get("maximum_soft")),
                effective_maximum_hard,
            ):
                warnings.append("SOFT_WEEKLY_VOLUME_EXCEEDED")
            if actual_effective < _int_metric(
                range_values.get("effective_target_sets", range_values.get("target_sets")),
                0,
            ):
                warnings.append("EFFECTIVE_VOLUME_BELOW_SOFT_TARGET")
            minimum_effective = _int_metric(
                range_values.get("minimum_effective_sets", range_values.get("minimum_soft")),
                0,
            )
            coverage_required = range_values.get("minimum_coverage_required") is True
            unavailable_coverage = _sequence_metric(
                program.aggregate_metrics.get("unavailable_muscle_coverage", ())
            )
            if (
                coverage_required
                and actual_effective < minimum_effective
                and muscle_key not in unavailable_coverage
            ):
                errors.append(f"MINIMUM_MUSCLE_COVERAGE_UNSATISFIED:{muscle_key}")
            minimum_direct = _int_metric(
                range_values.get("minimum_direct_sets", range_values.get("minimum_soft")),
                0,
            )
            if direct_sets[muscle_key] < minimum_direct:
                if range_values.get("direct_minimum_required") is True:
                    errors.append(f"MINIMUM_DIRECT_MUSCLE_COVERAGE_UNSATISFIED:{muscle_key}")
                else:
                    warnings.append("DIRECT_VOLUME_BELOW_SOFT_TARGET")
    else:
        maximum = ruleset.maximum_sets[program.training_status]
        if any(value > maximum for value in effective_sets.values()):
            errors.append("WEEKLY_MUSCLE_VOLUME_EXCEEDED")
    if isinstance(planned, dict) and any(
        effective_sets.get(str(muscle), 0) < int(target) for muscle, target in planned.items()
    ):
        warnings.append("PLANNED_SOFT_VOLUME_REDUCED_DURING_SESSION_FIT")
    return ValidationReport(
        errors=tuple(dict.fromkeys(errors)),
        warnings=tuple(dict.fromkeys(warnings)),
        assumptions=program.assumptions,
        metrics={
            **program.aggregate_metrics,
            "weekly_direct_sets_by_muscle": complete_tracked_metrics(dict(direct_sets)),
            "weekly_fractional_sets_by_muscle": complete_tracked_metrics(
                effective_volume.secondary_sets_by_muscle
            ),
            "weekly_effective_sets_by_muscle": complete_tracked_metrics(
                effective_volume.effective_sets_by_muscle
            ),
            "direct_session_frequency_by_muscle": complete_tracked_metrics(
                dict(direct_session_frequency)
            ),
            "movement_pattern_frequency": {
                pattern.value: count for pattern, count in patterns.items()
            },
        },
        decision_trace=program.decision_trace,
    )


def _int_metric(value: object, fallback: int) -> int:
    if isinstance(value, (int, float, str)):
        return int(value)
    return fallback


def _sequence_metric(value: object) -> tuple[object, ...]:
    if isinstance(value, (tuple, list, set, frozenset)):
        return tuple(value)
    return ()
