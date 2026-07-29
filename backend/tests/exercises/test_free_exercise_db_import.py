import json
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.exercises.enums import BodyRegion, Difficulty, Equipment, MuscleGroup
from app.exercises.models import Exercise

MP4_BYTES = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2"
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"


class FakeTranslator:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def translate(self, records: list[object]) -> dict[str, object]:
        from app.exercises.free_exercise_db_import import ExerciseTranslation

        source_ids = [record.source_id for record in records]
        self.calls.append(source_ids)
        return {
            record.source_id: ExerciseTranslation(
                name_fa="شنا سوئدی",
                instructions_fa=["آماده شو.", "پایین برو.", "فشار بده."],
            )
            for record in records
        }


class FailingTranslator:
    def translate(self, records: list[object]) -> dict[str, object]:
        raise AssertionError("Dry-run must not call the translator")


def source_record() -> dict[str, object]:
    return {
        "id": "0001",
        "name": "Push-Up",
        "aliases": ["Press-up"],
        "bodyPart": "chest",
        "target": "pectorals",
        "secondaryMuscles": ["triceps"],
        "equipment": "body weight",
        "difficulty": "beginner",
        "shortDescription": "A horizontal bodyweight press.",
        "instructions": "Lower and press with control.",
        "steps": ["Set up.", "Lower.", "Press."],
        "formCues": ["Brace your trunk."],
        "commonMistakes": ["Letting the hips sag."],
        "breathing": "Exhale while pressing.",
        "videos": {
            "male": "https://source.invalid/videos/male/push-up.mp4",
            "female": "https://source.invalid/videos/female/push-up.mp4",
        },
        "thumbnails": {
            "male": "https://source.invalid/thumbnails/male/push-up.jpg",
            "female": "https://source.invalid/thumbnails/female/push-up.jpg",
        },
    }


def write_source(
    root: Path,
    record: dict[str, object],
    *,
    missing: set[str] | None = None,
) -> None:
    (root / "data").mkdir(parents=True)
    (root / "data" / "exercises.json").write_text(json.dumps([record]), encoding="utf-8")
    assets = {
        "videos/male/push-up.mp4": MP4_BYTES,
        "videos/female/push-up.mp4": MP4_BYTES,
        "thumbnails/male/push-up.jpg": JPEG_BYTES,
        "thumbnails/female/push-up.jpg": JPEG_BYTES,
    }
    for relative_path, contents in assets.items():
        if missing is not None and relative_path in missing:
            continue
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)


def test_free_exercise_db_maps_known_values_and_reports_unknown_values() -> None:
    from app.exercises.free_exercise_db_import import (
        map_body_region,
        map_difficulty,
        map_equipment,
        map_muscle_group,
    )

    assert map_body_region("waist") is BodyRegion.CORE
    assert map_muscle_group("rectus abdominis") is MuscleGroup.ABS
    assert map_muscle_group("adductors") is MuscleGroup.ADDUCTORS
    assert map_muscle_group("lower back") is MuscleGroup.LOWER_BACK
    assert map_equipment("smith machine") is Equipment.MACHINE
    assert map_difficulty("advanced") is Difficulty.ADVANCED
    assert map_body_region("cardio") is None
    assert map_muscle_group("cardiovascular system") is None


