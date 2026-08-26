from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.exercises.enums import ExerciseContentType, PrescriptionMode
from app.profile.enums import ExperienceLevel
from app.training_templates.engine_reference import load_template_references
from app.training_templates.models import (
    TrainingProgramStructure,
    TrainingProgramTemplate,
    TrainingProgramTemplateDay,
    TrainingProgramTemplateSlot,
    TrainingTemplateMethod,
)
from app.training_templates.seed_data import (
    CANONICAL_TEMPLATE_DEFINITIONS,
    TRAINING_PROGRAM_TEMPLATE_SEEDS,
    TrainingProgramTemplateSeed,
)
from app.training_templates.service import (
    list_training_program_templates,
    seed_training_program_templates,
)
from tests.training_templates.catalog_fixture import seed_real_catalog_exercises
from tests.training_templates.frozen_catalog import FROZEN_2_3_4_SIGNATURES, seed_signature

NEW_PROGRAMS = (
    (
        "p26-5-day-classic-body-part-intermediate",
        5,
        "5d-classic-body-part-approved",
        ExperienceLevel.INTERMEDIATE,
    ),
    (
        "p27-5-day-classic-body-part-advanced",
        5,
        "5d-classic-body-part-approved",
        ExperienceLevel.ADVANCED,
    ),
    (
        "p28-5-day-split-weak-point-intermediate",
        5,
        "5d-split-weak-point",
        ExperienceLevel.INTERMEDIATE,
    ),
    ("p29-5-day-split-weak-point-advanced", 5, "5d-split-weak-point", ExperienceLevel.ADVANCED),
    (
        "p30-5-day-upper-priority-iranian-intermediate",
        5,
        "5d-upper-priority-iranian",
        ExperienceLevel.INTERMEDIATE,
    ),
    (
        "p31-5-day-upper-priority-iranian-advanced",
        5,
        "5d-upper-priority-iranian",
        ExperienceLevel.ADVANCED,
    ),
    (
        "p32-5-day-upper-lower-specialty-intermediate",
        5,
        "5d-upper-lower-specialty",
        ExperienceLevel.INTERMEDIATE,
    ),
    (
        "p33-5-day-upper-lower-specialty-advanced",
        5,
        "5d-upper-lower-specialty",
        ExperienceLevel.ADVANCED,
    ),
    (
        "p34-5-day-fst7-arms-priority-intermediate",
        5,
        "5d-fst7-arms-priority",
        ExperienceLevel.INTERMEDIATE,
    ),
    ("p35-5-day-fst7-arms-priority-advanced", 5, "5d-fst7-arms-priority", ExperienceLevel.ADVANCED),
    (
        "p36-5-day-professional-compound-intermediate",
        5,
        "5d-professional-compound",
        ExperienceLevel.INTERMEDIATE,
    ),
    (
        "p37-5-day-professional-compound-advanced",
        5,
        "5d-professional-compound",
        ExperienceLevel.ADVANCED,
    ),
    ("p38-6-day-ppl-ab-intermediate", 6, "6d-ppl-2x", ExperienceLevel.INTERMEDIATE),
    ("p39-6-day-ppl-ab-advanced", 6, "6d-ppl-2x", ExperienceLevel.ADVANCED),
    ("p40-6-day-upper-lower-x3-intermediate", 6, "6d-upper-lower-x3", ExperienceLevel.INTERMEDIATE),
    ("p41-6-day-upper-lower-x3-advanced", 6, "6d-upper-lower-x3", ExperienceLevel.ADVANCED),
    ("p42-6-day-fitclub-hybrid-intermediate", 6, "6d-fitclub-hybrid", ExperienceLevel.INTERMEDIATE),
    ("p43-6-day-fitclub-hybrid-advanced", 6, "6d-fitclub-hybrid", ExperienceLevel.ADVANCED),
    ("p44-6-day-arnold-split-intermediate", 6, "6d-arnold-split", ExperienceLevel.INTERMEDIATE),
    ("p45-6-day-arnold-split-advanced", 6, "6d-arnold-split", ExperienceLevel.ADVANCED),
    (
        "p46-6-day-classic-body-part-intermediate",
        6,
        "6d-classic-body-part",
        ExperienceLevel.INTERMEDIATE,
    ),
    ("p47-6-day-classic-body-part-advanced", 6, "6d-classic-body-part", ExperienceLevel.ADVANCED),
    (
        "p48-6-day-ronnie-double-exposure-intermediate",
        6,
        "6d-ronnie-double-exposure",
        ExperienceLevel.INTERMEDIATE,
    ),
    (
        "p49-6-day-ronnie-double-exposure-advanced",
        6,
        "6d-ronnie-double-exposure",
        ExperienceLevel.ADVANCED,
    ),
)

