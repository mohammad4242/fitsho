from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.exercises.enums import Difficulty, Equipment, ExerciseCautionTag
from app.exercises.models import Exercise
from app.profile.enums import (
    ExperienceLevel,
    HomeTrainingSetup,
    TrainingCaution,
    TrainingLocation,
)
from app.workouts.schemas import CandidateSet, WorkoutExerciseCandidate, WorkoutGenerationProfile
from app.workouts.signature import hash_candidate_set

CAUTION_EXCLUSIONS: dict[TrainingCaution, frozenset[ExerciseCautionTag]] = {
    TrainingCaution.LOWER_BACK: frozenset(
        {ExerciseCautionTag.LOWER_BACK_LOADING, ExerciseCautionTag.SPINAL_FLEXION}
    ),
    TrainingCaution.KNEE: frozenset({ExerciseCautionTag.DEEP_KNEE_FLEXION}),
    TrainingCaution.SHOULDER: frozenset(
        {
            ExerciseCautionTag.OVERHEAD_POSITION,
            ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION,
            ExerciseCautionTag.SHOULDER_EXTERNAL_ROTATION,
        }
    ),
    TrainingCaution.NECK: frozenset({ExerciseCautionTag.NECK_LOADING}),
    TrainingCaution.WRIST: frozenset({ExerciseCautionTag.WRIST_LOADING}),
    TrainingCaution.OTHER: frozenset(),
}
SOFT_CAUTIONS = frozenset({TrainingCaution.OTHER})

_ALLOWED_DIFFICULTIES: dict[ExperienceLevel, frozenset[Difficulty]] = {
    ExperienceLevel.BEGINNER: frozenset({Difficulty.BEGINNER}),
    ExperienceLevel.INTERMEDIATE: frozenset({Difficulty.BEGINNER, Difficulty.INTERMEDIATE}),
    ExperienceLevel.ADVANCED: frozenset(Difficulty),
}
_GYM_EQUIPMENT = frozenset(item for item in Equipment if item is not Equipment.OTHER)


class WorkoutCandidateSelector:
    def __init__(self, db: Session, *, maximum_candidates: int = 80) -> None:
        self._db = db
        self._maximum_candidates = maximum_candidates

    def select(self, profile: WorkoutGenerationProfile) -> CandidateSet:
        exercises = self._db.scalars(
            select(Exercise)
            .where(Exercise.is_active.is_(True), Exercise.is_programmable.is_(True))
            .options(
                selectinload(Exercise.secondary_muscles),
                selectinload(Exercise.equipment_items),
                selectinload(Exercise.caution_tag_items),
            )
        ).all()
        available_equipment = self._available_equipment(profile)
        excluded_tags = set().union(
            *(CAUTION_EXCLUSIONS[caution] for caution in profile.training_cautions)
        )
        candidates = [
            self._to_candidate(exercise)
            for exercise in exercises
            if self._is_eligible(
                exercise,
                available_equipment=available_equipment,
                allowed_difficulties=_ALLOWED_DIFFICULTIES[profile.experience_level],
                excluded_tags=excluded_tags,
            )
        ]
        capped = self._cap_for_movement_coverage(candidates)
        soft_cautions = tuple(
            sorted(
                (caution for caution in profile.training_cautions if caution in SOFT_CAUTIONS),
                key=lambda caution: caution.value,
            )
        )
        return CandidateSet(
            exercises=capped,
            candidate_set_hash=hash_candidate_set(capped),
            soft_cautions=soft_cautions,
            minimum_candidate_count=min(3, profile.training_days_per_week),
        )

    @staticmethod
    def _available_equipment(profile: WorkoutGenerationProfile) -> frozenset[Equipment]:
        if profile.training_location is TrainingLocation.GYM:
            return _GYM_EQUIPMENT
        if profile.home_training_setup is HomeTrainingSetup.DUMBBELLS_AVAILABLE:
            return frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL})
        return frozenset({Equipment.BODYWEIGHT})

    @staticmethod
    def _is_eligible(
        exercise: Exercise,
        *,
        available_equipment: frozenset[Equipment],
        allowed_difficulties: frozenset[Difficulty],
        excluded_tags: set[ExerciseCautionTag],
    ) -> bool:
        required_equipment = {item.equipment for item in exercise.equipment_items}
        caution_tags = {item.caution_tag for item in exercise.caution_tag_items}
        return (
            required_equipment.issubset(available_equipment)
            and exercise.difficulty in allowed_difficulties
            and not caution_tags.intersection(excluded_tags)
        )

    @staticmethod
    def _to_candidate(exercise: Exercise) -> WorkoutExerciseCandidate:
        return WorkoutExerciseCandidate(
            id=exercise.id,
            primary_muscle=exercise.primary_muscle,
            secondary_muscles=tuple(item.muscle for item in exercise.secondary_muscles),
            movement_pattern=exercise.movement_pattern,
            exercise_type=exercise.exercise_type,
            equipment=tuple(item.equipment for item in exercise.equipment_items),
            difficulty=exercise.difficulty,
            caution_tags=tuple(item.caution_tag for item in exercise.caution_tag_items),
        )

    def _cap_for_movement_coverage(
        self, candidates: Iterable[WorkoutExerciseCandidate]
    ) -> tuple[WorkoutExerciseCandidate, ...]:
        ordered = sorted(candidates, key=lambda item: (item.movement_pattern.value, str(item.id)))
        selected: list[WorkoutExerciseCandidate] = []
        covered_patterns = set()
        for candidate in ordered:
            if candidate.movement_pattern not in covered_patterns:
                selected.append(candidate)
                covered_patterns.add(candidate.movement_pattern)
        for candidate in ordered:
            if candidate not in selected:
                selected.append(candidate)
        return tuple(selected[: self._maximum_candidates])
