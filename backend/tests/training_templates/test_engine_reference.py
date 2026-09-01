from dataclasses import replace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.enums import Equipment
from app.exercises.models import Exercise
from app.profile.enums import TrainingLocation
from app.training_templates.engine_reference import load_template_references
from app.training_templates.models import TrainingProgramTemplate
from app.training_templates.service import (
    seed_training_program_templates,
    upgrade_training_program_template_catalog,
)
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, SplitType, TrainingExperience
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.service import WorkoutGenerationService
from tests.training_templates.catalog_fixture import seed_real_catalog_exercises
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def test_engine_references_preserve_linked_slot_and_adaptation_metadata(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)

    reference = next(
        item
        for item in load_template_references(db)
        if item.slug == "p24-4-day-push-pull-quads-posterior-intermediate"
    )

    assert reference.days_per_week == 4
    assert all(slot.exercise_id is not None for day in reference.days for slot in day.slots)
    assert all(
        slot.adaptation_priority in {"core", "accessory", "optional"}
        for day in reference.days
        for slot in day.slots
    )


def test_engine_reference_rejects_noncanonical_persisted_focus_tags(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)
    template = db.scalar(
        select(TrainingProgramTemplate).where(
            TrainingProgramTemplate.slug == "p24-4-day-push-pull-quads-posterior-intermediate"
        )
    )
    assert template is not None
    template.focus_tags = ["classic"]
    db.flush()

    with pytest.raises(ValueError, match="Unknown template focus tag"):
        load_template_references(db)


@pytest.mark.parametrize(
    ("slug", "expected"),
    (
        ("p01-2-day-full-body-ab-first-month", SplitType.FULL_BODY),
        ("p14-4-day-upper-lower-upper-lower-first-month", SplitType.UPPER_LOWER),
        (
            "p24-4-day-push-pull-quads-posterior-intermediate",
            SplitType.PUSH_PULL_LEGS,
        ),
    ),
)
def test_engine_reference_preserves_canonical_split_identity(
    db: Session,
    slug: str,
    expected: SplitType,
) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)

    reference = next(item for item in load_template_references(db) if item.slug == slug)

    assert reference.split_type is expected


def test_advanced_catalog_program_reaches_the_programmed_session(db: Session) -> None:
    seed_real_catalog_exercises(db)
    upgrade_training_program_template_catalog(db)
    reference = next(
        item
        for item in load_template_references(db)
        if item.slug == "p25-4-day-push-pull-quads-posterior-advanced"
    )
    linked_ids = {
        slot.exercise_id
        for day in reference.days
        for slot in day.slots
        if slot.exercise_id is not None
    }
    catalog = (
        *(
            replace(
                WorkoutGenerationService._domain_candidate(exercise),
                equipment=frozenset(Equipment),
            )
            for exercise in db.scalars(select(Exercise).where(Exercise.id.in_(linked_ids)))
        ),
        *full_catalog(),
    )

    source = request(
        primary_goal=Goal.MUSCLE_GAIN,
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
        available_training_days=4,
        session_duration_minutes=75,
        available_equipment=list(Equipment),
        training_location=TrainingLocation.GYM,
    )
    result = generate_program(
        source,
        catalog,
        RULESET,
        reference_templates=(reference,),
    )

    assert result.program is not None, result.errors
    primary_selection = next(
        item
        for item in result.program.decision_trace
        if item.get("stage") == "post_construction_template_selection"
    )
    template_candidates = primary_selection.get("candidates", ())
    assert any(
        item.get("slug") == reference.slug and item.get("status") == "succeeded"
        for item in template_candidates
    )
    assert len(result.program.weekly_schedule) == 4