EXPECTED_DAY_TITLES = {
    "p26-5-day-classic-body-part-intermediate": ("Chest", "Back", "Shoulders", "Arms", "Legs"),
    "p27-5-day-classic-body-part-advanced": ("Chest", "Back", "Shoulders", "Arms", "Legs"),
    "p28-5-day-split-weak-point-intermediate": (
        "Chest + Triceps",
        "Back + Biceps",
        "Legs",
        "Shoulders + Core",
        "Weak Point / Light Full Body",
    ),
    "p29-5-day-split-weak-point-advanced": (
        "Chest + Triceps",
        "Back + Biceps",
        "Legs",
        "Shoulders + Core",
        "Weak Point / Light Full Body",
    ),
    "p30-5-day-upper-priority-iranian-intermediate": (
        "Chest + Triceps",
        "Shoulders + Biceps",
        "Legs + Core",
        "Upper Chest + Biceps",
        "Back + Core",
    ),
    "p31-5-day-upper-priority-iranian-advanced": (
        "Chest + Triceps",
        "Shoulders + Biceps",
        "Legs + Core",
        "Upper Chest + Biceps",
        "Back + Core",
    ),
    "p32-5-day-upper-lower-specialty-intermediate": (
        "Upper A",
        "Lower A",
        "Upper B",
        "Lower B",
        "Arms + Delts Specialty",
    ),
    "p33-5-day-upper-lower-specialty-advanced": (
        "Upper A",
        "Lower A",
        "Upper B",
        "Lower B",
        "Arms + Delts Specialty",
    ),
    "p34-5-day-fst7-arms-priority-intermediate": (
        "Chest + Biceps",
        "Back + Triceps",
        "Legs",
        "Shoulders + Calves",
        "Arms",
    ),
    "p35-5-day-fst7-arms-priority-advanced": (
        "Chest + Biceps",
        "Back + Triceps",
        "Legs",
        "Shoulders + Calves",
        "Arms",
    ),
    "p36-5-day-professional-compound-intermediate": (
        "Chest + Triceps",
        "Legs + Core",
        "Back + Biceps",
        "Shoulders",
        "Compound Day",
    ),
    "p37-5-day-professional-compound-advanced": (
        "Chest + Triceps",
        "Legs + Core",
        "Back + Biceps",
        "Shoulders",
        "Compound Day",
    ),
    "p38-6-day-ppl-ab-intermediate": ("Push A", "Pull A", "Legs A", "Push B", "Pull B", "Legs B"),
    "p39-6-day-ppl-ab-advanced": ("Push A", "Pull A", "Legs A", "Push B", "Pull B", "Legs B"),
    "p40-6-day-upper-lower-x3-intermediate": (
        "Upper A",
        "Lower A",
        "Upper B",
        "Lower B",
        "Upper C",
        "Lower C",
    ),
    "p41-6-day-upper-lower-x3-advanced": (
        "Upper A",
        "Lower A",
        "Upper B",
        "Lower B",
        "Upper C",
        "Lower C",
    ),
    "p42-6-day-fitclub-hybrid-intermediate": (
        "Chest + Triceps",
        "Back + Biceps",
        "Legs",
        "Shoulders + Core",
        "Chest + Back",
        "Posterior + Core",
    ),
    "p43-6-day-fitclub-hybrid-advanced": (
        "Chest + Triceps",
        "Back + Biceps",
        "Legs",
        "Shoulders + Core",
        "Chest + Back",
        "Posterior + Core",
    ),
    "p44-6-day-arnold-split-intermediate": (
        "Chest + Back A",
        "Shoulders + Arms A",
        "Legs A",
        "Chest + Back B",
        "Shoulders + Arms B",
        "Legs B",
    ),
    "p45-6-day-arnold-split-advanced": (
        "Chest + Back A",
        "Shoulders + Arms A",
        "Legs A",
        "Chest + Back B",
        "Shoulders + Arms B",
        "Legs B",
    ),
    "p46-6-day-classic-body-part-intermediate": (
        "Chest",
        "Biceps",
        "Legs",
        "Triceps",
        "Back",
        "Shoulders",
    ),
    "p47-6-day-classic-body-part-advanced": (
        "Chest",
        "Biceps",
        "Legs",
        "Triceps",
        "Back",
        "Shoulders",
    ),
    "p48-6-day-ronnie-double-exposure-intermediate": (
        "Back + Biceps + Shoulders A",
        "Legs A",
        "Chest + Triceps A",
        "Back + Biceps + Shoulders B",
        "Legs B",
        "Chest + Triceps B",
    ),
    "p49-6-day-ronnie-double-exposure-advanced": (
        "Back + Biceps + Shoulders A",
        "Legs A",
        "Chest + Triceps A",
        "Back + Biceps + Shoulders B",
        "Legs B",
        "Chest + Triceps B",
    ),
}

