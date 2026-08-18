from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exercises.models import Exercise


def test_exercise_has_nullable_muscle_focus_column_and_composite_index() -> None:
    column = Exercise.__table__.c.muscle_focus
    assert column.nullable is True
    assert column.type.length == 40
    assert "ix_exercises_primary_muscle_muscle_focus" in {
        index.name for index in Exercise.__table__.indexes
    }


def test_exercise_content_type_defaults_to_exercise(db: Session) -> None:
    from app.exercises.enums import ExerciseContentType

    exercise = make_exercise("default-content-type")
    db.add(exercise)
    db.flush()

    assert exercise.content_type is ExerciseContentType.EXERCISE


def test_exercise_accepts_guide_content_type(db: Session) -> None:
    from app.exercises.enums import ExerciseContentType

    exercise = make_exercise("guide-content-type")
    exercise.content_type = ExerciseContentType.GUIDE
    db.add(exercise)
    db.flush()

    assert exercise.content_type is ExerciseContentType.GUIDE


def test_exercise_media_role_has_no_thumbnail() -> None:
    from app.exercises.enums import MediaRole

    assert [role.value for role in MediaRole] == ["video"]


def make_exercise(slug: str = "push-up") -> Exercise:
    from app.exercises.enums import (
        BodyRegion,
        Difficulty,
        MediaType,
        MuscleFocus,
        MuscleGroup,
    )

    return Exercise(
        slug=slug,
        name_en="Push-Up",
        name_fa="شنا سوئدی",
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=MuscleGroup.CHEST,
        muscle_focus=MuscleFocus.MID_CHEST,
        difficulty=Difficulty.BEGINNER,
        instructions_en=[
            "Brace your trunk.",
            "Lower your chest with control.",
            "Press back to the start.",
        ],
        instructions_fa=[
            "میان‌تنه را ثابت نگه دار.",
            "سینه را کنترل‌شده پایین ببر.",
            "به وضعیت شروع برگرد.",
        ],
        safety_notes_en=["Keep your neck neutral."],
        safety_notes_fa=["گردن را در وضعیت خنثی نگه دار."],
        media_path="/exercises/exercise-placeholder.svg",
        media_type=MediaType.PLACEHOLDER,
        media_license="Fitsho original",
        media_attribution="Fitsho",
    )


def test_exercise_stores_controlled_catalog_data(db: Session) -> None:
    from app.exercises.enums import Equipment, MuscleGroup
    from app.exercises.models import (
        Exercise,
        ExerciseEquipment,
        ExerciseSecondaryMuscle,
    )

    exercise = make_exercise()
    exercise.secondary_muscles.append(ExerciseSecondaryMuscle(muscle=MuscleGroup.TRICEPS))
    exercise.equipment_items.extend(
        [
            ExerciseEquipment(equipment=Equipment.BODYWEIGHT),
            ExerciseEquipment(equipment=Equipment.BENCH),
        ]
    )
    db.add(exercise)
    db.flush()
    db.expire(exercise, ["secondary_muscles", "equipment_items"])

    stored = db.scalar(select(Exercise).where(Exercise.slug == "push-up"))

    assert stored is not None
    assert stored.name_fa == "شنا سوئدی"
    assert [item.muscle.value for item in stored.secondary_muscles] == ["triceps"]
    assert [item.equipment.value for item in stored.equipment_items] == [
        "bench",
        "bodyweight",
    ]
    assert stored.is_active is True


def test_exercise_stores_lower_back_as_a_back_focus(db: Session) -> None:
    from app.exercises.enums import BodyRegion, MuscleFocus, MuscleGroup
    from app.exercises.models import Exercise

    exercise = make_exercise("back-extension")
    exercise.body_region = BodyRegion.UPPER_BODY
    exercise.primary_muscle = MuscleGroup.BACK
    exercise.muscle_focus = MuscleFocus.LOWER_BACK
    db.add(exercise)
    db.flush()

    stored = db.scalar(select(Exercise).where(Exercise.slug == "back-extension"))

    assert stored is not None
    assert stored.body_region is BodyRegion.UPPER_BODY
    assert stored.primary_muscle is MuscleGroup.BACK
    assert stored.muscle_focus is MuscleFocus.LOWER_BACK


