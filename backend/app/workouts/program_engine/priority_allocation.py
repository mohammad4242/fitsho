from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.body_analysis import eligible_body_analysis_priorities
from app.workouts.program_engine.enums import (
    Goal,
    TrainingStatus,
)
from app.workouts.program_engine.focus_topology import (
    MUSCLE_SPECIFIC_UPPER_PRIORITIES,
    FocusAffinity,
    priority_affinity,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import NormalizedProgramRequest
from app.workouts.program_engine.session_coherence import (
    SessionCoherence,
    specialization_focus_for_priorities,
)
from app.workouts.program_engine.supplemental_policy import SUPPLEMENTAL_MUSCLES
from app.workouts.program_engine.volume_policy import recovery_burden_for_request


@dataclass(frozen=True)
class PriorityAllocationPolicy:
    """Deterministic frequency and placement policy for requested priorities."""

    priorities: tuple[MuscleGroup, ...]
    explicit_priorities: tuple[MuscleGroup, ...]
    clear_lag_priorities: tuple[MuscleGroup, ...]
    mild_lag_priorities: tuple[MuscleGroup, ...]
    supplemental_priorities: tuple[MuscleGroup, ...]
    supplemental_body_priorities: tuple[MuscleGroup, ...]
    preferred_frequency: int
    recovery_limited: bool
    minimum_recovery_gap_days: int

    @classmethod
    def for_request(
        cls,
        request: NormalizedProgramRequest,
        ruleset: ProgramRuleset,
    ) -> PriorityAllocationPolicy:
        requested_priorities = tuple(
            sorted(request.source.priority_muscles, key=lambda muscle: muscle.value)
        )
        body_priorities = tuple(
            sorted(
                (
                    priority
                    for priority in eligible_body_analysis_priorities(request, ruleset)
                    if priority.muscle not in request.source.priority_muscles
                ),
                key=lambda priority: (
                    priority.classification != "clear_lag",
                    -priority.severity,
                    -priority.confidence,
                    priority.muscle.value,
                ),
            )
        )
        explicit_priorities = tuple(
            muscle for muscle in requested_priorities if muscle not in SUPPLEMENTAL_MUSCLES
        )
        supplemental_priorities = tuple(
            muscle for muscle in requested_priorities if muscle in SUPPLEMENTAL_MUSCLES
        )
        clear_lag_priorities = tuple(
            priority.muscle
            for priority in body_priorities
            if priority.classification == "clear_lag"
            and priority.muscle not in SUPPLEMENTAL_MUSCLES
        )
        mild_lag_priorities = tuple(
            priority.muscle
            for priority in body_priorities
            if priority.classification == "mild_lag" and priority.muscle not in SUPPLEMENTAL_MUSCLES
        )
        supplemental_body_priorities = tuple(
            priority.muscle
            for priority in body_priorities
            if priority.muscle in SUPPLEMENTAL_MUSCLES
        )
        priorities = tuple(explicit_priorities + clear_lag_priorities + mild_lag_priorities)
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
            explicit_priorities=explicit_priorities,
            clear_lag_priorities=clear_lag_priorities,
            mild_lag_priorities=mild_lag_priorities,
            supplemental_priorities=supplemental_priorities,
            supplemental_body_priorities=supplemental_body_priorities,
            preferred_frequency=preferred_frequency,
            recovery_limited=recovery_limited,
            minimum_recovery_gap_days=ruleset.minimum_recovery_gap_days,
        )

    def precedence_key(self, muscle: MuscleGroup | None) -> tuple[int, int, str]:
        if muscle is None:
            return (3, 0, "")
        for tier, priorities in enumerate(
            (
                (*self.explicit_priorities, *self.supplemental_priorities),
                (*self.clear_lag_priorities, *self.supplemental_body_priorities),
                self.mild_lag_priorities,
            )
        ):
            if muscle in priorities:
                return (tier, priorities.index(muscle), muscle.value)
        return (3, 0, muscle.value)

    def preservation_rank(self, muscle: MuscleGroup | None) -> int:
        tier = self.precedence_key(muscle)[0]
        # tier 0 = explicit priority → rank 3
        # tier 1 = clear_lag body analysis → rank 2
        # tier 2 = mild_lag body analysis → rank 1
        # tier 3 = unconstrained → rank 0
        return {0: 3, 1: 2, 2: 1}.get(tier, 0)

    def is_explicit(self, muscle: MuscleGroup | None) -> bool:
        return muscle in self.explicit_priorities or muscle in self.supplemental_priorities

    def is_body_analysis(self, muscle: MuscleGroup | None) -> bool:
        return (
            muscle in self.clear_lag_priorities
            or muscle in self.mild_lag_priorities
            or muscle in self.supplemental_body_priorities
        )

    def volume_bonuses(
        self,
        baseline_sets: Mapping[MuscleGroup, int],
        maximum_sets: Mapping[MuscleGroup, int],
        ruleset: ProgramRuleset,
    ) -> dict[MuscleGroup, int]:
        bonuses = {muscle: 0 for muscle in self.explicit_priorities}
        remaining = ruleset.priority_emphasis_budget(len(self.explicit_priorities))
        while remaining > 0:
            eligible = tuple(
                muscle
                for muscle in self.explicit_priorities
                if baseline_sets[muscle] + bonuses[muscle] < maximum_sets[muscle]
            )
            if not eligible:
                break
            selected = min(
                eligible,
                key=lambda muscle: (
                    -(maximum_sets[muscle] - baseline_sets[muscle] - bonuses[muscle]),
                    bonuses[muscle],
                    muscle.value,
                ),
            )
            bonuses[selected] += 1
            remaining -= 1
        return bonuses

    def useful_frequency(
        self,
        target_sets: int,
        ruleset: ProgramRuleset,
        muscle: MuscleGroup,
        request: NormalizedProgramRequest,
    ) -> int:
        if self.preferred_frequency <= 1:
            return self.preferred_frequency
        from app.workouts.program_engine.volume_policy import session_hard_volume_cap

        sess_max = session_hard_volume_cap(request.source.training_age_months)
        required = max(1, math.ceil(target_sets / sess_max))
        return min(self.preferred_frequency, required)

    def split_adjustment(
        self, focuses: tuple[str, ...], ruleset: ProgramRuleset
    ) -> tuple[int, tuple[str, ...]]:
        if not self.priorities or self.preferred_frequency <= 0:
            return 0, ()
        exposure_counts = {
            muscle: sum(
                priority_affinity(self._resolve_specialization(focus), muscle)
                is not FocusAffinity.NONE
                for focus in focuses
            )
            for muscle in self.priorities
        }
        affinity_score = sum(
            ruleset.priority_affinity_weights[
                priority_affinity(self._resolve_specialization(focus), muscle)
            ]
            for muscle in self.priorities
            for focus in focuses
            if muscle in MUSCLE_SPECIFIC_UPPER_PRIORITIES
        )
        fulfilled = sum(
            min(exposure_counts[muscle], self.preferred_frequency) for muscle in self.priorities
        )
        covered = sum(exposure_counts[muscle] > 0 for muscle in self.priorities)
        spread = max(exposure_counts.values()) - min(exposure_counts.values())
        frequency_weight = ruleset.split_weights.get("priority_frequency", 20)
        balance_penalty = ruleset.split_weights.get("priority_distribution", 4)
        score = fulfilled * frequency_weight + covered + affinity_score - spread * balance_penalty
        reasons: list[str] = []
        if all(exposure_counts[muscle] >= self.preferred_frequency for muscle in self.priorities):
            reasons.append("PRIORITY_FREQUENCY_INCREASED")
            if len(self.priorities) > 1:
                reasons.append("PRIORITY_VOLUME_REDISTRIBUTED")
        else:
            reasons.append("PRIORITY_TARGET_CONSTRAINED")
        return score, tuple(reasons)

    def focus_trains_muscle(self, focus: str, muscle: MuscleGroup) -> bool:
        return self.focus_affinity(focus, muscle) is not FocusAffinity.NONE

    def focus_affinity(self, focus: str, muscle: MuscleGroup) -> FocusAffinity:
        return priority_affinity(self._resolve_specialization(focus), muscle)

    def _resolve_specialization(self, focus: str) -> str:
        if focus != "specialization":
            return focus
        priority_source = self.explicit_priorities or self.priorities
        return specialization_focus_for_priorities(priority_source)

    def day_priority_key(
        self,
        days: Sequence[object],
        muscle: MuscleGroup,
        day_index: int,
        *,
        preferred_frequency: int | None = None,
    ) -> tuple[int, int, int, int]:
        """Prefer existing intended exposures, then another coherent intended day."""
        target_frequency = (
            self.preferred_frequency if preferred_frequency is None else preferred_frequency
        )
        if muscle not in self.priorities or target_frequency <= 0:
            return (1, 0, 0, day_index)
        intended_days = [
            index
            for index, day in enumerate(days)
            if SessionCoherence.from_workout_day(day).allows_direct(muscle)
        ]
        if day_index not in intended_days:
            return (2, 3, len(intended_days), day_index)
        exposure_indexes = [
            index
            for index, day in enumerate(days)
            if index in intended_days
            and any(getattr(item, "primary_muscle", None) is muscle for item in _day_exercises(day))
        ]
        has_exposure = day_index in exposure_indexes
        spacing_valid = self._spacing_is_valid(days, muscle, day_index, exposure_indexes)
        if len(exposure_indexes) < target_frequency:
            return (
                0 if has_exposure else 1,
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
    return recovery_burden_for_request(request).level != "normal"
