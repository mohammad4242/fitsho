from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.exercises.audit_substitution_metadata import _missing_muscle_focus, audit_catalogue
from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseContentType,
    ExerciseLabel,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.models import (
    Exercise,
    ExerciseAlternative,
    ExerciseEquipment,
    ExerciseLabelItem,
    ExerciseSecondaryMuscle,
)
from app.workouts.program_engine.enums import (
    BodyPosition,
    ImpactLimit,
    Laterality,
    LoadLimit,
    SkillDemand,
    StabilityDemand,
)


def make_exercise(slug: str, **overrides: object) -> Exercise:
    values: dict[str, object] = {
        "slug": slug,
        "name_en": f"Exercise {slug}",
        "name_fa": f"حرکت {slug}",
        "body_region": BodyRegion.UPPER_BODY,
        "primary_muscle": MuscleGroup.CHEST,
        "muscle_focus": MuscleFocus.GENERAL_CHEST,
        "difficulty": Difficulty.BEGINNER,
        "movement_pattern": MovementPattern.HORIZONTAL_PUSH,
        "exercise_type": ExerciseType.COMPOUND,
        "body_position": BodyPosition.SUPPORTED,
        "stability_demand": StabilityDemand.LOW,
        "skill_demand": SkillDemand.LOW,
        "impact_level": ImpactLimit.LOW,
        "axial_loading_level": LoadLimit.NONE,
        "laterality": Laterality.BILATERAL,
        "substitution_group": "horizontal_press_flat",
        "instructions_en": ["Brace.", "Lower.", "Stand."],
        "instructions_fa": ["آماده شو.", "پایین برو.", "بلند شو."],
        "safety_notes_en": [],
        "safety_notes_fa": [],
        "media_path": "/exercises/exercise-placeholder.svg",
        "media_type": MediaType.PLACEHOLDER,
        "is_programmable": True,
        "content_type": ExerciseContentType.EXERCISE,
    }
    values.update(overrides)
    return Exercise(**values)


def test_audit_reports_metadata_categories_and_exclusions(db: Session) -> None:
    missing = make_exercise(
        "z-missing",
        primary_muscle=None,
        muscle_focus=None,
        movement_pattern=MovementPattern.OTHER,
        exercise_type=ExerciseType.OTHER,
        body_position=None,
        stability_demand=None,
        skill_demand=None,
        impact_level=None,
        axial_loading_level=None,
        laterality=None,
        substitution_group=None,
    )
    equipment_other = make_exercise("equipment-other")
    equipment_other.equipment_items.append(ExerciseEquipment(equipment=Equipment.OTHER))
    legacy = make_exercise(
        "a-legacy",
        primary_muscle=MuscleGroup.QUADRICEPS,
        muscle_focus=None,
        substitution_group=MovementPattern.SQUAT.value,
    )
    legacy.equipment_items.append(ExerciseEquipment(equipment=Equipment.BODYWEIGHT))
    cardio = make_exercise("cardio", exercise_type=ExerciseType.COMPOUND)
    cardio.labels.append(ExerciseLabelItem(label=ExerciseLabel.CARDIO))
    mobility = make_exercise("mobility", exercise_type=ExerciseType.MOBILITY)
    guide = make_exercise("guide", content_type=ExerciseContentType.GUIDE)
    non_programmable = make_exercise("not-programmable", is_programmable=False)
    db.add_all([missing, equipment_other, legacy, cardio, mobility, guide, non_programmable])
    db.flush()

    report = audit_catalogue(db)

    assert [item.slug for item in report.exercises] == [
        "a-legacy",
        "equipment-other",
        "z-missing",
    ]
    assert [item.slug for item in report.missing_primary_muscle] == ["z-missing"]
    assert [item.slug for item in report.missing_muscle_focus] == []
    assert [item.slug for item in report.movement_pattern_other] == ["z-missing"]
    assert [item.slug for item in report.exercise_type_other] == ["z-missing"]
    assert [item.slug for item in report.missing_equipment] == ["z-missing"]
    assert [item.slug for item in report.equipment_other] == ["equipment-other"]
    assert [item.slug for item in report.missing_body_position] == ["z-missing"]
    assert [item.slug for item in report.missing_stability_demand] == ["z-missing"]
    assert [item.slug for item in report.missing_skill_demand] == ["z-missing"]
    assert [item.slug for item in report.missing_impact_level] == ["z-missing"]
    assert [item.slug for item in report.missing_axial_loading_level] == ["z-missing"]
    assert [item.slug for item in report.missing_laterality] == ["z-missing"]
    assert [item.slug for item in report.missing_substitution_group] == ["z-missing"]
    assert [item.slug for item in report.legacy_broad_substitution_groups] == ["a-legacy"]
    assert _missing_muscle_focus(make_exercise("transient-focus-missing", muscle_focus=None))
    assert not _missing_muscle_focus(
        make_exercise(
            "transient-focusless",
            primary_muscle=MuscleGroup.QUADRICEPS,
            muscle_focus=None,
        )
    )


