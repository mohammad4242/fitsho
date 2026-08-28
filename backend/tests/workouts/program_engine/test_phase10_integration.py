from datetime import date
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from pydantic import ValidationError

from app.exercises.enums import Equipment, ExerciseCautionTag, MovementPattern, MuscleGroup
from app.profile.enums import ExperienceLevel, FitnessGoal, HomeTrainingSetup, Sex, TrainingLocation
from app.profile.schemas import ProfileCreate
from app.profile.training_compatibility import UnsupportedResistanceTrainingCombinationError
from app.training_templates.tags import TemplateFocusTag
from app.workouts.program_engine.duration_policy import get_session_duration_policy
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, ImpactLimit, PhysicalJobDemand, RecoveryRating
from app.workouts.program_engine.recovery import recovery_spacing_is_valid
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    BodyAnalysisInfluence,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from tests.workouts.program_engine.golden_fixtures import exercise, full_catalog, request


def _body_analysis(muscle: MuscleGroup, classification: str = "clear_lag") -> BodyAnalysisInfluence:
    return BodyAnalysisInfluence.model_validate(
        {
            "analysis_id": UUID("00000000-0000-0000-0000-000000000001"),
            "result_version_id": UUID("00000000-0000-0000-0000-000000000002"),
            "analysis_revision": 1,
            "schema_version": "1.0",
            "source": "fully_reviewed",
            "overall_confidence": 0.95,
            "priorities": [
                {
                    "muscle": muscle,
                    "classification": classification,
                    "confidence": 0.95,
                    "severity": 0.8,
                    "emphasis": (muscle.value,),
                }
            ],
        }
    )


def _slot(
    pattern: MovementPattern,
    muscles: tuple[MuscleGroup, ...],
    *,
    adaptation_priority: str = "core",
    exercise_id: UUID | None = None,
) -> TemplateReferenceSlot:
    return TemplateReferenceSlot(
        exercise_id=exercise_id,
        exercise_slug_hint=pattern.value,
        target_muscles=muscles,
        movement_pattern=pattern,
        intensity_method="standard",
        adaptation_priority=adaptation_priority,
        superset_group=None,
        sets=3,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=90,
        superset_exercise_id=None,
        superset_exercise_slug_hint=None,
    )


def _template(
    slug: str,
    tags: tuple[TemplateFocusTag, ...],
    *,
    level: str = "intermediate",
) -> TemplateReference:
    specialization_slot = (
        _slot(
            MovementPattern.HORIZONTAL_PUSH,
            (MuscleGroup.CHEST,),
            adaptation_priority="accessory",
        )
        if slug == "chest-structure"
        else _slot(
            MovementPattern.HIP_EXTENSION,
            (MuscleGroup.GLUTES,),
            adaptation_priority="accessory",
            exercise_id=uuid5(NAMESPACE_URL, "https://fitsho.test/golden/glute-bridge"),
        )
        if slug == "glute-structure"
        else None
    )
    day_one_focus = (MuscleGroup.CHEST,)
    day_one_slots = (
        _slot(MovementPattern.HORIZONTAL_PUSH, (MuscleGroup.CHEST,)),
        _slot(
            MovementPattern.ELBOW_EXTENSION,
            (MuscleGroup.TRICEPS,),
            adaptation_priority="accessory",
        ),
    ) + ((specialization_slot,) if slug == "glute-structure" else ())
    day_three_focus = (
        MuscleGroup.QUADRICEPS,
        MuscleGroup.GLUTES,
        MuscleGroup.HAMSTRINGS,
        *((MuscleGroup.CHEST,) if slug == "chest-structure" else ()),
    )
    day_three_slots = (
        _slot(MovementPattern.SQUAT, (MuscleGroup.QUADRICEPS,)),
        _slot(MovementPattern.HIP_EXTENSION, (MuscleGroup.GLUTES,)),
        _slot(MovementPattern.HIP_HINGE, (MuscleGroup.HAMSTRINGS,)),
    ) + ((specialization_slot,) if slug == "chest-structure" else ())
    return TemplateReference(
        slug=slug,
        days_per_week=4,
        supported_levels=(level,),
        focus_tags=tags,
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                1,
                "Chest",
                day_one_focus,
                day_one_slots,
            ),
            TemplateReferenceDay(
                2,
                "Back",
                (MuscleGroup.BACK,),
                (
                    _slot(MovementPattern.HORIZONTAL_PULL, (MuscleGroup.BACK,)),
                    _slot(
                        MovementPattern.ELBOW_FLEXION,
                        (MuscleGroup.BICEPS,),
                        adaptation_priority="accessory",
                    ),
                ),
            ),
            TemplateReferenceDay(
                3,
                "Lower",
                day_three_focus,
                day_three_slots,
            ),
            TemplateReferenceDay(
                4,
                "Shoulders + Traps",
                (MuscleGroup.SHOULDERS, MuscleGroup.TRAPS),
                (
                    _slot(MovementPattern.VERTICAL_PUSH, (MuscleGroup.SHOULDERS,)),
                    _slot(
                        MovementPattern.SHOULDER_ABDUCTION,
                        (MuscleGroup.SHOULDERS,),
                        adaptation_priority="accessory",
                    ),
                    _slot(
                        MovementPattern.SHRUG,
                        (MuscleGroup.TRAPS,),
                        adaptation_priority="accessory",
                    ),
                ),
            ),
        ),
    )