EXERCISE = {
    "bar": "fedb-0025-barbell-bench-press",
    "db": "owner-cb58d2dbac7f-dumbbell-bench-press",
    "incline": "fedb-0314-dumbbell-incline-bench-press",
    "machine": "fedb-0577-lever-lying-chest-press",
    "hammer_press": "fedb-1299-lever-incline-hammer-chest-press",
    "fly": "fedb-1269-cable-standing-fly",
    "row": "owner-e0c26a271aac-barbell-bent-over-row",
    "seated_row": "owner-2a5de4dc7ba3-seated-cable-row",
    "high": "fedb-0581-lever-high-row",
    "lat": "fedb-0974-cable-close-grip-lat-pulldown",
    "straight": "fedb-0238-cable-straight-arm-pulldown",
    "military": "fedb-0553-military-press",
    "smith_press": "fedb-0765-smith-seated-shoulder-press",
    "cable_lateral": "fedb-0178-cable-lateral-raise",
    "machine_lateral": "fedb-0584-lever-lateral-raise",
    "db_lateral": "fedb-0334-dumbbell-lateral-raise",
    "rear": "fedb-0602-lever-seated-reverse-fly",
    "shrug": "fedb-0095-barbell-shrug",
    "bar_curl": "fedb-0031-barbell-curl",
    "cable_curl": "fedb-0229-cable-standing-inner-curl",
    "preacher": "fedb-0592-lever-preacher-curl",
    "db_curl": "fedb-0285-seated-alternating-dumbbell-curl",
    "hammer_curl": "fedb-0298-dumbbell-cross-body-hammer-curl",
    "triceps": "fedb-1723-cable-triceps-pushdown",
    "rope_triceps": "fedb-0200-cable-rope-triceps-pushdown",
    "overhead": "fedb-0194-cable-rope-overhead-triceps-extension",
    "squat": "fedb-1435-barbell-back-squat",
    "front_squat": "fedb-0042-barbell-front-squat",
    "press": "fedb-2611-lever-horizontal-leg-press",
    "extension": "fedb-0585-lever-leg-extension",
    "seated_leg": "fedb-0599-lever-seated-leg-curl",
    "lying_leg": "fedb-0586-lever-lying-leg-curl",
    "lunge": "fedb-0336-dumbbell-lunge",
    "bridge": "fedb-0668-rear-decline-bridge",
    "calf": "fedb-0605-lever-standing-calf-raise",
    "plank": "fedb-0464-front-plank",
    "side_plank": "fedb-0705-side-plank",
    "rdl": "fedb-0300-dumbbell-deadlift",
}

