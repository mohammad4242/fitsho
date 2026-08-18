from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.athlete_state.schemas import (
    AthleteState,
    AthleteStateAdherence,
    AthleteStateBodyProgress,
    AthleteStateDifficultyTrend,
    AthleteStateExerciseContext,
    AthleteStateProvenance,
    AthleteStateRecoveryTrend,
    AthleteStateScheduleContext,
    AthleteStateTrendDirection,
)
from app.body_analysis.enums import BodyArea
from app.exercises.enums import MuscleGroup
from app.profile.models import UserProfile
from app.workout_cycles.body_progress_models import WorkoutCycleBodyProgressComparison
from app.workout_cycles.body_progress_schemas import CycleBodyProgressComparisonResult
from app.workout_cycles.enums import (
    WorkoutExercisePreferenceType,
)
from app.workout_cycles.models import (
    WorkoutCycle,
    WorkoutCycleFeedback,
    WorkoutCycleWeeklyCheckIn,
    WorkoutExercisePreference,
    WorkoutExerciseReplacement,
    WorkoutExerciseSafetySignal,
)
from app.workouts.models import WorkoutPlan


class AthleteStateNotFoundError(LookupError):
    pass


class AthleteStateBuilder:
    """Build a deterministic, read-only coaching snapshot from owned source records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def build(self, user_id: UUID, *, cycle_id: UUID | None = None) -> AthleteState:
        cycles = self._owned_cycles(user_id)
        current: WorkoutCycle | None
        if cycle_id is not None:
            requested = next((cycle for cycle in cycles if cycle.id == cycle_id), None)
            if requested is None:
                raise AthleteStateNotFoundError
            current = requested
        else:
            current = next(
                (cycle for cycle in cycles if cycle.status.value == "active"),
                cycles[0] if cycles else None,
            )
        selected_cycles = self._selected_cycles(cycles, current)
        cycle_ids = tuple(cycle.id for cycle in selected_cycles)

        check_ins = self._check_ins(user_id, cycle_ids)
        feedbacks = self._feedbacks(user_id, cycle_ids)
        preferences = self._preferences(user_id)
        safety_signals = self._safety_signals(user_id)
        replacements = self._replacements(user_id)
        comparisons = self._comparisons(user_id, cycle_ids)
        profile = self._profile(user_id)
        plans = self._plans(user_id)

        return AthleteState(
            user_id=user_id,
            current_cycle_id=current.id if current else None,
            previous_cycle_ids=tuple(
                cycle.id for cycle in selected_cycles if not current or cycle.id != current.id
            ),
            adherence=self._adherence(check_ins, selected_cycles),
            recovery_trend=self._recovery_trend(check_ins),
            difficulty_trend=self._difficulty_trend(check_ins),
            persistent_disliked_exercises=self._preference_exercise_ids(
                preferences, WorkoutExercisePreferenceType.DISLIKE
            ),
            uncomfortable_exercises=self._preference_exercise_ids(
                preferences, WorkoutExercisePreferenceType.UNCOMFORTABLE
            ),
            unavailable_exercises=self._preference_exercise_ids(
                preferences, WorkoutExercisePreferenceType.EQUIPMENT_UNAVAILABLE
            ),
            unavailable_equipment_context=self._equipment_context(preferences),
            pain_sensitive_exercises=self._unique_ids(
                signal.original_exercise_id for signal in safety_signals
            ),
            priority_muscles=self._feedback_muscles(feedbacks, "lagging_muscles"),
            progressing_muscles=self._feedback_muscles(feedbacks, "progressed_muscles"),
            lagging_muscles=self._feedback_muscles(feedbacks, "lagging_muscles"),
            schedule=self._schedule(profile, feedbacks),
            body_progress=self._body_progress(comparisons),
            provenance=AthleteStateProvenance(
                profile_user_id=profile.user_id if profile else None,
                cycle_ids=cycle_ids,
                weekly_check_in_ids=tuple(check_in.id for check_in in check_ins),
                end_feedback_ids=tuple(feedback.id for feedback in feedbacks),
                replacement_ids=tuple(replacement.id for replacement in replacements),
                preference_ids=tuple(preference.id for preference in preferences),
                preference_source_replacement_ids=self._unique_ids(
                    preference.source_replacement_id for preference in preferences
                ),
                safety_signal_ids=tuple(signal.id for signal in safety_signals),
                body_progress_comparison_ids=tuple(
                    comparison.id for comparison in comparisons
                ),
                body_measurement_ids=self._comparison_source_ids(
                    comparisons, "start_measurement_id", "end_measurement_id"
                ),
                body_analysis_ids=self._comparison_source_ids(
                    comparisons, "start_analysis_id", "end_analysis_id"
                ),
                workout_plan_ids=tuple(plan.id for plan in plans),
            ),
        )

    def _owned_cycles(self, user_id: UUID) -> list[WorkoutCycle]:
        return list(
            self._db.scalars(
                select(WorkoutCycle)
                .options(selectinload(WorkoutCycle.workout_plan).selectinload(WorkoutPlan.days))
                .where(WorkoutCycle.user_id == user_id)
                .order_by(WorkoutCycle.started_at.desc(), WorkoutCycle.id.desc())
            ).all()
        )

    @staticmethod
    def _selected_cycles(
        cycles: list[WorkoutCycle],
        current: WorkoutCycle | None,
    ) -> list[WorkoutCycle]:
        if current is None:
            return []
        previous = next(
            (
                cycle
                for cycle in cycles
                if cycle.id != current.id and cycle.status.value == "completed"
            ),
            None,
        )
        return [current, previous] if previous is not None else [current]

    def _check_ins(
        self,
        user_id: UUID,
        cycle_ids: tuple[UUID, ...],
    ) -> list[WorkoutCycleWeeklyCheckIn]:
        if not cycle_ids:
            return []
        return list(
            self._db.scalars(
                select(WorkoutCycleWeeklyCheckIn)
                .join(WorkoutCycle, WorkoutCycle.id == WorkoutCycleWeeklyCheckIn.cycle_id)
                .where(
                    WorkoutCycleWeeklyCheckIn.user_id == user_id,
                    WorkoutCycleWeeklyCheckIn.cycle_id.in_(cycle_ids),
                )
                .order_by(
                    WorkoutCycle.started_at,
                    WorkoutCycleWeeklyCheckIn.week_number,
                    WorkoutCycleWeeklyCheckIn.submitted_at,
                    WorkoutCycleWeeklyCheckIn.id,
                )
            ).all()
        )

    def _feedbacks(
        self,
        user_id: UUID,
        cycle_ids: tuple[UUID, ...],
    ) -> list[WorkoutCycleFeedback]:
        if not cycle_ids:
            return []
        return list(
            self._db.scalars(
                select(WorkoutCycleFeedback)
                .join(WorkoutCycle, WorkoutCycle.id == WorkoutCycleFeedback.cycle_id)
                .where(
                    WorkoutCycleFeedback.cycle_id.in_(cycle_ids),
                    WorkoutCycle.user_id == user_id,
                )
                .order_by(WorkoutCycleFeedback.submitted_at, WorkoutCycleFeedback.id)
            ).all()
        )

    def _preferences(self, user_id: UUID) -> list[WorkoutExercisePreference]:
        return list(
            self._db.scalars(
                select(WorkoutExercisePreference)
                .where(WorkoutExercisePreference.user_id == user_id)
                .order_by(WorkoutExercisePreference.created_at, WorkoutExercisePreference.id)
            ).all()
        )

    def _safety_signals(self, user_id: UUID) -> list[WorkoutExerciseSafetySignal]:
        return list(
            self._db.scalars(
                select(WorkoutExerciseSafetySignal)
                .where(WorkoutExerciseSafetySignal.user_id == user_id)
                .order_by(WorkoutExerciseSafetySignal.created_at, WorkoutExerciseSafetySignal.id)
            ).all()
        )

    def _replacements(self, user_id: UUID) -> list[WorkoutExerciseReplacement]:
        return list(
            self._db.scalars(
                select(WorkoutExerciseReplacement)
                .where(WorkoutExerciseReplacement.user_id == user_id)
                .order_by(WorkoutExerciseReplacement.created_at, WorkoutExerciseReplacement.id)
            ).all()
        )

    def _comparisons(
        self,
        user_id: UUID,
        cycle_ids: tuple[UUID, ...],
    ) -> list[WorkoutCycleBodyProgressComparison]:
        if not cycle_ids:
            return []
        return list(
            self._db.scalars(
                select(WorkoutCycleBodyProgressComparison)
                .where(
                    WorkoutCycleBodyProgressComparison.user_id == user_id,
                    WorkoutCycleBodyProgressComparison.cycle_id.in_(cycle_ids),
                )
                .order_by(
                    WorkoutCycleBodyProgressComparison.updated_at,
                    WorkoutCycleBodyProgressComparison.id,
                )
            ).all()
        )

    def _profile(self, user_id: UUID) -> UserProfile | None:
        return self._db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))

    def _plans(self, user_id: UUID) -> list[WorkoutPlan]:
        return list(
            self._db.scalars(
                select(WorkoutPlan)
                .where(WorkoutPlan.user_id == user_id)
                .order_by(WorkoutPlan.created_at.desc(), WorkoutPlan.id.desc())
            ).all()
        )

    @staticmethod
    def _adherence(
        check_ins: list[WorkoutCycleWeeklyCheckIn],
        cycles: list[WorkoutCycle],
    ) -> AthleteStateAdherence:
        days_by_cycle = {
            cycle.id: len(cycle.workout_plan.days) if cycle.workout_plan else 0
            for cycle in cycles
        }
        planned_sessions = sum(days_by_cycle.get(check_in.cycle_id, 0) for check_in in check_ins)
        sessions_completed = sum(check_in.sessions_completed for check_in in check_ins)
        percent = (
            round(sessions_completed / planned_sessions * 100, 2)
            if planned_sessions > 0
            else None
        )
        return AthleteStateAdherence(
            sessions_completed=sessions_completed,
            planned_sessions=planned_sessions,
            percent=percent,
            source_check_in_ids=tuple(check_in.id for check_in in check_ins),
        )

    @staticmethod
    def _recovery_trend(
        check_ins: list[WorkoutCycleWeeklyCheckIn],
    ) -> AthleteStateRecoveryTrend:
        values = tuple(check_in.recovery_rating for check_in in check_ins)
        return AthleteStateRecoveryTrend(
            latest=values[-1] if values else None,
            values=values,
            direction=AthleteStateBuilder._direction(
                ["poor", "average", "good"], [value.value for value in values]
            ),
            source_check_in_ids=tuple(check_in.id for check_in in check_ins),
        )

    @staticmethod
    def _difficulty_trend(
        check_ins: list[WorkoutCycleWeeklyCheckIn],
    ) -> AthleteStateDifficultyTrend:
        values = tuple(check_in.perceived_difficulty for check_in in check_ins)
        return AthleteStateDifficultyTrend(
            latest=values[-1] if values else None,
            values=values,
            direction=AthleteStateBuilder._direction(
                ["too_easy", "easy", "appropriate", "hard", "too_hard"],
                [value.value for value in values],
            ),
            source_check_in_ids=tuple(check_in.id for check_in in check_ins),
        )

    @staticmethod
    def _direction(order: list[str], values: list[str]) -> AthleteStateTrendDirection:
        if len(values) < 2:
            return AthleteStateTrendDirection.UNKNOWN
        first = order.index(values[0])
        last = order.index(values[-1])
        if last > first:
            return AthleteStateTrendDirection.INCREASING
        if last < first:
            return AthleteStateTrendDirection.DECREASING
        return AthleteStateTrendDirection.STABLE

    @staticmethod
    def _preference_exercise_ids(
        preferences: list[WorkoutExercisePreference],
        preference_type: WorkoutExercisePreferenceType,
    ) -> tuple[UUID, ...]:
        return AthleteStateBuilder._unique_ids(
            preference.exercise_id
            for preference in preferences
            if preference.preference_type is preference_type
        )

    @staticmethod
    def _equipment_context(
        preferences: list[WorkoutExercisePreference],
    ) -> tuple[AthleteStateExerciseContext, ...]:
        return tuple(
            AthleteStateExerciseContext(
                exercise_id=preference.exercise_id,
                source_preference_ids=(preference.id,),
                source_replacement_ids=(preference.source_replacement_id,),
            )
            for preference in preferences
            if preference.preference_type is WorkoutExercisePreferenceType.EQUIPMENT_UNAVAILABLE
        )

    @staticmethod
    def _feedback_muscles(
        feedbacks: list[WorkoutCycleFeedback],
        field: str,
    ) -> tuple[MuscleGroup, ...]:
        result: list[MuscleGroup] = []
        for feedback in feedbacks:
            values = getattr(feedback, field) or []
            for value in values:
                try:
                    muscle = MuscleGroup(value)
                except ValueError:
                    continue
                if muscle not in result:
                    result.append(muscle)
        return tuple(result)

    @staticmethod
    def _schedule(
        profile: UserProfile | None,
        feedbacks: list[WorkoutCycleFeedback],
    ) -> AthleteStateScheduleContext:
        latest_feedback = feedbacks[-1] if feedbacks else None
        return AthleteStateScheduleContext(
            current_training_days_per_week=profile.training_days_per_week if profile else None,
            current_session_duration_minutes=profile.session_duration_minutes if profile else None,
            next_training_days=(
                latest_feedback.next_training_days
                if latest_feedback and latest_feedback.next_training_days is not None
                else profile.training_days_per_week if profile else None
            ),
            next_session_duration_minutes=(
                latest_feedback.next_session_duration_minutes
                if latest_feedback and latest_feedback.next_session_duration_minutes is not None
                else profile.session_duration_minutes if profile else None
            ),
            training_location=profile.training_location if profile else None,
            home_training_setup=profile.home_training_setup if profile else None,
            source_feedback_id=latest_feedback.id if latest_feedback else None,
            source_profile_user_id=profile.user_id if profile else None,
        )

    @staticmethod
    def _body_progress(
        comparisons: list[WorkoutCycleBodyProgressComparison],
    ) -> AthleteStateBodyProgress:
        improved: list[BodyArea] = []
        unchanged: list[BodyArea] = []
        lagging: list[BodyArea] = []
        for comparison in comparisons:
            try:
                result = CycleBodyProgressComparisonResult.model_validate(
                    comparison.comparison_result
                )
            except ValueError:
                continue
            for area in result.body_analysis.improved_areas:
                if area not in improved:
                    improved.append(area)
            for area in result.body_analysis.unchanged_areas:
                if area not in unchanged:
                    unchanged.append(area)
            for area in result.body_analysis.lagging_areas:
                if area not in lagging:
                    lagging.append(area)
        return AthleteStateBodyProgress(
            improved_areas=tuple(improved),
            unchanged_areas=tuple(unchanged),
            lagging_areas=tuple(lagging),
            comparison_ids=tuple(comparison.id for comparison in comparisons),
        )

    @staticmethod
    def _comparison_source_ids(
        comparisons: list[WorkoutCycleBodyProgressComparison],
        *fields: str,
    ) -> tuple[UUID, ...]:
        return AthleteStateBuilder._unique_ids(
            getattr(comparison, field)
            for comparison in comparisons
            for field in fields
            if getattr(comparison, field) is not None
        )

    @staticmethod
    def _unique_ids(values: Iterable[UUID]) -> tuple[UUID, ...]:
        result: list[UUID] = []
        for value in values:
            if value not in result:
                result.append(value)
        return tuple(result)