def test_exercise_stores_import_source_metadata_and_review_status(db: Session) -> None:
    exercise = make_exercise("source-backed-push-up")
    exercise.source = "free-exercise-db"
    exercise.source_id = "0001"
    exercise.aliases_en = ["Press-up"]
    exercise.short_description_en = "A horizontal bodyweight press."
    exercise.steps_en = ["Set up.", "Lower.", "Press."]
    exercise.form_cues_en = ["Keep the trunk braced."]
    exercise.common_mistakes_en = ["Letting the hips sag."]
    exercise.breathing_en = "Exhale while pressing."
    exercise.source_metadata_en = {"compound": True, "unilateral": False}
    exercise.needs_review = True
    db.add(exercise)
    db.flush()
    db.expunge(exercise)

    stored = db.scalar(select(Exercise).where(Exercise.slug == "source-backed-push-up"))

    assert stored is not None
    assert stored.source == "free-exercise-db"
    assert stored.source_id == "0001"
    assert stored.aliases_en == ["Press-up"]
    assert stored.short_description_en == "A horizontal bodyweight press."
    assert stored.steps_en == ["Set up.", "Lower.", "Press."]
    assert stored.form_cues_en == ["Keep the trunk braced."]
    assert stored.common_mistakes_en == ["Letting the hips sag."]
    assert stored.breathing_en == "Exhale while pressing."
    assert stored.source_metadata_en == {"compound": True, "unilateral": False}
    assert stored.needs_review is True


def test_exercise_stores_programming_metadata(db: Session) -> None:
    from app.workouts.program_engine.enums import (
        BodyPosition,
        ImpactLimit,
        Laterality,
        LoadLimit,
        SkillDemand,
        StabilityDemand,
    )

    exercise = make_exercise("programming-metadata")
    exercise.body_position = BodyPosition.SUPPORTED
    exercise.stability_demand = StabilityDemand.HIGH
    exercise.skill_demand = SkillDemand.MODERATE
    exercise.impact_level = ImpactLimit.LOW
    exercise.axial_loading_level = LoadLimit.NONE
    exercise.fatigue_cost = 4
    exercise.setup_cost = 2
    exercise.laterality = Laterality.UNILATERAL
    exercise.substitution_group = "horizontal_push"
    exercise.range_of_motion_profile = ["deep_knee_flexion", "supported"]
    db.add(exercise)
    db.flush()
    db.expire(exercise)

    stored = db.scalar(select(Exercise).where(Exercise.slug == "programming-metadata"))

    assert stored is not None
    assert stored.body_position is BodyPosition.SUPPORTED
    assert stored.stability_demand is StabilityDemand.HIGH
    assert stored.skill_demand is SkillDemand.MODERATE
    assert stored.impact_level is ImpactLimit.LOW
    assert stored.axial_loading_level is LoadLimit.NONE
    assert stored.fatigue_cost == 4
    assert stored.setup_cost == 2
    assert stored.laterality is Laterality.UNILATERAL
    assert stored.substitution_group == "horizontal_push"
    assert stored.range_of_motion_profile == ["deep_knee_flexion", "supported"]


def test_legacy_exercise_has_nullable_programming_metadata(db: Session) -> None:
    exercise = make_exercise("legacy-programming-metadata")
    db.add(exercise)
    db.flush()

    stored = db.scalar(select(Exercise).where(Exercise.slug == "legacy-programming-metadata"))

    assert stored is not None
    assert stored.body_position is None
    assert stored.stability_demand is None
    assert stored.skill_demand is None
    assert stored.impact_level is None
    assert stored.axial_loading_level is None
    assert stored.fatigue_cost is None
    assert stored.setup_cost is None
    assert stored.laterality is None
    assert stored.substitution_group is None
    assert stored.range_of_motion_profile is None


