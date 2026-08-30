from dataclasses import replace

import pytest

from app.profile.enums import ExperienceLevel
from app.workouts.bodyweight_templates import (
    BODYWEIGHT_TEMPLATE_LIBRARY,
    BODYWEIGHT_TEMPLATE_LIBRARY_VERSION,
    bodyweight_template_fingerprint,
    get_bodyweight_template,
)
from app.workouts.program_engine.enums import SplitType

EXPECTED_KEYS = {
    (ExperienceLevel.FIRST_MONTH, 2): "bw-first-month-2d-v1",
    (ExperienceLevel.FIRST_MONTH, 3): "bw-first-month-3d-v1",
    (ExperienceLevel.FIRST_MONTH, 4): "bw-first-month-4d-v1",
    (ExperienceLevel.BEGINNER, 2): "bw-beginner-2d-v1",
    (ExperienceLevel.BEGINNER, 3): "bw-beginner-3d-v1",
    (ExperienceLevel.BEGINNER, 4): "bw-beginner-4d-v1",
}


def _exercise_signature(exercise: object) -> tuple[object, ...]:
    return (
        exercise.exercise_slug,
        exercise.sets,
        exercise.rep_min,
        exercise.rep_max,
        exercise.target_rir,
        exercise.duration_min_seconds,
        exercise.duration_max_seconds,
        exercise.rest_seconds,
    )


def test_bodyweight_library_contains_exactly_the_six_supported_templates() -> None:
    assert BODYWEIGHT_TEMPLATE_LIBRARY_VERSION == "bodyweight_templates_v1"
    assert len(BODYWEIGHT_TEMPLATE_LIBRARY) == 6
    assert {
        (template.experience_level, template.days_per_week): template.slug
        for template in BODYWEIGHT_TEMPLATE_LIBRARY
    } == EXPECTED_KEYS

    for (level, days), slug in EXPECTED_KEYS.items():
        template = get_bodyweight_template(level, days)
        assert template is not None
        assert template.slug == slug
        assert len(template.days) == days
        assert template.days_per_week == days


def test_first_month_templates_have_exact_exercises_and_prescriptions() -> None:
    expected = {
        2: [
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, None, 75),
                ("fedb-0493-incline-push-up", 2, 8, 12, 4, None, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 10, 15, 4, None, None, 60),
                ("fedb-0464-front-plank", 2, None, None, None, 20, 30, 45),
            ],
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, None, 75),
                ("fedb-drv-push-ups-push-up", 2, 6, 10, 4, None, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 10, 15, 4, None, None, 60),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 30, 45),
            ],
        ],
        3: [
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, None, 75),
                ("fedb-0493-incline-push-up", 2, 8, 12, 4, None, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 10, 15, 4, None, None, 60),
                ("fedb-0464-front-plank", 2, None, None, None, 20, 30, 45),
            ],
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, None, 75),
                ("fedb-drv-push-ups-push-up", 2, 6, 10, 4, None, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 10, 15, 4, None, None, 60),
                ("fedb-0872-reverse-crunch", 2, 10, 15, 4, None, None, 45),
            ],
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, None, 75),
                ("fedb-0493-incline-push-up", 2, 8, 12, 4, None, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 10, 15, 4, None, None, 60),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 30, 45),
            ],
        ],
        4: [
            [
                ("fedb-0493-incline-push-up", 2, 8, 12, 4, None, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, None, 75),
                ("fedb-0259-close-grip-push-up", 2, 6, 10, 4, None, None, 60),
                ("fedb-0464-front-plank", 2, None, None, None, 20, 30, 45),
            ],
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 10, 15, 4, None, None, 60),
                ("fedb-0872-reverse-crunch", 2, 10, 15, 4, None, None, 45),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 30, 45),
            ],
            [
                ("fedb-drv-push-ups-push-up", 2, 6, 10, 4, None, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, None, 75),
                ("fedb-0259-close-grip-push-up", 2, 6, 10, 4, None, None, 60),
                ("fedb-0464-front-plank", 2, None, None, None, 20, 30, 45),
            ],
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 12, 15, 4, None, None, 60),
                ("fedb-0872-reverse-crunch", 2, 10, 15, 4, None, None, 45),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 30, 45),
            ],
        ],
    }

    for days, expected_days in expected.items():
        template = get_bodyweight_template(ExperienceLevel.FIRST_MONTH, days)
        assert template is not None
        assert [
            [_exercise_signature(exercise) for exercise in day.exercises] for day in template.days
        ] == expected_days


