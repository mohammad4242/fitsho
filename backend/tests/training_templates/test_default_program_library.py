from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.exercises.models import Exercise
from app.profile.enums import ExperienceLevel
from app.training_templates.models import (
    TrainingProgramTemplate,
    TrainingProgramTemplateDay,
    TrainingProgramTemplateSlot,
)
from app.training_templates.seed_data import (
    CANONICAL_TEMPLATE_DEFINITIONS,
    TRAINING_PROGRAM_TEMPLATE_SEEDS,
)
from app.training_templates.service import seed_training_program_templates
from tests.training_templates.catalog_fixture import seed_real_catalog_exercises

SLUGS = {
    "smith_squat": "fedb-0750-smith-chair-squat",
    "back_squat": "fedb-1435-barbell-back-squat",
    "front_squat": "fedb-0042-barbell-front-squat",
    "leg_press": "fedb-2611-lever-horizontal-leg-press",
    "leg_extension": "fedb-0585-lever-leg-extension",
    "leg_curl_seated": "fedb-0599-lever-seated-leg-curl",
    "leg_curl_lying": "fedb-0586-lever-lying-leg-curl",
    "deadlift": "fedb-0300-dumbbell-deadlift",
    "lunge": "fedb-0336-dumbbell-lunge",
    "bridge": "fedb-0668-rear-decline-bridge",
    "calf": "fedb-0605-lever-standing-calf-raise",
    "chest_machine": "fedb-0577-lever-lying-chest-press",
    "incline_machine": "fedb-1299-lever-incline-hammer-chest-press",
    "bench": "fedb-0025-barbell-bench-press",
    "incline_dumbbell": "fedb-0314-dumbbell-incline-bench-press",
    "high_row": "fedb-0581-lever-high-row",
    "barbell_row": "owner-e0c26a271aac-barbell-bent-over-row",
    "cable_row": "owner-2a5de4dc7ba3-seated-cable-row",
    "pulldown": "fedb-0974-cable-close-grip-lat-pulldown",
    "smith_press": "fedb-0765-smith-seated-shoulder-press",
    "military_press": "fedb-0553-military-press",
    "lever_lateral": "fedb-0584-lever-lateral-raise",
    "cable_lateral": "fedb-0178-cable-lateral-raise",
    "reverse_fly": "fedb-0602-lever-seated-reverse-fly",
    "preacher": "fedb-0592-lever-preacher-curl",
    "dumbbell_curl": "fedb-0285-seated-alternating-dumbbell-curl",
    "hammer_curl": "fedb-0298-dumbbell-cross-body-hammer-curl",
    "pushdown": "fedb-1723-cable-triceps-pushdown",
    "rope_pushdown": "fedb-0200-cable-rope-triceps-pushdown",
    "overhead": "fedb-0194-cable-rope-overhead-triceps-extension",
    "shrug": "fedb-0095-barbell-shrug",
}


def movement(slug_key: str, role: str) -> tuple[str, str]:
    return SLUGS[slug_key], role


def day(title: str, *items: tuple[str, str]) -> tuple[str, tuple[tuple[str, str], ...]]:
    return title, tuple(items)