EXPECTED_EXERCISE_ORDER = {
    "p26-5-day-classic-body-part-intermediate": (
        ("bar", "incline", "machine", "fly"),
        ("row", "lat", "high", "straight"),
        ("military", "cable_lateral", "rear", "shrug"),
        ("bar_curl", "preacher", "triceps", "overhead", "hammer_curl"),
        ("squat", "press", "rdl", "seated_leg", "calf"),
    ),
    "p27-5-day-classic-body-part-advanced": (
        ("bar", "hammer_press", "db", "fly"),
        ("row", "lat", "seated_row", "straight"),
        ("smith_press", "db_lateral", "rear", "shrug"),
        ("bar_curl", "cable_curl", "rope_triceps", "overhead", "hammer_curl"),
        ("front_squat", "press", "rdl", "lying_leg", "lunge", "calf"),
    ),
    "p28-5-day-split-weak-point-intermediate": (
        ("bar", "incline", "fly", "triceps", "overhead"),
        ("row", "lat", "seated_row", "bar_curl", "db_curl"),
        ("squat", "rdl", "press", "lying_leg", "calf"),
        ("military", "cable_lateral", "rear", "plank", "side_plank"),
        ("db", "high", "bridge", "lunge", "machine_lateral"),
    ),
    "p29-5-day-split-weak-point-advanced": (
        ("bar", "hammer_press", "fly", "rope_triceps", "overhead"),
        ("high", "lat", "seated_row", "bar_curl", "cable_curl"),
        ("front_squat", "rdl", "press", "lying_leg", "calf"),
        ("smith_press", "db_lateral", "rear", "shrug", "plank"),
        ("db", "row", "bridge", "lunge", "cable_lateral"),
    ),
    "p30-5-day-upper-priority-iranian-intermediate": (
        ("bar", "incline", "fly", "triceps", "overhead"),
        ("smith_press", "cable_lateral", "rear", "preacher", "hammer_curl"),
        ("squat", "press", "seated_leg", "calf", "plank"),
        ("incline", "machine", "fly", "cable_curl", "db_curl"),
        ("row", "lat", "seated_row", "straight", "side_plank"),
    ),
    "p31-5-day-upper-priority-iranian-advanced": (
        ("bar", "hammer_press", "fly", "rope_triceps", "overhead"),
        ("military", "machine_lateral", "rear", "bar_curl", "hammer_curl"),
        ("front_squat", "press", "lying_leg", "calf", "plank"),
        ("incline", "machine", "fly", "preacher", "cable_curl"),
        ("row", "high", "lat", "straight", "plank"),
    ),
    "p32-5-day-upper-lower-specialty-intermediate": (
        ("bar", "row", "lat", "military", "bar_curl", "triceps"),
        ("squat", "rdl", "press", "seated_leg", "calf"),
        ("incline", "seated_row", "high", "cable_lateral", "preacher", "overhead"),
        ("front_squat", "bridge", "lunge", "lying_leg", "calf"),
        ("smith_press", "machine_lateral", "rear", "bar_curl", "rope_triceps", "hammer_curl"),
    ),
    "p33-5-day-upper-lower-specialty-advanced": (
        ("bar", "row", "lat", "military"),
        ("squat", "rdl", "seated_leg", "calf"),
        ("hammer_press", "seated_row", "db", "high", "cable_lateral"),
        ("front_squat", "bridge", "lunge", "lying_leg"),
        ("smith_press", "rear", "cable_lateral", "cable_curl", "rope_triceps", "hammer_curl"),
    ),
    "p34-5-day-fst7-arms-priority-intermediate": (
        ("db", "incline", "fly", "db_curl", "preacher"),
        ("high", "lat", "straight", "triceps", "overhead"),
        ("squat", "press", "rdl", "extension", "lying_leg", "calf"),
        ("smith_press", "cable_lateral", "rear", "shrug", "calf"),
        ("bar_curl", "rope_triceps", "cable_curl", "overhead", "hammer_curl"),
    ),
    "p35-5-day-fst7-arms-priority-advanced": (
        ("bar", "hammer_press", "fly", "bar_curl"),
        ("row", "lat", "straight", "rope_triceps"),
        ("front_squat", "rdl", "press", "extension", "lying_leg"),
        ("smith_press", "rear", "machine_lateral", "calf"),
        ("bar_curl", "rope_triceps", "preacher", "overhead"),
    ),
    "p36-5-day-professional-compound-intermediate": (
        ("bar", "incline", "fly", "triceps"),
        ("squat", "rdl", "lunge", "calf", "plank"),
        ("lat", "row", "high", "bar_curl", "db_curl"),
        ("military", "db_lateral", "rear", "shrug"),
        ("rdl", "db", "seated_row", "front_squat", "smith_press"),
    ),
    "p37-5-day-professional-compound-advanced": (
        ("bar", "hammer_press", "fly", "rope_triceps"),
        ("front_squat", "press", "rdl", "lying_leg", "calf"),
        ("lat", "row", "high", "bar_curl", "hammer_curl"),
        ("smith_press", "cable_lateral", "rear", "shrug"),
        ("db", "high", "bridge", "lunge", "machine_lateral"),
    ),
    "p38-6-day-ppl-ab-intermediate": (
        ("bar", "incline", "military", "cable_lateral", "triceps"),
        ("lat", "high", "rear", "db_curl", "shrug"),
        ("squat", "press", "extension", "seated_leg", "calf"),
        ("smith_press", "db", "hammer_press", "db_lateral", "overhead"),
        ("seated_row", "row", "straight", "hammer_curl", "rear"),
        ("rdl", "lying_leg", "bridge", "front_squat", "lunge", "calf"),
    ),
    "p39-6-day-ppl-ab-advanced": (
        ("bar", "hammer_press", "fly", "cable_lateral", "rope_triceps"),
        ("lat", "high", "rear", "bar_curl", "shrug"),
        ("squat", "press", "extension", "seated_leg", "calf"),
        ("smith_press", "db", "fly", "db_lateral", "overhead"),
        ("row", "seated_row", "straight", "hammer_curl", "rear"),
        ("rdl", "lying_leg", "front_squat", "bridge", "lunge", "calf"),
    ),
    "p40-6-day-upper-lower-x3-intermediate": (
        ("bar", "row", "military", "lat", "bar_curl", "triceps"),
        ("squat", "press", "extension", "seated_leg", "calf"),
        ("incline", "seated_row", "high", "cable_lateral", "preacher", "overhead"),
        ("rdl", "lying_leg", "bridge", "lunge", "calf"),
        ("db", "lat", "smith_press", "straight", "hammer_curl", "rope_triceps"),
        ("front_squat", "press", "seated_leg", "lunge", "calf", "side_plank"),
    ),
    "p41-6-day-upper-lower-x3-advanced": (
        ("bar", "row", "military", "lat"),
        ("squat", "press", "extension", "seated_leg", "calf"),
        ("hammer_press", "seated_row", "high", "cable_lateral", "preacher", "overhead"),
        ("rdl", "lying_leg", "bridge", "lunge", "calf"),
        ("db", "lat", "smith_press", "straight", "cable_curl", "rope_triceps"),
        ("front_squat", "press", "seated_leg", "lunge", "calf", "side_plank"),
    ),
    "p42-6-day-fitclub-hybrid-intermediate": (
        ("bar", "incline", "fly", "triceps", "overhead"),
        ("row", "lat", "high", "cable_curl", "hammer_curl"),
        ("squat", "press", "extension", "seated_leg", "calf"),
        ("military", "cable_lateral", "rear", "shrug", "plank"),
        ("machine", "seated_row", "hammer_press", "lat", "fly", "straight"),
        ("rdl", "lying_leg", "bridge", "lunge", "calf", "side_plank"),
    ),
    "p43-6-day-fitclub-hybrid-advanced": (
        ("bar", "incline", "fly", "rope_triceps", "overhead"),
        ("row", "lat", "high", "cable_curl", "hammer_curl"),
        ("squat", "press", "extension", "seated_leg", "calf"),
        ("military", "cable_lateral", "rear", "shrug", "plank"),
        ("machine", "seated_row", "fly", "straight", "hammer_press", "lat"),
        ("rdl", "lying_leg", "bridge", "lunge", "calf", "side_plank"),
    ),
    "p44-6-day-arnold-split-intermediate": (
        ("bar", "row", "incline", "lat", "fly", "straight"),
        ("military", "cable_lateral", "rear", "bar_curl", "triceps", "hammer_curl"),
        ("squat", "press", "seated_leg", "calf"),
        ("db", "seated_row", "hammer_press", "high", "fly", "lat"),
        ("smith_press", "db_lateral", "rear", "preacher", "overhead", "cable_curl"),
        ("rdl", "front_squat", "lying_leg", "bridge", "lunge", "calf"),
    ),
    "p45-6-day-arnold-split-advanced": (
        ("bar", "row", "incline", "lat", "fly", "straight"),
        ("military", "cable_lateral", "rear", "bar_curl", "rope_triceps"),
        ("squat", "press", "seated_leg", "calf"),
        ("db", "seated_row", "hammer_press", "high", "fly", "lat"),
        ("smith_press", "machine_lateral", "preacher", "overhead", "hammer_curl"),
        ("rdl", "front_squat", "lying_leg", "bridge", "lunge", "calf"),
    ),
    "p46-6-day-classic-body-part-intermediate": (
        ("bar", "incline", "machine", "fly"),
        ("bar_curl", "preacher", "hammer_curl", "cable_curl"),
        ("squat", "press", "rdl", "seated_leg", "calf"),
        ("triceps", "rope_triceps", "overhead"),
        ("row", "lat", "seated_row", "high", "straight"),
        ("military", "cable_lateral", "rear", "shrug"),
    ),
    "p47-6-day-classic-body-part-advanced": (
        ("bar", "hammer_press", "db", "fly"),
        ("bar_curl", "preacher", "cable_curl", "hammer_curl"),
        ("front_squat", "press", "rdl", "lying_leg", "calf"),
        ("triceps", "rope_triceps", "overhead"),
        ("row", "lat", "seated_row", "straight"),
        ("smith_press", "cable_lateral", "rear", "shrug"),
    ),
    "p48-6-day-ronnie-double-exposure-intermediate": (
        ("lat", "row", "rear", "db_curl", "cable_lateral"),
        ("squat", "press", "extension", "seated_leg", "calf"),
        ("bar", "incline", "fly", "triceps", "overhead"),
        ("seated_row", "high", "straight", "hammer_curl", "smith_press"),
        ("rdl", "lying_leg", "bridge", "front_squat", "lunge", "calf"),
        ("db", "hammer_press", "fly", "rope_triceps", "overhead"),
    ),
    "p49-6-day-ronnie-double-exposure-advanced": (
        ("lat", "row", "rear", "bar_curl", "cable_lateral"),
        ("squat", "press", "extension", "seated_leg", "calf"),
        ("bar", "hammer_press", "fly", "triceps", "overhead"),
        ("seated_row", "high", "straight", "hammer_curl", "smith_press", "cable_lateral"),
        ("rdl", "front_squat", "lying_leg", "bridge", "lunge", "calf"),
        ("db", "incline", "fly", "rope_triceps", "overhead"),
    ),
}

