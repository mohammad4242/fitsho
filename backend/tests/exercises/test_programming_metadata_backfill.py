from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleGroup,
)
from app.exercises.models import Exercise, ExerciseCautionTagItem, ExerciseEquipment
from app.exercises.programming_metadata import (
    backfill_programming_metadata,
    infer_programming_metadata,
)
from app.workouts.program_engine.enums import BodyPosition, LoadLimit, SkillDemand


def make_exercise(slug: str) -> Exercise:
    return Exercise(
        slug=slug,
        name_en="Test Squat",
        name_fa="اسکوات آزمایشی",
        body_region=BodyRegion.LOWER_BODY,
        primary_muscle=MuscleGroup.QUADRICEPS,
        muscle_focus=None,
        difficulty=Difficulty.BEGINNER,
        movement_pattern=MovementPattern.SQUAT,
        exercise_type=ExerciseType.COMPOUND,
        instructions_en=["Brace.", "Lower.", "Stand."],
        instructions_fa=["آماده شو.", "پایین برو.", "بلند شو."],
        safety_notes_en=[],
        safety_notes_fa=[],
        media_path="/exercises/exercise-placeholder.svg",
        media_type=MediaType.PLACEHOLDER,
    )


def test_backfill_populates_supported_missing_metadata_and_reports_changes(db: Session) -> None:
    exercise = make_exercise("backfill-supported")
    exercise.equipment_items.append(ExerciseEquipment(equipment=Equipment.BODYWEIGHT))
    exercise.caution_tag_items.append(
        ExerciseCautionTagItem(caution_tag=ExerciseCautionTag.DEEP_KNEE_FLEXION)
    )
    db.add(exercise)
    db.flush()

    report = backfill_programming_metadata(db)
    db.expire_all()
    stored = db.scalar(select(Exercise).where(Exercise.slug == "backfill-supported"))

    assert stored is not None
    assert report.inspected == 1
    assert report.updated == 1
    assert report.skipped == 0
    assert stored.body_position is BodyPosition.STANDING
    assert stored.fatigue_cost == 3
    assert stored.setup_cost == 1
    assert stored.axial_loading_level is None
    assert stored.substitution_group == "squat"
    assert stored.range_of_motion_profile == ["deep_knee_flexion"]


def test_backfill_never_overwrites_explicit_metadata(db: Session) -> None:
    exercise = make_exercise("backfill-explicit")
    exercise.body_position = BodyPosition.SUPPORTED
    exercise.fatigue_cost = 5
    exercise.axial_loading_level = LoadLimit.NONE
    db.add(exercise)
    db.flush()

    backfill_programming_metadata(db)
    db.expire_all()
    stored = db.scalar(select(Exercise).where(Exercise.slug == "backfill-explicit"))

    assert stored is not None
    assert stored.body_position is BodyPosition.SUPPORTED
    assert stored.fatigue_cost == 5
    assert stored.axial_loading_level is LoadLimit.NONE
    assert stored.substitution_group == "squat"


def test_backfill_is_idempotent(db: Session) -> None:
    exercise = make_exercise("backfill-idempotent")
    db.add(exercise)
    db.flush()

    first = backfill_programming_metadata(db)
    db.expire_all()
    second = backfill_programming_metadata(db)

    assert first.updated == 1
    assert second.updated == 0
    assert second.skipped == 1
    assert infer_programming_metadata(exercise)["skill_demand"] is SkillDemand.LOW


def test_backfill_leaves_uncertain_metadata_unset(db: Session) -> None:
    exercise = make_exercise("backfill-uncertain")
    exercise.name_en = "Unspecified movement"
    exercise.movement_pattern = MovementPattern.OTHER
    exercise.exercise_type = ExerciseType.OTHER
    exercise.equipment_items.clear()
    db.add(exercise)
    db.flush()

    report = backfill_programming_metadata(db)
    db.expire_all()
    stored = db.scalar(select(Exercise).where(Exercise.slug == "backfill-uncertain"))

    assert stored is not None
    assert report.updated == 1
    assert report.skipped == 0
    assert stored.skill_demand is SkillDemand.LOW
    assert stored.body_position is None
    assert stored.fatigue_cost is None
    assert stored.setup_cost is None
    assert stored.laterality is None


def test_backfill_dry_run_reports_without_persisting_values(db: Session) -> None:
    exercise = make_exercise("backfill-dry-run")
    db.add(exercise)
    db.flush()

    report = backfill_programming_metadata(db, dry_run=True)
    db.expire_all()
    stored = db.scalar(select(Exercise).where(Exercise.slug == "backfill-dry-run"))

    assert stored is not None
    assert report.updated == 1
    assert report.field_updates["body_position"] == 1
    assert stored.body_position is None
    assert stored.fatigue_cost is None
