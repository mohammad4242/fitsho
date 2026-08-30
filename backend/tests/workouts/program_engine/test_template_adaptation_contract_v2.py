from app.exercises.enums import Equipment, MuscleGroup
from app.training_templates.tags import TemplateFocusTag
from app.workouts.program_engine.duration_capacity import SessionCapacity
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from app.workouts.program_engine.supplemental_policy import main_exercise_count
from app.workouts.program_engine.template_sessions import build_template_sessions
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _slot(
    candidate: ExerciseCandidate, focus: tuple[MuscleGroup, ...]
) -> TemplateReferenceSlot:
    return TemplateReferenceSlot(
        exercise_id=candidate.id,
        exercise_slug_hint=candidate.name,
        target_muscles=focus,
        movement_pattern=candidate.movement_pattern,
        intensity_method="standard",
        adaptation_priority="core",
        superset_group=None,
        superset_exercise_id=None,
        superset_exercise_slug_hint=None,
        sets=3,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=75,
    )


def _four_exercise_template(catalog: tuple[ExerciseCandidate, ...]) -> TemplateReference:
    initial = catalog[:4]
    focus = tuple(item.primary_muscle for item in catalog if item.primary_muscle is not None)
    return TemplateReference(
        slug="semantic-adaptation-fixture",
        days_per_week=1,
        supported_levels=("intermediate",),
        focus_tags=(TemplateFocusTag.FULL_BODY,),
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Professional full body",
                focus=focus,
                slots=tuple(_slot(item, focus) for item in initial),
            ),
        ),
    )


def _normalized_request() -> NormalizedProgramRequest:
    return normalize_request(
        request(
            training_experience="intermediate",
            training_age_months=30,
            available_training_days=1,
            session_duration_minutes=45,
            available_equipment=[Equipment.BODYWEIGHT, Equipment.DUMBBELL],
        ),
        RULESET,
    )


def _five_exercise_capacity() -> SessionCapacity:
    return SessionCapacity(
        requested_workout_minutes=45,
        target_total_minutes=45,
        minimum_workout_minutes=35,
        maximum_workout_minutes=55,
        resistance_work_budget_minutes=45,
        minimum_resistance_work_minutes=35,
        maximum_resistance_work_minutes=55,
        expected_exercise_count_capacity=5,
        expected_working_set_capacity=15,
        representative_exercise_minutes=7,
    )


def test_four_initial_exercises_are_repaired_with_one_useful_candidate() -> None:
    catalog = tuple(full_catalog()[:7])
    template = _four_exercise_template(catalog)

    build = build_template_sessions(
        _normalized_request(),
        template,
        catalog,
        RULESET,
        session_capacity=_five_exercise_capacity(),
    )

    assert main_exercise_count(build.drafts[0].exercises) == 5
    assert build.drafts[0].template_target_muscles == template.days[0].focus
    assert build.drafts[0].template_structure_focus == "full_body"
    assert "TEMPLATE_SESSION_COUNT_CONSTRAINED_BY_SAFE_CAPACITY" not in build.reason_codes


def test_no_useful_candidate_does_not_add_junk_or_duplicate_work() -> None:
    catalog = tuple(full_catalog()[:4])
    template = _four_exercise_template(catalog)

    build = build_template_sessions(
        _normalized_request(),
        template,
        catalog,
        RULESET,
        session_capacity=_five_exercise_capacity(),
    )

    selected = build.drafts[0].exercises
    assert main_exercise_count(selected) == 4
    assert len({item.id for item in selected}) == 4
    assert "TEMPLATE_SESSION_COUNT_CONSTRAINED_BY_SAFE_CAPACITY" in build.reason_codes
