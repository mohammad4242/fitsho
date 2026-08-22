from dataclasses import dataclass
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
    score_template_reference_result,
)


@dataclass(frozen=True)
class TemplateRankingResult:
    template: TemplateReference
    score: TemplateScore
    reason_codes: tuple[str, ...]

    def decision_trace(self) -> dict[str, object]:
        return {
            "slug": self.template.slug,
            "score": {
                "priority": self.score.priority_score,
                "body_analysis": self.score.body_analysis_score,
                "goal": self.score.goal_score,
                "sex": self.score.sex_score,
                "fallback": self.score.fallback_score,
                "total": self.score.total,
            },
            "reason_codes": self.reason_codes,
        }


@dataclass(frozen=True)
class HardRejectedTemplate:
    slug: str
    reason_codes: tuple[str, ...]

    def decision_trace(self) -> dict[str, object]:
        return {"slug": self.slug, "reason_codes": self.reason_codes}


@dataclass(frozen=True)
class TemplateTieBreak:
    score: int
    tied_slugs: tuple[str, ...]
    selected: str

    def decision_trace(self) -> dict[str, object]:
        return {
            "score": self.score,
            "tied_slugs": self.tied_slugs,
            "selected_by": "slug_descending",
            "selected": self.selected,
        }


@dataclass(frozen=True)
class TemplateSelectionResult:
    requested_days: int
    experience_level: str
    templates_considered: int
    hard_rejections: tuple[HardRejectedTemplate, ...]
    candidates: tuple[TemplateRankingResult, ...]
    selected: TemplateRankingResult | None
    tie_break: TemplateTieBreak | None

    def decision_trace(self) -> dict[str, object]:
        return {
            "stage": "template_selection",
            "requested_days": self.requested_days,
            "experience_level": self.experience_level,
            "templates_considered": self.templates_considered,
            "hard_rejections": tuple(item.decision_trace() for item in self.hard_rejections),
            "candidates": tuple(item.decision_trace() for item in self.candidates),
            "selected": self.selected.template.slug if self.selected is not None else None,
            "tie_break": self.tie_break.decision_trace() if self.tie_break is not None else None,
        }


def rank_template_references(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    templates: tuple[TemplateReference, ...],
    ruleset: ProgramRuleset,
) -> tuple[TemplateRankingResult, ...]:
    scored = tuple(
        TemplateRankingResult(template, result.score, result.reason_codes)
        for template in eligible_template_references(request, eligible, templates)
        for result in (score_template_reference_result(request, template, ruleset),)
    )
    return tuple(
        sorted(scored, key=lambda item: (item.score.total, item.template.slug), reverse=True)
    )


def select_template_reference_result(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    templates: tuple[TemplateReference, ...],
    ruleset: ProgramRuleset,
) -> TemplateSelectionResult:
    ranked = rank_template_references(request, eligible, templates, ruleset)
    selected = ranked[0] if ranked else None
    tie_break: TemplateTieBreak | None = None
    if selected is not None:
        tied = tuple(item for item in ranked if item.score.total == selected.score.total)
        if len(tied) > 1:
            tie_break = TemplateTieBreak(
                score=selected.score.total,
                tied_slugs=tuple(item.template.slug for item in tied),
                selected=selected.template.slug,
            )
    rejected_items: list[HardRejectedTemplate] = []
    for template in templates:
        reason_codes = _hard_rejection_reason_codes(request, eligible, template)
        if reason_codes:
            rejected_items.append(HardRejectedTemplate(template.slug, reason_codes))
    rejected = tuple(sorted(rejected_items, key=lambda item: item.slug))
    return TemplateSelectionResult(
        requested_days=request.resistance_training_days,
        experience_level=_template_level(request),
        templates_considered=len(templates),
        hard_rejections=rejected,
        candidates=ranked,
        selected=selected,
        tie_break=tie_break,
    )


def select_template_reference(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    templates: tuple[TemplateReference, ...],
    ruleset: ProgramRuleset,
) -> TemplateReference | None:
    result = select_template_reference_result(request, eligible, templates, ruleset)
    return result.selected.template if result.selected is not None else None


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
    return tuple(
        template
        for template in templates
        if not _hard_rejection_reason_codes(request, eligible, template, level=level)
    )


def _hard_rejection_reason_codes(
    request: NormalizedProgramRequest,
    eligible: tuple[ExerciseCandidate, ...],
    template: TemplateReference,
    *,
    level: str | None = None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if template.days_per_week != request.resistance_training_days:
        reasons.append("DAYS_MISMATCH")
    if template.training_level != (level or _template_level(request)):
        reasons.append("EXPERIENCE_LEVEL_MISMATCH")
    if not _core_slots_are_resolvable(
        template,
        eligible,
        {candidate.id for candidate in eligible},
    ):
        reasons.append("CORE_SLOT_UNRESOLVABLE")
    return tuple(reasons)


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