EXPECTED_DROP_SET_SLOTS = {
    ("p27-5-day-classic-body-part-advanced", "Chest", EXERCISE["fly"]),
    (
        "p29-5-day-split-weak-point-advanced",
        "Weak Point / Light Full Body",
        EXERCISE["cable_lateral"],
    ),
    ("p31-5-day-upper-priority-iranian-advanced", "Upper Chest + Biceps", EXERCISE["fly"]),
    (
        "p33-5-day-upper-lower-specialty-advanced",
        "Arms + Delts Specialty",
        EXERCISE["cable_lateral"],
    ),
    ("p39-6-day-ppl-ab-advanced", "Legs A", EXERCISE["extension"]),
    ("p41-6-day-upper-lower-x3-advanced", "Upper B", EXERCISE["cable_lateral"]),
    ("p47-6-day-classic-body-part-advanced", "Chest", EXERCISE["fly"]),
    (
        "p49-6-day-ronnie-double-exposure-advanced",
        "Back + Biceps + Shoulders B",
        EXERCISE["cable_lateral"],
    ),
}

EXPECTED_SUPERSET_REST = {
    ("p27-5-day-classic-body-part-advanced", "Arms", "SS-A"): 90,
    ("p33-5-day-upper-lower-specialty-advanced", "Arms + Delts Specialty", "SS-A"): 90,
    ("p41-6-day-upper-lower-x3-advanced", "Upper C", "SS-A"): 90,
    ("p43-6-day-fitclub-hybrid-advanced", "Chest + Back", "SS-A"): 90,
    ("p45-6-day-arnold-split-advanced", "Chest + Back A", "SS-A"): 120,
    ("p45-6-day-arnold-split-advanced", "Chest + Back A", "SS-B"): 90,
    ("p45-6-day-arnold-split-advanced", "Shoulders + Arms A", "SS-A"): 90,
    ("p45-6-day-arnold-split-advanced", "Chest + Back B", "SS-A"): 120,
    ("p45-6-day-arnold-split-advanced", "Shoulders + Arms B", "SS-A"): 90,
}


