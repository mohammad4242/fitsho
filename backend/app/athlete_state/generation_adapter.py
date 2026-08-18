from __future__ import annotations

from app.athlete_state.schemas import AthleteState, AthleteStateRecoverySummary
from app.workouts.program_engine.schemas import RecentTrainingHistory
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

        safety_or_unavailable = set(state.pain_sensitive_exercises) | set(
            state.unavailable_exercises
        )
        preference_exercises = (
            set(state.persistent_disliked_exercises) | set(state.uncomfortable_exercises)
        ) - safety_or_unavailable
        recent_training_history = AthleteStateToGenerationOverridesAdapter._recent_history(state)

        return ProgramGenerationOverrides.model_validate(
            {
                **values,
                "disliked_exercises": frozenset(preference_exercises),
                "blocked_exercises": frozenset(safety_or_unavailable),
                "priority_muscles": frozenset(state.priority_muscles),
                "recent_training_history": recent_training_history,
            }
        )

    @staticmethod
    def _recent_history(state: AthleteState) -> RecentTrainingHistory | None:
        adherence_ratio = (
            state.adherence.percent / 100 if state.adherence.percent is not None else None
        )
        has_recovery_signal = (
            state.recovery_trend.summary is not AthleteStateRecoverySummary.UNKNOWN
        )
        if adherence_ratio is None and not has_recovery_signal:
            return None
        return RecentTrainingHistory(
            completed_session_ratio=adherence_ratio or 0.0,
            recovery_problems=state.recovery_trend.summary is AthleteStateRecoverySummary.POOR,
        )
