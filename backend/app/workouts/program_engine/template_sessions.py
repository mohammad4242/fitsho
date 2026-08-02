from collections import Counter

from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.prescription import estimate_exercise_minutes
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    ProgrammedExercise,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
    WorkoutDay,
)


def build_template_sessions(
    request: NormalizedProgramRequest,
    template: TemplateReference,
    eligible: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
) -> tuple[WorkoutDay, ...] | None:
    eligible_by_id = {candidate.id: candidate for candidate in eligible}
    used: Counter[object] = Counter()
    days: list[WorkoutDay] = []
    weekly_patterns: set[MovementPattern] = set()
    for index, reference_day in enumerate(template.days, start=1):
        selected: list[tuple[ExerciseCandidate, TemplateReferenceSlot]] = []
        for slot in reference_day.slots:
            candidate = (
                eligible_by_id.get(slot.exercise_id) if slot.exercise_id is not None else None
            )
            if candidate is None or used[candidate.id]:
                candidate = next(
                    (
                        item
                        for item in eligible
                        if not used[item.id]
                        and item.movement_pattern is slot.movement_pattern
                        and item.primary_muscle in slot.target_muscles
                    ),
                    None,
                )
            if candidate is None:
                if slot.adaptation_priority == "core":
                    return None
                continue
            selected.append((candidate, slot))
            used[candidate.id] += 1
            weekly_patterns.add(candidate.movement_pattern)

        if index == len(template.days) and not weekly_patterns.intersection(
            {
                MovementPattern.CORE_ANTI_EXTENSION,
                MovementPattern.CORE_ANTI_ROTATION,
                MovementPattern.CORE_ANTI_LATERAL_FLEXION,
            }
        ):
            core = next(
                (
                    candidate
                    for candidate in eligible
                    if not used[candidate.id]
                    and candidate.primary_muscle is MuscleGroup.ABS
                    and candidate.movement_pattern
                    in {
                        MovementPattern.CORE_ANTI_EXTENSION,
                        MovementPattern.CORE_ANTI_ROTATION,
                        MovementPattern.CORE_ANTI_LATERAL_FLEXION,
                    }
                ),
                None,
            )
            if core is None:
                return None
            selected.append(
                (
                    core,
                    TemplateReferenceSlot(
                        exercise_id=core.id,
                        exercise_slug_hint="engine-required-core",
                        target_muscles=(MuscleGroup.ABS,),
                        movement_pattern=core.movement_pattern,
                        intensity_method="standard",
                        adaptation_priority="accessory",
                        superset_group=None,
                        sets=2,
                        rep_min=8,
                        rep_max=12,
                        target_rir=2,
                        rest_seconds=45,
                    ),
                )
            )

        _add_targeted_accessories(
            selected,
            reference_day,
            eligible,
            used,
            ruleset.minimum_exercises_per_session,
        )
        if not ruleset.minimum_exercises_per_session <= len(selected) <= (
            ruleset.max_exercises_per_session
        ):
            return None

        while (
            _minutes(selected, ruleset) + ruleset.general_warmup_minutes
            > request.source.session_duration_minutes
        ):
            removable = next(
                (
                    position
                    for priority in ("optional", "accessory")
                    for position in range(len(selected) - 1, -1, -1)
                    if selected[position][1].adaptation_priority == priority
                ),
                None,
            )
            if removable is None:
                return None
            selected.pop(removable)

        if len(selected) < ruleset.minimum_exercises_per_session:
            return None

        exercises = tuple(
            _programmed(candidate, slot, order, ruleset)
            for order, (candidate, slot) in enumerate(selected, start=1)
        )
        days.append(
            WorkoutDay(
                day_index=index,
                weekday=ruleset.default_weekdays[len(template.days)][index - 1],
                title=reference_day.title,
                focus=f"template_reference_{index}",
                estimated_duration_minutes=ruleset.general_warmup_minutes
                + sum(item.estimated_minutes for item in exercises),
                exercises=exercises,
            )
        )
    return tuple(days)


def _add_targeted_accessories(
    selected: list[tuple[ExerciseCandidate, TemplateReferenceSlot]],
    reference_day: TemplateReferenceDay,
    eligible: tuple[ExerciseCandidate, ...],
    used: Counter[object],
    minimum_exercises: int,
) -> None:
    target_muscles = reference_day.focus
    while len(selected) < minimum_exercises:
        candidate = next(
            (
                item
                for item in eligible
                if not used[item.id] and item.primary_muscle in target_muscles
            ),
            None,
        )
        if candidate is None:
            return
        selected.append(
            (
                candidate,
                TemplateReferenceSlot(
                    exercise_id=candidate.id,
                    exercise_slug_hint="engine-targeted-accessory",
                    target_muscles=target_muscles,
                    movement_pattern=candidate.movement_pattern,
                    intensity_method="standard",
                    adaptation_priority="accessory",
                    superset_group=None,
                    sets=2,
                    rep_min=8,
                    rep_max=15,
                    target_rir=2,
                    rest_seconds=60,
                ),
            )
        )
        used[candidate.id] += 1


def _programmed(
    candidate: ExerciseCandidate,
    slot: TemplateReferenceSlot,
    order: int,
    ruleset: ProgramRuleset,
) -> ProgrammedExercise:
    warmup_sets = 2 if order == 1 and candidate.exercise_type is ExerciseType.COMPOUND else 0
    return ProgrammedExercise(
        exercise_id=candidate.id,
        exercise_name=candidate.name,
        order=order,
        sets=slot.sets,
        rep_min=slot.rep_min,
        rep_max=slot.rep_max,
        target_rir=slot.target_rir,
        rest_seconds=slot.rest_seconds,
        estimated_minutes=estimate_exercise_minutes(
            slot.sets, slot.rest_seconds, warmup_sets, ruleset
        ),
        reason_codes=(
            "TEMPLATE_REFERENCE_EXERCISE"
            if candidate.id == slot.exercise_id
            else "TEMPLATE_SAFE_SUBSTITUTION",
        ),
        warmup_sets=warmup_sets,
        notes=None if slot.intensity_method == "standard" else slot.intensity_method,
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
    )


def _minutes(
    selected: list[tuple[ExerciseCandidate, TemplateReferenceSlot]], ruleset: ProgramRuleset
) -> int:
    return sum(
        estimate_exercise_minutes(
            slot.sets,
            slot.rest_seconds,
            2 if index == 0 and candidate.exercise_type is ExerciseType.COMPOUND else 0,
            ruleset,
        )
        for index, (candidate, slot) in enumerate(selected)
    )
