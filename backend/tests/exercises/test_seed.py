from collections import Counter
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

EXPECTED_BY_REGION = {"upper_body": 10, "lower_body": 7}
EXPECTED_BY_MUSCLE = {
    "chest": 1,
    "back": 1,
    "shoulders": 3,
    "biceps": 4,
    "triceps": 1,
    "glutes": 1,
    "quadriceps": 4,
    "hamstrings": 1,
    "calves": 1,
}
OWNER_MEDIA_SLUGS = {
    "dumbbell-bench-press",
    "barbell-bent-over-row",
    "dumbbell-lateral-raise",
    "smith-machine-shoulder-press",
    "rear-delt-fly",
    "dumbbell-curl",
    "hammer-curl",
    "cable-curl",
    "barbell-curl",
    "overhead-dumbbell-extension",
    "glute-bridge",
    "goblet-squat",
    "leg-press",
    "leg-extension",
    "dumbbell-lunge",
    "romanian-deadlift",
    "standing-calf-raise",
}


def test_seed_manifest_covers_every_catalog_category() -> None:
    from app.exercises.seed_data import EXERCISE_SEEDS

    assert len(EXERCISE_SEEDS) == 17
    assert len({seed.slug for seed in EXERCISE_SEEDS}) == 17
    assert Counter(seed.body_region.value for seed in EXERCISE_SEEDS) == EXPECTED_BY_REGION
    assert Counter(seed.primary_muscle.value for seed in EXERCISE_SEEDS) == EXPECTED_BY_MUSCLE


def test_seed_manifest_has_complete_bilingual_safe_content() -> None:
    from app.exercises.seed_data import ALTERNATIVE_SEEDS, EXERCISE_SEEDS
    from app.exercises.taxonomy import is_compatible_muscle_focus

    slugs = {seed.slug for seed in EXERCISE_SEEDS}
    for seed in EXERCISE_SEEDS:
        assert seed.name_en.strip()
        assert seed.name_fa.strip()
        assert 3 <= len(seed.instructions_en) <= 6
        assert 3 <= len(seed.instructions_fa) <= 6
        assert all(step.strip() for step in seed.instructions_en)
        assert all(step.strip() for step in seed.instructions_fa)
        assert seed.safety_notes_en and all(note.strip() for note in seed.safety_notes_en)
        assert seed.safety_notes_fa and all(note.strip() for note in seed.safety_notes_fa)
        assert seed.equipment
        assert len(set(seed.equipment)) == len(seed.equipment)
        assert seed.primary_muscle not in seed.secondary_muscles
        assert is_compatible_muscle_focus(seed.primary_muscle, seed.muscle_focus)
        assert len(set(seed.secondary_muscles)) == len(seed.secondary_muscles)
        assert seed.is_programmable is True
        assert seed.movement_pattern.value
        assert seed.exercise_type.value
        assert len(set(seed.caution_tags)) == len(seed.caution_tags)
        combined_copy = " ".join(
            (
                *seed.instructions_en,
                *seed.instructions_fa,
                *seed.safety_notes_en,
                *seed.safety_notes_fa,
            )
        ).casefold()
        assert "medical treatment" not in combined_copy
        assert "درمان پزشکی" not in combined_copy

    assert len(ALTERNATIVE_SEEDS) == 1
    assert len({(item.exercise_slug, item.alternative_slug) for item in ALTERNATIVE_SEEDS}) == 1
    assert all(item.exercise_slug in slugs for item in ALTERNATIVE_SEEDS)
    assert all(item.alternative_slug in slugs for item in ALTERNATIVE_SEEDS)
    assert all(item.exercise_slug != item.alternative_slug for item in ALTERNATIVE_SEEDS)
    assert all(item.reason_en.strip() and item.reason_fa.strip() for item in ALTERNATIVE_SEEDS)


def test_seed_manifest_uses_only_approved_media() -> None:
    from app.exercises.enums import MediaType
    from app.exercises.seed_data import EXERCISE_SEEDS

    owner_media = {seed.slug: seed for seed in EXERCISE_SEEDS if seed.slug in OWNER_MEDIA_SLUGS}
    assert set(owner_media) == OWNER_MEDIA_SLUGS
    assert len(owner_media) == 17
    for seed in owner_media.values():
        assert seed.media_path.startswith("/media/exercises/seed/")
        assert seed.media_path != "/media/exercises/seed/exercise-placeholder.svg"
        assert seed.media_type is MediaType.GIF
        assert seed.media_source_url is None
        assert seed.media_license == "Project owner supplied and authorized"
        assert seed.media_attribution == "Provided by Fitsho project owner"
    assert all(
        seed.media_path != "/media/exercises/seed/exercise-placeholder.svg"
        for seed in EXERCISE_SEEDS
    )


