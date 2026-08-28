from dataclasses import dataclass, replace

from app.exercises.enums import ExerciseType, MuscleFocus, MuscleGroup
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.exercise_semantics import (
    is_leg_extension_primer,
    is_pull_up_family,
    is_push_up_family,
    is_squat_family,
)
from app.workouts.program_engine.prescription import estimate_exercise_minutes
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.safety import effective_caution_tags
from app.workouts.program_engine.schemas import (
    NormalizedProgramRequest,
    ProgramGenerationRequest,
    ProgrammedExercise,
    WorkoutDay,
)
from app.workouts.program_engine.session_targets import english_session_title_for_targets
from app.workouts.program_engine.supplemental_policy import (
    SUPPLEMENTAL_MUSCLES,
    is_supplemental_muscle,
    main_exercise_count,
    supplemental_reason_codes,
)

_STRICT_BLOCKS: dict[str, tuple[frozenset[MuscleGroup], ...]] = {
    "chest_triceps": (
        frozenset({MuscleGroup.CHEST}),
        frozenset({MuscleGroup.SHOULDERS}),
        frozenset({MuscleGroup.TRICEPS}),
    ),
    "back_biceps": (
        frozenset({MuscleGroup.BACK}),
        frozenset({MuscleGroup.SHOULDERS, MuscleGroup.TRAPS}),
        frozenset({MuscleGroup.BICEPS}),
    ),
    "shoulders_traps": (
        frozenset({MuscleGroup.SHOULDERS}),
        frozenset({MuscleGroup.TRAPS}),
    ),
    "quadriceps_calves": (
        frozenset({MuscleGroup.QUADRICEPS}),
        frozenset({MuscleGroup.CALVES}),
    ),
    "posterior_chain_core": (frozenset({MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES}),),
    "push": (
        frozenset({MuscleGroup.CHEST, MuscleGroup.SHOULDERS}),
        frozenset({MuscleGroup.TRICEPS}),
    ),
    "pull": (
        frozenset({MuscleGroup.BACK, MuscleGroup.SHOULDERS, MuscleGroup.TRAPS}),
        frozenset({MuscleGroup.BICEPS}),
    ),
}


@dataclass(frozen=True)
class _ExerciseUnit:
    exercises: tuple[ProgrammedExercise, ...]

    @property
    def muscles(self) -> tuple[MuscleGroup, ...]:
        return tuple(
            item.primary_muscle for item in self.exercises if item.primary_muscle is not None
        )

    @property
    def identifier(self) -> tuple[str, ...]:
        return tuple(sorted(str(item.exercise_id) for item in self.exercises))

    @property
    def original_order(self) -> int:
        return min(item.order for item in self.exercises)