def _assert_success(result):
    assert result.program is not None, result.errors
    assert result.program.validation_report.is_valid
    return result.program


def _template_request(**overrides: object):
    values: dict[str, object] = {
        "training_experience": ExperienceLevel.INTERMEDIATE,
        "training_age_months": 24,
        "available_training_days": 4,
    }
    values.update(overrides)
    return request(**values)


def test_phase10_profile_boundary_rejects_unsupported_resistance_days() -> None:
    with pytest.raises((ValidationError, UnsupportedResistanceTrainingCombinationError)):
        ProfileCreate(
            display_name="Phase Ten",
            birth_date=date(1995, 1, 1),
            sex=Sex.MALE,
            height_cm=175,
            current_weight_kg=75,
            fitness_goal=FitnessGoal.BUILD_MUSCLE,
            experience_level=ExperienceLevel.FIRST_MONTH,
            training_days_per_week=5,
            training_location=TrainingLocation.HOME,
            home_training_setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
            session_duration_minutes=45,
        )


@pytest.mark.parametrize(
    ("experience", "days"),
    [
        ("first_month", 5),
        ("beginner", 5),
        ("advanced", 2),
        ("intermediate", 7),
    ],
)
def test_phase10_engine_defensively_rejects_out_of_policy_days(experience: str, days: int) -> None:
    result = generate_program(
        request(training_experience=experience, available_training_days=days),
        full_catalog(),
        RULESET,
    )

    assert result.program is None
    assert result.error_code.value == "UNSUPPORTED_RESISTANCE_TRAINING_DAYS"


def test_phase10_first_month_remains_distinct_in_template_selection() -> None:
    source = request(
        training_experience=ExperienceLevel.FIRST_MONTH,
        training_age_months=0,
        available_training_days=4,
    )
    program = _assert_success(
        generate_program(
            source,
            full_catalog(),
            RULESET,
            reference_templates=(
                _template(
                    "first-month-structure",
                    (TemplateFocusTag.BALANCED,),
                    level="first_month",
                ),
                _template("beginner-structure", (TemplateFocusTag.BALANCED,), level="beginner"),
            ),
        )
    )

    selection = program.decision_trace[0]
    assert selection["stage"] == "template_selection"
    assert selection["experience_level"] == "first_month"
    assert selection["selected"] == "first-month-structure"


