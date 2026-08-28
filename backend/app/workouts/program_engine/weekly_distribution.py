"""Deterministic whole-exercise redistribution across resistance days."""

from collections import Counter
from dataclasses import dataclass, fields, replace
from typing import cast

from app.workouts.program_engine.duration_policy import (
    calculate_resistance_minutes,
    effective_main_exercise_floor,
    get_session_duration_policy,
)
from app.workouts.program_engine.effective_volume import calculate_effective_volume
from app.workouts.program_engine.exercise_semantics import has_near_equivalent
from app.workouts.program_engine.recovery import recovery_spacing_is_valid
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    ProgrammedExercise,
    WorkoutDay,
)
from app.workouts.program_engine.session_builder import exercise_fits_focus
from app.workouts.program_engine.session_structure import (
    finalize_session_structure,
    session_structure_errors,
)
from app.workouts.program_engine.supplemental_policy import (
    is_supplemental_muscle,
    main_exercise_count,
    supplemental_muscle_fits_focus,
)
from app.workouts.program_engine.template_sessions import template_adaptation_priority

_IGNORED_FIELDS = frozenset({"order", "warmup_sets", "estimated_minutes"})


@dataclass(frozen=True)
class WeeklyDistributionResult:
    days: tuple[WorkoutDay, ...]
    status: str
    reason_codes: tuple[str, ...]
    moved_exercise_ids: tuple[str, ...]
    before_exercise_counts: tuple[int, ...]
    after_exercise_counts: tuple[int, ...]
    before_direct_sets_by_muscle: dict[str, int]
    after_direct_sets_by_muscle: dict[str, int]
    before_effective_sets_by_muscle: dict[str, float]
    after_effective_sets_by_muscle: dict[str, float]
    before_exercise_ids: tuple[str, ...]

    @property
    def metrics(self) -> dict[str, object]:
        metrics = {key: value for key, value in vars(self).items() if key != "days"}
        return metrics | {"moves_applied": len(self.moved_exercise_ids)}


def redistribute_weekly_exercises(
    days: tuple[WorkoutDay, ...],
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
    *,
    preserve_template_core_structure: bool = False,
) -> WeeklyDistributionResult:
    preserve_template_core_structure |= any(
        day.focus.startswith("template_reference") for day in days
    )
    before_counts = _exercise_counts(days)
    before_direct, before_effective = _volume(days, ruleset)
    current, moved = days, []
    while (
        proposal := _best_improving_move(
            current,
            request,
            ruleset,
            preserve_template_core_structure=preserve_template_core_structure,
        )
    ) is not None:
        current, moved_item = proposal
        moved.append(str(moved_item.exercise_id))

    after_counts = _exercise_counts(current)
    status, reason_codes = (
        ("applied", ("WEEKLY_REDISTRIBUTION_APPLIED",))
        if moved
        else ("not_needed", ("WEEKLY_REDISTRIBUTION_ALREADY_BALANCED",))
        if _balance_score(before_counts)[0] <= 1
        else ("constrained", ("WEEKLY_REDISTRIBUTION_NO_SAFE_IMPROVING_MOVE",))
    )
    after_direct, after_effective = _volume(current, ruleset)
    return WeeklyDistributionResult(
        days=current,
        status=status,
        reason_codes=reason_codes,
        moved_exercise_ids=tuple(moved),
        before_exercise_counts=before_counts,
        after_exercise_counts=after_counts,
        before_direct_sets_by_muscle=before_direct,
        after_direct_sets_by_muscle=after_direct,
        before_effective_sets_by_muscle=before_effective,
        after_effective_sets_by_muscle=after_effective,
        before_exercise_ids=tuple(str(item.exercise_id) for day in days for item in day.exercises),
    )


def _best_improving_move(
    days: tuple[WorkoutDay, ...],
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
    *,
    preserve_template_core_structure: bool,
) -> tuple[tuple[WorkoutDay, ...], ProgrammedExercise] | None:
    counts = _exercise_counts(days)
    current_score = _balance_score(counts)
    smallest_count = min(counts, default=0)
    recipients = tuple(index for index, count in enumerate(counts) if count == smallest_count)
    donors = tuple(index for index, count in enumerate(counts) if count > smallest_count)
    proposals: list[tuple[tuple[object, ...], tuple[WorkoutDay, ...], ProgrammedExercise]] = []
    floor = effective_main_exercise_floor(request.source.session_duration_minutes, ruleset)
    for recipient_index in recipients:
        recipient = days[recipient_index]
        for donor_index in donors:
            donor = days[donor_index]
            donor_main_count = main_exercise_count(donor.exercises)
            if len(donor.exercises) <= floor or donor_main_count < floor:
                continue
            for exercise_index, exercise in enumerate(donor.exercises):
                if donor_main_count == floor and not is_supplemental_muscle(
                    exercise.primary_muscle
                ):
                    continue
                if not _movable(
                    exercise,
                    preserve_template_core_structure=preserve_template_core_structure,
                ):
                    continue
                if not _fits_recipient_focus(exercise, recipient):
                    continue
                if has_near_equivalent(exercise, recipient.exercises):
                    continue
                candidate_days = _proposed_days(
                    days,
                    donor_index,
                    exercise_index,
                    recipient_index,
                    exercise,
                )
                try:
                    finalized = finalize_session_structure(candidate_days, request, ruleset)
                except (TypeError, ValueError):
                    continue
                if _balance_score(_exercise_counts(finalized)) >= current_score:
                    continue
                if not _invariants_hold(
                    days,
                    finalized,
                    request,
                    ruleset,
                    recipient_index=recipient_index,
                    moved_id=str(exercise.exercise_id),
                ):
                    continue
                key = (
                    _balance_score(_exercise_counts(finalized)),
                    days[recipient_index].day_index,
                    days[donor_index].day_index,
                    exercise.order,
                    str(exercise.exercise_id),
                )
                proposals.append((key, finalized, exercise))
    if not proposals:
        return None
    _, selected_days, selected_exercise = min(proposals, key=lambda item: item[0])
    return selected_days, selected_exercise