def _new_seed_map() -> dict[str, TrainingProgramTemplateSeed]:
    expected_slugs = {slug for slug, *_ in NEW_PROGRAMS}
    return {
        seed.slug: seed for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS if seed.slug in expected_slugs
    }


def test_approved_exercise_order_matches_the_specification() -> None:
    seeds = _new_seed_map()

    for slug, expected_days in EXPECTED_EXERCISE_ORDER.items():
        actual_days = tuple(
            tuple(
                next(key for key, value in EXERCISE.items() if value == slot.exercise_slug_hint)
                for slot in day.slots
            )
            for day in seeds[slug].days
        )
        assert actual_days == expected_days


def test_approved_prescriptions_match_roles_rest_and_techniques() -> None:
    new_slugs = {slug for slug, *_ in NEW_PROGRAMS}
    seeds = {seed.slug: seed for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS if seed.slug in new_slugs}
    definitions = {
        definition.canonical_slug: definition
        for definition in CANONICAL_TEMPLATE_DEFINITIONS
        if definition.canonical_slug in new_slugs
    }
    actual_drop_sets = set()

    for slug, seed in seeds.items():
        level = seed.supported_levels[0]
        definition = definitions[slug]
        for day, day_specs in zip(seed.days, definition.day_specs, strict=True):
            for slot, (_, role) in zip(day.slots, day_specs, strict=True):
                if role == "large_primary":
                    expected = (4, 6, 12, 1 if level is ExperienceLevel.ADVANCED else 2)
                    is_leg_primary = slot.exercise_slug_hint in {
                        EXERCISE["squat"],
                        EXERCISE["front_squat"],
                        EXERCISE["rdl"],
                    }
                    expected_rest = (
                        150 if is_leg_primary or level is ExperienceLevel.ADVANCED else 120
                    )
                elif role in {"large_compound", "small_main", "superset"}:
                    expected = (3, 8, 12, 2)
                    if role == "superset":
                        assert slot.superset_group is not None
                        expected_rest = EXPECTED_SUPERSET_REST[
                            (slug, day.title_en, slot.superset_group)
                        ]
                    elif role == "small_main":
                        is_press = slot.exercise_slug_hint in {
                            EXERCISE["military"],
                            EXERCISE["smith_press"],
                        }
                        expected_rest = (
                            (120 if level is ExperienceLevel.ADVANCED else 90)
                            if is_press
                            else (90 if level is ExperienceLevel.ADVANCED else 60)
                        )
                    else:
                        expected_rest = 120
                elif role in {"large_isolation", "small_isolation"}:
                    expected = (3, 10, 12, 2)
                    expected_rest = 75 if level is ExperienceLevel.ADVANCED else 60
                elif role == "fst7":
                    expected = (7, 8, 12, 2)
                    assert 45 <= slot.rest_seconds <= 60
                    expected_rest = slot.rest_seconds
                else:
                    expected = (3, 45, 60, 2) if role == "front_plank" else (3, 30, 45, 2)
                    expected_rest = 60

                assert (slot.sets, slot.rep_min, slot.rep_max, slot.target_rir) == expected
                assert slot.rest_seconds == expected_rest
                if slot.intensity_method is TrainingTemplateMethod.DROP_SET:
                    actual_drop_sets.add((slug, day.title_en, slot.exercise_slug_hint))
                elif role == "superset":
                    assert slot.intensity_method is TrainingTemplateMethod.SUPERSET
                else:
                    assert slot.intensity_method is TrainingTemplateMethod.STANDARD

    assert actual_drop_sets == EXPECTED_DROP_SET_SLOTS