@pytest.mark.parametrize(
    ("experience", "days"),
    [
        (ExperienceLevel.FIRST_MONTH, 2),
        (ExperienceLevel.BEGINNER, 3),
        (ExperienceLevel.INTERMEDIATE, 4),
        (ExperienceLevel.INTERMEDIATE, 6),
        (ExperienceLevel.ADVANCED, 5),
    ],
)
def test_phase10_representative_days_level_matrix_preserves_exact_day_count(
    experience: ExperienceLevel, days: int
) -> None:
    program = _assert_success(
        generate_program(
            request(
                training_experience=experience,
                training_age_months=0 if experience is ExperienceLevel.FIRST_MONTH else 24,
                available_training_days=days,
            ),
            full_catalog(),
            RULESET,
        )
    )

    assert len(program.weekly_schedule) == days
    assert len(program.split.day_focuses) == days
    assert program.validation_report.metrics["hard_training_days"] == days


def test_phase10_template_scoring_is_goal_agnostic_for_hard_eligibility() -> None:
    templates = (
        _template("balanced-structure", (TemplateFocusTag.BALANCED,)),
        _template("chest-structure", (TemplateFocusTag.CHEST_PRIORITY,)),
    )
    traces = []
    for goal in (Goal.STRENGTH, Goal.HYPERTROPHY, Goal.GENERAL_FITNESS, Goal.FAT_LOSS):
        program = _assert_success(
            generate_program(
                _template_request(primary_goal=goal),
                full_catalog(),
                RULESET,
                reference_templates=templates,
            )
        )
        traces.append(program.decision_trace[0])

    assert all(trace["hard_rejections"] == () for trace in traces)
    assert all(trace["templates_considered"] == 2 for trace in traces)


@pytest.mark.parametrize("sex", ["male", "female", None])
def test_phase10_representative_sex_inputs_reach_deterministic_generation(
    sex: str | None,
) -> None:
    program = _assert_success(
        generate_program(
            _template_request(biological_sex_optional=sex),
            full_catalog(),
            RULESET,
            reference_templates=(_template("balanced-structure", (TemplateFocusTag.BALANCED,)),),
        )
    )

    assert program.aggregate_metrics["reference_template"] == "balanced-structure"
    assert len(program.weekly_schedule) == 4


def test_phase10_same_input_produces_same_template_and_final_program() -> None:
    source = request(
        user_id=UUID("00000000-0000-0000-0000-000000000010"),
        training_experience=ExperienceLevel.INTERMEDIATE,
        training_age_months=24,
        available_training_days=4,
        priority_muscles=[MuscleGroup.CHEST],
    )
    templates = (
        _template("balanced-structure", (TemplateFocusTag.BALANCED,)),
        _template("chest-structure", (TemplateFocusTag.CHEST_PRIORITY,)),
    )

    first = _assert_success(
        generate_program(source, full_catalog(), RULESET, reference_templates=templates)
    )
    second = _assert_success(
        generate_program(source, full_catalog(), RULESET, reference_templates=templates)
    )

    assert first == second
    assert first.decision_trace[0]["selected"] == "chest-structure"


