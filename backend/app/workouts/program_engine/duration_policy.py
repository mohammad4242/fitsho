from dataclasses import dataclass

SESSION_DURATION_TOLERANCE_MINUTES = 10


@dataclass(frozen=True)
class SessionDurationPolicy:
    requested_minutes: int
    minimum_minutes: int
    maximum_minutes: int

    def contains(self, estimated_minutes: int) -> bool:
        return self.minimum_minutes <= estimated_minutes <= self.maximum_minutes


def get_session_duration_policy(
    requested_minutes: int,
) -> SessionDurationPolicy:
    tolerance = SESSION_DURATION_TOLERANCE_MINUTES
    return SessionDurationPolicy(
        requested_minutes=requested_minutes,
        minimum_minutes=requested_minutes - tolerance,
        maximum_minutes=requested_minutes + tolerance,
    )