def test_audit_preserves_directional_alternatives_and_reports_roles(db: Session) -> None:
    first = make_exercise("b-first")
    second = make_exercise("a-second")
    third = make_exercise("c-third", substitution_group="other-role")
    for item in (first, second, third):
        item.equipment_items.append(ExerciseEquipment(equipment=Equipment.DUMBBELL))
    third.equipment_items.clear()
    third.equipment_items.append(ExerciseEquipment(equipment=Equipment.BARBELL))
    first.secondary_muscles.extend(
        [
            ExerciseSecondaryMuscle(muscle=MuscleGroup.TRICEPS),
            ExerciseSecondaryMuscle(muscle=MuscleGroup.BICEPS),
        ]
    )
    second.secondary_muscles.extend(
        [
            ExerciseSecondaryMuscle(muscle=MuscleGroup.BICEPS),
            ExerciseSecondaryMuscle(muscle=MuscleGroup.TRICEPS),
        ]
    )
    db.add_all([first, second, third])
    db.flush()
    first.alternatives.append(
        ExerciseAlternative(
            alternative_exercise_id=second.id,
            reason_en="same role",
            reason_fa="هم‌نقش",
        )
    )
    db.flush()

    report = audit_catalogue(db)

    coverage = {item.exercise.slug: item for item in report.alternative_coverage}
    assert [item.slug for item in coverage["b-first"].alternatives] == ["a-second"]
    assert [item.slug for item in report.uncovered_alternative_exercises] == [
        "a-second",
        "c-third",
    ]
    incompatible_slugs = {
        item.slug for role in report.home_incompatible_roles for item in role.candidates
    }
    singleton_slugs = {item.slug for role in report.singleton_roles for item in role.candidates}
    assert incompatible_slugs == {"c-third"}
    assert "c-third" in singleton_slugs

    grouped_role = next(
        role
        for role in report.home_role_coverage
        if {item.slug for item in role.candidates} == {"b-first", "a-second"}
    )
    assert grouped_role.signature.secondary_muscles == (
        MuscleGroup.BICEPS,
        MuscleGroup.TRICEPS,
    )
    serialized_secondaries = grouped_role.as_json()["signature"]["secondary_muscles"]
    assert serialized_secondaries == [MuscleGroup.BICEPS.value, MuscleGroup.TRICEPS.value]


def test_audit_detects_mixed_groups_and_has_stable_json(db: Session) -> None:
    first = make_exercise(
        "z-group",
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        substitution_group="mixed",
    )
    second = make_exercise(
        "a-group",
        movement_pattern=MovementPattern.VERTICAL_PUSH,
        substitution_group="mixed",
    )
    db.add_all([first, second])
    db.flush()

    report = audit_catalogue(db)
    serialized = report.as_json()

    assert [item.group for item in report.mixed_substitution_groups] == ["mixed"]
    assert json.dumps(serialized, sort_keys=True) == json.dumps(report.as_json(), sort_keys=True)
    assert list(serialized) == sorted(serialized)
