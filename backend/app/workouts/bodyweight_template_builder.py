from __future__ import annotations

from collections.abc import Iterable

from app.exercises.enums import Equipment, PrescriptionMode
from app.profile.enums import ExperienceLevel
from app.workouts.bodyweight_templates import (
    BODYWEIGHT_TEMPLATE_LIBRARY_VERSION,
    BodyweightProgramTemplate,
    BodyweightTemplateExercise,
    bodyweight_template_fingerprint,
)
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.enums import SafetyStatus, SplitType
from app.workouts.program_engine.equipment import effective_required_equipment
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.safety import screen_safety
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    ProgramGenerationRequest,
    ProgrammedExercise,
    SplitPlan,
    ValidationReport,
    WorkoutDay,
    WorkoutProgram,
)
from app.workouts.time_budget import ExerciseTiming, calculate_exercise_minutes

BODYWEIGHT_FIXED_TEMPLATE = "BODYWEIGHT_FIXED_TEMPLATE"
BODYWEIGHT_TEMPLATE_EXERCISE_UNAVAILABLE = "BODYWEIGHT_TEMPLATE_EXERCISE_UNAVAILABLE"
BODYWEIGHT_PULL_UP_BAR_REQUIRED = "BODYWEIGHT_PULL_UP_BAR_REQUIRED"
PROGRAM_REJECTED_SAFETY_STATUS = "PROGRAM_REJECTED_SAFETY_STATUS"
BODYWEIGHT_PROGRESSION_RULE = "bodyweight_double_progression_v1"


