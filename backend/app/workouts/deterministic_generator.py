from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from app.ai.schemas import WorkoutPlanDayOutput, WorkoutPlanExerciseOutput, WorkoutPlanModelOutput
from app.exercises.enums import ExerciseLabel, ExerciseType
from app.profile.enums import ExperienceLevel, FitnessGoal
from app.workouts.schemas import CandidateSet, WorkoutExerciseCandidate, WorkoutGenerationProfile
from app.workouts.time_budget import (
    ExerciseTiming,
    WorkoutGenerationPolicy,
    calculate_day_minutes,
    calculate_exercise_minutes,
)

DETERMINISTIC_MODEL_ID = "fitsho-deterministic-v1"


@dataclass(frozen=True)
class _Prescription:
    sets: int
    reps_min: int
    reps_max: int
    rest_seconds: int
    rir: int


class DeterministicWorkoutPlanGenerator:
    def generate(
        self,
        profile: WorkoutGenerationProfile,
        candidates: CandidateSet,
        policy: WorkoutGenerationPolicy,
    ) -> WorkoutPlanModelOutput:
        ordered = self._balanced_candidates(candidates.exercises)
        exercise_count = min(policy.maximum_exercises_per_day, len(ordered))
        prescription = self._prescription(profile, policy)
        days: list[WorkoutPlanDayOutput] = []
        for day_index in range(profile.training_days_per_week):
            rotated = ordered[day_index % len(ordered) :] + ordered[: day_index % len(ordered)]
            selected = sorted(rotated[:exercise_count], key=self._candidate_rank)
            outputs = [self._exercise(candidate, prescription, policy) for candidate in selected]
            timing = [
                ExerciseTiming(sets=item.sets, rest_seconds=item.rest_seconds)
                for item in outputs
            ]
            days.append(
                WorkoutPlanDayOutput(
                    day_number=day_index + 1,
                    title_en=f"Balanced training {day_index + 1}",
                    title_fa=f"تمرین متعادل {day_index + 1}",
                    estimated_duration_minutes=policy.warmup_minutes
                    + calculate_day_minutes(timing),
                    exercises=outputs,
                )
            )
        return WorkoutPlanModelOutput(days=days)

    @classmethod
    def _balanced_candidates(
        cls,
        candidates: tuple[WorkoutExerciseCandidate, ...],
    ) -> list[WorkoutExerciseCandidate]:
        by_muscle: dict[str, deque[WorkoutExerciseCandidate]] = defaultdict(deque)
        for candidate in sorted(candidates, key=cls._candidate_rank):
            muscle_key = candidate.primary_muscle.value if candidate.primary_muscle else "unknown"
            by_muscle[muscle_key].append(candidate)

        ordered: list[WorkoutExerciseCandidate] = []
        muscle_keys = sorted(by_muscle)
        while any(by_muscle.values()):
            for muscle_key in muscle_keys:
                if by_muscle[muscle_key]:
                    ordered.append(by_muscle[muscle_key].popleft())
        return ordered

    @staticmethod
    def _candidate_rank(candidate: WorkoutExerciseCandidate) -> tuple[int, int, str, str]:
        type_rank = {
            ExerciseType.COMPOUND: 0,
            ExerciseType.CORE: 1,
            ExerciseType.ISOLATION: 2,
            ExerciseType.MOBILITY: 3,
            ExerciseType.OTHER: 4,
        }
        return (
            ExerciseLabel.CARDIO in candidate.labels,
            type_rank[candidate.exercise_type],
            candidate.movement_pattern.value,
            str(candidate.id),
        )

    @staticmethod
    def _prescription(
        profile: WorkoutGenerationProfile,
        policy: WorkoutGenerationPolicy,
    ) -> _Prescription:
        goal = profile.fitness_goal
        if goal is FitnessGoal.BUILD_MUSCLE or goal == FitnessGoal.BUILD_MUSCLE.value:
            reps = (8, 12)
            rest = 90
        elif goal is FitnessGoal.LOSE_WEIGHT or goal == FitnessGoal.LOSE_WEIGHT.value:
            reps = (10, 15)
            rest = 60
        else:
            reps = (8, 14)
            rest = 75
        sets = 2 if profile.experience_level is ExperienceLevel.BEGINNER else 3
        return _Prescription(
            sets=min(max(sets, policy.minimum_sets), policy.maximum_sets),
            reps_min=max(reps[0], policy.minimum_repetitions),
            reps_max=min(reps[1], policy.maximum_repetitions),
            rest_seconds=min(policy.allowed_rest_seconds, key=lambda value: abs(value - rest)),
            rir=3 if profile.experience_level is ExperienceLevel.BEGINNER else 2,
        )

    @staticmethod
    def _exercise(
        candidate: WorkoutExerciseCandidate,
        prescription: _Prescription,
        policy: WorkoutGenerationPolicy,
    ) -> WorkoutPlanExerciseOutput:
        timing = ExerciseTiming(
            sets=prescription.sets,
            rest_seconds=prescription.rest_seconds,
        )
        return WorkoutPlanExerciseOutput(
            exercise_id=candidate.id,
            sets=prescription.sets,
            reps_min=prescription.reps_min,
            reps_max=prescription.reps_max,
            rest_seconds=prescription.rest_seconds,
            rir=prescription.rir,
            estimated_minutes=calculate_exercise_minutes(
                timing,
                set_execution_seconds=policy.set_execution_seconds,
                transition_seconds=policy.transition_seconds_per_exercise,
            ),
            notes_en=None,
            notes_fa=None,
        )
