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
            desired_sets = max(2, math.ceil(target / max(1, appearance_count)))
            sets = min(ruleset.max_sets_per_muscle_per_session, desired_sets)
            rep_min, rep_max, rir, rest = _prescription_for(
                request.primary_goal,
                exercise.exercise_type,
                request.training_status,
            )
            warmup_sets = 0
            if index == 0 and exercise.exercise_type is ExerciseType.COMPOUND:
                warmup_sets = 3 if request.primary_goal is Goal.STRENGTH else 2
            while sets > 2 and _estimate_minutes(sets, rest, warmup_sets) > per_exercise_budget:
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
                    estimated_minutes=_estimate_minutes(sets, rest, warmup_sets),
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
) -> tuple[int, int, int, int]:
    novice = status is TrainingStatus.NOVICE
    if goal is Goal.STRENGTH:
        if exercise_type is ExerciseType.COMPOUND:
            return 3, 6, 3 if novice else 2, 180
        return 6, 12, 3 if novice else 2, 120
    if goal in {Goal.HYPERTROPHY, Goal.MUSCLE_GAIN}:
        if exercise_type is ExerciseType.ISOLATION:
            return 10, 20, 3 if novice else 2, 90
        return 6, 12, 3 if novice else 2, 120
    if goal is Goal.MUSCULAR_ENDURANCE:
        return 12, 25, 3, 60
    if goal in {Goal.FAT_LOSS, Goal.BODY_RECOMPOSITION}:
        return 8, 15, 3 if novice else 2, 90
    return 6, 15, 3 if novice else 2, 90


def _estimate_minutes(sets: int, rest_seconds: int, warmup_sets: int) -> int:
    work = sets * 0.6
    rest = max(0, sets - 1) * rest_seconds / 60
    ramp_up = warmup_sets * 0.75
    return max(3, math.ceil(1 + work + rest + ramp_up))