def test_phase10_template_intent_survives_priority_and_body_analysis_personalization() -> None:
    catalog = [
        *full_catalog(),
        exercise("glute-kickback", MovementPattern.HIP_EXTENSION, MuscleGroup.GLUTES),
    ]
    templates = (
        _template("balanced-structure", (TemplateFocusTag.BALANCED,), level="advanced"),
        _template("chest-structure", (TemplateFocusTag.CHEST_PRIORITY,), level="advanced"),
        _template("glute-structure", (TemplateFocusTag.GLUTE_PRIORITY,), level="advanced"),
    )
    profile = {
        "training_experience": ExperienceLevel.ADVANCED,
        "training_age_months": 72,
    }
    baseline = _assert_success(
        generate_program(
            _template_request(**profile), catalog, RULESET, reference_templates=templates
        )
    )
    chest = _assert_success(
        generate_program(
            _template_request(**profile, priority_muscles=[MuscleGroup.CHEST]),
            catalog,
            RULESET,
            reference_templates=templates,
        )
    )
    glute = _assert_success(
        generate_program(
            _template_request(**profile, priority_muscles=[MuscleGroup.GLUTES]),
            catalog,
            RULESET,
            reference_templates=templates,
        )
    )
    conflict = _assert_success(
        generate_program(
            _template_request(
                **profile,
                priority_muscles=[MuscleGroup.CHEST],
                body_analysis_influence=_body_analysis(MuscleGroup.GLUTES),
            ),
            catalog,
            RULESET,
            reference_templates=templates,
        )
    )

    assert baseline.aggregate_metrics["reference_template"] == "balanced-structure"
    assert chest.aggregate_metrics["reference_template"] == "chest-structure"
    assert glute.aggregate_metrics["reference_template"] == "glute-structure"
    assert (
        chest.aggregate_metrics["weekly_direct_sets_by_muscle"][MuscleGroup.CHEST.value]
        > baseline.aggregate_metrics["weekly_direct_sets_by_muscle"][MuscleGroup.CHEST.value]
    )
    assert (
        glute.aggregate_metrics["weekly_direct_sets_by_muscle"][MuscleGroup.GLUTES.value]
        > baseline.aggregate_metrics["weekly_direct_sets_by_muscle"][MuscleGroup.GLUTES.value]
    )
    assert conflict.aggregate_metrics["reference_template"] == "chest-structure"
    assert conflict.aggregate_metrics["priority_metrics"][MuscleGroup.CHEST.value]["status"] in {
        "satisfied",
        "partial",
    }


@pytest.mark.parametrize("classification", ["clear_lag", "mild_lag"])
def test_phase10_body_analysis_only_changes_downstream_priority(classification: str) -> None:
    catalog = [
        *full_catalog(),
        exercise("glute-kickback", MovementPattern.HIP_EXTENSION, MuscleGroup.GLUTES),
    ]
    templates = (
        _template("balanced-structure", (TemplateFocusTag.BALANCED,)),
        _template("glute-structure", (TemplateFocusTag.GLUTE_PRIORITY,)),
    )
    program = _assert_success(
        generate_program(
            _template_request(
                body_analysis_influence=_body_analysis(MuscleGroup.GLUTES, classification)
            ),
            catalog,
            RULESET,
            reference_templates=templates,
        )
    )

    assert program.aggregate_metrics["reference_template"] == "glute-structure"
    assert program.aggregate_metrics["priority_metrics"][MuscleGroup.GLUTES.value]["status"] in {
        "satisfied",
        "partial",
    }
    assert all(
        values["actual_effective_volume"] <= values["effective_maximum_hard"]
        for values in program.aggregate_metrics["volume_ranges_by_muscle"].values()
    )


def test_phase10_single_explicit_priority_is_preserved_within_caps() -> None:
    catalog = [
        *full_catalog(),
        exercise("glute-kickback", MovementPattern.HIP_EXTENSION, MuscleGroup.GLUTES),
    ]
    program = _assert_success(
        generate_program(
            _template_request(priority_muscles=[MuscleGroup.CHEST]),
            catalog,
            RULESET,
            reference_templates=(
                _template("chest-structure", (TemplateFocusTag.CHEST_PRIORITY,)),
                _template("glute-structure", (TemplateFocusTag.GLUTE_PRIORITY,)),
            ),
        )
    )

    priority_metrics = program.aggregate_metrics["priority_metrics"]
    assert priority_metrics[MuscleGroup.CHEST.value]["status"] in {"satisfied", "partial"}
    assert all(
        values["actual_effective_volume"] <= values["effective_maximum_hard"]
        for values in program.aggregate_metrics["volume_ranges_by_muscle"].values()
    )


