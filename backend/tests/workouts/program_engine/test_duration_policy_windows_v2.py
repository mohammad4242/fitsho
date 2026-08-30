import pytest

from app.workouts.program_engine.duration_policy import get_session_duration_policy


@pytest.mark.parametrize(
    ("requested", "minimum", "maximum", "below", "at_minimum", "at_maximum", "above"),
    [
        (30, 20, 40, 19, 20, 40, 41),
        (45, 35, 55, 34, 35, 55, 56),
        (60, 50, 70, 49, 50, 70, 71),
        (75, 60, 85, 59, 60, 85, 86),
        (90, 65, 100, 64, 65, 100, 101),
    ],
)
def test_official_duration_windows_are_hard_and_exact(
    requested: int,
    minimum: int,
    maximum: int,
    below: int,
    at_minimum: int,
    at_maximum: int,
    above: int,
) -> None:
    policy = get_session_duration_policy(requested)

    assert (policy.minimum_minutes, policy.maximum_minutes) == (minimum, maximum)
    assert not policy.contains(below)
    assert policy.contains(at_minimum)
    assert policy.contains(at_maximum)
    assert not policy.contains(above)


def test_long_session_lower_bounds_widen_without_changing_upper_tolerance() -> None:
    policy_75 = get_session_duration_policy(75)
    policy_90 = get_session_duration_policy(90)

    assert policy_75.minimum_minutes == 60
    assert policy_90.minimum_minutes == 65
    assert policy_75.maximum_minutes - policy_75.requested_minutes == 10
    assert policy_90.maximum_minutes - policy_90.requested_minutes == 10
    assert policy_75.minimum_minutes < 75 - 10
    assert policy_90.minimum_minutes < 90 - 10