class BodyweightTemplateBuildError(Exception):
    def __init__(
        self,
        code: str,
        *,
        template_slug: str,
        exercise_slug: str | None = None,
        rejection_reason_codes: tuple[str, ...] = (),
        safety_status: SafetyStatus | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.template_slug = template_slug
        self.exercise_slug = exercise_slug
        self.rejection_reason_codes = rejection_reason_codes
        self.safety_status = safety_status


def build_bodyweight_template_program(
    *,
    request: ProgramGenerationRequest,
    experience_level: ExperienceLevel,
    template: BodyweightProgramTemplate,
    exercise_catalog: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
) -> WorkoutProgram:
    normalized = normalize_request(request, ruleset)
    safety = screen_safety(normalized)
    if safety.status not in {SafetyStatus.CLEAR, SafetyStatus.CLEAR_WITH_MODIFICATIONS}:
        raise BodyweightTemplateBuildError(
            PROGRAM_REJECTED_SAFETY_STATUS,
            template_slug=template.slug,
            rejection_reason_codes=safety.reason_codes,
            safety_status=safety.status,
        )

    eligibility = filter_eligible_exercises(normalized, exercise_catalog)
    eligible_by_slug = {candidate.slug: candidate for candidate in eligibility.eligible}
    catalog_by_slug = {candidate.slug: candidate for candidate in exercise_catalog}
    rejection_by_id = {
        rejected.exercise_id: rejected.reason_codes for rejected in eligibility.rejected
    }

    days: list[WorkoutDay] = []
    direct_sets: dict[str, int] = {}
    for template_day in template.days:
        programmed: list[ProgrammedExercise] = []
        for order, slot in enumerate(template_day.exercises, start=1):
            candidate = eligible_by_slug.get(slot.exercise_slug)
            if candidate is None:
                catalog_candidate = catalog_by_slug.get(slot.exercise_slug)
                rejection_codes = (
                    rejection_by_id.get(catalog_candidate.id, ())
                    if catalog_candidate is not None
                    else ("EXERCISE_NOT_IN_CATALOG",)
                )
                if catalog_candidate is not None and _requires_pull_up_bar(catalog_candidate):
                    code = (
                        BODYWEIGHT_PULL_UP_BAR_REQUIRED
                        if Equipment.PULL_UP_BAR not in normalized.constraints.available_equipment
                        else BODYWEIGHT_TEMPLATE_EXERCISE_UNAVAILABLE
                    )
                else:
                    code = BODYWEIGHT_TEMPLATE_EXERCISE_UNAVAILABLE
                raise BodyweightTemplateBuildError(
                    code,
                    template_slug=template.slug,
                    exercise_slug=slot.exercise_slug,
                    rejection_reason_codes=rejection_codes,
                )

            item = _programmed_exercise(candidate, slot, order, template.slug)
            programmed.append(item)
            if candidate.primary_muscle is not None:
                muscle = candidate.primary_muscle.value
                direct_sets[muscle] = direct_sets.get(muscle, 0) + slot.sets

        days.append(
            WorkoutDay(
                day_index=template_day.day_number,
                weekday=_weekday_for_day(request, template_day.day_number, template.days),
                title=template_day.title_en,
                focus=_focus_for_day(programmed),
                estimated_duration_minutes=sum(item.estimated_minutes for item in programmed),
                exercises=tuple(programmed),
                cardio=None,
                template_target_muscles=tuple(
                    dict.fromkeys(
                        item.primary_muscle
                        for item in programmed
                        if item.primary_muscle is not None
                    )
                ),
                template_structure_focus=(
                    "upper_lower" if template.split_type is SplitType.UPPER_LOWER else "full_body"
                ),
            )
        )

    assumptions = tuple(dict.fromkeys((*normalized.assumptions, BODYWEIGHT_FIXED_TEMPLATE)))
    warnings = (
        ("SAFETY_MODIFICATIONS_APPLIED",)
        if safety.status is SafetyStatus.CLEAR_WITH_MODIFICATIONS
        else ()
    )
    estimated_weekly_duration = sum(day.estimated_duration_minutes for day in days)
    direct_metrics = dict(sorted(direct_sets.items()))
    decision_trace = (
        {
            "stage": "bodyweight_template_route",
            "status": "selected",
            "template_slug": template.slug,
            "template_fingerprint": bodyweight_template_fingerprint(template),
        },
    )
    metrics = {
        "template_slug": template.slug,
        "template_library_version": BODYWEIGHT_TEMPLATE_LIBRARY_VERSION,
        "template_fingerprint": bodyweight_template_fingerprint(template),
        "estimated_weekly_duration": estimated_weekly_duration,
        "days_per_week": template.days_per_week,
    }
    aggregate_metrics = {
        "template_slug": template.slug,
        "template_library_version": BODYWEIGHT_TEMPLATE_LIBRARY_VERSION,
        "estimated_weekly_duration": estimated_weekly_duration,
        "hard_training_days": template.days_per_week,
        "recovery_days": max(0, 7 - template.days_per_week),
        "weekly_direct_sets_by_muscle": direct_metrics,
        "planned_direct_sets_by_muscle": direct_metrics,
    }
    snapshot = request.model_dump(mode="json")
    snapshot["bodyweight_template_slug"] = template.slug
    snapshot["bodyweight_template_fingerprint"] = bodyweight_template_fingerprint(template)

    return WorkoutProgram(
        user_profile_snapshot=snapshot,
        engine_version="bodyweight_template_v1",
        ruleset_version="bodyweight_template_v1",
        seed=0,
        primary_goal=request.primary_goal,
        secondary_goal=request.secondary_goal_optional,
        training_status=normalized.training_status,
        safety_status=safety.status,
        assumptions=assumptions,
        warnings=warnings,
        duration_weeks=request.program_duration_weeks,
        split=SplitPlan(
            split_type=template.split_type,
            day_focuses=tuple(day.focus for day in days),
            weekdays=tuple(day.weekday for day in days if day.weekday is not None),
            score=0,
            reason_codes=(BODYWEIGHT_FIXED_TEMPLATE, template.slug),
        ),
        weekly_schedule=tuple(days),
        progression_policy={
            "type": BODYWEIGHT_PROGRESSION_RULE,
            "instruction": (
                "Progress repetitions within the prescribed range while preserving target RIR. "
                "After consistently reaching the top of the range with clean technique, "
                "progress to a harder bodyweight variation when available."
            ),
        },
        validation_report=ValidationReport(
            errors=(),
            warnings=warnings,
            assumptions=assumptions,
            metrics=metrics,
            decision_trace=decision_trace,
        ),
        aggregate_metrics=aggregate_metrics,
        decision_trace=decision_trace,
        body_analysis_provenance=(
            request.body_analysis_influence.model_dump(mode="json")
            if request.body_analysis_influence is not None
            else {}
        ),
    )


def _programmed_exercise(
    candidate: ExerciseCandidate,
    slot: BodyweightTemplateExercise,
    order: int,
    template_slug: str,
) -> ProgrammedExercise:
    is_duration = slot.duration_min_seconds is not None
    execution_seconds = slot.duration_max_seconds if is_duration else 45
    return ProgrammedExercise(
        exercise_id=candidate.id,
        exercise_name=candidate.name,
        exercise_slug=candidate.slug,
        order=order,
        sets=slot.sets,
        rep_min=None if is_duration else slot.rep_min,
        rep_max=None if is_duration else slot.rep_max,
        target_rir=None if is_duration else slot.target_rir,
        rest_seconds=slot.rest_seconds,
        estimated_minutes=calculate_exercise_minutes(
            ExerciseTiming(slot.sets, slot.rest_seconds),
            set_execution_seconds=execution_seconds,
        ),
        reason_codes=(BODYWEIGHT_FIXED_TEMPLATE, template_slug),
        substitution_exercise_ids=(),
        warmup_sets=0,
        load_guidance="Use a bodyweight variation that preserves the target RIR.",
        progression_rule=BODYWEIGHT_PROGRESSION_RULE,
        counts_toward_volume=True,
        movement_pattern=candidate.movement_pattern,
        primary_muscle=candidate.primary_muscle,
        secondary_muscles=candidate.secondary_muscles,
        equipment=candidate.equipment,
        caution_tags=candidate.caution_tags,
        range_of_motion_profile=candidate.range_of_motion_profile,
        impact_level=candidate.impact_level,
        axial_loading_level=candidate.axial_loading_level,
        stability_demand=candidate.stability_demand,
        is_active=candidate.is_active,
        is_programmable=candidate.is_programmable,
        needs_review=candidate.needs_review,
        prescription_mode=(PrescriptionMode.DURATION if is_duration else PrescriptionMode.REPS),
        exercise_type=candidate.exercise_type,
        duration_min_seconds=slot.duration_min_seconds if is_duration else None,
        duration_max_seconds=slot.duration_max_seconds if is_duration else None,
        muscle_focus=candidate.muscle_focus,
        body_position=candidate.body_position,
        laterality=candidate.laterality,
        substitution_group=candidate.substitution_group,
    )


def _requires_pull_up_bar(candidate: ExerciseCandidate) -> bool:
    return Equipment.PULL_UP_BAR in effective_required_equipment(
        candidate.equipment, candidate.movement_pattern
    )


def _weekday_for_day(
    request: ProgramGenerationRequest,
    day_number: int,
    days: Iterable[object],
) -> int | None:
    if len(request.preferred_weekdays) != len(tuple(days)):
        return None
    return request.preferred_weekdays[day_number - 1]


def _focus_for_day(exercises: Iterable[ProgrammedExercise]) -> str:
    muscles = dict.fromkeys(
        item.primary_muscle.value for item in exercises if item.primary_muscle is not None
    )
    return ", ".join(muscles)


__all__ = [
    "BODYWEIGHT_FIXED_TEMPLATE",
    "BODYWEIGHT_PULL_UP_BAR_REQUIRED",
    "BODYWEIGHT_PROGRESSION_RULE",
    "BODYWEIGHT_TEMPLATE_EXERCISE_UNAVAILABLE",
    "BodyweightTemplateBuildError",
    "build_bodyweight_template_program",
]
