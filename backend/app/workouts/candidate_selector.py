from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseContentType,
    ExerciseLabel,
    ExerciseType,
    MovementPattern,
)
from app.exercises.models import Exercise
from app.profile.enums import (
    ExperienceLevel,
    HomeTrainingSetup,
    TrainingCaution,
    TrainingLocation,
)
from app.workouts.program_engine.equipment import effective_required_equipment
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
    TrainingCaution.OTHER: frozenset({ExerciseCautionTag.OTHER}),
}
SOFT_CAUTIONS = frozenset({TrainingCaution.OTHER})


def caution_tags_for_training_cautions(
    cautions: Iterable[TrainingCaution],
) -> frozenset[ExerciseCautionTag]:
    return frozenset().union(*(CAUTION_EXCLUSIONS[caution] for caution in cautions))


_ALLOWED_DIFFICULTIES: dict[ExperienceLevel, frozenset[Difficulty]] = {
    ExperienceLevel.FIRST_MONTH: frozenset({Difficulty.BEGINNER}),
    ExperienceLevel.BEGINNER: frozenset({Difficulty.BEGINNER}),
    ExperienceLevel.INTERMEDIATE: frozenset({Difficulty.BEGINNER, Difficulty.INTERMEDIATE}),
    ExperienceLevel.ADVANCED: frozenset(Difficulty),
}
_GYM_EQUIPMENT = frozenset(Equipment)


class WorkoutCandidateSelector:
    def __init__(self, db: Session, *, maximum_candidates: int | None = 80) -> None:
        self._db = db
        self._maximum_candidates = maximum_candidates

    def select(self, profile: WorkoutGenerationProfile) -> CandidateSet:
        exercises = self._db.scalars(
            select(Exercise)
            .where(
                Exercise.is_active.is_(True),
                Exercise.is_programmable.is_(True),
                Exercise.needs_review.is_(False),
                Exercise.content_type == ExerciseContentType.EXERCISE,
            )
            .options(
                selectinload(Exercise.secondary_muscles),
                selectinload(Exercise.equipment_items),
                selectinload(Exercise.caution_tag_items),
                selectinload(Exercise.labels),
            )
        ).all()
        available_equipment = self._available_equipment(profile)
        excluded_tags = caution_tags_for_training_cautions(profile.training_cautions)
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
        capped = self._cap_for_movement_coverage(candidates, profile.experience_level)
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
            minimum_candidate_count=max(3, min(6, profile.training_days_per_week + 1)),
            minimum_movement_pattern_count=2 if profile.training_days_per_week > 1 else 1,
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
        excluded_tags: frozenset[ExerciseCautionTag],
    ) -> bool:
        required_equipment = effective_required_equipment(
            (item.equipment for item in exercise.equipment_items), exercise.movement_pattern
        )
        caution_tags = {item.caution_tag for item in exercise.caution_tag_items}
        return (
            bool(required_equipment)
            and required_equipment.issubset(available_equipment)
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
            equipment=tuple(
                effective_required_equipment(
                    (item.equipment for item in exercise.equipment_items),
                    exercise.movement_pattern,
                )
            ),
            difficulty=exercise.difficulty,
            caution_tags=tuple(item.caution_tag for item in exercise.caution_tag_items),
            labels=tuple(item.label for item in exercise.labels),
            prescription_mode=exercise.prescription_mode,
            duration_min_seconds=exercise.duration_min_seconds,
            duration_max_seconds=exercise.duration_max_seconds,
        )

    def _cap_for_movement_coverage(
        self,
        candidates: Iterable[WorkoutExerciseCandidate],
        experience_level: ExperienceLevel,
    ) -> tuple[WorkoutExerciseCandidate, ...]:
        difficulty_rank = {
            Difficulty.BEGINNER: 0,
            Difficulty.INTERMEDIATE: 1,
            Difficulty.ADVANCED: 2,
        }
        type_rank = {
            ExerciseType.COMPOUND: 0,
            ExerciseType.CORE: 1,
            ExerciseType.ISOLATION: 2,
            ExerciseType.MOBILITY: 3,
            ExerciseType.OTHER: 4,
        }
        target_difficulty = {
            ExperienceLevel.FIRST_MONTH: difficulty_rank[Difficulty.BEGINNER],
            ExperienceLevel.BEGINNER: difficulty_rank[Difficulty.BEGINNER],
            ExperienceLevel.INTERMEDIATE: difficulty_rank[Difficulty.INTERMEDIATE],
            ExperienceLevel.ADVANCED: difficulty_rank[Difficulty.ADVANCED],
        }[experience_level]
        grouped: dict[MovementPattern, list[WorkoutExerciseCandidate]] = {}
        for candidate in candidates:
            grouped.setdefault(candidate.movement_pattern, []).append(candidate)
        for group in grouped.values():
            group.sort(
                key=lambda item: (
                    ExerciseLabel.CARDIO in item.labels,
                    type_rank[item.exercise_type],
                    abs(difficulty_rank[item.difficulty] - target_difficulty),
                    str(item.id),
                )
            )
        selected: list[WorkoutExerciseCandidate] = []
        patterns = sorted(grouped, key=lambda item: item.value)
        while any(grouped[pattern] for pattern in patterns):
            for pattern in patterns:
                if grouped[pattern]:
                    selected.append(grouped[pattern].pop(0))
                    if (
                        self._maximum_candidates is not None
                        and len(selected) == self._maximum_candidates
                    ):
                        return tuple(selected)
        if self._maximum_candidates is None:
            return tuple(selected)
        return tuple(selected[: self._maximum_candidates])
