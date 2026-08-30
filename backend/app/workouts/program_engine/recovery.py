from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from enum import StrEnum
from itertools import combinations

from app.exercises.enums import ExerciseType, MuscleGroup
from app.workouts.program_engine.constraint_classification import ConstraintClass
from app.workouts.program_engine.duration_policy import (
    calculate_main_training_minutes,
    get_session_duration_policy,
    get_session_exercise_count_policy,
)
from app.workouts.program_engine.enums import LoadLimit
from app.workouts.program_engine.exercise_semantics import has_near_equivalent
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    NormalizedProgramRequest,
    ProgrammedExercise,
    SplitPlan,
    WorkoutDay,
)
from app.workouts.program_engine.session_coherence import SessionCoherence
from app.workouts.program_engine.supplemental_policy import (
    is_supplemental_muscle,
    main_exercise_count,
    supplemental_muscle_fits_focus,
)
from app.workouts.program_engine.volume_policy import session_hard_volume_cap


class ExposureLoad(StrEnum):
    LIGHT = "light"
    MODERATE = "moderate"
    HIGH = "high"


class ExposureSource(StrEnum):
    """How a muscle was loaded during one session."""

    DIRECT = "direct"
    SECONDARY_ONLY = "secondary_only"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class MuscleExposureDetails:
    direct_sets: float
    secondary_effective_sets: float
    total_effective_sets: float
    source: ExposureSource
    load: ExposureLoad
    high_load_evidence: bool
    fatigue_evidence: bool


@dataclass(frozen=True, slots=True)
class RecoveryConflict:
    muscle: MuscleGroup
    day_a: int
    day_b: int
    day_a_exposure: ExposureLoad
    day_b_exposure: ExposureLoad
    day_a_source: ExposureSource
    day_b_source: ExposureSource
    day_a_direct_sets: float
    day_b_direct_sets: float
    day_a_secondary_effective_sets: float
    day_b_secondary_effective_sets: float
    actual_gap_days: int
    required_gap_days: int
    constraint_class: ConstraintClass


@dataclass(frozen=True, slots=True)
class RecoveryAssessment:
    conflicts: tuple[RecoveryConflict, ...]

    @property
    def is_valid(self) -> bool:
        return not self.hard_conflicts and not self.repairable_conflicts

    @property
    def is_safe(self) -> bool:
        """Return whether no genuinely unsafe direct-recovery conflict remains."""
        return not self.hard_conflicts

    @property
    def hard_conflicts(self) -> tuple[RecoveryConflict, ...]:
        return tuple(
            conflict
            for conflict in self.conflicts
            if conflict.constraint_class is ConstraintClass.HARD
        )

    @property
    def repairable_conflicts(self) -> tuple[RecoveryConflict, ...]:
        return tuple(
            conflict
            for conflict in self.conflicts
            if conflict.constraint_class is ConstraintClass.REPAIRABLE
        )

    @property
    def soft_conflicts(self) -> tuple[RecoveryConflict, ...]:
        return tuple(
            conflict
            for conflict in self.conflicts
            if conflict.constraint_class is ConstraintClass.SOFT
        )

    def decision_trace(
        self,
        *,
        repair_attempts: tuple[str, ...] = (),
        final_result: str | None = None,
    ) -> dict[str, object]:
        if self.hard_conflicts:
            status = "hard_conflict"
        elif self.repairable_conflicts:
            status = "repairable_conflict"
        elif self.soft_conflicts:
            status = "soft_warning"
        else:
            status = "valid"
        return {
            "status": status,
            "repair_attempts": repair_attempts,
            "final_result": final_result or ("repaired" if self.is_valid else "unrepaired"),
            "conflicts": tuple(_conflict_trace(conflict) for conflict in self.conflicts),
        }


def _conflict_trace(conflict: RecoveryConflict) -> dict[str, object]:
    return {
        "muscle": conflict.muscle.value,
        "day_a": conflict.day_a,
        "day_b": conflict.day_b,
        "day_a_exposure": conflict.day_a_exposure.value,
        "day_b_exposure": conflict.day_b_exposure.value,
        "day_a_source": conflict.day_a_source.value,
        "day_b_source": conflict.day_b_source.value,
        "day_a_direct_sets": conflict.day_a_direct_sets,
        "day_b_direct_sets": conflict.day_b_direct_sets,
        "day_a_secondary_effective_sets": conflict.day_a_secondary_effective_sets,
        "day_b_secondary_effective_sets": conflict.day_b_secondary_effective_sets,
        "actual_gap_days": conflict.actual_gap_days,
        "required_gap_days": conflict.required_gap_days,
        "constraint_class": conflict.constraint_class.value,
    }


