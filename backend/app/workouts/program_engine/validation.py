from collections import Counter

from app.exercises.enums import MovementPattern
from app.workouts.program_engine.enums import SafetyStatus
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
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
    constraints = request
    patterns: Counter[MovementPattern] = Counter()
    exercise_usage: Counter[object] = Counter()
    direct_sets: Counter[str] = Counter()
    for day in program.weekly_schedule:
        if day.estimated_duration_minutes > (
            request.session_duration_minutes + ruleset.duration_tolerance_minutes
        ):
            errors.append("SESSION_DURATION_EXCEEDED")
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
            if item.caution_tags.intersection(constraints.blocked_caution_tags):
                errors.append("BLOCKED_CAUTION_TAG_SELECTED")
            if not item.equipment.issubset(constraints.available_equipment):
                errors.append("UNAVAILABLE_EQUIPMENT_SELECTED")
            if item.sets < 1 or item.rep_min < 1 or item.rep_max < item.rep_min:
                errors.append("INVALID_EXERCISE_PRESCRIPTION")
            if (
                not 0 <= item.target_rir <= ruleset.maximum_target_rir
                or item.rest_seconds < ruleset.minimum_rest_seconds
            ):
                errors.append("INVALID_EXERCISE_PRESCRIPTION")
            if not item.reason_codes:
                errors.append("MISSING_SELECTION_REASON")
            if item.primary_muscle is not None and item.counts_toward_volume:
                key = item.primary_muscle.value
                direct_sets[key] += item.sets
                per_session[key] += item.sets
        if any(value > ruleset.max_sets_per_muscle_per_session for value in per_session.values()):
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
    if not _recovery_spacing_is_valid(program, ruleset):
        errors.append("RECOVERY_SPACING_INVALID")
    if program.safety_status not in {
        SafetyStatus.CLEAR,
        SafetyStatus.CLEAR_WITH_MODIFICATIONS,
    }:
        errors.append("SAFETY_STATUS_DISALLOWS_GENERATION")
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
    maximum = ruleset.maximum_sets[program.training_status]
    if any(value > maximum for value in direct_sets.values()):
        errors.append("WEEKLY_MUSCLE_VOLUME_EXCEEDED")
    planned = program.aggregate_metrics.get("planned_direct_sets_by_muscle", {})
    if isinstance(planned, dict) and any(
        direct_sets[str(muscle)] < int(target) for muscle, target in planned.items()
    ):
        warnings.append("PLANNED_VOLUME_REDUCED_DURING_SESSION_FIT")
    return ValidationReport(
        errors=tuple(dict.fromkeys(errors)),
        warnings=tuple(dict.fromkeys(warnings)),
        assumptions=program.assumptions,
        metrics={
            **program.aggregate_metrics,
            "weekly_direct_sets_by_muscle": dict(direct_sets),
            "movement_pattern_frequency": {
                pattern.value: count for pattern, count in patterns.items()
            },
        },
        decision_trace=program.decision_trace,
    )


def _recovery_spacing_is_valid(program: WorkoutProgram, ruleset: ProgramRuleset) -> bool:
    scheduled = sorted(
        (day.weekday, day.focus) for day in program.weekly_schedule if day.weekday is not None
    )
    if len(scheduled) <= 1:
        return True
    circular = scheduled + [(scheduled[0][0] + ruleset.days_per_week, scheduled[0][1])]
    for current, following in zip(circular, circular[1:], strict=False):
        recovery_sensitive = (
            current[1].startswith("full_body")
            or following[1].startswith("full_body")
            or current[1] == following[1]
        )
        if recovery_sensitive and following[0] - current[0] < ruleset.minimum_recovery_gap_days:
            return False
    return True
