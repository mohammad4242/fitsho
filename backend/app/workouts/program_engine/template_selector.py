from uuid import UUID

from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    TemplateReference,
)
from app.workouts.program_engine.slot_compatibility import evaluate_candidate_slot_compatibility
from app.workouts.program_engine.template_scoring import (
    TemplateScore,
    score_template_reference,
)


def rank_template_references(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    templates: tuple[TemplateReference, ...],
    ruleset: ProgramRuleset,
) -> tuple[tuple[TemplateReference, TemplateScore], ...]:
    scored = tuple(
        (template, score_template_reference(request, template, ruleset))
        for template in eligible_template_references(request, eligible, templates)
    )
    return tuple(sorted(scored, key=lambda item: (item[1].total, item[0].slug), reverse=True))


def select_template_reference(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    templates: tuple[TemplateReference, ...],
    ruleset: ProgramRuleset,
) -> TemplateReference | None:
    ranked = rank_template_references(request, eligible, templates, ruleset)
    if not ranked:
        return None
    return ranked[0][0]


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