def test_exercise_slug_is_unique(db: Session) -> None:
    db.add_all([make_exercise(), make_exercise()])

    with pytest.raises(IntegrityError) as error:
        db.flush()

    assert "uq_exercises_slug" in str(error.value)


def test_exercise_database_rejects_incompatible_primary_muscle_focus(db: Session) -> None:
    from app.exercises.enums import MuscleFocus

    exercise = make_exercise("invalid-focus")
    exercise.muscle_focus = MuscleFocus.REAR_DELT
    db.add(exercise)

    with pytest.raises(IntegrityError) as error:
        db.flush()

    assert "ck_exercises_primary_muscle_focus_compatible" in str(error.value)


def test_exercise_database_requires_focus_for_known_primary_muscle(db: Session) -> None:
    exercise = make_exercise("missing-focus")
    exercise.muscle_focus = None
    db.add(exercise)

    with pytest.raises(IntegrityError) as error:
        db.flush()

    assert "ck_exercises_primary_muscle_focus_compatible" in str(error.value)


@pytest.mark.parametrize("primary_muscle", ["abductors", "legs"])
def test_exercise_database_accepts_new_lower_body_muscle_groups(
    db: Session,
    primary_muscle: str,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO exercises (
                id, slug, name_en, name_fa, body_region, primary_muscle, muscle_focus,
                difficulty, instructions_en, instructions_fa,
                safety_notes_en, safety_notes_fa, media_path, media_type, content_type
            ) VALUES (
                :id, :slug, 'Leg Exercise', 'حرکت پا', 'lower_body', :primary_muscle, NULL,
                'beginner', '[\"Step one\", \"Step two\", \"Step three\"]',
                '[\"گام یک\", \"گام دو\", \"گام سه\"]', '[\"Use control\"]',
                '[\"حرکت را کنترل کن\"]', '/exercises/exercise-placeholder.svg',
                'placeholder', 'exercise'
            )
            """
        ),
        {"id": uuid4(), "slug": f"{primary_muscle}-exercise", "primary_muscle": primary_muscle},
    )


@pytest.mark.parametrize(
    ("column", "invalid_value", "constraint_name"),
    [
        ("body_region", "arms", "ck_exercises_body_region_values"),
        ("primary_muscle", "pelvic_floor", "ck_exercises_primary_muscle_values"),
        ("primary_muscle", "core_stability", "ck_exercises_primary_muscle_values"),
        ("muscle_focus", "inner_chest", "ck_exercises_muscle_focus_values"),
        ("difficulty", "expert", "ck_exercises_difficulty_values"),
        ("body_position", "hanging", "ck_exercises_body_position_values"),
        ("stability_demand", "extreme", "ck_exercises_stability_demand_values"),
        ("skill_demand", "expert", "ck_exercises_skill_demand_values"),
        ("impact_level", "extreme", "ck_exercises_impact_level_values"),
        ("axial_loading_level", "extreme", "ck_exercises_axial_loading_level_values"),
        ("laterality", "alternating", "ck_exercises_laterality_values"),
        ("media_type", "youtube", "ck_exercises_media_type_values"),
        ("content_type", "article", "ck_exercises_content_type_values"),
    ],
)
def test_exercise_database_rejects_invalid_controlled_values(
    db: Session,
    column: str,
    invalid_value: str,
    constraint_name: str,
) -> None:
    values = {
        "id": uuid4(),
        "slug": f"invalid-{column.replace('_', '-')}",
        "body_region": "upper_body",
        "primary_muscle": "chest",
        "muscle_focus": "mid_chest",
        "difficulty": "beginner",
        "media_type": "placeholder",
        "content_type": "exercise",
        "body_position": None,
        "stability_demand": None,
        "skill_demand": None,
        "impact_level": None,
        "axial_loading_level": None,
        "laterality": None,
    }
    values[column] = invalid_value

    with pytest.raises(IntegrityError) as error:
        db.execute(
            text(
                """
                INSERT INTO exercises (
                    id, slug, name_en, name_fa, body_region, primary_muscle, muscle_focus,
                    difficulty, body_position, stability_demand, skill_demand,
                    impact_level, axial_loading_level, laterality,
                    instructions_en, instructions_fa,
                    safety_notes_en, safety_notes_fa, media_path, media_type, content_type
                ) VALUES (
                    :id, :slug, 'Push-Up', 'شنا سوئدی', :body_region,
                    :primary_muscle, :muscle_focus, :difficulty,
                    :body_position, :stability_demand, :skill_demand,
                    :impact_level, :axial_loading_level, :laterality,
                    '["Step one", "Step two", "Step three"]',
                    '["گام یک", "گام دو", "گام سه"]', '["Use control"]',
                    '["حرکت را کنترل کن"]', '/exercises/exercise-placeholder.svg',
                    :media_type, :content_type
                )
                """
            ),
            values,
        )

    assert constraint_name in str(error.value)


@pytest.mark.parametrize(
    ("field", "value", "constraint_name"),
    [
        ("fatigue_cost", 0, "ck_exercises_fatigue_cost_range"),
        ("fatigue_cost", 6, "ck_exercises_fatigue_cost_range"),
        ("setup_cost", 0, "ck_exercises_setup_cost_range"),
        ("setup_cost", 6, "ck_exercises_setup_cost_range"),
    ],
)
def test_exercise_database_rejects_out_of_range_programming_cost(
    db: Session,
    field: str,
    value: int,
    constraint_name: str,
) -> None:
    exercise = make_exercise(f"invalid-{field.replace('_', '-')}-{value}")
    setattr(exercise, field, value)
    db.add(exercise)

    with pytest.raises(IntegrityError) as error:
        db.flush()

    assert constraint_name in str(error.value)


def test_exercise_database_rejects_invalid_equipment(db: Session) -> None:
    exercise = make_exercise()
    db.add(exercise)
    db.flush()

    with pytest.raises(IntegrityError) as error:
        db.execute(
            text(
                """
                INSERT INTO exercise_equipment (exercise_id, equipment)
                VALUES (:exercise_id, 'kettlebell')
                """
            ),
            {"exercise_id": exercise.id},
        )

    assert "ck_exercise_equipment_equipment_values" in str(error.value)


def test_exercise_database_rejects_duplicate_associations(db: Session) -> None:
    from app.exercises.enums import Equipment, MuscleGroup
    from app.exercises.models import ExerciseEquipment, ExerciseSecondaryMuscle

    exercise = make_exercise()
    exercise.secondary_muscles.extend(
        [
            ExerciseSecondaryMuscle(muscle=MuscleGroup.TRICEPS),
            ExerciseSecondaryMuscle(muscle=MuscleGroup.TRICEPS),
        ]
    )
    exercise.equipment_items.extend(
        [
            ExerciseEquipment(equipment=Equipment.BODYWEIGHT),
            ExerciseEquipment(equipment=Equipment.BODYWEIGHT),
        ]
    )
    db.add(exercise)

    with pytest.raises(IntegrityError):
        db.flush()


def test_exercise_database_rejects_self_alternative(db: Session) -> None:
    from app.exercises.models import ExerciseAlternative

    exercise = make_exercise()
    db.add(exercise)
    db.flush()
    db.add(
        ExerciseAlternative(
            exercise_id=exercise.id,
            alternative_exercise_id=exercise.id,
            reason_en="Use the same exercise.",
            reason_fa="همان حرکت را استفاده کن.",
        )
    )

    with pytest.raises(IntegrityError) as error:
        db.flush()

    assert "ck_exercise_alternatives_distinct_exercises" in str(error.value)


def test_exercise_stores_programming_metadata_and_caution_tags(db: Session) -> None:
    from app.exercises.enums import (
        ExerciseCautionTag,
        ExerciseType,
        MovementPattern,
    )
    from app.exercises.models import ExerciseCautionTagItem

    exercise = make_exercise("dumbbell-press")
    exercise.movement_pattern = MovementPattern.HORIZONTAL_PUSH
    exercise.exercise_type = ExerciseType.COMPOUND
    exercise.is_programmable = True
    exercise.caution_tag_items.append(
        ExerciseCautionTagItem(caution_tag=ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION)
    )
    db.add(exercise)
    db.flush()
    db.expire(exercise)

    stored = db.scalar(select(Exercise).where(Exercise.slug == "dumbbell-press"))

    assert stored is not None
    assert stored.movement_pattern is MovementPattern.HORIZONTAL_PUSH
    assert stored.exercise_type is ExerciseType.COMPOUND
    assert stored.is_programmable is True
    assert [item.caution_tag for item in stored.caution_tag_items] == [
        ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION
    ]


def test_exercise_stores_separate_male_and_female_media_metadata(db: Session) -> None:
    from app.exercises.enums import MediaPresentation, MediaRole, MediaType
    from app.exercises.models import ExerciseMediaAsset

    exercise = make_exercise("variant-media-push-up")
    exercise.media_assets.extend(
        [
            ExerciseMediaAsset(
                presentation=MediaPresentation.MALE,
                role=MediaRole.VIDEO,
                media_path="/media/push-up-male.mp4",
                media_type=MediaType.VIDEO,
                media_source_url="https://source.example/male.mp4",
                media_license="MIT",
                media_attribution="Male creator",
            ),
            ExerciseMediaAsset(
                presentation=MediaPresentation.FEMALE,
                role=MediaRole.VIDEO,
                media_path="/media/push-up-female.mp4",
                media_type=MediaType.VIDEO,
                media_source_url="https://source.example/female.mp4",
                media_license="MIT",
                media_attribution="Female creator",
            ),
        ]
    )
    db.add(exercise)
    db.flush()
    db.expire(exercise, ["media_assets"])

    stored = db.scalar(select(Exercise).where(Exercise.slug == "variant-media-push-up"))

    assert stored is not None
    assert [item.presentation for item in stored.media_assets] == [
        MediaPresentation.FEMALE,
        MediaPresentation.MALE,
    ]
    assert {item.media_attribution for item in stored.media_assets} == {
        "Female creator",
        "Male creator",
    }


def test_exercise_database_allows_multiple_media_assets_in_display_order(db: Session) -> None:
    from app.exercises.enums import MediaPresentation, MediaRole, MediaType
    from app.exercises.models import ExerciseMediaAsset

    exercise = make_exercise("duplicate-media-variant")
    exercise.media_assets.extend(
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
    db.add(exercise)
    db.flush()
    db.expire(exercise, ["media_assets"])

    stored = db.scalar(select(Exercise).where(Exercise.slug == "duplicate-media-variant"))

    assert stored is not None
    assert [item.sort_order for item in stored.media_assets] == [0, 1]


def test_exercise_media_asset_stores_unique_owner_provenance(db: Session) -> None:
    from app.exercises.enums import MediaPresentation, MediaRole, MediaType
    from app.exercises.models import ExerciseMediaAsset

    first = make_exercise("owner-video-first")
    second = make_exercise("owner-video-second")
    first.media_assets.append(
        ExerciseMediaAsset(
            presentation=MediaPresentation.UNSPECIFIED,
            role=MediaRole.VIDEO,
            sort_order=0,
            media_path="/media/owner-video/aa/first.mp4",
            media_type=MediaType.VIDEO,
            source="owner-video",
            source_id="a" * 64,
        )
    )
    second.media_assets.append(
        ExerciseMediaAsset(
            presentation=MediaPresentation.UNSPECIFIED,
            role=MediaRole.VIDEO,
            sort_order=0,
            media_path="/media/owner-video/aa/second.mp4",
            media_type=MediaType.VIDEO,
            source="owner-video",
            source_id="a" * 64,
        )
    )
    db.add(first)
    db.flush()
    db.add(second)

    with pytest.raises(IntegrityError) as error:
        db.flush()

    assert "uq_exercise_media_assets_source_source_id" in str(error.value)
