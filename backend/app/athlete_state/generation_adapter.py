from __future__ import annotations

from app.athlete_state.schemas import AthleteState
from app.workouts.schemas import ProgramGenerationOverrides


class AthleteStateToGenerationOverridesAdapter:
    """Convert only direct AthleteState inputs into generation overrides."""

    @staticmethod
    def to_overrides(state: AthleteState) -> ProgramGenerationOverrides:
        values: dict[str, int] = {}
        if state.schedule.next_training_days is not None:
            values["available_training_days"] = state.schedule.next_training_days
        if state.schedule.next_session_duration_minutes is not None:
            values["session_duration_minutes"] = state.schedule.next_session_duration_minutes
        return ProgramGenerationOverrides.model_validate(values)