def finalize_session_structure(
    days: tuple[WorkoutDay, ...],
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> tuple[WorkoutDay, ...]:
    policy = PriorityAllocationPolicy.for_request(request, ruleset)
    finalized: list[WorkoutDay] = []
    for day in days:
        block = _strict_block(day)
        original_units = _exercise_units(day.exercises)
        units = sorted(
            original_units,
            key=lambda unit: _unit_sort_key(
                unit,
                original_units,
                block,
                request,
                request.primary_goal,
                policy,
            ),
        )
        flat_exercises = tuple(item for unit in units for item in unit.exercises)

        compound_seen = False
        recalculated: list[ProgrammedExercise] = []
        for index, item in enumerate(flat_exercises, start=1):
            warmup_sets = 0
            if not compound_seen and item.exercise_type is ExerciseType.COMPOUND:
                compound_seen = True
                warmup_sets = (
                    ruleset.strength_compound_warmup_sets
                    if request.primary_goal is Goal.STRENGTH
                    else ruleset.first_compound_warmup_sets
                )
            if item.warmup_sets != warmup_sets:
                est_mins = estimate_exercise_minutes(
                    item.sets, item.rest_seconds, warmup_sets, ruleset
                )
                recalculated.append(
                    replace(item, order=index, warmup_sets=warmup_sets, estimated_minutes=est_mins)
                )
            else:
                recalculated.append(replace(item, order=index))

        exercises = tuple(recalculated)
        estimated_duration = (
            ruleset.general_warmup_minutes
            + sum(item.estimated_minutes for item in exercises)
            + (day.cardio.duration_minutes if day.cardio else 0)
        )

        finalized.append(
            replace(
                day,
                exercises=exercises,
                title=main_session_title(day.day_index, exercises),
                estimated_duration_minutes=estimated_duration,
            )
        )
    return tuple(finalized)


def main_session_title(
    day_index: int,
    exercises: tuple[ProgrammedExercise, ...],
) -> str:
    targets = tuple(
        dict.fromkeys(
            item.primary_muscle
            for item in exercises
            if item.primary_muscle is not None and not is_supplemental_muscle(item.primary_muscle)
        )
    )
    return english_session_title_for_targets(day_index, targets)


def session_structure_errors(
    day: WorkoutDay,
    goal: Goal,
    request: ProgramGenerationRequest | NormalizedProgramRequest | None = None,
) -> tuple[str, ...]:
    errors: list[str] = []
    if tuple(item.order for item in day.exercises) != tuple(range(1, len(day.exercises) + 1)):
        errors.append("SESSION_EXERCISE_ORDER_INVALID")

    supplemental_seen = False
    supplemental_count = 0
    for item in day.exercises:
        if is_supplemental_muscle(item.primary_muscle):
            supplemental_seen = True
            supplemental_count += 1
        elif supplemental_seen:
            errors.append("SUPPLEMENTAL_WORK_NOT_AT_SESSION_END")
    if supplemental_count > 2:
        errors.append("SUPPLEMENTAL_EXERCISE_LIMIT_EXCEEDED")

    block = _strict_block(day)
    units = _exercise_units(day.exercises)
    errors.extend(_semantic_ordering_errors(units, request))
    previous_block = -1
    phases_by_block: dict[int, int] = {}
    previous_phase = -1
    for unit in units:
        if all(is_supplemental_muscle(muscle) for muscle in unit.muscles):
            continue
        phase = _role_phase(unit, goal)
        if any(is_push_up_family(item) or is_pull_up_family(item) for item in unit.exercises):
            phase = 0
        elif any(
            is_leg_extension_primer(item) and _ordering_eligible(item, request)
            for item in unit.exercises
        ):
            phase = 0
        if block is None:
            if phase < previous_phase:
                errors.append("EXERCISE_TYPE_SEQUENCE_INVALID")
            previous_phase = max(previous_phase, phase)
            continue
        block_rank = _unit_block_rank(unit, block)
        if block_rank < previous_block:
            errors.append("STRICT_MUSCLE_BLOCK_ORDER_INVALID")
        previous_block = max(previous_block, block_rank)
        prior_phase = phases_by_block.get(block_rank, -1)
        if phase < prior_phase:
            errors.append("EXERCISE_TYPE_SEQUENCE_INVALID")
        phases_by_block[block_rank] = max(prior_phase, phase)

    if goal is Goal.STRENGTH:
        main_units = tuple(
            unit
            for unit in units
            if not all(is_supplemental_muscle(muscle) for muscle in unit.muscles)
        )
        if any(_contains_reason(unit, "STRENGTH_PRIMARY_COMPOUND") for unit in main_units) and (
            not main_units or not _contains_reason(main_units[0], "STRENGTH_PRIMARY_COMPOUND")
        ):
            errors.append("STRENGTH_PRIMARY_NOT_FIRST")
    return tuple(dict.fromkeys(errors))


def _exercise_units(
    exercises: tuple[ProgrammedExercise, ...],
) -> tuple[_ExerciseUnit, ...]:
    emitted: set[str] = set()
    units: list[_ExerciseUnit] = []
    for item in exercises:
        group = item.superset_group
        if group is None:
            units.append(_ExerciseUnit((item,)))
            continue
        if group in emitted:
            continue
        emitted.add(group)
        members = tuple(
            sorted(
                (member for member in exercises if member.superset_group == group),
                key=lambda member: (member.order, str(member.exercise_id)),
            )
        )
        units.append(_ExerciseUnit(members))
    return tuple(units)


def _unit_sort_key(
    unit: _ExerciseUnit,
    all_units: tuple[_ExerciseUnit, ...],
    block: tuple[frozenset[MuscleGroup], ...] | None,
    request: NormalizedProgramRequest,
    goal: Goal,
    policy: PriorityAllocationPolicy,
) -> tuple[object, ...]:
    supplemental = all(is_supplemental_muscle(muscle) for muscle in unit.muscles)
    main_muscles = tuple(muscle for muscle in unit.muscles if not is_supplemental_muscle(muscle))
    priority = min(
        (policy.precedence_key(muscle) for muscle in main_muscles),
        default=(4, 0, ""),
    )
    if priority[0] >= 3:
        priority = (3, 0, "")
    return (
        1 if supplemental else 0,
        _semantic_order_rank(unit, all_units, request),
        _unit_block_rank(unit, block) if block is not None else 0,
        _role_phase(unit, goal),
        priority,
        unit.original_order,
        unit.identifier,
    )


def _semantic_order_rank(
    unit: _ExerciseUnit,
    all_units: tuple[_ExerciseUnit, ...],
    request: NormalizedProgramRequest,
) -> int:
    if _session_has_meaningful_muscle(all_units, MuscleGroup.CHEST) and any(
        is_push_up_family(item) for item in unit.exercises
    ):
        return 0
    if _session_has_meaningful_back(all_units) and any(
        is_pull_up_family(item) for item in unit.exercises
    ):
        return 0
    has_safe_primer = any(
        is_leg_extension_primer(item) and _ordering_eligible(item, request)
        for candidate_unit in all_units
        for item in candidate_unit.exercises
    )
    if has_safe_primer and any(is_leg_extension_primer(item) for item in unit.exercises):
        return 1
    return 2


def _session_has_meaningful_muscle(units: tuple[_ExerciseUnit, ...], muscle: MuscleGroup) -> bool:
    return any(
        item.primary_muscle is muscle
        or muscle in item.secondary_muscles
        or (
            muscle is MuscleGroup.CHEST
            and item.muscle_focus
            in {
                MuscleFocus.GENERAL_CHEST,
                MuscleFocus.UPPER_CHEST,
                MuscleFocus.MID_CHEST,
                MuscleFocus.LOWER_CHEST,
            }
        )
        for unit in units
        for item in unit.exercises
    )


def _session_has_meaningful_back(units: tuple[_ExerciseUnit, ...]) -> bool:
    return any(
        item.primary_muscle is MuscleGroup.BACK
        or MuscleGroup.BACK in item.secondary_muscles
        or item.muscle_focus
        in {
            MuscleFocus.GENERAL_BACK,
            MuscleFocus.LATS,
            MuscleFocus.LOWER_BACK,
            MuscleFocus.MID_BACK_RHOMBOIDS,
            MuscleFocus.UPPER_BACK,
        }
        for unit in units
        for item in unit.exercises
    )


def _ordering_eligible(
    item: ProgrammedExercise,
    request: NormalizedProgramRequest | ProgramGenerationRequest | None,
) -> bool:
    if request is None:
        return True
    if isinstance(request, NormalizedProgramRequest):
        blocked_patterns = set(request.constraints.blocked_movement_patterns)
        blocked_cautions = set(request.constraints.blocked_caution_tags)
    else:
        blocked_patterns = set(request.blocked_movement_patterns)
        blocked_cautions = set(request.blocked_caution_tags)
        for limitation in request.injuries_and_limitations:
            blocked_patterns = blocked_patterns | limitation.blocked_movement_patterns
            blocked_cautions = blocked_cautions | limitation.blocked_caution_tags
    return not (
        item.movement_pattern in blocked_patterns
        or effective_caution_tags(item).intersection(blocked_cautions)
    )


def _semantic_ordering_errors(
    units: tuple[_ExerciseUnit, ...],
    request: ProgramGenerationRequest | NormalizedProgramRequest | None,
) -> list[str]:
    main_units = tuple(
        unit for unit in units if not all(is_supplemental_muscle(muscle) for muscle in unit.muscles)
    )
    if not main_units:
        return []
    errors: list[str] = []
    first_unit = main_units[0]
    first_has_upper_opener = any(
        is_push_up_family(item) or is_pull_up_family(item) for item in first_unit.exercises
    )
    if _session_has_meaningful_muscle(units, MuscleGroup.CHEST):
        push_index = next(
            (
                index
                for index, unit in enumerate(main_units)
                if any(is_push_up_family(item) for item in unit.exercises)
            ),
            None,
        )
        if push_index is not None and push_index != 0 and not first_has_upper_opener:
            errors.append("PUSH_UP_OPENER_ORDER_INVALID")
    if _session_has_meaningful_back(units):
        pull_index = next(
            (
                index
                for index, unit in enumerate(main_units)
                if any(is_pull_up_family(item) for item in unit.exercises)
            ),
            None,
        )
        if pull_index is not None and pull_index != 0 and not first_has_upper_opener:
            errors.append("PULL_UP_OPENER_ORDER_INVALID")
    primer_indices = [
        index
        for index, unit in enumerate(main_units)
        if any(
            is_leg_extension_primer(item) and _ordering_eligible(item, request)
            for item in unit.exercises
        )
    ]
    squat_indices = [
        index
        for index, unit in enumerate(main_units)
        if any(is_squat_family(item) for item in unit.exercises)
    ]
    if primer_indices and squat_indices and min(primer_indices) > min(squat_indices):
        errors.append("LEG_EXTENSION_PRIMER_ORDER_INVALID")
    return errors


def _role_phase(unit: _ExerciseUnit, goal: Goal) -> int:
    if goal is Goal.STRENGTH:
        if _contains_reason(unit, "STRENGTH_PRIMARY_COMPOUND"):
            return 0
        if _contains_reason(unit, "PRIMARY_WORKING_COMPOUND"):
            return 1
        if _contains_reason(unit, "STRENGTH_SECONDARY_COMPOUND") or any(
            item.exercise_type is ExerciseType.COMPOUND for item in unit.exercises
        ):
            return 2
        return 3
    if _contains_reason(unit, "PRIMARY_WORKING_COMPOUND"):
        return 0
    if any(item.exercise_type is ExerciseType.COMPOUND for item in unit.exercises):
        return 1
    return 2


def _contains_reason(unit: _ExerciseUnit, reason: str) -> bool:
    return any(reason in item.reason_codes for item in unit.exercises)


def _unit_block_rank(
    unit: _ExerciseUnit,
    block: tuple[frozenset[MuscleGroup], ...] | None,
) -> int:
    if block is None:
        return 0
    ranks = tuple(
        index
        for muscle in unit.muscles
        if not is_supplemental_muscle(muscle)
        for index, muscles in enumerate(block)
        if muscle in muscles
    )
    return min(ranks, default=len(block))


def _strict_block(day: WorkoutDay) -> tuple[frozenset[MuscleGroup], ...] | None:
    if day.focus in _STRICT_BLOCKS:
        return _STRICT_BLOCKS[day.focus]
    if not day.focus.startswith("template_reference"):
        return None
    if day.template_structure_focus in _STRICT_BLOCKS:
        return _STRICT_BLOCKS[day.template_structure_focus]
    return None


__all__ = [
    "SUPPLEMENTAL_MUSCLES",
    "finalize_session_structure",
    "main_exercise_count",
    "main_session_title",
    "session_structure_errors",
    "supplemental_reason_codes",
]