def test_exactly_24_approved_5_and_6_day_additions_exist() -> None:
    seeds = _new_seed_map()

    assert len(seeds) == 24
    assert Counter(seed.days_per_week for seed in seeds.values()) == {5: 12, 6: 12}
    assert set(seeds) == {slug for slug, *_ in NEW_PROGRAMS}


def test_all_approved_structures_have_intermediate_and_advanced_variants() -> None:
    by_structure: dict[str, set[ExperienceLevel]] = {}
    for _, _, structure_slug, level in NEW_PROGRAMS:
        by_structure.setdefault(structure_slug, set()).add(level)

    assert all(
        levels == {ExperienceLevel.INTERMEDIATE, ExperienceLevel.ADVANCED}
        for levels in by_structure.values()
    )
    assert len(by_structure) == 12


def test_approved_day_counts_and_exact_day_order() -> None:
    seeds = _new_seed_map()

    for slug, _, _, _ in NEW_PROGRAMS:
        assert tuple(day.title_en for day in seeds[slug].days) == EXPECTED_DAY_TITLES[slug]
        assert len(seeds[slug].days) == seeds[slug].days_per_week


def test_approved_new_prescriptions_use_supported_pyramid_ranges() -> None:
    seeds = _new_seed_map()

    for seed in seeds.values():
        for day in seed.days:
            for slot in day.slots:
                assert slot.rep_min >= 6
                assert slot.sets >= 3
                assert slot.rep_max >= slot.rep_min

    fst7 = seeds["p35-5-day-fst7-arms-priority-advanced"]
    assert [slot.sets for day in fst7.days for slot in day.slots if slot.sets == 7] == [7] * 5
    assert all(
        (slot.rep_min, slot.rep_max) == (8, 12)
        for day in fst7.days
        for slot in day.slots
        if slot.sets == 7
    )