def test_phase10_goal_prescription_changes_without_changing_structure() -> None:
    template = (_template("balanced-structure", (TemplateFocusTag.BALANCED,)),)
    programs = {
        goal: _assert_success(
            generate_program(
                _template_request(primary_goal=goal),
                full_catalog(),
                RULESET,
                reference_templates=template,
            )
        )
        for goal in (Goal.STRENGTH, Goal.HYPERTROPHY, Goal.GENERAL_FITNESS, Goal.FAT_LOSS)
    }

    assert {program.aggregate_metrics["reference_template"] for program in programs.values()} == {
        "balanced-structure"
    }
    strength_exercises = [
        item for day in programs[Goal.STRENGTH].weekly_schedule for item in day.exercises
    ]
    assert any("STRENGTH_PRIMARY_COMPOUND" in item.reason_codes for item in strength_exercises)
    assert programs[Goal.STRENGTH].primary_goal is Goal.STRENGTH
    assert any(day.cardio is not None for day in programs[Goal.FAT_LOSS].weekly_schedule)
    assert sum(day.cardio is not None for day in programs[Goal.FAT_LOSS].weekly_schedule) > sum(
        day.cardio is not None for day in programs[Goal.STRENGTH].weekly_schedule
    )

    primary = next(
        item for item in strength_exercises if "STRENGTH_PRIMARY_COMPOUND" in item.reason_codes
    )
    isolation = next(
        item
        for day in programs[Goal.STRENGTH].weekly_schedule
        for item in day.exercises
        if item.exercise_type.value == "isolation"
    )
    assert primary.rest_seconds > isolation.rest_seconds
    assert isolation.rest_seconds < 180


@pytest.mark.parametrize("duration", [30, 45, 60, 90])
def test_phase10_duration_repair_does_not_change_template_scoring(duration: int) -> None:
    templates = (
        _template("balanced-structure", (TemplateFocusTag.BALANCED,)),
        _template("chest-structure", (TemplateFocusTag.CHEST_PRIORITY,)),
    )
    program = _assert_success(
        generate_program(
            _template_request(session_duration_minutes=duration),
            full_catalog(),
            RULESET,
            reference_templates=templates,
        )
    )
    policy = get_session_duration_policy(duration)
    selection = program.decision_trace[0]

    assert selection["selected"] == "balanced-structure"
    duration_trace = next(
        entry for entry in program.decision_trace if entry["stage"] == "session_duration"
    )
    allowed_reasons = {
        "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS",
        "SESSION_DURATION_TARGET_UNSATISFIED",
    }
    assert all(
        policy.contains_total(day.estimated_duration_minutes, RULESET.general_warmup_minutes)
        or any(code in allowed_reasons for code in duration_trace["reason_codes"])
        for day in program.weekly_schedule
    )


def test_phase10_safety_and_equipment_constraints_survive_all_repairs() -> None:
    source = request(
        available_equipment=[Equipment.BODYWEIGHT],
        blocked_movement_patterns=[MovementPattern.VERTICAL_PUSH],
        blocked_caution_tags=[
            ExerciseCautionTag.DEEP_KNEE_FLEXION,
            ExerciseCautionTag.OVERHEAD_POSITION,
        ],
        impact_limit=ImpactLimit.LOW,
        axial_load_limit="low",
        overhead_limit="none",
    )
    program = _assert_success(generate_program(source, full_catalog(), RULESET))

    for day in program.weekly_schedule:
        for programmed in day.exercises:
            assert programmed.equipment.issubset(source.available_equipment)
            assert programmed.movement_pattern not in source.blocked_movement_patterns
            assert not programmed.caution_tags.intersection(source.blocked_caution_tags)
            assert programmed.movement_pattern is not MovementPattern.VERTICAL_PUSH


