import pytest

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import full_catalog
from tests.workouts.program_engine.test_template_reference import template_request


@pytest.fixture(scope="module")
def catalog():
    return full_catalog()


# Combinations to test:
# Experience: beginner, intermediate, advanced
# Days: 2, 3, 4, 5, 6
# Durations: 30, 45, 60, 75, 90


def make_request(
    days: int, duration: int, exp: str, goal: str, priorities: list[MuscleGroup] | None = None
):
    age_map = {
        "beginner": 3,
        "intermediate": 24,
        "advanced": 60,
    }

    return template_request(
        available_training_days=days,
        primary_goal=goal.lower(),
        training_experience=exp,
        training_age_months=age_map[exp],
        session_duration_minutes=duration,
        priority_muscles=priorities or [],
    )


def test_set_allocation_invariants(catalog):
    # Select a broad subset of combinations to keep test time reasonable,
    # but still cover all the extremes.

    combinations = [
        # Beginner short bodyweight
        (2, 30, "beginner", "muscle_gain"),
        # Intermediate standard dumbbells
        (4, 60, "intermediate", "body_recomposition"),
        # Advanced long gym strength
        (5, 90, "advanced", "strength"),
        # Max frequency short gym
        (6, 45, "intermediate", "fat_loss"),
        # Mid frequency long bodyweight
        (3, 75, "beginner", "muscle_gain"),
    ]

    for days, duration, exp, goal in combinations:
        request = make_request(
            days,
            duration,
            exp,
            goal,
            priorities=[MuscleGroup.CHEST, MuscleGroup.BACK],
        )
        result = generate_program(request, catalog, RULESET, reference_templates=())
        assert result.program is not None, (
            f"Failed to generate program for {days}d {duration}m {exp} {goal}: {result.errors}"
        )

        for day in result.program.weekly_schedule:
            for ex in day.exercises:
                assert ex.sets in {3, 4}, (
                    f"Exercise {ex.exercise_name} has {ex.sets} sets (must be 3 or 4)"
                )
