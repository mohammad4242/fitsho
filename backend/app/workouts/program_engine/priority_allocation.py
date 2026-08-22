from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.body_analysis import body_analysis_priority_muscles
from app.workouts.program_engine.enums import (
    Goal,
    PhysicalJobDemand,
    RecoveryRating,
    TrainingStatus,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import NormalizedProgramRequest
from app.workouts.program_engine.slot_compatibility import focus_scope


@dataclass(frozen=True)
class PriorityAllocationPolicy:
    """Deterministic frequency and placement policy for requested priorities."""

    priorities: tuple[MuscleGroup, ...]
    preferred_frequency: int
    recovery_limited: bool
    minimum_recovery_gap_days: int

    @classmethod
    def for_request(
        cls,
        request: NormalizedProgramRequest,
        ruleset: ProgramRuleset,
    ) -> PriorityAllocationPolicy:
        priorities = tuple(
            sorted(
                request.source.priority_muscles | body_analysis_priority_muscles(request, ruleset),
                key=lambda muscle: muscle.value,
            )
        )
        available_days = min(request.resistance_training_days, ruleset.max_resistance_days)
        recovery_limited = _recovery_is_limited(request)
        exposure_capacity = min(
            ruleset.maximum_direct_sessions_per_muscle_per_week,
            available_days // max(ruleset.minimum_recovery_gap_days, 1),
        )
        goal_supports_frequency = request.primary_goal in {
            Goal.HYPERTROPHY,
            Goal.MUSCLE_GAIN,
            Goal.STRENGTH,
        }
        if (
            not priorities
            or recovery_limited
            or not goal_supports_frequency
            or request.training_status is TrainingStatus.NOVICE
        ):
            preferred_frequency = min(exposure_capacity, 1)
        else:
            preferred_frequency = exposure_capacity
        return cls(
            priorities=priorities,
            preferred_frequency=preferred_frequency,
            recovery_limited=recovery_limited,
            minimum_recovery_gap_days=ruleset.minimum_recovery_gap_days,
        )

    def split_adjustment(
        self, focuses: tuple[str, ...], ruleset: ProgramRuleset
    ) -> tuple[int, tuple[str, ...]]:
        if not self.priorities or self.preferred_frequency <= 0:
            return 0, ()
        exposure_counts = {
            muscle: sum(self.focus_trains_muscle(focus, muscle) for focus in focuses)
            for muscle in self.priorities
        }
        fulfilled = sum(
            min(exposure_counts[muscle], self.preferred_frequency) for muscle in self.priorities
        )
        covered = sum(exposure_counts[muscle] > 0 for muscle in self.priorities)
        spread = max(exposure_counts.values()) - min(exposure_counts.values())
        frequency_weight = ruleset.split_weights.get("priority_frequency", 20)
        balance_penalty = ruleset.split_weights.get("priority_distribution", 4)
        score = fulfilled * frequency_weight + covered - spread * balance_penalty
        reasons: list[str] = []
        if all(exposure_counts[muscle] >= self.preferred_frequency for muscle in self.priorities):
            reasons.append("PRIORITY_FREQUENCY_INCREASED")
            if len(self.priorities) > 1:
                reasons.append("PRIORITY_VOLUME_REDISTRIBUTED")
        else:
            reasons.append("PRIORITY_TARGET_CONSTRAINED")
        return score, tuple(reasons)

    def focus_trains_muscle(self, focus: str, muscle: MuscleGroup) -> bool:
        resolved = self._resolve_specialization(focus)
        _patterns, muscles = focus_scope(resolved)
        return muscles is None or muscle in muscles

    def _resolve_specialization(self, focus: str) -> str:
        if focus != "specialization":
            return focus
        for group, specialized_focus in (
            ((MuscleGroup.CHEST, MuscleGroup.TRICEPS), "chest_triceps"),
            ((MuscleGroup.BACK, MuscleGroup.BICEPS), "back_biceps"),
            ((MuscleGroup.SHOULDERS, MuscleGroup.TRAPS), "shoulders_traps"),
            ((MuscleGroup.QUADRICEPS, MuscleGroup.CALVES), "quadriceps_calves"),
            ((MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES, MuscleGroup.ABS), "posterior_chain_core"),
        ):
            if set(group).intersection(self.priorities):
                return specialized_focus
        return "chest_triceps"

    def day_priority_key(
        self,
        days: Sequence[object],
        muscle: MuscleGroup,
        day_index: int,
    ) -> tuple[int, int, int, int]:
        """Prefer new, well-spaced exposures until the desired frequency is met."""
        if muscle not in self.priorities or self.preferred_frequency <= 0:
            return (1, 0, 0, day_index)
        exposure_indexes = [
            index
            for index, day in enumerate(days)
            if any(
                getattr(item, "primary_muscle", None) is muscle
                for item in _day_exercises(day)
            )
        ]
        has_exposure = day_index in exposure_indexes
        spacing_valid = self._spacing_is_valid(days, muscle, day_index, exposure_indexes)
        if len(exposure_indexes) < self.preferred_frequency:
            return (
                0 if not has_exposure else 1,
                0 if spacing_valid else 1,
                len(exposure_indexes),
                day_index,
            )
        return (0 if has_exposure else 1, 0, len(exposure_indexes), day_index)

    def _spacing_is_valid(
        self,
        days: Sequence[object],
        muscle: MuscleGroup,
        day_index: int,
        exposure_indexes: list[int],
    ) -> bool:
        if day_index in exposure_indexes:
            return True
        weekdays = [_day_weekday(days[index]) for index in exposure_indexes + [day_index]]
        if any(weekday is None for weekday in weekdays):
            return True
        candidate = weekdays[-1]
        for weekday in weekdays[:-1]:
            if weekday is None or candidate is None:
                return True
            distance = abs(candidate - weekday)
            circular_distance = min(distance, 7 - distance)
            if circular_distance < self.minimum_recovery_gap_days:
                return False
        return True


def _day_exercises(day: object) -> tuple[object, ...]:
    exercises = getattr(day, "exercises", None)
    if isinstance(exercises, (tuple, list)):
        return tuple(exercises)
    if isinstance(day, (tuple, list)):
        return tuple(day)
    return ()


def _day_weekday(day: object) -> int | None:
    weekday = getattr(day, "weekday", None)
    return weekday if isinstance(weekday, int) else None


def _recovery_is_limited(request: NormalizedProgramRequest) -> bool:
    source = request.source
    return (
        source.sleep_quality is RecoveryRating.POOR
        or source.stress_level is RecoveryRating.POOR
        or source.physical_job_demand is PhysicalJobDemand.HIGH
        or source.recent_training_history.recovery_problems
    )