def test_approved_techniques_are_level_and_program_scoped() -> None:
    seeds = _new_seed_map()

    assert all(
        slot.intensity_method is TrainingTemplateMethod.STANDARD
        for slug, seed in seeds.items()
        if slug.endswith("-intermediate")
        for day in seed.days
        for slot in day.slots
    )
    assert all(
        slot.sets == 7
        for day in seeds["p35-5-day-fst7-arms-priority-advanced"].days
        for slot in day.slots
        if slot.sets == 7
    )
    assert all(
        slot.sets != 7
        for slug, seed in seeds.items()
        if slug != "p35-5-day-fst7-arms-priority-advanced"
        for day in seed.days
        for slot in day.slots
    )


def test_frozen_2_3_4_day_seed_signatures_are_unchanged() -> None:
    actual = {
        seed.slug: seed_signature(seed)
        for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if seed.days_per_week in {2, 3, 4}
    }

    assert actual == FROZEN_2_3_4_SIGNATURES


def test_seed_adds_24_rows_and_resolves_all_exercises(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)

    expected_slugs = {slug for slug, *_ in NEW_PROGRAMS}
    templates = list(
        db.scalars(
            select(TrainingProgramTemplate)
            .where(TrainingProgramTemplate.slug.in_(expected_slugs))
            .options(
                selectinload(TrainingProgramTemplate.days).selectinload(
                    TrainingProgramTemplateDay.slots
                ),
                selectinload(TrainingProgramTemplate.structure),
            )
        )
    )
    assert len(templates) == 24
    assert all(template.structure is not None for template in templates)
    assert all(
        slot.exercise_id is not None
        for template in templates
        for day in template.days
        for slot in day.slots
    )


def test_seed_is_idempotent_for_5_and_6_day_additions(db: Session) -> None:
    seed_real_catalog_exercises(db)
    first = seed_training_program_templates(db)
    first_counts = (
        db.scalar(select(func.count()).select_from(TrainingProgramTemplate)),
        db.scalar(select(func.count()).select_from(TrainingProgramTemplateSlot)),
        db.scalar(select(func.count()).select_from(TrainingProgramStructure)),
    )
    second = seed_training_program_templates(db)
    second_counts = (
        db.scalar(select(func.count()).select_from(TrainingProgramTemplate)),
        db.scalar(select(func.count()).select_from(TrainingProgramTemplateSlot)),
        db.scalar(select(func.count()).select_from(TrainingProgramStructure)),
    )

    assert second == first
    assert second_counts == first_counts
    assert first.templates == 49


def test_default_library_groups_new_rows_by_structure_and_level(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)

    for days in (5, 6):
        templates = list_training_program_templates(db, days_per_week=days)
        assert len(templates) == 12
        assert all(
            template.supported_levels in [["intermediate"], ["advanced"]] for template in templates
        )
        assert {template.structure.slug for template in templates if template.structure}


def test_engine_references_keep_new_slots_and_intensity_metadata(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)

    references = {
        reference.slug: reference
        for reference in load_template_references(db)
        if reference.slug in {slug for slug, *_ in NEW_PROGRAMS}
    }
    assert len(references) == 24
    assert all(
        slot.exercise_id is not None
        for reference in references.values()
        for day in reference.days
        for slot in day.slots
    )


def test_real_exercise_library_rows_are_active_programmable_and_reps_or_duration_valid(
    db: Session,
) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)
    slots = list(
        db.scalars(
            select(TrainingProgramTemplateSlot)
            .where(TrainingProgramTemplateSlot.exercise_id.is_not(None))
            .options(selectinload(TrainingProgramTemplateSlot.exercise))
        )
    )
    assert all(slot.exercise is not None for slot in slots)
    assert all(
        slot.exercise.content_type is ExerciseContentType.EXERCISE
        for slot in slots
        if slot.exercise
    )
    assert all(
        slot.exercise.is_active and slot.exercise.is_programmable for slot in slots if slot.exercise
    )
    assert all(
        slot.exercise.prescription_mode in {PrescriptionMode.REPS, PrescriptionMode.DURATION}
        for slot in slots
        if slot.exercise
    )
