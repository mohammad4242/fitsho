from dataclasses import replace

from app.exercises.enums import ExerciseLabel, ExerciseType, MovementPattern, MuscleGroup
from app.exercises.free_exercise_db_import import classify_programming_metadata
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from app.workouts.program_engine.session_builder import exercise_fits_focus
from app.workouts.program_engine.slot_compatibility import (
    evaluate_candidate_slot_compatibility,
)
from app.workouts.program_engine.template_sessions import build_template_sessions
from tests.workouts.program_engine.golden_fixtures import exercise, full_catalog, request


def test_full_body_candidate_cannot_fill_specialized_lower_focus() -> None:
    candidate = type("Candidate", (), {})()
    candidate.movement_pattern = MovementPattern.SQUAT
    candidate.primary_muscle = MuscleGroup.QUADRICEPS
    candidate.secondary_muscles = (MuscleGroup.SHOULDERS,)
    candidate.exercise_type = ExerciseType.COMPOUND
    candidate.labels = frozenset({ExerciseLabel.FULL_BODY})

    assert not exercise_fits_focus(candidate, "lower")


def test_valid_lower_compound_remains_compatible_with_specialized_focus() -> None:
    candidate = type("Candidate", (), {})()
    candidate.movement_pattern = MovementPattern.SQUAT
    candidate.primary_muscle = MuscleGroup.QUADRICEPS
    candidate.secondary_muscles = (MuscleGroup.GLUTES,)
    candidate.exercise_type = ExerciseType.COMPOUND
    candidate.labels = frozenset()

    assert exercise_fits_focus(candidate, "lower")


def test_clean_and_press_metadata_is_not_inferred_as_knee_extension() -> None:
    metadata = classify_programming_metadata(
        name_en="Barbell Clean And Press",
        primary_muscle=MuscleGroup.QUADRICEPS,
        instructions_en=(),
        steps_en=(),
        form_cues_en=(),
        common_mistakes_en=(),
    )

    assert metadata.movement_pattern is MovementPattern.VERTICAL_PUSH
    assert metadata.is_full_body


def test_primary_muscle_match_does_not_override_full_body_semantics() -> None:
    candidate = exercise(
        "ambiguous-lower-primary",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
        secondary=(MuscleGroup.SHOULDERS,),
        labels=frozenset({ExerciseLabel.FULL_BODY}),
    )

    result = evaluate_candidate_slot_compatibility(
        candidate,
        allowed_patterns=frozenset({MovementPattern.SQUAT}),
        target_muscles=frozenset({MuscleGroup.QUADRICEPS}),
        day_focus="lower",
    )

    assert not result.compatible
    assert "SLOT_FULL_BODY_INCOMPATIBLE_WITH_SPECIALIZED_FOCUS" in result.reason_codes


def test_compatible_compound_secondary_target_is_allowed_but_isolation_is_not() -> None:
    compound = exercise(
        "compound-lunge",
        MovementPattern.LUNGE,
        MuscleGroup.GLUTES,
        secondary=(MuscleGroup.QUADRICEPS,),
    )
    isolation = exercise(
        "isolation-lunge",
        MovementPattern.LUNGE,
        MuscleGroup.GLUTES,
        secondary=(MuscleGroup.QUADRICEPS,),
        exercise_type=ExerciseType.ISOLATION,
    )

    assert evaluate_candidate_slot_compatibility(
        compound,
        allowed_patterns=frozenset({MovementPattern.LUNGE}),
        target_muscles=frozenset({MuscleGroup.QUADRICEPS}),
        day_focus="lower",
    ).compatible
    assert not evaluate_candidate_slot_compatibility(
        isolation,
        allowed_patterns=frozenset({MovementPattern.LUNGE}),
        target_muscles=frozenset({MuscleGroup.QUADRICEPS}),
        day_focus="lower",
    ).compatible


