from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    MediaPresentation,
    MediaRole,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.models import Exercise, ExerciseMediaAsset


def exercise(*, slug: str, source: str, source_id: str) -> Exercise:
    return Exercise(
        slug=slug,
        name_en="Barbell Bench Press",
        name_fa="پرس سینه هالتر",
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=MuscleGroup.CHEST,
        muscle_focus=MuscleFocus.MID_CHEST,
        difficulty=Difficulty.BEGINNER,
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        instructions_en=["Set up.", "Lower.", "Press."],
        instructions_fa=["آماده شو.", "پایین برو.", "بالا برو."],
        safety_notes_en=[],
        safety_notes_fa=[],
        media_path="/media/original.mp4",
        media_type=MediaType.VIDEO,
        source=source,
        source_id=source_id,
        is_programmable=True,
    )


def test_merges_owner_video_duplicate_into_existing_card(db: Session) -> None:
    from app.exercises.owner_video_deduplicate import merge_duplicate_exercises

    canonical = exercise(slug="barbell-bench-press", source="free-exercise-db", source_id="0025")
    canonical.media_assets.append(
        ExerciseMediaAsset(
            presentation=MediaPresentation.MALE,
            role=MediaRole.VIDEO,
            sort_order=0,
            media_path="/media/free-exercise-db/bench.mp4",
            media_type=MediaType.VIDEO,
        )
    )
    duplicate = exercise(slug="owner-duplicate-bench", source="owner-video", source_id="a" * 64)
    duplicate.media_assets.append(
        ExerciseMediaAsset(
            presentation=MediaPresentation.MALE,
            role=MediaRole.VIDEO,
            sort_order=0,
            media_path="/media/owner-video/bench.mp4",
            media_type=MediaType.VIDEO,
            source="owner-video",
            source_id="b" * 64,
        )
    )
    db.add_all([canonical, duplicate])
    db.commit()

    report = merge_duplicate_exercises(db, apply=True)

    stored = db.scalars(select(Exercise).where(Exercise.name_en == "Barbell Bench Press")).all()
    db.refresh(canonical, ["media_assets"])
    assert report.merged_exercises == 1
    assert len(stored) == 1
    assert [asset.sort_order for asset in canonical.media_assets] == [0, 1]
    assert canonical.media_assets[1].media_path == "/media/owner-video/bench.mp4"


def test_merges_exact_duplicate_even_without_owner_video_source(db: Session) -> None:
    from app.exercises.owner_video_deduplicate import merge_duplicate_exercises

    canonical = exercise(slug="sit-up", source="free-exercise-db", source_id="one")
    duplicate = exercise(slug="sit-up-variant", source="free-exercise-db", source_id="two")
    canonical.media_assets.append(
        ExerciseMediaAsset(
            presentation=MediaPresentation.FEMALE,
            role=MediaRole.VIDEO,
            sort_order=0,
            media_path="/media/free-exercise-db/one.mp4",
            media_type=MediaType.VIDEO,
        )
    )
    duplicate.media_assets.append(
        ExerciseMediaAsset(
            presentation=MediaPresentation.FEMALE,
            role=MediaRole.VIDEO,
            sort_order=0,
            media_path="/media/free-exercise-db/two.mp4",
            media_type=MediaType.VIDEO,
        )
    )
    db.add_all([canonical, duplicate])
    db.commit()

    report = merge_duplicate_exercises(db, apply=True)

    assert report.merged_exercises == 1
    stored = db.scalars(select(Exercise).where(Exercise.name_en == "Barbell Bench Press")).all()
    assert len(stored) == 1
    db.refresh(stored[0], ["media_assets"])
    assert [asset.sort_order for asset in stored[0].media_assets] == [0, 1]