def test_beginner_templates_have_exact_exercises_and_prescriptions() -> None:
    expected = {
        2: [
            [
                ("fedb-drv-squat-squat", 3, 10, 15, 3, None, None, 75),
                ("fedb-drv-push-ups-push-up", 3, 6, 12, 3, None, None, 75),
                ("fedb-0651-shoulder-width-pull-up", 3, 3, 8, 3, None, None, 90),
                ("fedb-0668-rear-decline-bridge", 3, 10, 15, 3, None, None, 75),
                ("fedb-0464-front-plank", 2, None, None, None, 25, 40, 45),
            ],
            [
                ("fedb-drv-squat-squat", 3, 10, 15, 3, None, None, 75),
                ("fedb-0259-close-grip-push-up", 2, 6, 12, 3, None, None, 75),
                ("fedb-2327-reverse-grip-pull-up", 3, 3, 8, 3, None, None, 90),
                ("fedb-0668-rear-decline-bridge", 3, 10, 15, 3, None, None, 75),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 30, 45),
            ],
        ],
        3: [
            [
                ("fedb-drv-squat-squat", 3, 10, 15, 3, None, None, 75),
                ("fedb-drv-push-ups-push-up", 3, 6, 12, 3, None, None, 75),
                ("fedb-0651-shoulder-width-pull-up", 3, 3, 8, 3, None, None, 90),
                ("fedb-0668-rear-decline-bridge", 3, 10, 15, 3, None, None, 75),
                ("fedb-0464-front-plank", 2, None, None, None, 25, 40, 45),
            ],
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 3, None, None, 75),
                ("fedb-0493-incline-push-up", 2, 10, 15, 3, None, None, 60),
                ("fedb-2987-close-grip-chin-up", 2, 3, 8, 3, None, None, 90),
                ("fedb-0668-rear-decline-bridge", 2, 12, 15, 3, None, None, 60),
                ("fedb-0872-reverse-crunch", 2, 10, 15, 3, None, None, 45),
            ],
            [
                ("fedb-drv-squat-squat", 3, 10, 15, 3, None, None, 75),
                ("fedb-0259-close-grip-push-up", 3, 6, 12, 3, None, None, 75),
                ("fedb-2327-reverse-grip-pull-up", 3, 3, 8, 3, None, None, 90),
                ("fedb-0668-rear-decline-bridge", 3, 10, 15, 3, None, None, 75),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 30, 45),
            ],
        ],
        4: [
            [
                ("fedb-drv-push-ups-push-up", 3, 6, 12, 3, None, None, 75),
                ("fedb-0651-shoulder-width-pull-up", 3, 3, 8, 3, None, None, 90),
                ("fedb-0259-close-grip-push-up", 2, 6, 12, 3, None, None, 75),
                ("fedb-2987-close-grip-chin-up", 2, 3, 8, 3, None, None, 90),
                ("fedb-0464-front-plank", 2, None, None, None, 30, 40, 45),
            ],
            [
                ("fedb-drv-squat-squat", 3, 10, 15, 3, None, None, 75),
                ("fedb-0668-rear-decline-bridge", 3, 10, 15, 3, None, None, 75),
                ("fedb-0872-reverse-crunch", 2, 10, 15, 3, None, None, 45),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 30, 45),
            ],
            [
                ("fedb-0493-incline-push-up", 3, 8, 15, 3, None, None, 75),
                ("fedb-2327-reverse-grip-pull-up", 3, 3, 8, 3, None, None, 90),
                ("fedb-drv-push-ups-push-up", 2, 6, 12, 3, None, None, 75),
                ("fedb-1429-pull-up-wide-grip", 2, 3, 6, 3, None, None, 90),
                ("fedb-0464-front-plank", 2, None, None, None, 30, 40, 45),
            ],
            [
                ("fedb-drv-squat-squat", 3, 10, 15, 3, None, None, 75),
                ("fedb-0668-rear-decline-bridge", 3, 12, 15, 3, None, None, 75),
                ("fedb-0872-reverse-crunch", 2, 10, 15, 3, None, None, 45),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 30, 45),
            ],
        ],
    }

    for days, expected_days in expected.items():
        template = get_bodyweight_template(ExperienceLevel.BEGINNER, days)
        assert template is not None
        assert [
            [_exercise_signature(exercise) for exercise in day.exercises] for day in template.days
        ] == expected_days


def test_duration_and_rep_slots_have_exclusive_prescription_fields() -> None:
    for template in BODYWEIGHT_TEMPLATE_LIBRARY:
        for day in template.days:
            for exercise in day.exercises:
                if exercise.duration_min_seconds is None:
                    assert exercise.rep_min is not None
                    assert exercise.rep_max is not None
                    assert exercise.target_rir is not None
                else:
                    assert exercise.rep_min is None
                    assert exercise.rep_max is None
                    assert exercise.target_rir is None


def test_template_fingerprint_is_deterministic_and_changes_with_prescription() -> None:
    template = get_bodyweight_template(ExperienceLevel.BEGINNER, 2)
    assert template is not None
    assert bodyweight_template_fingerprint(template) == bodyweight_template_fingerprint(template)

    first_day = template.days[0]
    first_exercise = first_day.exercises[0]
    changed = replace(
        template,
        days=(
            replace(
                first_day,
                exercises=(
                    replace(first_exercise, sets=first_exercise.sets + 1),
                    *first_day.exercises[1:],
                ),
            ),
            *template.days[1:],
        ),
    )
    assert bodyweight_template_fingerprint(changed) != bodyweight_template_fingerprint(template)


def test_template_lookup_is_deterministic_and_has_no_random_selection() -> None:
    observed = [get_bodyweight_template(ExperienceLevel.BEGINNER, 3).slug for _ in range(20)]

    assert observed == ["bw-beginner-3d-v1"] * 20


@pytest.mark.parametrize(
    ("level", "days"),
    [
        (ExperienceLevel.INTERMEDIATE, 2),
        (ExperienceLevel.BEGINNER, 1),
        (ExperienceLevel.BEGINNER, 5),
    ],
)
def test_unsupported_bodyweight_template_returns_none(level: ExperienceLevel, days: int) -> None:
    assert get_bodyweight_template(level, days) is None


def test_template_split_types_are_fixed_by_day_count() -> None:
    for days in (2, 3):
        for level in (ExperienceLevel.FIRST_MONTH, ExperienceLevel.BEGINNER):
            template = get_bodyweight_template(level, days)
            assert template is not None
            assert template.split_type is SplitType.FULL_BODY
    for level in (ExperienceLevel.FIRST_MONTH, ExperienceLevel.BEGINNER):
        template = get_bodyweight_template(level, 4)
        assert template is not None
        assert template.split_type is SplitType.UPPER_LOWER
