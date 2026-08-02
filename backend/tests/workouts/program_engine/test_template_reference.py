from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from workouts.program_engine.golden_fixtures import full_catalog, request


def test_safe_matching_template_becomes_deterministic_program_reference() -> None:
    catalog = full_catalog()
    template = TemplateReference(
        slug="four-day-chest-reference",
        days_per_week=4,
        training_level="intermediate",
        fitness_goal="build_muscle",
        focus_tags=("classic", "chest_priority"),
        intensity_methods=("standard",),
        days=tuple(
            TemplateReferenceDay(
                day_number=index,
                title=title,
                focus=muscles,
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=None,
                        exercise_slug_hint=pattern.value,
                        target_muscles=muscles,
                        movement_pattern=pattern,
                        intensity_method="standard",
                        adaptation_priority="core",
                        superset_group=None,
                        sets=3,
                        rep_min=8,
                        rep_max=12,
                        target_rir=2,
                        rest_seconds=90,
                    ),
                )
                + (
                    (
                        TemplateReferenceSlot(
                            exercise_id=None,
                            exercise_slug_hint="hip_hinge",
                            target_muscles=(MuscleGroup.HAMSTRINGS,),
                            movement_pattern=MovementPattern.HIP_HINGE,
                            intensity_method="standard",
                            adaptation_priority="core",
                            superset_group=None,
                            sets=3,
                            rep_min=8,
                            rep_max=12,
                            target_rir=2,
                            rest_seconds=90,
                        ),
                    )
                    if pattern is MovementPattern.SQUAT
                    else ()
                ),
            )
            for index, (title, muscles, pattern) in enumerate(
                (
                    ("Chest", (MuscleGroup.CHEST,), MovementPattern.HORIZONTAL_PUSH),
                    ("Back", (MuscleGroup.BACK,), MovementPattern.HORIZONTAL_PULL),
                    (
                        "Legs",
                        (MuscleGroup.QUADRICEPS, MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES),
                        MovementPattern.SQUAT,
                    ),
                    ("Core", (MuscleGroup.ABS,), MovementPattern.CORE_ANTI_EXTENSION),
                ),
                start=1,
            )
        ),
    )

    result = generate_program(
        request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=60,
        ),
        catalog,
        RULESET,
        reference_templates=(template,),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics["reference_template"] == template.slug
    assert any(
        entry["stage"] == "template_reference" and entry["selected"] == template.slug
        for entry in result.program.decision_trace
    )
