from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

from app.exercises.enums import Difficulty, Equipment, ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from app.workouts.program_engine.template_sessions import build_template_sessions
from tests.workouts.program_engine.golden_fixtures import request

TEST_RULESET = replace(RULESET, minimum_exercises_per_session=1)


def _exercise(slug: str, equipment: Equipment) -> ExerciseCandidate:
    return ExerciseCandidate(
        id=uuid5(NAMESPACE_URL, f"https://fitsho.test/shared-template/{slug}"),
        name=slug.replace("-", " ").title(),
        primary_muscle=MuscleGroup.CHEST,
        secondary_muscles=(),
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        exercise_type=ExerciseType.COMPOUND,
        equipment=frozenset({equipment}),
        difficulty=(
            Difficulty.BEGINNER if equipment is Equipment.MACHINE else Difficulty.ADVANCED
        ),
        substitution_group="horizontal-push",
    )


def _template(anchor: ExerciseCandidate) -> TemplateReference:
    return TemplateReference(
        slug="t05-shared-canonical-template",
        days_per_week=1,
        supported_levels=("first_month", "beginner", "intermediate", "advanced"),
        focus_tags=("full_body",),
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Push",
                focus=(MuscleGroup.CHEST,),
                structure_focus="full_body",
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=anchor.id,
                        exercise_slug_hint=anchor.name,
                        target_muscles=(MuscleGroup.CHEST,),
                        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
                        intensity_method="standard",
                        adaptation_priority="core",
                        superset_group=None,
                        superset_exercise_id=None,
        superset_exercise_slug_hint=None,
        sets=3,
                        rep_min=8,
                        rep_max=12,
                        target_rir=2,
                        rest_seconds=90,
                    ),
                ),
            ),
        ),
    )


def test_one_shared_template_resolves_level_appropriate_content_deterministically() -> None:
    machine = _exercise("machine-chest-press", Equipment.MACHINE)
    barbell = _exercise("barbell-bench-press", Equipment.BARBELL)
    catalog = (machine, barbell)
    template = _template(machine)

    first_month = normalize_request(
        request(
            available_training_days=1,
            training_experience="first_month",
            training_age_months=0,
            available_equipment=[Equipment.BARBELL, Equipment.BENCH, Equipment.MACHINE],
        ),
        TEST_RULESET,
    )
    intermediate = normalize_request(
        request(
            available_training_days=1,
            training_experience="intermediate",
            training_age_months=24,
            available_equipment=[Equipment.BARBELL, Equipment.BENCH, Equipment.MACHINE],
        ),
        TEST_RULESET,
    )

    first_month_build = build_template_sessions(
        first_month,
        template,
        catalog,
        TEST_RULESET,
        exercise_catalog=catalog,
    )
    intermediate_build = build_template_sessions(
        intermediate,
        template,
        catalog,
        TEST_RULESET,
        exercise_catalog=catalog,
    )
    repeat_intermediate_build = build_template_sessions(
        intermediate,
        template,
        tuple(reversed(catalog)),
        TEST_RULESET,
        exercise_catalog=tuple(reversed(catalog)),
    )

    assert template.slug == "t05-shared-canonical-template"
    assert first_month_build.resolutions[0].selected_exercise_id == machine.id
    assert intermediate_build.resolutions[0].selected_exercise_id == barbell.id
    assert (
        repeat_intermediate_build.resolutions[0].selected_exercise_id
        == intermediate_build.resolutions[0].selected_exercise_id
    )
