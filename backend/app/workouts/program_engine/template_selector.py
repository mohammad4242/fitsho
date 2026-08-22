from uuid import UUID

from app.workouts.program_engine.body_analysis import (
    TEMPLATE_TAGS_BY_MUSCLE,
    eligible_body_analysis_priorities,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    TemplateReference,
)
from app.workouts.program_engine.slot_compatibility import evaluate_candidate_slot_compatibility


def select_template_reference(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    templates: tuple[TemplateReference, ...],
    ruleset: ProgramRuleset,
) -> TemplateReference | None:
    scored = [
        (template, _score(request, template, ruleset))
        for template in eligible_template_references(request, eligible, templates)
    ]
    if not scored:
        return None
    return max(scored, key=lambda item: (item[1], item[0].slug))[0]


def eligible_template_references(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    templates: tuple[TemplateReference, ...],
) -> tuple[TemplateReference, ...]:
    """Return templates that pass structural hard eligibility.

    Goal remains available to downstream programming, but template metadata
    ``fitness_goal`` is intentionally not an exclusion criterion here.
    """
    level = _template_level(request)
    eligible_by_id = {candidate.id for candidate in eligible}
    return tuple(
        template
        for template in templates
        if template.days_per_week == request.resistance_training_days
        and template.training_level == level
        and _core_slots_are_resolvable(template, eligible, eligible_by_id)
    )


def _template_level(request: NormalizedProgramRequest) -> str:
    return request.source.training_experience.value


def _score(
    request: NormalizedProgramRequest,
    template: TemplateReference,
    ruleset: ProgramRuleset,
) -> int:
    priority_tags = {f"{muscle.value}_priority" for muscle in request.source.priority_muscles}
    score = 100 + 35 * len(priority_tags.intersection(template.focus_tags))
    template_tags = set(template.focus_tags)
    for priority in eligible_body_analysis_priorities(request, ruleset):
        if not template_tags.intersection(TEMPLATE_TAGS_BY_MUSCLE.get(priority.muscle, ())):
            continue
        score += (
            ruleset.body_analysis_clear_lag_template_boost
            if priority.classification == "clear_lag"
            else ruleset.body_analysis_mild_lag_template_boost
        )
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
                requested = next(item for item in eligible if item.id == slot.exercise_id)
                if evaluate_candidate_slot_compatibility(
                    requested,
                    allowed_patterns=frozenset({slot.movement_pattern}),
                    target_muscles=frozenset(slot.target_muscles),
                    day_focus=f"template_reference_{day.day_number}",
                ).compatible:
                    continue
            if not any(
                evaluate_candidate_slot_compatibility(
                    candidate,
                    allowed_patterns=frozenset({slot.movement_pattern}),
                    target_muscles=frozenset(slot.target_muscles),
                    day_focus=f"template_reference_{day.day_number}",
                ).compatible
                for candidate in eligible
            ):
                return False
    return True
