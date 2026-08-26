from dataclasses import replace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.enums import Equipment, MuscleGroup
from app.exercises.models import Exercise
from app.profile.enums import TrainingLocation
from app.training_templates.engine_reference import load_template_references
from app.training_templates.models import TrainingProgramTemplate
from app.training_templates.service import (
    seed_training_program_templates,
    upgrade_training_program_template_catalog,
)
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, SplitType, TrainingExperience
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.supplemental_policy import is_supplemental_muscle
from app.workouts.program_engine.template_sessions import build_template_sessions
from app.workouts.service import WorkoutGenerationService
from tests.training_templates.catalog_fixture import seed_real_catalog_exercises
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def test_engine_references_preserve_linked_slot_and_adaptation_metadata(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)

    reference = next(
        item for item in load_template_references(db) if item.slug == "t14-5-day-leg-specialization"
    )

    assert reference.days_per_week == 5
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
            TrainingProgramTemplate.slug == "t10-5-day-classic-body-part"
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
        ("t01-2-day-full-body-ab", SplitType.FULL_BODY),
        ("t05-4-day-upper-lower-2x", SplitType.UPPER_LOWER),
        (
            "t09-5-day-ppl-upper-lower",
            SplitType.PUSH_PULL_LEGS_UPPER_LOWER,
        ),
        ("t10-5-day-classic-body-part", SplitType.BODY_PART_ROTATION),
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


def test_advanced_catalog_methods_reach_the_programmed_session(db: Session) -> None:
    seed_real_catalog_exercises(db)
    upgrade_training_program_template_catalog(db)
    reference = next(
        item
        for item in load_template_references(db)
        if item.slug == "t16-6-day-advanced-body-part"
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
        available_training_days=6,
        session_duration_minutes=90,
        available_equipment=list(Equipment),
        training_location=TrainingLocation.GYM,
    )
    normalized = normalize_request(source, RULESET)
    eligible = filter_eligible_exercises(normalized, catalog).eligible
    build = build_template_sessions(normalized, reference, eligible, RULESET)
    mismatches = tuple(
        (draft.day_index, candidate.name, candidate.primary_muscle)
        for draft in build.drafts
        for candidate in draft.exercises
        if candidate.primary_muscle not in reference.days[draft.day_index - 1].focus
        and not is_supplemental_muscle(candidate.primary_muscle)
    )
    assert not mismatches, mismatches

    result = generate_program(
        source,
        catalog,
        RULESET,
        reference_templates=(reference,),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics.get("reference_template") == reference.slug, (
        tuple(
            item.get("reason_codes")
            for item in result.decision_trace
            if item.get("stage") in {"template_reference", "template_attempt"}
        )
    )
    exercises = tuple(
        exercise for day in result.program.weekly_schedule for exercise in day.exercises
    )
    grouped = tuple(item for item in exercises if item.superset_group == "t16-arms-superset")
    drop_sets = tuple(
        item for item in exercises if "SAFE_TEMPLATE_DROP_SET_APPLIED" in item.reason_codes
    )
    assert len(grouped) == 2, tuple(
        (item.exercise_name, item.primary_muscle, item.superset_group, item.reason_codes)
        for item in exercises
        if item.primary_muscle in {MuscleGroup.BICEPS, MuscleGroup.TRICEPS}
    )
    assert all("SAFE_TEMPLATE_SUPERSET_PRESERVED" in item.reason_codes for item in grouped)
    assert len(drop_sets) == 1
    assert drop_sets[0].notes == "drop_set:last_working_set_reduce_load_20_to_30_percent"
