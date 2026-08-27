from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.exercises.enums import MuscleGroup
from app.training_templates.tags import priority_tags_for_muscles
from app.workouts.program_engine.schemas import TemplateReference
from app.workouts.schemas import WorkoutGenerationProfile


@dataclass(frozen=True)
class AiCoachProgramCandidate:
    template: TemplateReference
    score: int


def candidate_program_payload(
    candidate: AiCoachProgramCandidate,
    *,
    exercise_names_fa: dict[UUID, str],
) -> dict[str, object]:
    return {
        "candidate_id": candidate.template.slug,
        "days": [
            {
                "day_number": day.day_number,
                "title": day.title,
                "title_fa": day.title_fa or day.title,
                "exercise_names_fa": [
                    exercise_names_fa[slot.exercise_id]
                    for slot in day.slots
                    if slot.exercise_id is not None
                ],
            }
            for day in candidate.template.days
        ],
    }


def select_ai_coach_candidates(
    *,
    templates: tuple[TemplateReference, ...],
    profile: WorkoutGenerationProfile,
    eligible_exercise_ids: frozenset[UUID],
    priority_muscles: tuple[MuscleGroup, ...] = (),
    maximum_candidates: int = 3,
) -> tuple[AiCoachProgramCandidate, ...]:
    """Return only fully eligible library programs in deterministic priority order."""
    priority_tags = priority_tags_for_muscles(priority_muscles)
    candidates: list[AiCoachProgramCandidate] = []
    for template in templates:
        if (
            template.days_per_week != profile.training_days_per_week
            or profile.experience_level.value not in template.supported_levels
        ):
            continue
        exercise_ids = tuple(slot.exercise_id for day in template.days for slot in day.slots)
        if not exercise_ids or any(exercise_id is None for exercise_id in exercise_ids):
            continue
        if not set(exercise_ids).issubset(eligible_exercise_ids):
            continue
        score = 100 + 10 * len(priority_tags.intersection(template.focus_tags))
        candidates.append(AiCoachProgramCandidate(template=template, score=score))
    return tuple(
        sorted(candidates, key=lambda candidate: (-candidate.score, candidate.template.slug))[
            :maximum_candidates
        ]
    )
