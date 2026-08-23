from dataclasses import dataclass

SESSION_DURATION_TOLERANCE_MINUTES = 10
CORE_PRESERVATION_EXTENSION_MINUTES = 20


@dataclass(frozen=True)
class SessionDurationPolicy:
    requested_minutes: int
    minimum_minutes: int
    maximum_minutes: int

    def contains(self, estimated_minutes: int) -> bool:
        return self.minimum_minutes <= estimated_minutes <= self.maximum_minutes

    @property
    def core_preservation_maximum_minutes(self) -> int:
        return self.requested_minutes + CORE_PRESERVATION_EXTENSION_MINUTES

    def workout_minutes(self, estimated_total_minutes: int, general_warmup_minutes: int) -> int:
        return max(0, estimated_total_minutes - general_warmup_minutes)

    def contains_total(self, estimated_total_minutes: int, general_warmup_minutes: int) -> bool:
        return self.contains(self.workout_minutes(estimated_total_minutes, general_warmup_minutes))

    def minimum_total_minutes(self, general_warmup_minutes: int) -> int:
        return self.minimum_minutes + general_warmup_minutes

    def maximum_total_minutes(self, general_warmup_minutes: int) -> int:
        return self.maximum_minutes + general_warmup_minutes

    def core_preservation_maximum_total_minutes(self, general_warmup_minutes: int) -> int:
        return self.core_preservation_maximum_minutes + general_warmup_minutes


def get_session_duration_policy(
    requested_minutes: int,
) -> SessionDurationPolicy:
    tolerance = SESSION_DURATION_TOLERANCE_MINUTES
    return SessionDurationPolicy(
        requested_minutes=requested_minutes,
        minimum_minutes=requested_minutes - tolerance,
        maximum_minutes=requested_minutes + tolerance,
    )