def direct_muscles(day: WorkoutDay) -> frozenset[MuscleGroup]:
    return frozenset(
        item.primary_muscle
        for item in day.exercises
        if item.primary_muscle is not None and not is_supplemental_muscle(item.primary_muscle)
    )


def classify_muscle_exposures(
    day: WorkoutDay,
    ruleset: ProgramRuleset,
) -> dict[MuscleGroup, ExposureLoad]:
    return {
        muscle: details.load
        for muscle, details in classify_muscle_exposure_details(day, ruleset).items()
    }


def classify_muscle_exposure_details(
    day: WorkoutDay,
    ruleset: ProgramRuleset,
) -> dict[MuscleGroup, MuscleExposureDetails]:
    direct_sets: Counter[MuscleGroup] = Counter()
    secondary_effective_sets: defaultdict[MuscleGroup, float] = defaultdict(float)
    high_load_muscles: set[MuscleGroup] = set()
    fatigue_muscles: set[MuscleGroup] = set()
    for exercise in day.exercises:
        if exercise.primary_muscle is not None and not is_supplemental_muscle(
            exercise.primary_muscle
        ):
            direct_sets[exercise.primary_muscle] += exercise.sets
            if "STRENGTH_PRIMARY_COMPOUND" in exercise.reason_codes:
                high_load_muscles.add(exercise.primary_muscle)
                fatigue_muscles.add(exercise.primary_muscle)
            if exercise.axial_loading_level is LoadLimit.HIGH:
                high_load_muscles.add(exercise.primary_muscle)
                fatigue_muscles.add(exercise.primary_muscle)
        for muscle in exercise.secondary_muscles:
            if is_supplemental_muscle(muscle):
                continue
            secondary_effective_sets[muscle] += exercise.sets * ruleset.secondary_set_credit
            if exercise.axial_loading_level is LoadLimit.HIGH:
                fatigue_muscles.add(muscle)

    muscles = set(direct_sets).union(secondary_effective_sets)
    details: dict[MuscleGroup, MuscleExposureDetails] = {}
    for muscle in sorted(muscles, key=lambda item: item.value):
        direct = float(direct_sets[muscle])
        secondary = secondary_effective_sets[muscle]
        total = direct + secondary
        if direct and secondary:
            source = ExposureSource.MIXED
        elif direct:
            source = ExposureSource.DIRECT
        else:
            source = ExposureSource.SECONDARY_ONLY
        high_load_evidence = muscle in high_load_muscles
        # Secondary work is deliberately not equivalent to direct work. It can
        # still be high when its effective dose is genuinely large.
        if (
            high_load_evidence
            or direct >= ruleset.recovery_high_direct_sets * 2
            or secondary >= ruleset.recovery_high_effective_sets
        ):
            load = ExposureLoad.HIGH
        elif (
            direct > ruleset.recovery_light_max_direct_sets
            or total >= ruleset.recovery_moderate_effective_sets
        ):
            load = ExposureLoad.MODERATE
        else:
            load = ExposureLoad.LIGHT
        details[muscle] = MuscleExposureDetails(
            direct_sets=direct,
            secondary_effective_sets=secondary,
            total_effective_sets=total,
            source=source,
            load=load,
            high_load_evidence=high_load_evidence,
            fatigue_evidence=muscle in fatigue_muscles,
        )
    return details


def recovery_spacing_is_valid(
    days: tuple[WorkoutDay, ...],
    ruleset: ProgramRuleset,
) -> bool:
    return assess_recovery_spacing(days, ruleset).is_safe


