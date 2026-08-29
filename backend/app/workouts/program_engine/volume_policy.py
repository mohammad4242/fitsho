from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import NamedTuple

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.enums import (
    Goal,
    PhysicalJobDemand,
    RecoveryRating,
    TrainingStatus,
)
from app.workouts.program_engine.schemas import NormalizedProgramRequest


@dataclass(frozen=True)
class MuscleVolumeProfile:
    baseline_sets: int
    minimum_useful_sets: int


@dataclass(frozen=True)
class RecoveryBurden:
    level: str
    reduction_sets: int
    reason_code: str | None


@dataclass(frozen=True)
class VolumePolicy:
    profiles: Mapping[MuscleGroup, MuscleVolumeProfile]
    status_multipliers: Mapping[TrainingStatus, float]
    goal_multipliers: Mapping[Goal, float]
    moderate_recovery_reduction_sets: int = 2
    strong_recovery_reduction_sets: int = 3
    supported_previous_volume_override_sets: int = 1

    def preferred_target(
        self,
        muscle: MuscleGroup,
        training_status: TrainingStatus,
        goal: Goal,
    ) -> int:
        raw = (
            self.profiles[muscle].baseline_sets
            * self.status_multipliers[training_status]
            * self.goal_multipliers[goal]
        )
        return math.floor(raw + 0.5)

    def minimum_useful_target(
        self,
        muscle: MuscleGroup,
        training_status: TrainingStatus,
    ) -> int:
        raw = self.profiles[muscle].minimum_useful_sets * self.status_multipliers[training_status]
        return max(1, math.floor(raw + 0.5))

    def flexibility_sets(self, target_sets: int) -> int:
        if target_sets <= 6:
            return 1
        if target_sets <= 12:
            return 2
        return 3

    def recovery_burden(self, signal_count: int) -> RecoveryBurden:
        if signal_count <= 0:
            return RecoveryBurden("normal", 0, None)
        if signal_count <= 2:
            return RecoveryBurden(
                "moderate",
                self.moderate_recovery_reduction_sets,
                "RECOVERY_BURDEN_MODERATE",
            )
        return RecoveryBurden(
            "strong",
            self.strong_recovery_reduction_sets,
            "RECOVERY_BURDEN_STRONG",
        )


VOLUME_POLICY = VolumePolicy(
    profiles=MappingProxyType(
        {
            MuscleGroup.CHEST: MuscleVolumeProfile(10, 6),
            MuscleGroup.BACK: MuscleVolumeProfile(11, 6),
            MuscleGroup.SHOULDERS: MuscleVolumeProfile(8, 5),
            MuscleGroup.GLUTES: MuscleVolumeProfile(9, 5),
            MuscleGroup.QUADRICEPS: MuscleVolumeProfile(10, 6),
            MuscleGroup.HAMSTRINGS: MuscleVolumeProfile(9, 5),
            MuscleGroup.ABS: MuscleVolumeProfile(7, 4),
            MuscleGroup.CALVES: MuscleVolumeProfile(7, 4),
            MuscleGroup.BICEPS: MuscleVolumeProfile(7, 4),
            MuscleGroup.TRICEPS: MuscleVolumeProfile(7, 4),
            MuscleGroup.TRAPS: MuscleVolumeProfile(6, 3),
            MuscleGroup.FOREARMS: MuscleVolumeProfile(4, 3),
        }
    ),
    status_multipliers=MappingProxyType(
        {
            TrainingStatus.NOVICE: 0.65,
            TrainingStatus.EARLY_INTERMEDIATE: 0.8,
            TrainingStatus.INTERMEDIATE: 1.0,
            TrainingStatus.ADVANCED: 1.2,
        }
    ),
    goal_multipliers=MappingProxyType(
        {
            Goal.FAT_LOSS: 0.75,
            Goal.HYPERTROPHY: 1.0,
            Goal.STRENGTH: 0.85,
            Goal.MUSCLE_GAIN: 1.0,
            Goal.BODY_RECOMPOSITION: 0.9,
            Goal.GENERAL_FITNESS: 0.75,
            Goal.MUSCULAR_ENDURANCE: 0.85,
        }
    ),
)


def recovery_burden_for_request(request: NormalizedProgramRequest) -> RecoveryBurden:
    source = request.source
    signal_count = sum(
        (
            source.sleep_quality is RecoveryRating.POOR,
            source.stress_level is RecoveryRating.POOR,
            source.physical_job_demand is PhysicalJobDemand.HIGH,
            source.recent_training_history.recovery_problems,
        )
    )
    return VOLUME_POLICY.recovery_burden(signal_count)


LARGE_MUSCLES = frozenset(
    {
        MuscleGroup.CHEST,
        MuscleGroup.BACK,
        MuscleGroup.SHOULDERS,
        MuscleGroup.QUADRICEPS,
        MuscleGroup.HAMSTRINGS,
        MuscleGroup.GLUTES,
    }
)

SMALL_MUSCLES = frozenset(
    {MuscleGroup.BICEPS, MuscleGroup.TRICEPS, MuscleGroup.FOREARMS, MuscleGroup.CALVES}
)


class VolumeRange(NamedTuple):
    minimum: int
    maximum: int


def volume_experience_band(training_age_months: int) -> str:
    if training_age_months <= 5:
        return "NOVICE"
    if training_age_months <= 24:
        return "INTERMEDIATE"
    return "ADVANCED"


def weekly_direct_volume_range(muscle: MuscleGroup, training_age_months: int) -> VolumeRange | None:
    band = volume_experience_band(training_age_months)
    if muscle in LARGE_MUSCLES:
        if band == "NOVICE":
            return VolumeRange(6, 12)
        if band == "INTERMEDIATE":
            return VolumeRange(8, 16)
        return VolumeRange(10, 20)
    if muscle in SMALL_MUSCLES:
        if band == "NOVICE":
            return VolumeRange(4, 8)
        if band == "INTERMEDIATE":
            return VolumeRange(6, 12)
        return VolumeRange(8, 16)
    return None


def session_direct_volume_range(
    muscle: MuscleGroup, training_age_months: int
) -> VolumeRange | None:
    band = volume_experience_band(training_age_months)
    if muscle in LARGE_MUSCLES:
        if band == "NOVICE":
            return VolumeRange(3, 6)
        if band == "INTERMEDIATE":
            return VolumeRange(4, 8)
        return VolumeRange(5, 10)
    if muscle in SMALL_MUSCLES:
        if band == "NOVICE":
            return VolumeRange(2, 4)
        if band == "INTERMEDIATE":
            return VolumeRange(3, 6)
        return VolumeRange(4, 8)
    return None


def session_hard_volume_cap(training_age_months: int) -> int:
    if training_age_months < 6:
        return 12
    if training_age_months <= 24:
        return 20
    return 30
