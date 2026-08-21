from app.exercises.enums import Equipment, ExerciseCautionTag, MovementPattern, MuscleGroup
from app.workouts.program_engine.enums import SafetyStatus
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    ProgrammedExercise,
    SafetyAssessment,
)


def effective_caution_tags(
    exercise: ExerciseCandidate | ProgrammedExercise,
) -> frozenset[ExerciseCautionTag]:
    """Return explicit and conservative caution tags from catalog metadata."""

    tags = set(exercise.caution_tags)
    if (
        exercise.movement_pattern
        in {
            MovementPattern.HORIZONTAL_PUSH,
            MovementPattern.ELBOW_EXTENSION,
            MovementPattern.CORE_ANTI_EXTENSION,
            MovementPattern.CORE_ANTI_LATERAL_FLEXION,
        }
        and Equipment.BODYWEIGHT in exercise.equipment
    ):
        tags.add(ExerciseCautionTag.WRIST_LOADING)
    if exercise.movement_pattern is MovementPattern.SHRUG:
        tags.add(ExerciseCautionTag.NECK_LOADING)
    if (
        exercise.primary_muscle is MuscleGroup.SHOULDERS
        and exercise.movement_pattern is MovementPattern.HORIZONTAL_PULL
    ):
        tags.add(ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION)
    if exercise.movement_pattern is MovementPattern.VERTICAL_PUSH:
        tags.add(ExerciseCautionTag.OVERHEAD_POSITION)
    if exercise.movement_pattern in {MovementPattern.SQUAT, MovementPattern.LUNGE}:
        tags.add(ExerciseCautionTag.DEEP_KNEE_FLEXION)
    if exercise.movement_pattern is MovementPattern.HIP_HINGE:
        tags.add(ExerciseCautionTag.LOWER_BACK_LOADING)
    if exercise.movement_pattern is MovementPattern.SPINAL_FLEXION:
        tags.add(ExerciseCautionTag.SPINAL_FLEXION)
    return frozenset(tags)


def screen_safety(request: NormalizedProgramRequest) -> SafetyAssessment:
    source = request.source
    if source.current_pain_or_red_flags or source.reports_uncontrolled_medical_condition:
        return SafetyAssessment(
            status=SafetyStatus.STOP_AND_REFER,
            reason_codes=("PROGRAM_REJECTED_SAFETY_STATUS",),
        )
    if source.pregnancy_or_postpartum:
        return SafetyAssessment(
            status=SafetyStatus.REQUIRES_PROFESSIONAL_REVIEW,
            reason_codes=("SPECIALIST_PATHWAY_REQUIRED",),
        )
    if any(
        not item.stable or not item.has_computable_constraint
        for item in source.injuries_and_limitations
    ):
        return SafetyAssessment(
            status=SafetyStatus.REQUIRES_PROFESSIONAL_REVIEW,
            reason_codes=("LIMITATION_REQUIRES_COMPUTABLE_CONSTRAINTS",),
        )
    if source.injuries_and_limitations or any(
        (
            source.blocked_exercises,
            source.blocked_movement_patterns,
            source.blocked_caution_tags,
        )
    ):
        return SafetyAssessment(
            status=SafetyStatus.CLEAR_WITH_MODIFICATIONS,
            reason_codes=("EXPLICIT_LIMITATIONS_APPLIED",),
        )
    return SafetyAssessment(status=SafetyStatus.CLEAR, reason_codes=("SAFETY_SCREEN_CLEAR",))