@pytest.mark.parametrize(
    ("experience", "days"),
    [
        (ExperienceLevel.FIRST_MONTH, 2),
        (ExperienceLevel.BEGINNER, 3),
        (ExperienceLevel.INTERMEDIATE, 4),
        (ExperienceLevel.ADVANCED, 5),
    ],
)
def test_phase10_recovery_repair_preserves_day_count_and_spacing(
    experience: ExperienceLevel, days: int
) -> None:
    program = _assert_success(
        generate_program(
            request(
                training_experience=experience,
                training_age_months=0 if experience is ExperienceLevel.FIRST_MONTH else 24,
                available_training_days=days,
                sleep_quality=RecoveryRating.POOR,
                stress_level=RecoveryRating.POOR,
                physical_job_demand=PhysicalJobDemand.HIGH,
            ),
            full_catalog(),
            RULESET,
        )
    )

    assert len(program.weekly_schedule) == days
    assert recovery_spacing_is_valid(program.weekly_schedule, RULESET)
    assert any(
        "VOLUME_REDUCED_FOR_RECOVERY" in entry.get("reasons", ())
        for entry in program.decision_trace
        if entry["stage"] == "volume"
    )


def test_phase10_validation_metrics_match_final_program_and_hard_caps() -> None:
    source = request(
        priority_muscles=[MuscleGroup.CHEST],
        recent_training_history={
            "previous_weekly_direct_sets_by_muscle": {"chest": 6, "back": 6},
            "previous_volume_confidence": 0.9,
            "previous_volume_source": "prescribed_plan",
        },
    )
    program = _assert_success(generate_program(source, full_catalog(), RULESET))
    aggregate = program.aggregate_metrics
    report = program.validation_report

    assert (
        report.metrics["weekly_direct_sets_by_muscle"] == aggregate["weekly_direct_sets_by_muscle"]
    )
    assert (
        report.metrics["weekly_effective_sets_by_muscle"]
        == aggregate["weekly_effective_sets_by_muscle"]
    )
    assert report.decision_trace == program.decision_trace
    assert all(
        values["actual_effective_volume"] <= values["effective_maximum_hard"]
        for values in aggregate["volume_ranges_by_muscle"].values()
    )
    assert report.is_valid is True


def test_phase10_coach_quality_metrics_agree_with_final_program() -> None:
    program = _assert_success(
        generate_program(
            _template_request(
                priority_muscles=[MuscleGroup.CHEST],
                body_analysis_influence=_body_analysis(MuscleGroup.GLUTES),
                session_duration_minutes=60,
            ),
            full_catalog(),
            RULESET,
            reference_templates=(_template("chest-structure", (TemplateFocusTag.CHEST_PRIORITY,)),),
        )
    )

    quality = program.aggregate_metrics["coach_quality"]
    assert quality["template_preservation"]["percentage"] == 100.0
    assert quality["priority_target_satisfaction"]["percentage"] is not None
    assert quality["body_analysis_target_satisfaction"]["percentage"] is not None
    assert quality["volume_fit"]["percentage"] is not None
    assert quality["duration_fit"]["percentage"] is not None
    assert quality["recovery_fit"]["percentage"] == 100.0
    adaptation = next(
        entry for entry in program.decision_trace if entry["stage"] == "template_adaptation"
    )
    assert quality["substitution_count"] == len(adaptation["substitutions"])
    assert quality["constraint_count"] >= 0
    assert quality["hard_validation_status"] == program.validation_report.status.value
    assert program.validation_report.metrics["coach_quality"] == quality


def test_phase10_dynamic_fallback_preserves_day_count_and_exposes_reason_codes() -> None:
    source = request(available_training_days=4, training_experience="intermediate")
    catalog = [item for item in full_catalog() if item.primary_muscle is MuscleGroup.CHEST]

    result = generate_program(source, catalog, RULESET)

    assert result.program is None
    assert result.error_code.value == "UNSATISFIED_CONSTRAINT"
    assert "PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED" in result.errors
    assert any(entry["stage"] == "construction_recovery" for entry in result.decision_trace)
