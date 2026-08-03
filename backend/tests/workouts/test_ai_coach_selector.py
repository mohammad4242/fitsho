from uuid import uuid4

from app.exercises.enums import MovementPattern, MuscleGroup
from app.profile.enums import ExperienceLevel, FitnessGoal, HomeTrainingSetup, TrainingLocation
from app.workouts.ai_coach import (
    AiCoachProgramCandidate,
    candidate_program_payload,
    select_ai_coach_candidates,
)
from app.workouts.program_engine.schemas import (
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from app.workouts.schemas import WorkoutGenerationProfile


def _template(
    slug: str,
    *,
    focus: tuple[str, ...],
    exercise_id: object,
    days_per_week: int = 3,
    training_level: str = "beginner",
    fitness_goal: str = "build_muscle",
) -> TemplateReference:
    return TemplateReference(
        slug=slug,
        days_per_week=days_per_week,
        training_level=training_level,
        fitness_goal=fitness_goal,
        focus_tags=focus,
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Full body",
                focus=(MuscleGroup.CHEST,),
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=exercise_id,
                        exercise_slug_hint="push-up",
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


def _profile() -> WorkoutGenerationProfile:
    return WorkoutGenerationProfile(
        fitness_goal=FitnessGoal.BUILD_MUSCLE,
        experience_level=ExperienceLevel.BEGINNER,
        training_days_per_week=3,
        training_location=TrainingLocation.HOME,
        home_training_setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
        session_duration_minutes=45,
        plan_duration_weeks=4,
        training_cautions=(),
        physical_limitations=None,
        current_weight_kg=75,
    )


def test_ai_coach_selects_distinct_eligible_library_programs_in_priority_order() -> None:
    eligible_exercise = uuid4()
    unavailable_exercise = uuid4()

    candidates = select_ai_coach_candidates(
        templates=(
            _template("balanced", focus=("general",), exercise_id=eligible_exercise),
            _template("chest-focus", focus=("chest",), exercise_id=eligible_exercise),
            _template("unavailable", focus=("chest",), exercise_id=unavailable_exercise),
        ),
        profile=_profile(),
        eligible_exercise_ids=frozenset({eligible_exercise}),
        priority_muscles=(MuscleGroup.CHEST,),
    )

    assert [candidate.template.slug for candidate in candidates] == ["chest-focus", "balanced"]


def test_ai_coach_candidate_payload_contains_fixed_library_exercises_only() -> None:
    exercise_id = uuid4()
    candidate = AiCoachProgramCandidate(
        template=_template("fixed-library-plan", focus=("chest",), exercise_id=exercise_id),
        score=110,
    )

    payload = candidate_program_payload(
        candidate,
        exercise_names_fa={exercise_id: "شنا سوئدی"},
    )

    assert payload == {
        "candidate_id": "fixed-library-plan",
        "days": [
            {
                "day_number": 1,
                "title": "Full body",
                "title_fa": "Full body",
                "exercise_names_fa": ["شنا سوئدی"],
            }
        ],
    }