def test_other_pattern_fails_closed_for_slot_matching() -> None:
    candidate = ExerciseCandidate(
        id=exercise("other", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST).id,
        name="Incomplete",
        primary_muscle=MuscleGroup.QUADRICEPS,
        secondary_muscles=(),
        movement_pattern=MovementPattern.OTHER,
        exercise_type=ExerciseType.OTHER,
        equipment=frozenset(),
        difficulty=exercise(
            "other-difficulty", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST
        ).difficulty,
    )

    result = evaluate_candidate_slot_compatibility(
        candidate,
        allowed_patterns=frozenset({MovementPattern.SQUAT}),
        target_muscles=frozenset({MuscleGroup.QUADRICEPS}),
        day_focus="lower",
    )

    assert not result.compatible
    assert result.reason_codes == ("SLOT_SEMANTIC_METADATA_INCOMPLETE",)


def test_generate_program_does_not_place_semantically_full_body_candidate_in_lower_day() -> None:
    misleading = exercise(
        "catalog-misclassified-clean-press",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
        secondary=(MuscleGroup.SHOULDERS,),
        labels=frozenset({ExerciseLabel.FULL_BODY}),
    )
    source = request(
        available_training_days=4,
        training_experience="advanced",
        training_age_months=72,
        primary_goal=Goal.STRENGTH,
    )

    result = generate_program(source, [misleading, *full_catalog()], RULESET)

    assert result.program is not None, result.errors
    lower_days = [
        day
        for day in result.program.weekly_schedule
        if day.focus in {"lower", "legs"} or day.focus.startswith("lower")
    ]
    assert lower_days
    assert all(
        misleading.id not in {item.exercise_id for item in day.exercises} for day in lower_days
    )


def test_template_substitution_rejects_semantically_incompatible_reference() -> None:
    misleading = exercise(
        "template-misclassified-clean-press",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
        secondary=(MuscleGroup.SHOULDERS,),
        labels=frozenset({ExerciseLabel.FULL_BODY}),
    )
    valid = exercise("template-valid-squat", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS)
    template = TemplateReference(
        slug="semantic-template",
        days_per_week=1,
        training_level="advanced",
        fitness_goal="build_muscle",
        focus_tags=("classic",),
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Lower",
                focus=(MuscleGroup.QUADRICEPS,),
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=misleading.id,
                        exercise_slug_hint=misleading.name,
                        target_muscles=(MuscleGroup.QUADRICEPS,),
                        movement_pattern=MovementPattern.SQUAT,
                        intensity_method="standard",
                        adaptation_priority="core",
                        superset_group=None,
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

    build = build_template_sessions(
        normalize_request(request(training_experience="advanced", training_age_months=72)),
        template,
        tuple([misleading, valid, *full_catalog()]),
        RULESET,
    )

    assert valid.id in {item.id for item in build.drafts[0].exercises}
    assert misleading.id not in {item.id for item in build.drafts[0].exercises}
    assert "TEMPLATE_SLOT_SEMANTIC_MISMATCH" in build.reason_codes


def test_template_substitution_ids_exclude_matching_group_with_incompatible_role() -> None:
    candidates = full_catalog()
    target = next(item for item in candidates if item.name == "Push Up")
    incompatible = replace(
        exercise(
            "template-incompatible-pull",
            MovementPattern.HORIZONTAL_PULL,
            MuscleGroup.CHEST,
        ),
        substitution_group=target.substitution_group,
    )
    template = TemplateReference(
        slug="semantic-substitution-template",
        days_per_week=1,
        training_level="beginner",
        fitness_goal="general_fitness",
        focus_tags=("classic",),
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Push",
                focus=(MuscleGroup.CHEST,),
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=target.id,
                        exercise_slug_hint=target.name,
                        target_muscles=(MuscleGroup.CHEST,),
                        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
                        intensity_method="standard",
                        adaptation_priority="core",
                        superset_group=None,
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

    build = build_template_sessions(
        normalize_request(request(available_training_days=1)),
        template,
        tuple([incompatible, *candidates]),
        RULESET,
    )

    assert incompatible.id not in build.drafts[0].substitutions[target.id]