def assess_recovery_spacing(
    days: tuple[WorkoutDay, ...],
    ruleset: ProgramRuleset,
) -> RecoveryAssessment:
    scheduled = sorted(
        ((day.weekday, day) for day in days if day.weekday is not None),
        key=lambda item: item[0],
    )
    if len(scheduled) <= 1:
        return RecoveryAssessment(())
    circular = scheduled + [(scheduled[0][0] + ruleset.days_per_week, scheduled[0][1])]
    conflicts: list[RecoveryConflict] = []
    for current, following in zip(circular, circular[1:], strict=False):
        current_exposures = classify_muscle_exposure_details(current[1], ruleset)
        following_exposures = classify_muscle_exposure_details(following[1], ruleset)
        for muscle in sorted(
            set(current_exposures).intersection(following_exposures),
            key=lambda item: item.value,
        ):
            current_details = current_exposures[muscle]
            following_details = following_exposures[muscle]
            required, constraint_class = _pair_recovery_requirement(
                current_details, following_details, ruleset
            )
            actual_gap = following[0] - current[0]
            if required > actual_gap:
                conflicts.append(
                    RecoveryConflict(
                        muscle=muscle,
                        day_a=current[0] % ruleset.days_per_week,
                        day_b=following[0] % ruleset.days_per_week,
                        day_a_exposure=current_details.load,
                        day_b_exposure=following_details.load,
                        day_a_source=current_details.source,
                        day_b_source=following_details.source,
                        day_a_direct_sets=current_details.direct_sets,
                        day_b_direct_sets=following_details.direct_sets,
                        day_a_secondary_effective_sets=current_details.secondary_effective_sets,
                        day_b_secondary_effective_sets=following_details.secondary_effective_sets,
                        actual_gap_days=actual_gap,
                        required_gap_days=required,
                        constraint_class=constraint_class,
                    )
                )
    return RecoveryAssessment(tuple(conflicts))


def _pair_recovery_requirement(
    current: MuscleExposureDetails,
    following: MuscleExposureDetails,
    ruleset: ProgramRuleset,
) -> tuple[int, ConstraintClass]:
    sources = {current.source, following.source}
    if sources == {ExposureSource.SECONDARY_ONLY}:
        # Secondary-to-secondary overlap is never independently fatal. The
        # credited work remains available to volume accounting elsewhere.
        return ruleset.recovery_light_gap_days, ConstraintClass.SOFT
    if ExposureSource.SECONDARY_ONLY in sources:
        secondary = (
            current
            if current.source is ExposureSource.SECONDARY_ONLY
            else following
        )
        # Small secondary overlap is normal in professional splits. Escalate
        # only when the secondary dose is at least a moderate direct-equivalent
        # or has explicit high-load evidence.
        substantial = (
            secondary.secondary_effective_sets >= ruleset.recovery_moderate_effective_sets
            or secondary.high_load_evidence
            or secondary.fatigue_evidence
        )
        if not substantial:
            return ruleset.recovery_light_gap_days, ConstraintClass.SOFT
        return ruleset.minimum_recovery_gap_days, ConstraintClass.REPAIRABLE
    if current.load is ExposureLoad.HIGH and following.load is ExposureLoad.HIGH:
        return ruleset.minimum_recovery_gap_days, ConstraintClass.HARD
    if ExposureLoad.HIGH in {current.load, following.load}:
        return ruleset.minimum_recovery_gap_days, ConstraintClass.REPAIRABLE
    if current.load is ExposureLoad.MODERATE and following.load is ExposureLoad.MODERATE:
        return ruleset.minimum_recovery_gap_days, ConstraintClass.REPAIRABLE
    return ruleset.recovery_light_gap_days, ConstraintClass.SOFT


def repair_recovery_weekdays(
    split: SplitPlan,
    days: tuple[WorkoutDay, ...],
    ruleset: ProgramRuleset,
) -> tuple[SplitPlan, tuple[WorkoutDay, ...], tuple[str, ...]]:
    if assess_recovery_spacing(days, ruleset).is_valid:
        return split, days, ()
    original = tuple(day.weekday for day in days)
    if any(weekday is None for weekday in original):
        return split, days, ("RECOVERY_WEEKDAY_REPAIR_UNAVAILABLE",)
    original_days = tuple(int(weekday) for weekday in original if weekday is not None)
    options: list[tuple[int, tuple[int, ...], tuple[WorkoutDay, ...]]] = []
    for weekdays in combinations(range(ruleset.days_per_week), len(days)):
        scheduled = tuple(
            replace(day, weekday=weekday) for day, weekday in zip(days, weekdays, strict=True)
        )
        if assess_recovery_spacing(scheduled, ruleset).is_valid:
            distance = sum(
                abs(candidate - current)
                for candidate, current in zip(weekdays, original_days, strict=True)
            )
            options.append((distance, weekdays, scheduled))
    if not options:
        return split, days, ("RECOVERY_WEEKDAY_REPAIR_UNAVAILABLE",)
    _, weekdays, scheduled = min(options, key=lambda item: (item[0], item[1]))
    repaired_split = replace(
        split,
        weekdays=weekdays,
        reason_codes=split.reason_codes
        + (
            "RECOVERY_WEEKDAYS_REARRANGED_FOR_DIRECT_MUSCLE_OVERLAP",
            "RECOVERY_WEEKDAYS_REARRANGED_FOR_EXPOSURE_LOAD",
        ),
    )
    return (
        repaired_split,
        scheduled,
        (
            "RECOVERY_WEEKDAYS_REARRANGED_FOR_DIRECT_MUSCLE_OVERLAP",
            "RECOVERY_WEEKDAYS_REARRANGED_FOR_EXPOSURE_LOAD",
        ),
    )


