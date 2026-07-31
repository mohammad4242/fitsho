import math
from collections import Counter

from app.exercises.enums import ExerciseType
from app.workouts.program_engine.enums import Goal, TrainingStatus
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    NormalizedProgramRequest,
    ProgrammedExercise,
    SessionDraft,
    WeeklyVolumePlan,
    WorkoutDay,
)


def prescribe_sessions(
    request: NormalizedProgramRequest,
    drafts: tuple[SessionDraft, ...],
    volume: WeeklyVolumePlan,
    ruleset: ProgramRuleset,
    *,
    cardio_reserve_minutes: int,
) -> tuple[WorkoutDay, ...]:
    appearances = Counter(
        item.primary_muscle
        for draft in drafts
        for item in draft.exercises
        if item.primary_muscle is not None
    )
    days: list[WorkoutDay] = []
    for draft in drafts:
        exercise_count = max(1, len(draft.exercises))
        available = max(
            10,
            request.source.session_duration_minutes
            - ruleset.general_warmup_minutes
            - cardio_reserve_minutes,
        )
        per_exercise_budget = max(3, available // exercise_count)
        programmed: list[ProgrammedExercise] = []
        for index, exercise in enumerate(draft.exercises):
            primary_muscle = exercise.primary_muscle
            target = volume.direct_sets_for(primary_muscle) if primary_muscle is not None else 2
            appearance_count = appearances[primary_muscle] if primary_muscle is not None else 1
            desired_sets = max(
                ruleset.minimum_working_sets,
                math.ceil(target / max(1, appearance_count)),
            )
            sets = min(ruleset.max_sets_per_muscle_per_session, desired_sets)
            rep_min, rep_max, rir, rest = _prescription_for(
                request.primary_goal,
                exercise.exercise_type,
                request.training_status,
                ruleset,
            )
            warmup_sets = 0
            if index == 0 and exercise.exercise_type is ExerciseType.COMPOUND:
                warmup_sets = (
                    ruleset.strength_compound_warmup_sets
                    if request.primary_goal is Goal.STRENGTH
                    else ruleset.first_compound_warmup_sets
                )
            while (
                sets > ruleset.minimum_working_sets
                and _estimate_minutes(sets, rest, warmup_sets, ruleset) > per_exercise_budget
            ):
                sets -= 1
            programmed.append(
                ProgrammedExercise(
                    exercise_id=exercise.id,
                    exercise_name=exercise.name,
                    order=index + 1,
                    sets=sets,
                    rep_min=rep_min,
                    rep_max=rep_max,
                    target_rir=rir,
                    rest_seconds=rest,
                    estimated_minutes=_estimate_minutes(sets, rest, warmup_sets, ruleset),
                    reason_codes=draft.selection_reasons[exercise.id],
                    substitution_exercise_ids=draft.substitutions[exercise.id],
                    warmup_sets=warmup_sets,
                    movement_pattern=exercise.movement_pattern,
                    primary_muscle=exercise.primary_muscle,
                    secondary_muscles=exercise.secondary_muscles,
                    equipment=exercise.equipment,
                    caution_tags=exercise.caution_tags,
                    range_of_motion_profile=exercise.range_of_motion_profile,
                    impact_level=exercise.impact_level,
                    axial_loading_level=exercise.axial_loading_level,
                    stability_demand=exercise.stability_demand,
                    is_active=exercise.is_active,
                    is_programmable=exercise.is_programmable,
                    needs_review=exercise.needs_review,
                )
            )
        estimated = ruleset.general_warmup_minutes + sum(
            item.estimated_minutes for item in programmed
        )
        days.append(
            WorkoutDay(
                day_index=draft.day_index,
                weekday=draft.weekday,
                title=f"Day {draft.day_index}: {draft.focus.replace('_', ' ').title()}",
                focus=draft.focus,
                estimated_duration_minutes=estimated,
                exercises=tuple(programmed),
            )
        )
    return tuple(days)


def _prescription_for(
    goal: Goal,
    exercise_type: ExerciseType,
    status: TrainingStatus,
    ruleset: ProgramRuleset,
) -> tuple[int, int, int, int]:
    novice = status is TrainingStatus.NOVICE
    rir = ruleset.novice_target_rir if novice else ruleset.experienced_target_rir
    if goal is Goal.STRENGTH:
        key = (
            "strength_compound" if exercise_type is ExerciseType.COMPOUND else "strength_accessory"
        )
    if goal in {Goal.HYPERTROPHY, Goal.MUSCLE_GAIN}:
        key = (
            "hypertrophy_isolation"
            if exercise_type is ExerciseType.ISOLATION
            else "hypertrophy_compound"
        )
    elif goal is Goal.MUSCULAR_ENDURANCE:
        key = "muscular_endurance"
        rir = ruleset.novice_target_rir
    elif goal in {Goal.FAT_LOSS, Goal.BODY_RECOMPOSITION}:
        key = "fat_loss"
    elif goal is not Goal.STRENGTH:
        key = "general_fitness"
    rule = ruleset.prescription_rules[key]
    return rule.rep_min, rule.rep_max, rir, rule.rest_seconds


def _estimate_minutes(
    sets: int,
    rest_seconds: int,
    warmup_sets: int,
    ruleset: ProgramRuleset,
) -> int:
    work = sets * ruleset.set_execution_minutes
    rest = max(0, sets - 1) * rest_seconds / 60
    ramp_up = warmup_sets * ruleset.warmup_set_minutes
    return max(
        ruleset.minimum_exercise_estimate_minutes,
        math.ceil(ruleset.exercise_transition_minutes + work + rest + ramp_up),
    )
