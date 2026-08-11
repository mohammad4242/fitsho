from uuid import uuid4

from sqlalchemy.orm import Session

from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseLabel,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleGroup,
)
from app.exercises.models import (
    Exercise,
    ExerciseCautionTagItem,
    ExerciseEquipment,
    ExerciseLabelItem,
)
from app.profile.enums import ExperienceLevel, HomeTrainingSetup, TrainingCaution, TrainingLocation
from app.workouts.candidate_selector import WorkoutCandidateSelector
from app.workouts.schemas import WorkoutGenerationProfile


def profile(
    *,
    location: TrainingLocation,
    setup: HomeTrainingSetup | None,
    experience: ExperienceLevel = ExperienceLevel.BEGINNER,
    cautions: tuple[TrainingCaution, ...] = (),
) -> WorkoutGenerationProfile:
    return WorkoutGenerationProfile(
        fitness_goal="build_muscle",
        experience_level=experience,
        training_days_per_week=3,
        training_location=location,
        home_training_setup=setup,
        session_duration_minutes=60,
        plan_duration_weeks=4,
        training_cautions=cautions,
        physical_limitations=None,
        current_weight_kg=76,
    )


def exercise(
    db: Session,
    slug: str,
    *,
    equipment: tuple[Equipment, ...],
    difficulty: Difficulty = Difficulty.BEGINNER,
    caution_tags: tuple[ExerciseCautionTag, ...] = (),
    movement_pattern: MovementPattern = MovementPattern.ELBOW_FLEXION,
    is_active: bool = True,
    is_programmable: bool = True,
    needs_review: bool = False,
) -> Exercise:
    unique_slug = f"{slug}-{uuid4().hex}"
    item = Exercise(
        slug=unique_slug,
        name_en=unique_slug,
        name_fa=unique_slug,
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=MuscleGroup.BICEPS,
        difficulty=difficulty,
        movement_pattern=movement_pattern,
        exercise_type=ExerciseType.COMPOUND,
        instructions_en=["one", "two", "three"],
        instructions_fa=["یک", "دو", "سه"],
        safety_notes_en=["steady"],
        safety_notes_fa=["آرام"],
        media_path="placeholder.webp",
        media_type=MediaType.PLACEHOLDER,
        is_active=is_active,
        is_programmable=is_programmable,
        needs_review=needs_review,
        equipment_items=[ExerciseEquipment(equipment=value) for value in equipment],
        caution_tag_items=[ExerciseCautionTagItem(caution_tag=value) for value in caution_tags],
    )
    db.add(item)
    db.flush()
    return item


def test_dumbbell_home_requires_all_equipment(db: Session) -> None:
    curl = exercise(db, "dumbbell-curl", equipment=(Equipment.DUMBBELL,))
    bench_press = exercise(
        db,
        "dumbbell-bench-press",
        equipment=(Equipment.DUMBBELL, Equipment.BENCH),
    )

    result = WorkoutCandidateSelector(db).select(
        profile(location=TrainingLocation.HOME, setup=HomeTrainingSetup.DUMBBELLS_AVAILABLE)
    )

    assert result.ids == (curl.id,)
    assert bench_press.id not in result.ids


def test_selector_excludes_inactive_nonprogrammable_unsafe_and_too_hard_exercises(
    db: Session,
) -> None:
    allowed = exercise(db, "bodyweight-row", equipment=(Equipment.BODYWEIGHT,))
    exercise(db, "inactive-row", equipment=(Equipment.BODYWEIGHT,), is_active=False)
    exercise(db, "catalog-only-row", equipment=(Equipment.BODYWEIGHT,), is_programmable=False)
    exercise(db, "review-pending-row", equipment=(Equipment.BODYWEIGHT,), needs_review=True)
    exercise(
        db,
        "advanced-row",
        equipment=(Equipment.BODYWEIGHT,),
        difficulty=Difficulty.ADVANCED,
    )
    exercise(
        db,
        "loaded-row",
        equipment=(Equipment.BODYWEIGHT,),
        caution_tags=(ExerciseCautionTag.LOWER_BACK_LOADING,),
    )

    result = WorkoutCandidateSelector(db).select(
        profile(
            location=TrainingLocation.HOME,
            setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
            cautions=(TrainingCaution.LOWER_BACK,),
        )
    )

    assert result.ids == (allowed.id,)


def test_first_month_uses_only_beginner_exercises(db: Session) -> None:
    beginner = exercise(db, "first-month-row", equipment=(Equipment.BODYWEIGHT,))
    intermediate = exercise(
        db,
        "intermediate-row",
        equipment=(Equipment.BODYWEIGHT,),
        difficulty=Difficulty.INTERMEDIATE,
    )

    result = WorkoutCandidateSelector(db).select(
        profile(
            location=TrainingLocation.HOME,
            setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
            experience=ExperienceLevel.FIRST_MONTH,
        )
    )

    assert beginner.id in result.ids
    assert intermediate.id not in result.ids


def test_gym_allows_supported_gym_equipment_and_keeps_soft_other_caution(db: Session) -> None:
    cable_row = exercise(db, "cable-row", equipment=(Equipment.CABLE,))

    result = WorkoutCandidateSelector(db).select(
        profile(
            location=TrainingLocation.GYM,
            setup=None,
            cautions=(TrainingCaution.OTHER,),
        )
    )

    assert result.ids == (cable_row.id,)
    assert result.soft_cautions == (TrainingCaution.OTHER,)


def test_selector_reports_an_insufficient_candidate_set(db: Session) -> None:
    exercise(db, "only-bodyweight-row", equipment=(Equipment.BODYWEIGHT,))

    result = WorkoutCandidateSelector(db).select(
        profile(location=TrainingLocation.HOME, setup=HomeTrainingSetup.BODYWEIGHT_ONLY)
    )

    assert not result.is_sufficient


def test_selector_strictly_excludes_other_caution_tag(db: Session) -> None:
    safe = exercise(db, "safe-row", equipment=(Equipment.BODYWEIGHT,))
    blocked = exercise(
        db,
        "other-caution-row",
        equipment=(Equipment.BODYWEIGHT,),
        caution_tags=(ExerciseCautionTag.OTHER,),
    )

    result = WorkoutCandidateSelector(db).select(
        profile(
            location=TrainingLocation.HOME,
            setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
            cautions=(TrainingCaution.OTHER,),
        )
    )

    assert safe.id in result.ids
    assert blocked.id not in result.ids


def test_multiday_selector_requires_candidate_count_and_pattern_coverage(db: Session) -> None:
    for index in range(4):
        exercise(
            db,
            f"same-pattern-{index}",
            equipment=(Equipment.BODYWEIGHT,),
            movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        )

    result = WorkoutCandidateSelector(db).select(
        profile(location=TrainingLocation.HOME, setup=HomeTrainingSetup.BODYWEIGHT_ONLY)
    )

    assert len(result.exercises) == 4
    assert not result.is_sufficient


def test_candidate_preserves_cardio_label_and_null_primary_muscle(db: Session) -> None:
    cardio = exercise(db, "cardio-step", equipment=(Equipment.BODYWEIGHT,))
    cardio.primary_muscle = None
    cardio.labels.append(ExerciseLabelItem(label=ExerciseLabel.CARDIO))
    db.commit()

    result = WorkoutCandidateSelector(db).select(
        profile(location=TrainingLocation.HOME, setup=HomeTrainingSetup.BODYWEIGHT_ONLY)
    )

    candidate = next(item for item in result.exercises if item.id == cardio.id)
    assert candidate.primary_muscle is None
    assert ExerciseLabel.CARDIO in candidate.labels
