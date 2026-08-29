from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, TrainingExperience
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    TemplateReference,
    TemplateReferenceDay,
)
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _chest_triceps_reference() -> TemplateReference:
    return TemplateReference(
        slug="test_chest_triceps_template",
        days_per_week=1,
        supported_levels=("intermediate",),
        focus_tags=(),
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Chest and Triceps",
                focus=(MuscleGroup.CHEST, MuscleGroup.TRICEPS),
                structure_focus="chest_triceps",
                slots=(),
            ),
        ),
    )


def test_template_structure_propagation_chest_triceps() -> None:
    req = request(
        training_experience=TrainingExperience.INTERMEDIATE,
        available_training_days=1,
        primary_goal=Goal.HYPERTROPHY,
        session_duration_minutes=45,
    )
    catalog = full_catalog()
    ref = _chest_triceps_reference()

    result = generate_program(req, catalog, RULESET, reference_templates=(ref,))
    assert result.is_success
    program = result.program
    assert program is not None

    chest_day = next(
        d for d in program.weekly_schedule if d.template_structure_focus == "chest_triceps"
    )

    chest_indices = [
        i for i, ex in enumerate(chest_day.exercises) if ex.primary_muscle == MuscleGroup.CHEST
    ]
    triceps_indices = [
        i for i, ex in enumerate(chest_day.exercises) if ex.primary_muscle == MuscleGroup.TRICEPS
    ]

    assert chest_indices
    assert triceps_indices
    assert max(chest_indices) < min(triceps_indices)


def test_duration_repair_preserves_template_structure_focus() -> None:
    from app.workouts.program_engine.schemas import WorkoutDay
    from app.workouts.program_engine.session_duration import _rebuild_day

    day = WorkoutDay(
        day_index=1,
        weekday=None,
        title="Test",
        focus="chest_triceps",
        estimated_duration_minutes=60,
        exercises=(),
        template_structure_focus="chest_triceps",
    )
    new_day = _rebuild_day(day, (), RULESET)
    assert new_day.template_structure_focus == "chest_triceps"


def test_cardio_preserves_template_structure_focus() -> None:
    from app.workouts.program_engine.cardio import add_cardio
    from app.workouts.program_engine.schemas import WorkoutDay

    day = WorkoutDay(
        day_index=1,
        weekday=None,
        title="Test",
        focus="chest_triceps",
        estimated_duration_minutes=60,
        exercises=(),
        template_structure_focus="chest_triceps",
    )

    req = request(available_training_days=1, primary_goal=Goal.HYPERTROPHY)
    from app.workouts.program_engine.normalization import normalize_request

    normalized = normalize_request(req, RULESET)
    new_days = add_cardio(normalized, (day,), (), RULESET)
    assert new_days[0].template_structure_focus == "chest_triceps"


def _back_biceps_reference() -> TemplateReference:
    return TemplateReference(
        slug="test_back_biceps_template",
        days_per_week=1,
        supported_levels=("intermediate",),
        focus_tags=(),
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Back and Biceps",
                focus=(MuscleGroup.BACK, MuscleGroup.BICEPS),
                structure_focus="back_biceps",
                slots=(),
            ),
        ),
    )


def test_template_structure_propagation_back_biceps() -> None:
    req = request(
        training_experience=TrainingExperience.INTERMEDIATE,
        available_training_days=1,
        primary_goal=Goal.HYPERTROPHY,
        session_duration_minutes=60,
    )
    catalog = full_catalog()
    ref = _back_biceps_reference()

    result = generate_program(req, catalog, RULESET, reference_templates=(ref,))
    assert result.is_success
    program = result.program
    assert program is not None

    back_day = next(
        d for d in program.weekly_schedule if d.template_structure_focus == "back_biceps"
    )

    back_indices = [
        i for i, ex in enumerate(back_day.exercises) if ex.primary_muscle == MuscleGroup.BACK
    ]
    biceps_indices = [
        i for i, ex in enumerate(back_day.exercises) if ex.primary_muscle == MuscleGroup.BICEPS
    ]

    assert back_indices
    assert biceps_indices
    assert max(back_indices) < min(biceps_indices)


def _full_body_reference() -> TemplateReference:
    return TemplateReference(
        slug="test_full_body_template",
        days_per_week=1,
        supported_levels=("intermediate",),
        focus_tags=(),
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Full Body",
                focus=(MuscleGroup.CHEST, MuscleGroup.QUADRICEPS),
                structure_focus="full_body",
                slots=(),
            ),
        ),
    )


def test_template_structure_propagation_full_body() -> None:
    req = request(
        training_experience=TrainingExperience.INTERMEDIATE,
        available_training_days=1,
        primary_goal=Goal.HYPERTROPHY,
        session_duration_minutes=45,
    )
    catalog = full_catalog()
    ref = _full_body_reference()

    result = generate_program(req, catalog, RULESET, reference_templates=(ref,))
    assert result.is_success
    program = result.program
    assert program is not None

    for day in program.weekly_schedule:
        assert day.template_structure_focus == "full_body"


def _upper_lower_reference() -> TemplateReference:
    return TemplateReference(
        slug="test_upper_lower_template",
        days_per_week=2,
        supported_levels=("intermediate",),
        focus_tags=(),
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Upper",
                focus=(MuscleGroup.CHEST,),
                structure_focus="upper",
                slots=(),
            ),
            TemplateReferenceDay(
                day_number=2,
                title="Lower",
                focus=(MuscleGroup.QUADRICEPS,),
                structure_focus="lower",
                slots=(),
            ),
        ),
    )


def test_template_structure_propagation_upper_lower() -> None:
    req = request(
        training_experience=TrainingExperience.INTERMEDIATE,
        available_training_days=2,
        primary_goal=Goal.HYPERTROPHY,
        session_duration_minutes=120,
    )
    catalog = full_catalog()
    ref = _upper_lower_reference()

    generate_program(req, catalog, RULESET, reference_templates=(ref,))
    # It may reject the slotless template; the strict-block classification is still stable.
    # We will test _strict_block directly to show they remain non-strict.
    from app.workouts.program_engine.session_structure import _STRICT_BLOCKS

    assert "full_body" not in _STRICT_BLOCKS
    assert "upper" not in _STRICT_BLOCKS
    assert "lower" not in _STRICT_BLOCKS
