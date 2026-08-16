from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseType,
    MediaPresentation,
    MediaRole,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.models import Exercise, ExerciseEquipment, ExerciseMediaAsset

TARGET_SOURCE_ID = "a4a25c322a76c64bbce28aae12b5f0d728ba5364ab58d10aa66a0b93dd3fb31e"
VIDEO_SOURCE_IDS = (
    "68e61505aafd03733258f1179b26a85dc1a788a064bd961b8c859cda02d027df",
    "da3c8c259901827c33ef5bef4d3fe6fba8c392f3c48aa7953e6c6244c16365f3",
    "2be5b59c8936746aa20374595ee0a1d6b009ed1fe58e488185697624dbee0708",
    "435983d4e255403d32d7767e296dc1a0a1b2e9147014102d8767951e54f76bf1",
    TARGET_SOURCE_ID,
)


def _load_migration() -> Any:
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/20260816_84_split_wide_neutral_lat_pulldown.py"
    )
    spec = spec_from_file_location("split_wide_neutral_lat_pulldown_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _target_exercise() -> Exercise:
    exercise = Exercise(
        slug="owner-a4a25c322a76-wide-grip-lat-pulldown",
        name_en="Wide Neutral-Grip Lat Pulldown",
        name_fa="لت سیم‌کش دست باز دست موازی",
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=MuscleGroup.BACK,
        muscle_focus=MuscleFocus.UPPER_BACK,
        difficulty=Difficulty.BEGINNER,
        movement_pattern=MovementPattern.VERTICAL_PULL,
        exercise_type=ExerciseType.COMPOUND,
        instructions_en=["Sit securely", "Pull the bar down", "Return with control"],
        instructions_fa=["محکم بنشینید", "میله را پایین بکشید", "با کنترل برگردانید"],
        safety_notes_en=["Keep the torso stable"],
        safety_notes_fa=["تنه را ثابت نگه دارید"],
        media_path="/media/owner-video/placeholder.mp4",
        media_type=MediaType.VIDEO,
        media_license="Project owner supplied and authorized",
        media_attribution="Provided by Fitsho project owner",
        source="owner-video",
        source_id=TARGET_SOURCE_ID,
        source_metadata_en={"owner_video_filename": "_200203855_3.mp4"},
        needs_review=True,
    )
    exercise.equipment_items = [
        ExerciseEquipment(equipment=Equipment.CABLE),
        ExerciseEquipment(equipment=Equipment.MACHINE),
    ]
    return exercise


def test_migration_splits_five_video_variations_into_independent_exercises(
    db: Session,
) -> None:
    parent = _target_exercise()
    db.add(parent)
    db.flush()
    for sort_order, source_id in enumerate(VIDEO_SOURCE_IDS):
        db.add(
            ExerciseMediaAsset(
                exercise=parent,
                presentation=(
                    MediaPresentation.UNSPECIFIED
                    if source_id == TARGET_SOURCE_ID
                    else MediaPresentation.MALE
                ),
                role=MediaRole.VIDEO,
                sort_order=sort_order,
                media_path=f"/media/owner-video/{source_id}.mp4",
                media_type=MediaType.VIDEO,
                source="owner-video",
                source_id=source_id,
            )
        )
    db.flush()

    migration = _load_migration()
    migration.split_target_exercise(db.connection())
    db.expire_all()

    exercises = db.scalars(
        select(Exercise)
        .where(Exercise.source == "owner-video")
        .where(Exercise.source_id.in_(VIDEO_SOURCE_IDS))
        .order_by(Exercise.name_en, Exercise.id)
    ).all()

    assert len(exercises) == 5
    assert (
        db.scalar(
            select(Exercise).where(Exercise.slug == "owner-a4a25c322a76-wide-grip-lat-pulldown")
        )
        is None
    )
    assert sorted(len(exercise.media_assets) for exercise in exercises) == [1, 1, 1, 1, 1]
    assert {asset.source_id for exercise in exercises for asset in exercise.media_assets} == set(
        VIDEO_SOURCE_IDS
    )
    assert len({exercise.slug for exercise in exercises}) == 5
    assert len({exercise.name_en for exercise in exercises}) == 5
