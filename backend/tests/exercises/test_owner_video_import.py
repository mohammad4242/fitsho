import hashlib
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    MediaPresentation,
    MediaRole,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.models import Exercise, ExerciseEquipment, ExerciseMediaAsset
from app.exercises.owner_video_analysis import OwnerVideoAnalysis
from app.exercises.owner_video_media import PreparedOwnerVideo, PublishedOwnerVideo


def analysis_for(
    source_id: str,
    *,
    decision: str = "create_new",
    existing_exercise_id: UUID | None = None,
    match_confidence: float = 0.0,
    identification_confidence: float = 0.98,
    presentation: str = "male",
    presentation_confidence: float = 0.95,
) -> OwnerVideoAnalysis:
    return OwnerVideoAnalysis.model_validate(
        {
            "source_id": source_id,
            "name_en": "Push-Up",
            "name_fa": "شنا سوئدی",
            "visible_text": ["PUSH UP"],
            "aliases_en": ["Press-Up"],
            "body_region": "upper_body",
            "primary_muscle": "chest",
            "muscle_focus": "mid_chest",
            "secondary_muscles": ["triceps"],
            "equipment": ["bodyweight"],
            "difficulty": "beginner",
            "movement_pattern": "horizontal_push",
            "exercise_type": "compound",
            "labels": [],
            "caution_tags": ["wrist_loading"],
            "instructions_en": ["Set up.", "Lower.", "Press."],
            "instructions_fa": ["آماده شو.", "پایین برو.", "بالا برو."],
            "safety_notes_en": ["Keep the neck neutral."],
            "safety_notes_fa": ["گردن را خنثی نگه دار."],
            "short_description_en": "A horizontal bodyweight press.",
            "short_description_fa": "یک حرکت فشاری افقی با وزن بدن.",
            "form_cues_en": ["Brace the trunk."],
            "form_cues_fa": ["میان‌تنه را ثابت نگه دار."],
            "common_mistakes_en": ["Letting the hips sag."],
            "common_mistakes_fa": ["افتادن لگن."],
            "breathing_en": "Exhale while pressing.",
            "breathing_fa": "هنگام بالا رفتن بازدم کن.",
            "presentation": presentation,
            "presentation_confidence": presentation_confidence,
            "identification_confidence": identification_confidence,
            "decision": decision,
            "match_confidence": match_confidence,
            "existing_exercise_id": existing_exercise_id,
            "review_reasons": [],
        }
    )


class FakeAnalyzer:
    def __init__(self, results: dict[str, OwnerVideoAnalysis | Exception]) -> None:
        self.results = results
        self.calls: list[str] = []

    def analyze(
        self,
        prepared: PreparedOwnerVideo,
        catalogue: object,
    ) -> OwnerVideoAnalysis:
        self.calls.append(prepared.source_id)
        result = self.results[prepared.source_id]
        if isinstance(result, Exception):
            raise result
        return result


def fake_prepare(
    source_path: Path,
    *,
    settings: Settings,
) -> PreparedOwnerVideo:
    source_id = hashlib.sha256(source_path.read_bytes()).hexdigest()
    work = settings.owner_video_import_work_root / source_id
    work.mkdir(parents=True, exist_ok=True)
    muted = work / "muted.mp4"
    muted.write_bytes(b"muted-" + source_path.read_bytes())
    frames = tuple(work / f"frame-{index}.jpg" for index in range(5))
    for frame in frames:
        frame.write_bytes(b"frame")
    return PreparedOwnerVideo(
        source_path=source_path,
        source_id=source_id,
        muted_path=muted,
        frame_paths=frames,
        duration_seconds=1.0,
    )


def fake_publish(
    prepared: PreparedOwnerVideo,
    *,
    settings: Settings,
) -> PublishedOwnerVideo:
    relative = Path("owner-video") / prepared.source_id[:2] / f"{prepared.source_id}.mp4"
    destination = settings.media_root / relative
    existed = destination.exists()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(prepared.muted_path.read_bytes())
    return PublishedOwnerVideo(
        public_path=f"/media/{relative.as_posix()}",
        absolute_path=destination,
        created=not existed,
    )


def importer_settings(test_settings: Settings, tmp_path: Path) -> Settings:
    return test_settings.model_copy(
        update={
            "media_root": tmp_path / "media",
            "owner_video_import_work_root": tmp_path / "work",
        }
    )


def write_video(root: Path, name: str, contents: bytes) -> tuple[Path, str]:
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_bytes(contents)
    return path, hashlib.sha256(contents).hexdigest()


def existing_push_up(slug: str = "existing-push-up") -> Exercise:
    exercise = Exercise(
        slug=slug,
        name_en="Push-Up",
        name_fa="شنا سوئدی",
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
        aliases_en=["Press-Up"],
        is_programmable=True,
    )
    exercise.equipment_items.append(ExerciseEquipment(equipment=Equipment.BODYWEIGHT))
    return exercise


def build_importer(
    db: Session,
    settings: Settings,
    source_root: Path,
    analyzer: FakeAnalyzer,
) -> object:
    from app.exercises.owner_video_import import OwnerVideoImporter

    return OwnerVideoImporter(
        db,
        settings=settings,
        source_root=source_root,
        analyzer=analyzer,
        prepare_video=fake_prepare,
        publish_video=fake_publish,
    )


