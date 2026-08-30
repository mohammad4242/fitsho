from uuid import UUID, uuid5

import pytest

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
    PrescriptionMode,
)
from app.profile.enums import ExperienceLevel, TrainingLocation
from app.workouts.bodyweight_template_builder import (
    BodyweightTemplateBuildError,
    build_bodyweight_template_program,
)
from app.workouts.bodyweight_templates import get_bodyweight_template
from app.workouts.program_engine.enums import (
    Goal,
    RedFlag,
    SafetyStatus,
    TrainingExperience,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ExerciseCandidate, ProgramGenerationRequest


def _id(slug: str) -> UUID:
    return uuid5(UUID("018f0000-0000-7000-8000-000000000001"), slug)


def _candidate(
    slug: str,
    *,
    muscle: MuscleGroup,
    pattern: MovementPattern,
    exercise_type: ExerciseType = ExerciseType.COMPOUND,
    equipment: frozenset[Equipment] = frozenset({Equipment.BODYWEIGHT}),
    caution_tags: frozenset[ExerciseCautionTag] = frozenset(),
    prescription_mode: PrescriptionMode = PrescriptionMode.REPS,
    duration_min_seconds: int | None = None,
    duration_max_seconds: int | None = None,
) -> ExerciseCandidate:
    return ExerciseCandidate(
        id=_id(slug),
        name=slug,
        primary_muscle=muscle,
        secondary_muscles=(),
        movement_pattern=pattern,
        exercise_type=exercise_type,
        equipment=equipment,
        difficulty=Difficulty.BEGINNER,
        slug=slug,
        caution_tags=caution_tags,
        prescription_mode=prescription_mode,
        duration_min_seconds=duration_min_seconds,
        duration_max_seconds=duration_max_seconds,
    )


def _catalog() -> tuple[ExerciseCandidate, ...]:
    return (
        _candidate(
            "fedb-drv-squat-squat", muscle=MuscleGroup.QUADRICEPS, pattern=MovementPattern.SQUAT
        ),
        _candidate(
            "fedb-0493-incline-push-up",
            muscle=MuscleGroup.CHEST,
            pattern=MovementPattern.HORIZONTAL_PUSH,
        ),
        _candidate(
            "fedb-drv-push-ups-push-up",
            muscle=MuscleGroup.CHEST,
            pattern=MovementPattern.HORIZONTAL_PUSH,
        ),
        _candidate(
            "fedb-0259-close-grip-push-up",
            muscle=MuscleGroup.TRICEPS,
            pattern=MovementPattern.HORIZONTAL_PUSH,
        ),
        _candidate(
            "fedb-0499-inverted-row-between-chairs",
            muscle=MuscleGroup.BACK,
            pattern=MovementPattern.HORIZONTAL_PULL,
        ),
        _candidate(
            "fedb-0651-shoulder-width-pull-up",
            muscle=MuscleGroup.BACK,
            pattern=MovementPattern.VERTICAL_PULL,
            equipment=frozenset({Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR}),
        ),
        _candidate(
            "fedb-2327-reverse-grip-pull-up",
            muscle=MuscleGroup.BACK,
            pattern=MovementPattern.VERTICAL_PULL,
            equipment=frozenset({Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR}),
        ),
        _candidate(
            "fedb-2987-close-grip-chin-up",
            muscle=MuscleGroup.BACK,
            pattern=MovementPattern.VERTICAL_PULL,
            equipment=frozenset({Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR}),
        ),
        _candidate(
            "fedb-1429-pull-up-wide-grip",
            muscle=MuscleGroup.BACK,
            pattern=MovementPattern.VERTICAL_PULL,
            equipment=frozenset({Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR}),
        ),
        _candidate(
            "fedb-0668-rear-decline-bridge",
            muscle=MuscleGroup.GLUTES,
            pattern=MovementPattern.HIP_EXTENSION,
        ),
        _candidate(
            "fedb-0464-front-plank",
            muscle=MuscleGroup.ABS,
            pattern=MovementPattern.CORE_ANTI_EXTENSION,
            exercise_type=ExerciseType.CORE,
            prescription_mode=PrescriptionMode.DURATION,
            duration_min_seconds=20,
            duration_max_seconds=40,
        ),
        _candidate(
            "fedb-0705-side-plank",
            muscle=MuscleGroup.OBLIQUES,
            pattern=MovementPattern.CORE_ANTI_LATERAL_FLEXION,
            exercise_type=ExerciseType.CORE,
            prescription_mode=PrescriptionMode.DURATION,
            duration_min_seconds=20,
            duration_max_seconds=40,
        ),
        _candidate(
            "fedb-0872-reverse-crunch",
            muscle=MuscleGroup.ABS,
            pattern=MovementPattern.SPINAL_FLEXION,
            exercise_type=ExerciseType.CORE,
        ),
    )


def _request(
    *,
    experience: TrainingExperience = TrainingExperience.FIRST_MONTH,
    days: int = 2,
    equipment: frozenset[Equipment] = frozenset({Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR}),
    blocked_caution_tags: frozenset[ExerciseCautionTag] = frozenset(),
    red_flags: tuple[RedFlag, ...] = (),
) -> ProgramGenerationRequest:
    return ProgramGenerationRequest(
        user_id=_id("user"),
        age=30,
        height_cm=180,
        weight_kg=75,
        primary_goal=Goal.MUSCLE_GAIN,
        training_experience=experience,
        training_age_months=0,
        available_training_days=days,
        session_duration_minutes=120,
        available_equipment=equipment,
        training_location=TrainingLocation.HOME,
        blocked_caution_tags=blocked_caution_tags,
        current_pain_or_red_flags=red_flags,
    )


def test_builds_fixed_first_month_program_without_dynamic_construction() -> None:
    template = get_bodyweight_template(ExperienceLevel.FIRST_MONTH, 2)
    assert template is not None

    program = build_bodyweight_template_program(
        request=_request(),
        experience_level=ExperienceLevel.FIRST_MONTH,
        template=template,
        exercise_catalog=_catalog(),
        ruleset=RULESET,
    )

    assert program.engine_version == "bodyweight_template_v1"
    assert len(program.weekly_schedule) == 2
    assert program.validation_report.errors == ()
    assert program.validation_report.metrics["template_slug"] == template.slug


def test_builds_fixed_beginner_program_with_exact_order_and_no_substitutions() -> None:
    template = get_bodyweight_template(ExperienceLevel.BEGINNER, 3)
    assert template is not None

    program = build_bodyweight_template_program(
        request=_request(experience=TrainingExperience.BEGINNER, days=3),
        experience_level=ExperienceLevel.BEGINNER,
        template=template,
        exercise_catalog=_catalog(),
        ruleset=RULESET,
    )

    for output_day, template_day in zip(program.weekly_schedule, template.days, strict=True):
        assert [item.exercise_slug for item in output_day.exercises] == [
            item.exercise_slug for item in template_day.exercises
        ]
        assert all(item.substitution_exercise_ids == () for item in output_day.exercises)


def test_front_and_side_planks_persist_as_duration_prescriptions() -> None:
    template = get_bodyweight_template(ExperienceLevel.FIRST_MONTH, 2)
    assert template is not None
    program = build_bodyweight_template_program(
        request=_request(),
        experience_level=ExperienceLevel.FIRST_MONTH,
        template=template,
        exercise_catalog=_catalog(),
        ruleset=RULESET,
    )

    exercises = [item for day in program.weekly_schedule for item in day.exercises]
    for slug in ("fedb-0464-front-plank", "fedb-0705-side-plank"):
        plank = next(item for item in exercises if item.exercise_slug == slug)
        assert plank.prescription_mode is PrescriptionMode.DURATION
        assert plank.rep_min is None
        assert plank.rep_max is None
        assert plank.target_rir is None
        assert plank.duration_min_seconds is not None
        assert plank.duration_max_seconds is not None


def test_larger_requested_session_duration_does_not_append_exercises_or_fail() -> None:
    template = get_bodyweight_template(ExperienceLevel.FIRST_MONTH, 2)
    assert template is not None
    program = build_bodyweight_template_program(
        request=_request(),
        experience_level=ExperienceLevel.FIRST_MONTH,
        template=template,
        exercise_catalog=_catalog(),
        ruleset=RULESET,
    )

    assert all(day.estimated_duration_minutes < 120 for day in program.weekly_schedule)
    assert [len(day.exercises) for day in program.weekly_schedule] == [5, 5]


def test_safety_rejection_prevents_fixed_template_output() -> None:
    template = get_bodyweight_template(ExperienceLevel.FIRST_MONTH, 2)
    assert template is not None

    with pytest.raises(BodyweightTemplateBuildError) as error:
        build_bodyweight_template_program(
            request=_request(red_flags=(RedFlag.CHEST_PAIN,)),
            experience_level=ExperienceLevel.FIRST_MONTH,
            template=template,
            exercise_catalog=_catalog(),
            ruleset=RULESET,
        )

    assert error.value.code == "PROGRAM_REJECTED_SAFETY_STATUS"
    assert error.value.safety_status is SafetyStatus.STOP_AND_REFER


def test_blocked_template_exercise_rejects_without_substitution() -> None:
    template = get_bodyweight_template(ExperienceLevel.FIRST_MONTH, 2)
    assert template is not None

    with pytest.raises(BodyweightTemplateBuildError) as error:
        build_bodyweight_template_program(
            request=_request(blocked_caution_tags=frozenset({ExerciseCautionTag.WRIST_LOADING})),
            experience_level=ExperienceLevel.FIRST_MONTH,
            template=template,
            exercise_catalog=_catalog(),
            ruleset=RULESET,
        )

    assert error.value.code == "BODYWEIGHT_TEMPLATE_EXERCISE_UNAVAILABLE"
    assert error.value.exercise_slug == "fedb-0493-incline-push-up"
    assert "EXERCISE_REJECTED_BLOCKED_CAUTION_TAG" in error.value.rejection_reason_codes


def test_missing_pull_up_bar_has_actionable_error() -> None:
    template = get_bodyweight_template(ExperienceLevel.BEGINNER, 2)
    assert template is not None

    with pytest.raises(BodyweightTemplateBuildError) as error:
        build_bodyweight_template_program(
            request=_request(
                experience=TrainingExperience.BEGINNER,
                equipment=frozenset({Equipment.BODYWEIGHT}),
            ),
            experience_level=ExperienceLevel.BEGINNER,
            template=template,
            exercise_catalog=_catalog(),
            ruleset=RULESET,
        )

    assert error.value.code == "BODYWEIGHT_PULL_UP_BAR_REQUIRED"
    assert error.value.exercise_slug == "fedb-0651-shoulder-width-pull-up"
    assert "EXERCISE_REJECTED_MISSING_EQUIPMENT" in error.value.rejection_reason_codes
