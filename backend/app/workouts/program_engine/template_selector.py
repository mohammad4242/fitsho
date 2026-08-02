from uuid import UUID

from app.workouts.program_engine.enums import Goal, TrainingStatus
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    TemplateReference,
)


def select_template_reference(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    templates: tuple[TemplateReference, ...],
) -> TemplateReference | None:
    level = _template_level(request.training_status)
    eligible_by_id = {candidate.id for candidate in eligible}
    scored = [
        (template, _score(request, template))
        for template in templates
        if template.days_per_week == request.resistance_training_days
        and template.training_level == level
        and _matches_goal(request.primary_goal, template.fitness_goal)
        and _core_slots_are_resolvable(template, eligible, eligible_by_id)
    ]
    if not scored:
        return None
    return max(scored, key=lambda item: (item[1], item[0].slug))[0]


def _template_level(status: TrainingStatus) -> str:
    if status is TrainingStatus.NOVICE:
        return "beginner"
    if status in {TrainingStatus.EARLY_INTERMEDIATE, TrainingStatus.INTERMEDIATE}:
        return "intermediate"
    return "advanced"


def _matches_goal(goal: Goal, template_goal: str) -> bool:
    return goal in {Goal.HYPERTROPHY, Goal.MUSCLE_GAIN} and template_goal == "build_muscle"


def _score(request: NormalizedProgramRequest, template: TemplateReference) -> int:
    priority_tags = {f"{muscle.value}_priority" for muscle in request.source.priority_muscles}
    score = 100 + 35 * len(priority_tags.intersection(template.focus_tags))
    if "classic" in template.focus_tags and not priority_tags:
        score += 10
    if "long_session" in template.focus_tags and request.source.session_duration_minutes < 80:
        score -= 50
    return score


def _core_slots_are_resolvable(
    template: TemplateReference,
    eligible: tuple[ExerciseCandidate, ...],
    eligible_by_id: set[UUID],
) -> bool:
    for day in template.days:
        for slot in day.slots:
            if slot.adaptation_priority != "core":
                continue
            if slot.exercise_id in eligible_by_id:
                continue
            if not any(
                candidate.movement_pattern is slot.movement_pattern
                and candidate.primary_muscle in slot.target_muscles
                for candidate in eligible
            ):
                return False
    return True