def test_seed_is_idempotent_and_restores_seed_owned_fields(db: Session) -> None:
    from app.exercises.enums import (
        BodyRegion,
        Difficulty,
        Equipment,
        MediaType,
        MuscleFocus,
        MuscleGroup,
    )
    from app.exercises.models import Exercise, ExerciseAlternative, ExerciseEquipment
    from app.exercises.service import seed_exercises

    first = seed_exercises(db)
    ids_before: dict[str, UUID] = {
        slug: exercise_id
        for slug, exercise_id in db.execute(select(Exercise.slug, Exercise.id)).tuples()
    }
    bench_press = db.scalar(select(Exercise).where(Exercise.slug == "dumbbell-bench-press"))
    assert bench_press is not None
    bench_press.name_en = "Outdated Bench Press"
    bench_press.needs_review = True
    bench_press.equipment_items.append(ExerciseEquipment(equipment=Equipment.OTHER))
    custom = Exercise(
        slug="project-owner-custom-exercise",
        name_en="Project Owner Custom Exercise",
        name_fa="حرکت سفارشی مالک پروژه",
        body_region=BodyRegion.CORE,
        primary_muscle=MuscleGroup.LOWER_BACK,
        muscle_focus=MuscleFocus.LUMBAR_ERECTORS,
        difficulty=Difficulty.BEGINNER,
        instructions_en=["Set a stable stance.", "Move with control.", "Return to start."],
        instructions_fa=[
            "در وضعیت پایدار قرار بگیر.",
            "حرکت را کنترل‌شده انجام بده.",
            "به شروع برگرد.",
        ],
        safety_notes_en=["Stop if the movement causes pain."],
        safety_notes_fa=["اگر حرکت باعث درد شد، آن را متوقف کن."],
        media_path="/exercises/exercise-placeholder.svg",
        media_type=MediaType.PLACEHOLDER,
        media_license="Fitsho original",
        media_attribution="Fitsho",
    )
    custom.equipment_items.append(ExerciseEquipment(equipment=Equipment.BODYWEIGHT))
    db.add(custom)
    db.commit()
    custom_id = custom.id

    second = seed_exercises(db)
    db.expire_all()

    ids_after: dict[str, UUID] = {
        slug: exercise_id
        for slug, exercise_id in db.execute(
            select(Exercise.slug, Exercise.id).where(Exercise.slug != custom.slug)
        ).tuples()
    }
    restored_bench_press = db.scalar(
        select(Exercise).where(Exercise.slug == "dumbbell-bench-press")
    )

    assert first.exercises == second.exercises == 17
    assert first.alternatives == second.alternatives == 1
    assert ids_after == ids_before
    assert restored_bench_press is not None
    assert restored_bench_press.is_programmable is True
    assert restored_bench_press.needs_review is False
    assert restored_bench_press.movement_pattern.value == "horizontal_push"
    assert restored_bench_press.name_en == "Dumbbell Bench Press"
    assert {item.equipment for item in restored_bench_press.equipment_items} == {
        Equipment.DUMBBELL,
        Equipment.BENCH,
    }
    preserved_custom = db.scalar(select(Exercise).where(Exercise.slug == custom.slug))
    assert preserved_custom is not None
    assert preserved_custom.id == custom_id
    assert preserved_custom.media_path == "/exercises/exercise-placeholder.svg"
    assert {item.equipment for item in preserved_custom.equipment_items} == {Equipment.BODYWEIGHT}
    assert db.scalar(select(func.count()).select_from(Exercise)) == 18
    assert db.scalar(select(func.count()).select_from(ExerciseAlternative)) == 1


def test_seed_preserves_admin_owned_media(db: Session) -> None:
    from app.exercises.enums import MediaPresentation, MediaRole
    from app.exercises.models import Exercise, ExerciseMediaAsset
    from app.exercises.service import seed_exercises

    seed_exercises(db)
    exercise = db.scalar(select(Exercise).where(Exercise.slug == "romanian-deadlift"))
    assert exercise is not None
    exercise.media_path = "/media/exercises/romanian-deadlift--admin/video.mp4"
    exercise.media_type = "video"
    exercise.media_assets.append(
        ExerciseMediaAsset(
            presentation=MediaPresentation.MALE,
            role=MediaRole.VIDEO,
            sort_order=0,
            media_path="/media/exercises/romanian-deadlift--admin/video.mp4",
            media_type="video",
            source="admin",
        )
    )
    db.commit()

    seed_exercises(db)
    db.refresh(exercise)

    assert exercise.media_path == "/media/exercises/romanian-deadlift--admin/video.mp4"
    assert exercise.media_assets[0].media_path == exercise.media_path


def test_seed_rolls_back_when_commit_fails(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.exercises.models import Exercise
    from app.exercises.service import seed_exercises

    count_before = db.scalar(select(func.count()).select_from(Exercise))

    def unavailable_commit() -> None:
        raise OperationalError("COMMIT", {}, Exception("database unavailable"))

    monkeypatch.setattr(db, "commit", unavailable_commit)

    with pytest.raises(OperationalError):
        seed_exercises(db)

    assert db.scalar(select(func.count()).select_from(Exercise)) == count_before


def test_seed_command_uses_singular_alternative_label() -> None:
    import app.exercises.seed as seed_command
    from app.exercises.service import SeedResult

    formatter = getattr(seed_command, "format_seed_result", None)

    assert formatter is not None
    assert formatter(SeedResult(exercises=17, alternatives=1)) == (
        "Seeded 17 exercises and 1 alternative."
    )
