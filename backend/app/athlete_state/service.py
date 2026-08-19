from __future__ import annotations

from collections.abc import Iterable
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.athlete_state.schemas import (
    AthleteState,
    AthleteStateAdherence,
    AthleteStateBodyProgress,
    AthleteStateDifficultySummary,
    AthleteStateDifficultyTrend,
    AthleteStateExerciseContext,
    AthleteStateProvenance,
    AthleteStateReasonCode,
    AthleteStateRecoverySummary,
    AthleteStateRecoveryTrend,
    AthleteStateReplacementContext,
    AthleteStateScheduleContext,
    AthleteStateTrendDirection,
)
from app.body_analysis.enums import BodyArea
from app.exercises.enums import MuscleGroup
from app.profile.models import UserProfile
from app.workout_cycles.body_progress_models import WorkoutCycleBodyProgressComparison
from app.workout_cycles.body_progress_schemas import CycleBodyProgressComparisonResult
from app.workout_cycles.enums import (
    WorkoutCycleStatus,
    WorkoutCycleWeeklyCheckInDifficulty,
    WorkoutCycleWeeklyCheckInRecovery,
    WorkoutExercisePreferenceType,
    WorkoutExerciseReplacementScope,
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
                (cycle for cycle in cycles if cycle.status is WorkoutCycleStatus.ACTIVE),
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
        pain_sensitive_exercises = self._unique_ids(
            signal.original_exercise_id for signal in safety_signals
        )

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
                preferences,
                WorkoutExercisePreferenceType.DISLIKE,
                excluded_ids=pain_sensitive_exercises,
            ),
            uncomfortable_exercises=self._preference_exercise_ids(
                preferences,
                WorkoutExercisePreferenceType.UNCOMFORTABLE,
                excluded_ids=pain_sensitive_exercises,
            ),
            unavailable_exercises=self._preference_exercise_ids(
                preferences,
                WorkoutExercisePreferenceType.EQUIPMENT_UNAVAILABLE,
                excluded_ids=pain_sensitive_exercises,
            ),
            unavailable_equipment_context=self._equipment_context(
                preferences, excluded_ids=pain_sensitive_exercises
            ),
            replacement_context=self._replacement_context(replacements),
            pain_sensitive_exercises=pain_sensitive_exercises,
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
                body_progress_comparison_ids=tuple(comparison.id for comparison in comparisons),
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
                if cycle.id != current.id and cycle.status is WorkoutCycleStatus.COMPLETED
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
                    WorkoutCycle.user_id == user_id,
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
            cycle.id: len(cycle.workout_plan.days) if cycle.workout_plan else 0 for cycle in cycles
        }
        planned_sessions = sum(days_by_cycle.get(check_in.cycle_id, 0) for check_in in check_ins)
        sessions_completed = sum(check_in.sessions_completed for check_in in check_ins)
        percent = (
            round(sessions_completed / planned_sessions * 100, 2) if planned_sessions > 0 else None
        )
        return AthleteStateAdherence(
            sessions_completed=sessions_completed,
            planned_sessions=planned_sessions,
            percent=percent,
            source_check_in_ids=tuple(check_in.id for check_in in check_ins),
            reason_codes=(
                (AthleteStateReasonCode.ADHERENCE_CALCULATED_FROM_WEEKLY_CHECK_INS,)
                if check_ins
                else (AthleteStateReasonCode.NO_WEEKLY_CHECK_IN_DATA,)
            ),
        )

    @staticmethod
    def _recovery_trend(
        check_ins: list[WorkoutCycleWeeklyCheckIn],
    ) -> AthleteStateRecoveryTrend:
        values = tuple(check_in.recovery_rating for check_in in check_ins)
        recent_values = values[-4:]
        summary, reason_code = AthleteStateBuilder._recovery_summary(recent_values)
        return AthleteStateRecoveryTrend(
            latest=values[-1] if values else None,
            values=values,
            direction=AthleteStateBuilder._direction(
                ["poor", "average", "good"], [value.value for value in recent_values]
            ),
            source_check_in_ids=tuple(check_in.id for check_in in check_ins),
            summary=summary,
            reason_codes=(reason_code,),
        )

    @staticmethod
    def _difficulty_trend(
        check_ins: list[WorkoutCycleWeeklyCheckIn],
    ) -> AthleteStateDifficultyTrend:
        values = tuple(check_in.perceived_difficulty for check_in in check_ins)
        recent_values = values[-4:]
        summary, reason_code = AthleteStateBuilder._difficulty_summary(recent_values)
        return AthleteStateDifficultyTrend(
            latest=values[-1] if values else None,
            values=values,
            direction=AthleteStateBuilder._direction(
                ["too_easy", "easy", "appropriate", "hard", "too_hard"],
                [value.value for value in recent_values],
            ),
            source_check_in_ids=tuple(check_in.id for check_in in check_ins),
            summary=summary,
            reason_codes=(reason_code,),
        )

    @staticmethod
    def _recovery_summary(
        values: tuple[WorkoutCycleWeeklyCheckInRecovery, ...],
    ) -> tuple[AthleteStateRecoverySummary, AthleteStateReasonCode]:
        if not values:
            return (
                AthleteStateRecoverySummary.UNKNOWN,
                AthleteStateReasonCode.NO_RECOVERY_DATA,
            )
        if all(value is WorkoutCycleWeeklyCheckInRecovery.GOOD for value in values):
            return (
                AthleteStateRecoverySummary.GOOD,
                AthleteStateReasonCode.ALL_RECENT_RECOVERY_GOOD,
            )
        if all(value is WorkoutCycleWeeklyCheckInRecovery.POOR for value in values):
            return (
                AthleteStateRecoverySummary.POOR,
                AthleteStateReasonCode.ALL_RECENT_RECOVERY_POOR,
            )
        return (
            AthleteStateRecoverySummary.MIXED,
            AthleteStateReasonCode.MIXED_RECENT_RECOVERY,
        )

    @staticmethod
    def _difficulty_summary(
        values: tuple[WorkoutCycleWeeklyCheckInDifficulty, ...],
    ) -> tuple[AthleteStateDifficultySummary, AthleteStateReasonCode]:
        if not values:
            return (
                AthleteStateDifficultySummary.UNKNOWN,
                AthleteStateReasonCode.NO_DIFFICULTY_DATA,
            )
        categories = {AthleteStateBuilder._difficulty_category(value) for value in values}
        if len(categories) != 1:
            return (
                AthleteStateDifficultySummary.MIXED,
                AthleteStateReasonCode.MIXED_RECENT_DIFFICULTY,
            )
        category = categories.pop()
        reason_codes = {
            AthleteStateDifficultySummary.TOO_EASY: AthleteStateReasonCode.CONSISTENTLY_TOO_EASY,
            AthleteStateDifficultySummary.APPROPRIATE: (
                AthleteStateReasonCode.CONSISTENTLY_APPROPRIATE
            ),
            AthleteStateDifficultySummary.TOO_HARD: AthleteStateReasonCode.CONSISTENTLY_TOO_HARD,
        }
        return category, reason_codes[category]

    @staticmethod
    def _difficulty_category(
        value: WorkoutCycleWeeklyCheckInDifficulty,
    ) -> AthleteStateDifficultySummary:
        if value in (
            WorkoutCycleWeeklyCheckInDifficulty.TOO_EASY,
            WorkoutCycleWeeklyCheckInDifficulty.EASY,
        ):
            return AthleteStateDifficultySummary.TOO_EASY
        if value is WorkoutCycleWeeklyCheckInDifficulty.APPROPRIATE:
            return AthleteStateDifficultySummary.APPROPRIATE
        return AthleteStateDifficultySummary.TOO_HARD

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
        *,
        excluded_ids: tuple[UUID, ...] = (),
    ) -> tuple[UUID, ...]:
        return AthleteStateBuilder._unique_ids(
            preference.exercise_id
            for preference in preferences
            if preference.preference_type is preference_type
            and preference.exercise_id not in excluded_ids
        )

    @staticmethod
    def _equipment_context(
        preferences: list[WorkoutExercisePreference],
        *,
        excluded_ids: tuple[UUID, ...] = (),
    ) -> tuple[AthleteStateExerciseContext, ...]:
        return tuple(
            AthleteStateExerciseContext(
                exercise_id=preference.exercise_id,
                source_preference_ids=(preference.id,),
                source_replacement_ids=(preference.source_replacement_id,),
                reason_codes=(AthleteStateReasonCode.PERSISTENT_EQUIPMENT_CONTEXT,),
            )
            for preference in preferences
            if preference.preference_type is WorkoutExercisePreferenceType.EQUIPMENT_UNAVAILABLE
            and preference.exercise_id not in excluded_ids
        )

    @staticmethod
    def _replacement_context(
        replacements: list[WorkoutExerciseReplacement],
    ) -> tuple[AthleteStateReplacementContext, ...]:
        grouped: dict[tuple[UUID, UUID], dict[str, object]] = {}
        for replacement in replacements:
            key = (replacement.original_exercise_id, replacement.replacement_exercise_id)
            entry = grouped.setdefault(
                key,
                {
                    "persistent_count": 0,
                    "this_time_count": 0,
                    "reasons": set(),
                    "source_replacement_ids": [],
                },
            )
            if replacement.scope is WorkoutExerciseReplacementScope.PERSISTENT:
                entry["persistent_count"] = cast(int, entry["persistent_count"]) + 1
            else:
                entry["this_time_count"] = cast(int, entry["this_time_count"]) + 1
            cast_reasons = entry["reasons"]
            assert isinstance(cast_reasons, set)
            cast_reasons.add(replacement.reason)
            cast_ids = entry["source_replacement_ids"]
            assert isinstance(cast_ids, list)
            cast_ids.append(replacement.id)

        contexts: list[AthleteStateReplacementContext] = []
        for (original_id, replacement_id), entry in grouped.items():
            reasons = entry["reasons"]
            source_ids = entry["source_replacement_ids"]
            assert isinstance(reasons, set)
            assert isinstance(source_ids, list)
            contexts.append(
                AthleteStateReplacementContext(
                    original_exercise_id=original_id,
                    replacement_exercise_id=replacement_id,
                    persistent_count=cast(int, entry["persistent_count"]),
                    this_time_count=cast(int, entry["this_time_count"]),
                    reasons=tuple(sorted(reasons, key=lambda reason: reason.value)),
                    source_replacement_ids=tuple(sorted(source_ids, key=str)),
                )
            )
        return tuple(
            sorted(
                contexts,
                key=lambda context: (
                    str(context.original_exercise_id),
                    str(context.replacement_exercise_id),
                ),
            )
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
                else profile.training_days_per_week
                if profile
                else None
            ),
            next_session_duration_minutes=(
                latest_feedback.next_session_duration_minutes
                if latest_feedback and latest_feedback.next_session_duration_minutes is not None
                else profile.session_duration_minutes
                if profile
                else None
            ),
            training_location=profile.training_location if profile else None,
            home_training_setup=profile.home_training_setup if profile else None,
            source_feedback_id=latest_feedback.id if latest_feedback else None,
            source_profile_user_id=profile.user_id if profile else None,
            reason_codes=(
                (AthleteStateReasonCode.LATEST_CONFIRMED_FEEDBACK_SCHEDULE,)
                if latest_feedback
                and (
                    latest_feedback.next_training_days is not None
                    or latest_feedback.next_session_duration_minutes is not None
                )
                else (
                    (AthleteStateReasonCode.PROFILE_SCHEDULE_FALLBACK,)
                    if profile
                    else (AthleteStateReasonCode.NO_SCHEDULE_DATA,)
                )
            ),
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
            reason_codes=(
                (AthleteStateReasonCode.BODY_COMPARISON_EVIDENCE,)
                if comparisons
                else (AthleteStateReasonCode.NO_BODY_PROGRESS_DATA,)
            ),
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