EXPECTED_PROGRAMS = {
    "p01-2-day-full-body-ab-first-month": (
        "2d-full-body-ab",
        ExperienceLevel.FIRST_MONTH,
        (
            day(
                "Full Body A",
                movement("smith_squat", "P"),
                movement("leg_curl_seated", "S"),
                movement("chest_machine", "P"),
                movement("high_row", "P"),
                movement("pulldown", "S"),
                movement("smith_press", "S"),
            ),
            day(
                "Full Body B",
                movement("leg_press", "P"),
                movement("bridge", "P"),
                movement("incline_machine", "P"),
                movement("high_row", "P"),
                movement("pulldown", "S"),
                movement("lever_lateral", "I"),
            ),
        ),
    ),
    "p02-2-day-full-body-ab-beginner": (
        "2d-full-body-ab",
        ExperienceLevel.BEGINNER,
        (
            day(
                "Full Body A",
                movement("smith_squat", "P"),
                movement("leg_curl_seated", "S"),
                movement("chest_machine", "P"),
                movement("high_row", "P"),
                movement("pulldown", "S"),
                movement("smith_press", "S"),
            ),
            day(
                "Full Body B",
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("incline_dumbbell", "P"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("cable_lateral", "I"),
            ),
        ),
    ),
    "p03-2-day-full-body-ab-intermediate": (
        "2d-full-body-ab",
        ExperienceLevel.INTERMEDIATE,
        (
            day(
                "Full Body A",
                movement("back_squat", "P"),
                movement("leg_curl_seated", "S"),
                movement("bench", "P"),
                movement("barbell_row", "P"),
                movement("pulldown", "S"),
                movement("military_press", "S"),
            ),
            day(
                "Full Body B",
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("incline_dumbbell", "P"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("cable_lateral", "I"),
            ),
        ),
    ),
    "p04-3-day-upper-lower-full-first-month": (
        "3d-upper-lower-full-body",
        ExperienceLevel.FIRST_MONTH,
        (
            day(
                "Upper",
                movement("chest_machine", "P"),
                movement("incline_machine", "S"),
                movement("high_row", "P"),
                movement("pulldown", "S"),
                movement("smith_press", "P"),
                movement("lever_lateral", "I"),
            ),
            day(
                "Lower",
                movement("smith_squat", "P"),
                movement("leg_press", "P"),
                movement("bridge", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Full",
                movement("leg_press", "P"),
                movement("leg_curl_seated", "S"),
                movement("chest_machine", "P"),
                movement("high_row", "P"),
                movement("pulldown", "S"),
                movement("lever_lateral", "I"),
            ),
        ),
    ),
    "p05-3-day-upper-lower-full-beginner": (
        "3d-upper-lower-full-body",
        ExperienceLevel.BEGINNER,
        (
            day(
                "Upper",
                movement("chest_machine", "P"),
                movement("incline_dumbbell", "S"),
                movement("high_row", "P"),
                movement("pulldown", "S"),
                movement("smith_press", "P"),
                movement("cable_lateral", "I"),
            ),
            day(
                "Lower",
                movement("smith_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Full",
                movement("leg_press", "P"),
                movement("leg_curl_seated", "S"),
                movement("chest_machine", "P"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("cable_lateral", "I"),
            ),
        ),
    ),
    "p06-3-day-upper-lower-full-intermediate": (
        "3d-upper-lower-full-body",
        ExperienceLevel.INTERMEDIATE,
        (
            day(
                "Upper",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("barbell_row", "P"),
                movement("pulldown", "S"),
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
            ),
            day(
                "Lower",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Full",
                movement("leg_press", "P"),
                movement("leg_curl_seated", "S"),
                movement("bench", "P"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("cable_lateral", "I"),
            ),
        ),
    ),
    "p07-3-day-upper-lower-full-advanced": (
        "3d-upper-lower-full-body",
        ExperienceLevel.ADVANCED,
        (
            day(
                "Upper",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("barbell_row", "P"),
                movement("pulldown", "S"),
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
            ),
            day(
                "Lower",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Full",
                movement("leg_press", "P"),
                movement("leg_curl_seated", "S"),
                movement("bench", "P"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("cable_lateral", "I"),
            ),
        ),
    ),
    "p08-3-day-upper-lower-upper-beginner": (
        "3d-upper-lower-upper",
        ExperienceLevel.BEGINNER,
        (
            day(
                "Upper A",
                movement("chest_machine", "P"),
                movement("incline_dumbbell", "S"),
                movement("high_row", "P"),
                movement("pulldown", "S"),
                movement("smith_press", "P"),
                movement("cable_lateral", "I"),
                movement("preacher", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Lower",
                movement("smith_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper B",
                movement("incline_dumbbell", "P"),
                movement("chest_machine", "S"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("reverse_fly", "I"),
                movement("cable_lateral", "I"),
                movement("hammer_curl", "I"),
                movement("rope_pushdown", "I"),
            ),
        ),
    ),
    "p09-3-day-upper-lower-upper-intermediate": (
        "3d-upper-lower-upper",
        ExperienceLevel.INTERMEDIATE,
        (
            day(
                "Upper A",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("barbell_row", "P"),
                movement("pulldown", "S"),
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
                movement("dumbbell_curl", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Lower",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper B",
                movement("incline_dumbbell", "P"),
                movement("bench", "S"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("reverse_fly", "I"),
                movement("cable_lateral", "I"),
                movement("hammer_curl", "I"),
                movement("overhead", "I"),
            ),
        ),
    ),
    "p10-3-day-upper-lower-upper-advanced": (
        "3d-upper-lower-upper",
        ExperienceLevel.ADVANCED,
        (
            day(
                "Upper A",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("barbell_row", "P"),
                movement("pulldown", "S"),
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
                movement("dumbbell_curl", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Lower",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper B",
                movement("incline_dumbbell", "P"),
                movement("bench", "S"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("reverse_fly", "I"),
                movement("cable_lateral", "I"),
                movement("hammer_curl", "I"),
                movement("overhead", "I"),
            ),
        ),
    ),
    "p11-3-day-lower-upper-lower-beginner": (
        "3d-lower-upper-lower",
        ExperienceLevel.BEGINNER,
        (
            day(
                "Lower A",
                movement("smith_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper",
                movement("chest_machine", "P"),
                movement("incline_dumbbell", "S"),
                movement("high_row", "P"),
                movement("pulldown", "S"),
                movement("smith_press", "P"),
                movement("cable_lateral", "I"),
                movement("preacher", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Lower B",
                movement("leg_press", "P"),
                movement("lunge", "S"),
                movement("deadlift", "P"),
                movement("leg_curl_lying", "S"),
                movement("calf", "I"),
            ),
        ),
    ),
    "p12-3-day-lower-upper-lower-intermediate": (
        "3d-lower-upper-lower",
        ExperienceLevel.INTERMEDIATE,
        (
            day(
                "Lower A",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("barbell_row", "P"),
                movement("pulldown", "S"),
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
                movement("dumbbell_curl", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Lower B",
                movement("leg_press", "P"),
                movement("lunge", "S"),
                movement("deadlift", "P"),
                movement("leg_curl_lying", "S"),
                movement("calf", "I"),
            ),
        ),
    ),
    "p13-3-day-lower-upper-lower-advanced": (
        "3d-lower-upper-lower",
        ExperienceLevel.ADVANCED,
        (
            day(
                "Lower A",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("barbell_row", "P"),
                movement("pulldown", "S"),
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
                movement("dumbbell_curl", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Lower B",
                movement("leg_press", "P"),
                movement("lunge", "S"),
                movement("deadlift", "P"),
                movement("leg_curl_lying", "S"),
                movement("calf", "I"),
            ),
        ),
    ),
    "p14-4-day-upper-lower-upper-lower-first-month": (
        "4d-upper-lower-2x",
        ExperienceLevel.FIRST_MONTH,
        (
            day(
                "Upper A",
                movement("chest_machine", "P"),
                movement("incline_machine", "S"),
                movement("high_row", "P"),
                movement("pulldown", "S"),
                movement("smith_press", "P"),
                movement("lever_lateral", "I"),
            ),
            day(
                "Lower A",
                movement("smith_squat", "P"),
                movement("leg_press", "P"),
                movement("bridge", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper B",
                movement("incline_machine", "P"),
                movement("chest_machine", "S"),
                movement("high_row", "P"),
                movement("pulldown", "S"),
                movement("reverse_fly", "I"),
                movement("lever_lateral", "I"),
            ),
            day(
                "Lower B",
                movement("smith_squat", "P"),
                movement("leg_extension", "I"),
                movement("bridge", "P"),
                movement("leg_curl_lying", "S"),
                movement("calf", "I"),
            ),
        ),
    ),
    "p15-4-day-upper-lower-upper-lower-beginner": (
        "4d-upper-lower-2x",
        ExperienceLevel.BEGINNER,
        (
            day(
                "Upper A",
                movement("chest_machine", "P"),
                movement("incline_dumbbell", "S"),
                movement("high_row", "P"),
                movement("pulldown", "S"),
                movement("smith_press", "P"),
                movement("cable_lateral", "I"),
            ),
            day(
                "Lower A",
                movement("smith_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper B",
                movement("incline_dumbbell", "P"),
                movement("chest_machine", "S"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("reverse_fly", "I"),
                movement("cable_lateral", "I"),
            ),
            day(
                "Lower B",
                movement("smith_squat", "P"),
                movement("leg_extension", "I"),
                movement("deadlift", "P"),
                movement("leg_curl_lying", "S"),
                movement("calf", "I"),
            ),
        ),
    ),
    "p16-4-day-upper-lower-upper-lower-intermediate": (
        "4d-upper-lower-2x",
        ExperienceLevel.INTERMEDIATE,
        (
            day(
                "Upper A",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("barbell_row", "P"),
                movement("pulldown", "S"),
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
            ),
            day(
                "Lower A",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper B",
                movement("incline_dumbbell", "P"),
                movement("bench", "S"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("reverse_fly", "I"),
                movement("cable_lateral", "I"),
            ),
            day(
                "Lower B",
                movement("front_squat", "P"),
                movement("leg_extension", "I"),
                movement("deadlift", "P"),
                movement("leg_curl_lying", "S"),
                movement("calf", "I"),
            ),
        ),
    ),
    "p17-4-day-upper-lower-upper-lower-advanced": (
        "4d-upper-lower-2x",
        ExperienceLevel.ADVANCED,
        (
            day(
                "Upper A",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("barbell_row", "P"),
                movement("pulldown", "S"),
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
            ),
            day(
                "Lower A",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper B",
                movement("incline_dumbbell", "P"),
                movement("bench", "S"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("reverse_fly", "I"),
                movement("cable_lateral", "I"),
            ),
            day(
                "Lower B",
                movement("front_squat", "P"),
                movement("leg_extension", "I"),
                movement("deadlift", "P"),
                movement("leg_curl_lying", "S"),
                movement("calf", "I"),
            ),
        ),
    ),
    "p18-4-day-3-upper-1-lower-beginner": (
        "4d-3-upper-1-lower",
        ExperienceLevel.BEGINNER,
        (
            day(
                "Upper A",
                movement("chest_machine", "P"),
                movement("incline_dumbbell", "S"),
                movement("high_row", "P"),
                movement("pulldown", "S"),
                movement("cable_lateral", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Lower",
                movement("smith_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper B",
                movement("smith_press", "P"),
                movement("cable_lateral", "I"),
                movement("reverse_fly", "I"),
                movement("preacher", "I"),
                movement("hammer_curl", "I"),
                movement("pushdown", "I"),
                movement("rope_pushdown", "I"),
            ),
            day(
                "Upper C",
                movement("incline_dumbbell", "P"),
                movement("chest_machine", "S"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("preacher", "I"),
            ),
        ),
    ),
    "p19-4-day-3-upper-1-lower-intermediate": (
        "4d-3-upper-1-lower",
        ExperienceLevel.INTERMEDIATE,
        (
            day(
                "Upper A",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("barbell_row", "P"),
                movement("pulldown", "S"),
                movement("cable_lateral", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Lower",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper B",
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
                movement("reverse_fly", "I"),
                movement("dumbbell_curl", "I"),
                movement("hammer_curl", "I"),
                movement("pushdown", "I"),
                movement("overhead", "I"),
            ),
            day(
                "Upper C",
                movement("incline_dumbbell", "P"),
                movement("bench", "S"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("dumbbell_curl", "I"),
            ),
        ),
    ),
    "p20-4-day-3-upper-1-lower-advanced": (
        "4d-3-upper-1-lower",
        ExperienceLevel.ADVANCED,
        (
            day(
                "Upper A",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("barbell_row", "P"),
                movement("pulldown", "S"),
                movement("cable_lateral", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Lower",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("deadlift", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper B",
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
                movement("reverse_fly", "I"),
                movement("dumbbell_curl", "I"),
                movement("hammer_curl", "I"),
                movement("pushdown", "I"),
                movement("overhead", "I"),
            ),
            day(
                "Upper C",
                movement("incline_dumbbell", "P"),
                movement("bench", "S"),
                movement("cable_row", "P"),
                movement("pulldown", "S"),
                movement("dumbbell_curl", "I"),
            ),
        ),
    ),
    "p21-4-day-3-lower-1-upper-beginner": (
        "4d-3-lower-1-upper",
        ExperienceLevel.BEGINNER,
        (
            day(
                "Lower A",
                movement("smith_squat", "P"),
                movement("leg_press", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper",
                movement("chest_machine", "P"),
                movement("incline_dumbbell", "S"),
                movement("high_row", "P"),
                movement("pulldown", "S"),
                movement("smith_press", "P"),
                movement("cable_lateral", "I"),
                movement("preacher", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Lower B",
                movement("deadlift", "P"),
                movement("leg_curl_lying", "S"),
                movement("bridge", "P"),
                movement("calf", "I"),
            ),
            day(
                "Lower C",
                movement("leg_press", "P"),
                movement("leg_extension", "I"),
                movement("bridge", "P"),
                movement("calf", "I"),
            ),
        ),
    ),
    "p22-4-day-3-lower-1-upper-intermediate": (
        "4d-3-lower-1-upper",
        ExperienceLevel.INTERMEDIATE,
        (
            day(
                "Lower A",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("barbell_row", "P"),
                movement("pulldown", "S"),
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
                movement("dumbbell_curl", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Lower B",
                movement("deadlift", "P"),
                movement("leg_curl_lying", "S"),
                movement("bridge", "P"),
                movement("calf", "I"),
            ),
            day(
                "Lower C",
                movement("leg_press", "P"),
                movement("leg_extension", "I"),
                movement("bridge", "P"),
                movement("calf", "I"),
            ),
        ),
    ),
    "p23-4-day-3-lower-1-upper-advanced": (
        "4d-3-lower-1-upper",
        ExperienceLevel.ADVANCED,
        (
            day(
                "Lower A",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("leg_curl_seated", "S"),
                movement("calf", "I"),
            ),
            day(
                "Upper",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("barbell_row", "P"),
                movement("pulldown", "S"),
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
                movement("dumbbell_curl", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Lower B",
                movement("deadlift", "P"),
                movement("leg_curl_lying", "S"),
                movement("bridge", "P"),
                movement("calf", "I"),
            ),
            day(
                "Lower C",
                movement("leg_press", "P"),
                movement("leg_extension", "I"),
                movement("bridge", "P"),
                movement("calf", "I"),
            ),
        ),
    ),
    "p24-4-day-push-pull-quads-posterior-intermediate": (
        "4d-push-pull-quads-posterior",
        ExperienceLevel.INTERMEDIATE,
        (
            day(
                "Push",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Pull",
                movement("barbell_row", "P"),
                movement("pulldown", "P"),
                movement("dumbbell_curl", "I"),
                movement("shrug", "I"),
            ),
            day(
                "Quads",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("leg_extension", "I"),
                movement("calf", "I"),
            ),
            day(
                "Posterior",
                movement("deadlift", "P"),
                movement("leg_curl_lying", "S"),
                movement("bridge", "P"),
                movement("calf", "I"),
            ),
        ),
    ),
    "p25-4-day-push-pull-quads-posterior-advanced": (
        "4d-push-pull-quads-posterior",
        ExperienceLevel.ADVANCED,
        (
            day(
                "Push",
                movement("bench", "P"),
                movement("incline_dumbbell", "S"),
                movement("military_press", "P"),
                movement("cable_lateral", "I"),
                movement("pushdown", "I"),
            ),
            day(
                "Pull",
                movement("barbell_row", "P"),
                movement("pulldown", "P"),
                movement("dumbbell_curl", "I"),
                movement("shrug", "I"),
            ),
            day(
                "Quads",
                movement("back_squat", "P"),
                movement("leg_press", "P"),
                movement("leg_extension", "I"),
                movement("calf", "I"),
            ),
            day(
                "Posterior",
                movement("deadlift", "P"),
                movement("leg_curl_lying", "S"),
                movement("bridge", "P"),
                movement("calf", "I"),
            ),
        ),
    ),
}


def test_default_program_matrix_preserves_exactly_25_legacy_programs() -> None:
    legacy_definitions = [
        definition
        for definition in CANONICAL_TEMPLATE_DEFINITIONS
        if definition.canonical_slug in EXPECTED_PROGRAMS
    ]
    legacy_seeds = [
        seed for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS if seed.slug in EXPECTED_PROGRAMS
    ]
    assert len(legacy_definitions) == 25
    assert len(legacy_seeds) == 25
    assert {seed.slug for seed in legacy_seeds} == set(EXPECTED_PROGRAMS)


def test_default_program_definitions_match_approved_days_and_exercises() -> None:
    definitions = {
        definition.canonical_slug: definition for definition in CANONICAL_TEMPLATE_DEFINITIONS
    }

    for slug, (structure_slug, level, expected_days) in EXPECTED_PROGRAMS.items():
        definition = definitions[slug]
        assert definition.structure_slug == structure_slug
        assert definition.supported_levels == (level,)
        assert (
            tuple(
                (
                    day_seed.title_en,
                    tuple((movement.exercise_slug, role) for movement, role in day_specs),
                )
                for day_seed, day_specs in zip(definition.days, definition.day_specs, strict=True)
            )
            == expected_days
        )


def test_default_program_prescriptions_match_level_and_role() -> None:
    expected = {
        ExperienceLevel.FIRST_MONTH: {"P": (3, 8, 12, 3), "S": (3, 8, 12, 3), "I": (3, 10, 15, 3)},
        ExperienceLevel.BEGINNER: {"P": (3, 8, 12, 3), "S": (3, 8, 12, 3), "I": (3, 10, 15, 3)},
        ExperienceLevel.INTERMEDIATE: {"P": (3, 6, 10, 2), "S": (3, 8, 12, 2), "I": (3, 10, 15, 2)},
        ExperienceLevel.ADVANCED: {"P": (4, 5, 8, 1), "S": (3, 8, 12, 2), "I": (3, 10, 15, 2)},
    }
    seeds = {seed.slug: seed for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS}

    for slug, (_, level, expected_days) in EXPECTED_PROGRAMS.items():
        seed = seeds[slug]
        for day_seed, (_, expected_slots) in zip(seed.days, expected_days, strict=True):
            for slot, (_, role) in zip(day_seed.slots, expected_slots, strict=True):
                assert (slot.sets, slot.rep_min, slot.rep_max, slot.target_rir) == expected[level][
                    role
                ]


def test_seed_creates_exactly_53_linked_programs_with_valid_structures(db: Session) -> None:
    seed_real_catalog_exercises(db)

    result = seed_training_program_templates(db)

    assert result.templates == 53
    assert (
        db.scalar(
            select(func.count())
            .select_from(TrainingProgramTemplate)
            .where(
                TrainingProgramTemplate.source_name == "Fitsho canonical training template catalog"
            )
        )
        == 53
    )
    templates = list(
        db.scalars(
            select(TrainingProgramTemplate)
            .where(
                TrainingProgramTemplate.source_name == "Fitsho canonical training template catalog"
            )
            .options(
                selectinload(TrainingProgramTemplate.days).selectinload(
                    TrainingProgramTemplateDay.slots
                ),
                selectinload(TrainingProgramTemplate.structure),
            )
        )
    )
    assert all(template.structure_id is not None for template in templates)
    assert all(
        template.structure is not None
        and template.structure.days_per_week == template.days_per_week
        for template in templates
    )
    assert all(len(template.days) == template.days_per_week for template in templates)
    assert all(
        slot.exercise_id is not None
        for template in templates
        for day in template.days
        for slot in day.slots
    )


def test_seed_is_idempotent_and_does_not_duplicate_program_days_or_slots(db: Session) -> None:
    seed_real_catalog_exercises(db)

    first = seed_training_program_templates(db)
    first_days = db.scalar(select(func.count()).select_from(TrainingProgramTemplateDay))
    first_slots = db.scalar(select(func.count()).select_from(TrainingProgramTemplateSlot))
    second = seed_training_program_templates(db)

    assert second == first
    assert second.templates == 53
    assert db.scalar(select(func.count()).select_from(TrainingProgramTemplate)) == 53
    assert db.scalar(select(func.count()).select_from(TrainingProgramTemplateDay)) == first_days
    assert db.scalar(select(func.count()).select_from(TrainingProgramTemplateSlot)) == first_slots


def test_seed_uses_only_active_programmable_exercise_library_records(db: Session) -> None:
    seed_real_catalog_exercises(db)
    before = db.scalar(select(func.count()).select_from(Exercise))

    seed_training_program_templates(db)

    slots = list(
        db.scalars(
            select(TrainingProgramTemplateSlot).options(
                selectinload(TrainingProgramTemplateSlot.exercise)
            )
        )
    )
    assert all(
        slot.exercise is not None
        and slot.exercise.is_active
        and slot.exercise.is_programmable
        for slot in slots
    )
    assert db.scalar(select(func.count()).select_from(Exercise)) == before


def test_unsupported_level_combinations_are_absent() -> None:
    by_structure: dict[str, set[ExperienceLevel]] = {}
    for definition in CANONICAL_TEMPLATE_DEFINITIONS:
        by_structure.setdefault(definition.structure_slug, set()).update(
            definition.supported_levels
        )
    assert by_structure["2d-full-body-ab"] == {
        ExperienceLevel.FIRST_MONTH,
        ExperienceLevel.BEGINNER,
        ExperienceLevel.INTERMEDIATE,
    }
    assert by_structure["3d-upper-lower-upper"] == {
        ExperienceLevel.BEGINNER,
        ExperienceLevel.INTERMEDIATE,
        ExperienceLevel.ADVANCED,
    }
    assert by_structure["3d-lower-upper-lower"] == {
        ExperienceLevel.BEGINNER,
        ExperienceLevel.INTERMEDIATE,
        ExperienceLevel.ADVANCED,
    }
    assert by_structure["4d-3-upper-1-lower"] == {
        ExperienceLevel.BEGINNER,
        ExperienceLevel.INTERMEDIATE,
        ExperienceLevel.ADVANCED,
    }
    assert by_structure["4d-3-lower-1-upper"] == {
        ExperienceLevel.BEGINNER,
        ExperienceLevel.INTERMEDIATE,
        ExperienceLevel.ADVANCED,
    }
    assert by_structure["4d-push-pull-quads-posterior"] == {
        ExperienceLevel.INTERMEDIATE,
        ExperienceLevel.ADVANCED,
    }


def test_all_expected_slugs_are_resolvable() -> None:
    expected_slugs: Iterable[str] = (
        slug
        for program in EXPECTED_PROGRAMS.values()
        for _, slots in program[2]
        for slug, _ in slots
    )
    assert set(expected_slugs) <= set(SLUGS.values())