def test_importer_matches_existing_exercise_and_uses_next_media_sort_order(
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "raw"
    _, source_id = write_video(source_root, "one.mp4", b"one")
    existing = existing_push_up()
    existing.media_assets.extend(
        [
            ExerciseMediaAsset(
                presentation=MediaPresentation.MALE,
                role=MediaRole.VIDEO,
                sort_order=0,
                media_path="/media/first.mp4",
                media_type=MediaType.VIDEO,
            ),
            ExerciseMediaAsset(
                presentation=MediaPresentation.MALE,
                role=MediaRole.VIDEO,
                sort_order=1,
                media_path="/media/second.mp4",
                media_type=MediaType.VIDEO,
            ),
        ]
    )
    db.add(existing)
    db.commit()
    analyzer = FakeAnalyzer(
        {
            source_id: analysis_for(
                source_id,
                decision="match_existing",
                existing_exercise_id=existing.id,
                match_confidence=0.99,
            )
        }
    )
    settings = importer_settings(test_settings, tmp_path)

    report = build_importer(db, settings, source_root, analyzer).run(apply=True)

    db.refresh(existing, ["media_assets"])
    owner_asset = next(asset for asset in existing.media_assets if asset.source == "owner-video")
    assert report.matched_existing == 1
    assert report.created_new == 0
    assert owner_asset.sort_order == 2
    assert existing.media_path == "/media/original.mp4"


def test_importer_creates_complete_new_exercise_and_second_run_is_idempotent(
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "raw"
    _, source_id = write_video(source_root, "one.mp4", b"one")
    analyzer = FakeAnalyzer({source_id: analysis_for(source_id)})
    settings = importer_settings(test_settings, tmp_path)
    importer = build_importer(db, settings, source_root, analyzer)

    first = importer.run(apply=True)
    second = importer.run(apply=True)

    exercise = db.scalar(
        select(Exercise).where(Exercise.source == "owner-video", Exercise.source_id == source_id)
    )
    assert exercise is not None
    assert first.created_new == 1
    assert second.duplicate_videos == 1
    assert analyzer.calls == [source_id]
    assert exercise.name_fa == "شنا سوئدی"
    assert exercise.is_programmable is True
    assert exercise.needs_review is False
    assert {item.equipment for item in exercise.equipment_items} == {Equipment.BODYWEIGHT}
    assert len(exercise.media_assets) == 1
    assert exercise.media_assets[0].sort_order == 0


def test_uncertain_match_creates_unprogrammable_review_exercise(
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "raw"
    _, source_id = write_video(source_root, "one.mp4", b"one")
    existing = existing_push_up()
    db.add(existing)
    db.commit()
    analyzer = FakeAnalyzer(
        {
            source_id: analysis_for(
                source_id,
                decision="match_existing",
                existing_exercise_id=existing.id,
                match_confidence=0.40,
                presentation="female",
                presentation_confidence=0.20,
            )
        }
    )
    settings = importer_settings(test_settings, tmp_path)

    report = build_importer(db, settings, source_root, analyzer).run(apply=True)

    review = db.scalar(
        select(Exercise).where(Exercise.source == "owner-video", Exercise.source_id == source_id)
    )
    assert review is not None
    assert report.created_new == 1
    assert report.needs_review == 1
    assert review.needs_review is True
    assert review.is_programmable is False
    assert review.media_assets[0].presentation is MediaPresentation.UNSPECIFIED
    assert all(asset.source is None for asset in existing.media_assets)
    assert review.source_metadata_en is not None
    assert review.source_metadata_en["owner_video_analysis"]["review_reasons"]


def test_database_failure_rolls_back_rows_and_removes_newly_published_media(
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "raw"
    _, source_id = write_video(source_root, "one.mp4", b"one")
    conflicting = existing_push_up("conflicting-owner-record")
    conflicting.source = "owner-video"
    conflicting.source_id = source_id
    db.add(conflicting)
    db.commit()
    analyzer = FakeAnalyzer({source_id: analysis_for(source_id)})
    settings = importer_settings(test_settings, tmp_path)

    report = build_importer(db, settings, source_root, analyzer).run(apply=True)

    assert report.failed == 1
    assert (
        db.scalar(
            select(func.count())
            .select_from(Exercise)
            .where(Exercise.source == "owner-video", Exercise.source_id == source_id)
        )
        == 1
    )
    assert db.scalar(
        select(ExerciseMediaAsset).where(
            ExerciseMediaAsset.source == "owner-video",
            ExerciseMediaAsset.source_id == source_id,
        )
    ) is None
    accepted = settings.media_root / "owner-video" / source_id[:2] / f"{source_id}.mp4"
    assert not accepted.exists()


def test_failed_video_does_not_stop_the_next_video(
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "raw"
    _, first_id = write_video(source_root, "01-first.mp4", b"first")
    _, second_id = write_video(source_root, "02-second.mp4", b"second")
    analyzer = FakeAnalyzer(
        {
            first_id: RuntimeError("analysis unavailable"),
            second_id: analysis_for(second_id),
        }
    )
    settings = importer_settings(test_settings, tmp_path)

    report = build_importer(db, settings, source_root, analyzer).run(apply=True)

    assert report.total == 2
    assert report.processed == 2
    assert report.failed == 1
    assert report.created_new == 1
    assert db.scalar(
        select(Exercise).where(
            Exercise.source == "owner-video",
            Exercise.source_id == second_id,
        )
    ) is not None