def _proposed_days(
    days: tuple[WorkoutDay, ...],
    donor_index: int,
    exercise_index: int,
    recipient_index: int,
    exercise: ProgrammedExercise,
) -> tuple[WorkoutDay, ...]:
    proposed = list(days)
    donor = days[donor_index]
    proposed[donor_index] = replace(
        donor, exercises=donor.exercises[:exercise_index] + donor.exercises[exercise_index + 1 :]
    )
    proposed[recipient_index] = replace(
        proposed[recipient_index], exercises=(*proposed[recipient_index].exercises, exercise)
    )
    return tuple(proposed)


def _invariants_hold(
    before: tuple[WorkoutDay, ...],
    after: tuple[WorkoutDay, ...],
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
    *,
    recipient_index: int,
    moved_id: str,
) -> bool:
    if (
        tuple((day.day_index, day.weekday) for day in before)
        != tuple((day.day_index, day.weekday) for day in after)
        or _exercise_signatures(before) != _exercise_signatures(after)
        or _volume(before, ruleset) != _volume(after, ruleset)
        or any(
            sum(item.sets for item in day.exercises if item.primary_muscle is muscle)
            > ruleset.max_sets_per_muscle_per_session
            for day in after
            for muscle in {item.primary_muscle for item in day.exercises if item.primary_muscle}
        )
        or not recovery_spacing_is_valid(after, ruleset)
        or not _duration_is_safe(before, after, request, ruleset)
        or any(session_structure_errors(day, request.primary_goal, request) for day in after)
        or any(
            has_near_equivalent(item, day.exercises[index + 1 :])
            for day in after
            for index, item in enumerate(day.exercises)
        )
    ):
        return False
    return any(str(item.exercise_id) == moved_id for item in after[recipient_index].exercises)


def _duration_is_safe(
    before: tuple[WorkoutDay, ...],
    after: tuple[WorkoutDay, ...],
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> bool:
    policy = get_session_duration_policy(request.source.session_duration_minutes)
    for prior, candidate in zip(before, after, strict=True):
        prior_minutes = calculate_resistance_minutes(prior, ruleset.general_warmup_minutes)
        candidate_minutes = calculate_resistance_minutes(candidate, ruleset.general_warmup_minutes)
        if candidate_minutes > policy.core_preservation_maximum_minutes or (
            prior_minutes <= policy.maximum_minutes and candidate_minutes > policy.maximum_minutes
        ):
            return False
    return True


def _movable(
    exercise: ProgrammedExercise,
    *,
    preserve_template_core_structure: bool,
) -> bool:
    return (
        exercise.superset_group is None
        and exercise.order != 1
        and "STRENGTH_PRIMARY_COMPOUND" not in exercise.reason_codes
        and (not preserve_template_core_structure or not _template_origin(exercise))
    )


def _template_origin(exercise: ProgrammedExercise) -> bool:
    return template_adaptation_priority(exercise) is not None or any(
        code.startswith("TEMPLATE_") for code in exercise.reason_codes
    )


def _fits_recipient_focus(exercise: ProgrammedExercise, day: WorkoutDay) -> bool:
    if day.focus.startswith("template_reference") and day.template_target_muscles:
        return exercise.primary_muscle in day.template_target_muscles
    if is_supplemental_muscle(exercise.primary_muscle):
        return exercise.primary_muscle is not None and supplemental_muscle_fits_focus(
            exercise.primary_muscle,
            day.template_structure_focus
            if day.focus.startswith("template_reference")
            else day.focus,
        )
    return exercise_fits_focus(cast(ExerciseCandidate, exercise), day.focus)


def _exercise_counts(days: tuple[WorkoutDay, ...]) -> tuple[int, ...]:
    return tuple(len(day.exercises) for day in days)


def _balance_score(counts: tuple[int, ...]) -> tuple[int, int, tuple[int, ...]]:
    if not counts:
        return (0, 0, ())
    total, size = sum(counts), len(counts)
    variance = sum((count * size - total) ** 2 for count in counts)
    return (max(counts) - min(counts), variance, tuple(sorted(counts, reverse=True)))


def _volume(
    days: tuple[WorkoutDay, ...], ruleset: ProgramRuleset
) -> tuple[dict[str, int], dict[str, float]]:
    effective = calculate_effective_volume((i for d in days for i in d.exercises), ruleset)
    return effective.direct_sets_by_muscle, effective.effective_sets_by_muscle


def _exercise_signatures(days: tuple[WorkoutDay, ...]) -> Counter[tuple[object, ...]]:
    return Counter(_prescription_signature(item) for day in days for item in day.exercises)


def _prescription_signature(item: ProgrammedExercise) -> tuple[object, ...]:
    return tuple(getattr(item, f.name) for f in fields(item) if f.name not in _IGNORED_FIELDS)