def test_importer_prevents_duplicates_on_a_second_run(
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.free_exercise_db_import import FreeExerciseDbImporter

    source_root = tmp_path / "source"
    write_source(source_root, source_record())
    translator = FakeTranslator()

    first = FreeExerciseDbImporter(
        db,
        settings=test_settings,
        source_root=source_root,
        translator=translator,
    ).run()
    second = FreeExerciseDbImporter(
        db,
        settings=test_settings,
        source_root=source_root,
        translator=translator,
    ).run()

    exercise = db.scalar(select(Exercise).where(Exercise.source_id == "0001"))

    assert first.imported_records == ["0001"]
    assert second.skipped_records == ["0001"]
    assert (
        db.scalar(
            select(func.count())
            .select_from(Exercise)
            .where(Exercise.source == "free-exercise-db")
        )
        == 1
    )
    assert exercise is not None
    assert exercise.name_fa == "شنا سوئدی"
    assert exercise.needs_review is True
    assert len(exercise.media_assets) == 4
    assert translator.calls == [["0001"]]


def test_importer_dry_run_does_not_write_database_files_or_translations(
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.free_exercise_db_import import FreeExerciseDbImporter

    source_root = tmp_path / "source"
    write_source(source_root, source_record())

    report = FreeExerciseDbImporter(
        db,
        settings=test_settings,
        source_root=source_root,
        translator=FailingTranslator(),
        dry_run=True,
    ).run()

    assert report.imported_records == ["0001"]
    assert (
        db.scalar(
            select(func.count())
            .select_from(Exercise)
            .where(Exercise.source == "free-exercise-db")
        )
        == 0
    )
    assert not test_settings.media_root.exists()


def test_importer_reports_missing_media_but_imports_available_variants(
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.free_exercise_db_import import FreeExerciseDbImporter

    source_root = tmp_path / "source"
    write_source(source_root, source_record(), missing={"thumbnails/female/push-up.jpg"})

    report = FreeExerciseDbImporter(
        db,
        settings=test_settings,
        source_root=source_root,
        translator=FakeTranslator(),
    ).run()
    exercise = db.scalar(select(Exercise).where(Exercise.source_id == "0001"))

    assert report.imported_records == ["0001"]
    assert report.missing_media == ["0001:female:thumbnail"]
    assert exercise is not None
    assert len(exercise.media_assets) == 3


def test_importer_reports_invalid_records_without_writing_them(
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.free_exercise_db_import import FreeExerciseDbImporter

    source_root = tmp_path / "source"
    invalid = source_record()
    invalid["steps"] = "not a list"
    write_source(source_root, invalid)

    report = FreeExerciseDbImporter(
        db,
        settings=test_settings,
        source_root=source_root,
        translator=FakeTranslator(),
    ).run()

    assert report.validation_failures == ["0001: steps must be a list of text values"]
    assert report.skipped_records == ["0001"]
    assert (
        db.scalar(
            select(func.count())
            .select_from(Exercise)
            .where(Exercise.source == "free-exercise-db")
        )
        == 0
    )


def test_opencode_zen_translator_returns_persian_name_and_steps() -> None:
    from app.exercises.free_exercise_db_import import (
        ImportCandidate,
        OpenCodeZenExerciseTranslator,
    )

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "translations": [
                            {
                                "source_id": "0001",
                                "name_fa": "شنا سوئدی",
                                "instructions_fa": ["آماده شو.", "پایین برو.", "فشار بده."],
                            }
                        ]
                    }
                )
            },
        )

    candidate = ImportCandidate(
        source_id="0001",
        source_metadata={},
        slug="fedb-0001-push-up",
        name_en="Push-Up",
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=MuscleGroup.CHEST,
        secondary_muscles=[],
        equipment=[Equipment.BODYWEIGHT],
        difficulty=Difficulty.BEGINNER,
        aliases_en=[],
        short_description_en=None,
        instructions_en=["Set up.", "Lower.", "Press."],
        steps_en=["Set up.", "Lower.", "Press."],
        form_cues_en=[],
        common_mistakes_en=[],
        breathing_en=None,
        media_assets=[],
    )
    settings = Settings(opencode_zen_api_key="test-key", opencode_zen_base_url="https://zen.test/v1")
    translator = OpenCodeZenExerciseTranslator(
        settings,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    translations = translator.translate([candidate])

    assert translations["0001"].name_fa == "شنا سوئدی"
    assert translations["0001"].instructions_fa == ["آماده شو.", "پایین برو.", "فشار بده."]
    assert requests[0].url == "https://zen.test/v1/responses"
    assert requests[0].headers["authorization"] == "Bearer test-key"
