from app.workouts.prompt_builder import build_workout_generation_model_request

from .evaluation_fixtures import evaluation_fixtures


def test_evaluation_fixtures_cover_the_supported_training_scenarios() -> None:
    fixtures = evaluation_fixtures()

    assert len(fixtures) == 6
    assert {
        (item.profile.training_location.value, item.profile.training_days_per_week)
        for item in fixtures
    } == {
        ("gym", 3),
        ("home", 3),
        ("gym", 4),
        ("gym", 2),
        ("gym", 5),
    }
    assert {item.profile.session_duration_minutes for item in fixtures} == {30, 45, 60, 75, 90}
    assert any(item.profile.training_cautions for item in fixtures)


def test_evaluation_fixture_request_uses_only_its_deterministic_candidates() -> None:
    fixture = evaluation_fixtures()[0]

    request = build_workout_generation_model_request(
        fixture.profile,
        fixture.candidates,
        fixture.policy,
    )

    allowed = request.input_payload["allowed_exercises"]
    assert isinstance(allowed, list)
    assert len(allowed) == len(fixture.candidates.exercises)
    assert request.input_payload["profile"]["fitness_goal"] == "build_muscle"  # type: ignore[index]