def repair_recovery_accessory_distribution(
    days: tuple[WorkoutDay, ...],
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> tuple[tuple[WorkoutDay, ...], tuple[str, ...]]:
    """Move optional isolation work only when every hard contract remains valid."""
    if assess_recovery_spacing(days, ruleset).is_valid:
        return days, ()
    count_policy = get_session_exercise_count_policy(
        request.source.session_duration_minutes, ruleset
    )
    duration_policy = get_session_duration_policy(request.source.session_duration_minutes)
    for source_index, source in enumerate(days):
        for item_index, item in enumerate(source.exercises):
            if not _is_movable_recovery_accessory(item):
                continue
            muscle = item.primary_muscle
            if muscle is None:
                continue
            source_exercises = source.exercises[:item_index] + source.exercises[item_index + 1 :]
            ranked_recipients: list[
                tuple[tuple[int, int, int, int, str], int, int, WorkoutDay]
            ] = []
            for recipient_index, recipient in enumerate(days):
                if recipient_index == source_index or not _recipient_supports_muscle(
                    recipient, muscle
                ):
                    continue
                coherence = SessionCoherence.from_workout_day(recipient)
                placement = coherence.placement_rank(
                    muscle,
                    existing_exposure=any(
                        exercise.primary_muscle is muscle for exercise in recipient.exercises
                    ),
                )
                if placement[0] >= 3:
                    continue
                ranked_recipients.append(
                    (placement, recipient.day_index, recipient_index, recipient)
                )
            for _, _, recipient_index, recipient in sorted(
                ranked_recipients,
                key=lambda candidate: (candidate[0], candidate[1], candidate[2]),
            ):
                recipient_exposure = classify_muscle_exposure_details(recipient, ruleset).get(
                    muscle
                )
                if recipient_exposure is not None and recipient_exposure.load is ExposureLoad.HIGH:
                    continue
                if has_near_equivalent(item, recipient.exercises):
                    continue
                recipient_exercises = (*recipient.exercises, item)
                candidate_days = list(days)
                candidate_days[source_index] = replace(
                    source, exercises=_reorder_exercises(source_exercises)
                )
                candidate_days[recipient_index] = replace(
                    recipient, exercises=_reorder_exercises(recipient_exercises)
                )
                scheduled = tuple(candidate_days)
                if not all(
                    count_policy.contains(main_exercise_count(day.exercises))
                    and duration_policy.contains(calculate_main_training_minutes(day))
                    and _within_session_hard_volume(day, request)
                    for day in scheduled
                ):
                    continue
                if assess_recovery_spacing(scheduled, ruleset).is_valid:
                    return scheduled, ("RECOVERY_OPTIONAL_ISOLATION_REDISTRIBUTED",)
    return days, ("RECOVERY_OPTIONAL_ISOLATION_REDISTRIBUTION_UNAVAILABLE",)


def _recipient_supports_muscle(day: WorkoutDay, muscle: MuscleGroup) -> bool:
    if is_supplemental_muscle(muscle):
        return supplemental_muscle_fits_focus(
            muscle,
            day.template_structure_focus if day.template_target_muscles else day.focus,
        )
    return SessionCoherence.from_workout_day(day).allows_direct(muscle)


def _within_session_hard_volume(
    day: WorkoutDay,
    request: NormalizedProgramRequest,
) -> bool:
    direct_sets: Counter[MuscleGroup] = Counter()
    for item in day.exercises:
        if item.primary_muscle is not None:
            direct_sets[item.primary_muscle] += item.sets
    maximum = session_hard_volume_cap(request.source.training_age_months)
    return all(sets <= maximum for sets in direct_sets.values())


def _is_movable_recovery_accessory(item: ProgrammedExercise) -> bool:
    exercise_type = item.exercise_type
    primary_muscle = item.primary_muscle
    reason_codes = item.reason_codes
    return (
        exercise_type is ExerciseType.ISOLATION
        and primary_muscle is not None
        and not any("REQUIRED" in code or "PRIORITY" in code for code in reason_codes)
    )


def _reorder_exercises(
    exercises: tuple[ProgrammedExercise, ...],
) -> tuple[ProgrammedExercise, ...]:
    return tuple(replace(item, order=index) for index, item in enumerate(exercises, start=1))
