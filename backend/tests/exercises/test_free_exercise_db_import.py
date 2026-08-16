import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseLabel,
    ExerciseType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
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


def test_importer_maps_forearms_and_preserves_unmapped_anatomy_for_review(
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.free_exercise_db_import import FreeExerciseDbImporter

    source_root = tmp_path / "source"
    record = source_record()
    record.update(
        {
            "name": "Dumbbell Wrist Curl",
            "target": "forearms",
            "muscleGroup": "forearm flexors",
        }
    )
    write_source(source_root, record)
    report = FreeExerciseDbImporter(
        db,
        settings=test_settings,
        source_root=source_root,
        translator=FakeTranslator(),
    ).run()
    exercise = db.scalar(select(Exercise).where(Exercise.source_id == "0001"))

    assert report.imported_records == ["0001"]
    assert exercise is not None
    assert exercise.primary_muscle is MuscleGroup.FOREARMS
    assert exercise.muscle_focus is MuscleFocus.FOREARM_FLEXORS


def test_importer_assigns_source_backed_upper_chest_focus(
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.free_exercise_db_import import FreeExerciseDbImporter

    source_root = tmp_path / "source"
    record = source_record()
    record.update(
        {
            "name": "Incline Bench Press",
            "target": "upper pectorals",
            "muscleGroup": "pectoralis major, clavicular head",
        }
    )
    write_source(source_root, record)

    report = FreeExerciseDbImporter(
        db,
        settings=test_settings,
        source_root=source_root,
        translator=FakeTranslator(),
    ).run()
    exercise = db.scalar(select(Exercise).where(Exercise.source_id == "0001"))

    assert report.validation_failures == []
    assert exercise is not None
    assert exercise.muscle_focus is MuscleFocus.UPPER_CHEST


def test_importer_rejects_known_muscle_when_focus_is_unresolved(
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.free_exercise_db_import import FreeExerciseDbImporter

    source_root = tmp_path / "source"
    record = source_record()
    record.update(
        {
            "name": "Unknown Chest Movement",
            "target": "pectorals",
            "muscleGroup": "pectorals",
        }
    )
    write_source(source_root, record)

    report = FreeExerciseDbImporter(
        db,
        settings=test_settings,
        source_root=source_root,
        translator=FakeTranslator(),
    ).run()

    assert report.validation_failures == ["0001: muscle focus is unresolved"]
    assert report.skipped_records == ["0001"]
    assert db.scalar(select(Exercise).where(Exercise.source_id == "0001")) is None


def test_importer_imports_unmapped_anatomy_with_review_flag_and_cardio_label(
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.free_exercise_db_import import FreeExerciseDbImporter

    source_root = tmp_path / "source"
    record = source_record()
    record.update({"bodyPart": "cardio", "target": "cardiovascular system"})
    write_source(source_root, record)
    report = FreeExerciseDbImporter(
        db,
        settings=test_settings,
        source_root=source_root,
        translator=FakeTranslator(),
    ).run()
    exercise = db.scalar(select(Exercise).where(Exercise.source_id == "0001"))

    assert report.imported_records == ["0001"]
    assert "bodyPart:cardio" in report.unmapped_enum_values
    assert "target:cardiovascular system" in report.unmapped_enum_values
    assert exercise is not None
    assert exercise.body_region is None
    assert exercise.primary_muscle is None
    assert exercise.needs_review is True
    assert {item.label for item in exercise.labels} == {ExerciseLabel.CARDIO}


def test_programming_metadata_classifies_sample_movements_conservatively() -> None:
    from app.exercises.free_exercise_db_import import classify_programming_metadata

    cases = (
        (
            "45 Degree Hyperextension",
            MuscleGroup.LOWER_BACK,
            ["Hinge from hips"],
            MovementPattern.HIP_HINGE,
            ExerciseType.COMPOUND,
            (ExerciseCautionTag.LOWER_BACK_LOADING,),
        ),
        (
            "45-Degree Bicycle Twisting Crunch",
            MuscleGroup.OBLIQUES,
            ["Do not pull on neck"],
            MovementPattern.SPINAL_FLEXION,
            ExerciseType.CORE,
            (ExerciseCautionTag.SPINAL_FLEXION, ExerciseCautionTag.NECK_LOADING),
        ),
        (
            "All Fours Groin Stretch",
            MuscleGroup.ADDUCTORS,
            ["Relax into stretch"],
            MovementPattern.OTHER,
            ExerciseType.MOBILITY,
            (),
        ),
        (
            "Band Assisted Pull-up",
            MuscleGroup.BACK,
            ["Hang with straight arms"],
            MovementPattern.VERTICAL_PULL,
            ExerciseType.COMPOUND,
            (ExerciseCautionTag.OVERHEAD_POSITION,),
        ),
        (
            "Biceps Static Hold",
            MuscleGroup.BICEPS,
            [],
            MovementPattern.ELBOW_FLEXION,
            ExerciseType.ISOLATION,
            (),
        ),
    )

    for name_en, primary_muscle, form_cues_en, pattern, exercise_type, cautions in cases:
        result = classify_programming_metadata(
            name_en=name_en,
            primary_muscle=primary_muscle,
            instructions_en=[],
            steps_en=[],
            form_cues_en=form_cues_en,
            common_mistakes_en=[],
        )

        assert result.movement_pattern is pattern
        assert result.exercise_type is exercise_type
        assert result.caution_tags == cautions


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
    assert len(exercise.media_assets) == 2
    assert translator.calls == [["0001"]]


def test_importer_recopies_existing_media_when_target_storage_is_empty(
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
    replica_settings = test_settings.model_copy(
        update={"media_root": tmp_path / "replica-media"}
    )

    second = FreeExerciseDbImporter(
        db,
        settings=replica_settings,
        source_root=source_root,
        translator=translator,
    ).run()
    exercise = db.scalar(select(Exercise).where(Exercise.source_id == "0001"))

    assert first.imported_records == ["0001"]
    assert second.updated_records == ["0001"]
    assert exercise is not None
    assert all(
        (replica_settings.media_root / asset.media_path.removeprefix("/media/")).is_file()
        for asset in exercise.media_assets
    )


def test_importer_sets_programming_metadata_and_updates_existing_import(
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
    exercise = db.scalar(select(Exercise).where(Exercise.source_id == "0001"))

    assert first.imported_records == ["0001"]
    assert exercise is not None
    assert exercise.movement_pattern is MovementPattern.HORIZONTAL_PUSH
    assert exercise.exercise_type is ExerciseType.COMPOUND
    assert exercise.is_programmable is True
    assert exercise.caution_tag_items == []

    exercise.movement_pattern = MovementPattern.OTHER
    exercise.exercise_type = ExerciseType.OTHER
    exercise.is_programmable = False
    db.commit()

    second = FreeExerciseDbImporter(
        db,
        settings=test_settings,
        source_root=source_root,
        translator=translator,
    ).run()
    db.refresh(exercise)

    assert second.updated_records == ["0001"]
    assert exercise.movement_pattern is MovementPattern.HORIZONTAL_PUSH
    assert exercise.exercise_type is ExerciseType.COMPOUND
    assert exercise.is_programmable is True


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
    assert report.missing_media == []
    assert exercise is not None
    assert len(exercise.media_assets) == 2
    assert all(asset.role.value == "video" for asset in exercise.media_assets)


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


def test_curated_translator_returns_only_local_persian_content() -> None:
    from app.exercises.free_exercise_db_import import (
        CuratedExerciseTranslator,
        ImportCandidate,
        ProgrammingMetadata,
    )

    candidate = ImportCandidate(
        source_id="0001",
        source_metadata={},
        slug="fedb-0001-push-up",
        name_en="Push-Up",
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=MuscleGroup.CHEST,
        muscle_focus=MuscleFocus.MID_CHEST,
        labels=(),
        secondary_muscles=[],
        equipment=[Equipment.BODYWEIGHT],
        difficulty=Difficulty.BEGINNER,
        programming_metadata=ProgrammingMetadata(
            movement_pattern=MovementPattern.HORIZONTAL_PUSH,
            exercise_type=ExerciseType.COMPOUND,
            caution_tags=(),
        ),
        aliases_en=[],
        short_description_en=None,
        instructions_en=["Set up.", "Lower.", "Press."],
        steps_en=["Set up.", "Lower.", "Press."],
        form_cues_en=[],
        common_mistakes_en=[],
        breathing_en=None,
        media_assets=[],
    )
    translator = CuratedExerciseTranslator(
        {
            "0001": {
                "name_fa": "شنا سوئدی",
                "instructions_fa": ["آماده شو.", "پایین برو.", "فشار بده."],
            }
        }
    )

    translations = translator.translate([candidate])

    assert translations["0001"].name_fa == "شنا سوئدی"
    assert translations["0001"].instructions_fa == ["آماده شو.", "پایین برو.", "فشار بده."]


def test_local_translation_catalog_keeps_existing_imported_exercises() -> None:
    from app.exercises.free_exercise_db_translations import CURATED_TRANSLATIONS

    expected_ids = {
        "0489",
        "drv-45-degree-bycicle-twisting-crunch",
        "drv-45-degree-bycicle-twisting-crunch-1",
        "drv-stretching-all-fours-squad-stretch",
        "0970",
        "drv-band-bent-over-rear-lateral-raise",
        "3006",
        "drv-band-hip-adduction",
        "0983",
        "1017",
        "drv-band-one-leg-kickback-bent-position",
        "new-band-overhead-triceps-extension",
        "0976",
        "0991",
        "drv-band-decline-sit-ups",
        "0980",
        "0990",
        "drv-stretching-band-warm-up-shoulder-stretch",
        "0002",
        "0999",
        "1005",
        "0988",
        "1408",
        "1022",
        "3144",
    }
    assert expected_ids.issubset(CURATED_TRANSLATIONS)
    assert all(CURATED_TRANSLATIONS[source_id]["name_fa"] for source_id in expected_ids)


def test_local_translation_catalog_matches_normalized_instruction_limit() -> None:
    from app.exercises.free_exercise_db_translations import CURATED_TRANSLATIONS

    assert len(CURATED_TRANSLATIONS["0983"]["instructions_fa"]) == 6
