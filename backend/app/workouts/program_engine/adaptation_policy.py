from __future__ import annotations

import json
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.athlete_state.schemas import (
    AthleteState,
    AthleteStateDifficultySummary,
    AthleteStateRecoverySummary,
)
from app.exercises.enums import MuscleGroup
from app.workout_cycles.enums import (
    WorkoutCycleWeeklyCheckInDifficulty,
    WorkoutCycleWeeklyCheckInRecovery,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import (
    RULESET,
    ProgramRuleset,
)
from app.workouts.program_engine.schemas import RecentTrainingHistory
from app.workouts.program_engine.volume_history import derive_previous_volume_baseline


class CycleAdaptationAction(StrEnum):
    INCREASE = "increase"
    MAINTAIN = "maintain"
    REDUCE = "reduce"


class CycleAdaptationReasonCode(StrEnum):
    PROGRESSION_SUPPORTED_BY_ADHERENCE_RECOVERY_DIFFICULTY = (
        "PROGRESSION_SUPPORTED_BY_ADHERENCE_RECOVERY_DIFFICULTY"
    )
    POOR_RECOVERY_REQUIRES_REDUCTION = "POOR_RECOVERY_REQUIRES_REDUCTION"
    TOO_HARD_REQUIRES_REDUCTION = "TOO_HARD_REQUIRES_REDUCTION"
    SAFETY_OVERRIDES_PROGRESSION = "SAFETY_OVERRIDES_PROGRESSION"
    SAFETY_OVERRIDES_PREFERENCE = "SAFETY_OVERRIDES_PREFERENCE"
    LOW_ADHERENCE_BLOCKS_PROGRESSION = "LOW_ADHERENCE_BLOCKS_PROGRESSION"
    INSUFFICIENT_RELIABLE_EVIDENCE = "INSUFFICIENT_RELIABLE_EVIDENCE"
    HISTORY_BASELINE_REQUIRED_FOR_PROGRESSION = "HISTORY_BASELINE_REQUIRED_FOR_PROGRESSION"
    MIXED_SIGNAL_RESOLVED_CONSERVATIVELY = "MIXED_SIGNAL_RESOLVED_CONSERVATIVELY"
    LAGGING_MUSCLE_SUPPORTED_CONSERVATIVELY = "LAGGING_MUSCLE_SUPPORTED_CONSERVATIVELY"
    PROGRESSING_MUSCLE_NOT_AUTOMATICALLY_INCREASED = (
        "PROGRESSING_MUSCLE_NOT_AUTOMATICALLY_INCREASED"
    )
    PERSISTENT_PREFERENCES_PRESERVED = "PERSISTENT_PREFERENCES_PRESERVED"
    HIGH_ADHERENCE = "HIGH_ADHERENCE"
    LOW_ADHERENCE = "LOW_ADHERENCE"
    GOOD_RECOVERY = "GOOD_RECOVERY"
    POOR_RECOVERY = "POOR_RECOVERY"
    DIFFICULTY_TOO_HARD = "DIFFICULTY_TOO_HARD"
    PROGRESSION_ALLOWED = "PROGRESSION_ALLOWED"
    PROGRESSION_HELD = "PROGRESSION_HELD"
    RECOVERY_LIMITED = "RECOVERY_LIMITED"


class CycleAdaptationMuscleAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    muscle: MuscleGroup
    action: CycleAdaptationAction
    volume_delta_sets: int = Field(ge=-10, le=10)
    priority_delta: int = Field(ge=-10, le=10)
    reason_codes: tuple[CycleAdaptationReasonCode, ...] = ()


class CycleAdaptationRecoveryConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prevent_increase: bool
    max_volume_increase_ratio: float = Field(ge=0, le=1)


class CycleAdaptationVolumeContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    previous_direct_sets_by_muscle: dict[MuscleGroup, float] = Field(default_factory=dict)
    previous_effective_sets_by_muscle: dict[MuscleGroup, float] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    source: str


class CycleAdaptationPreferenceConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    disliked_exercises: tuple[UUID, ...] = ()
    unavailable_exercises: tuple[UUID, ...] = ()


class CycleAdaptationSafetyConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    blocked_exercises: tuple[UUID, ...] = ()


class CycleAdaptationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cycle_ids: tuple[UUID, ...] = ()
    weekly_check_in_ids: tuple[UUID, ...] = ()
    end_feedback_ids: tuple[UUID, ...] = ()
    preference_ids: tuple[UUID, ...] = ()
    safety_signal_ids: tuple[UUID, ...] = ()
    workout_plan_ids: tuple[UUID, ...] = ()


class CycleAdaptationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    overall_action: CycleAdaptationAction
    muscle_adjustments: tuple[CycleAdaptationMuscleAdjustment, ...] = ()
    volume_context: CycleAdaptationVolumeContext
    recovery_constraints: CycleAdaptationRecoveryConstraints
    preference_constraints: CycleAdaptationPreferenceConstraints
    safety_constraints: CycleAdaptationSafetyConstraints
    reason_codes: tuple[CycleAdaptationReasonCode, ...] = ()
    provenance: CycleAdaptationProvenance

    def to_snapshot(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def to_snapshot_json(self) -> str:
        return json.dumps(
            self.to_snapshot(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )


def decide_cycle_adaptation(
    state: AthleteState,
    history: RecentTrainingHistory | None = None,
    ruleset: ProgramRuleset = RULESET,
) -> CycleAdaptationDecision:
    recent_history = history or RecentTrainingHistory()
    baseline = derive_previous_volume_baseline(recent_history)
    adherence, adherence_conflict = _adherence_ratio(state, recent_history)
    safety_ids = _sorted_ids(state.pain_sensitive_exercises)
    preference_source_ids = set(state.persistent_disliked_exercises) | set(
        state.uncomfortable_exercises
    )
    disliked_ids = _sorted_ids(
        preference_source_ids - set(safety_ids)
    )
    unavailable_ids = _sorted_ids(state.unavailable_exercises)
    reasons: list[CycleAdaptationReasonCode] = []
    poor_recovery = state.recovery_trend.summary is AthleteStateRecoverySummary.POOR
    repeated_poor_recovery = poor_recovery and _signal_count(
        state.recovery_trend.values,
        WorkoutCycleWeeklyCheckInRecovery.POOR,
    ) >= ruleset.adaptation_repeated_poor_recovery_weeks
    too_hard = state.difficulty_trend.summary is AthleteStateDifficultySummary.TOO_HARD
    repeated_too_hard = too_hard and _signal_count(
        state.difficulty_trend.values,
        WorkoutCycleWeeklyCheckInDifficulty.TOO_HARD,
    ) >= ruleset.adaptation_repeated_too_hard_weeks

    action = CycleAdaptationAction.MAINTAIN
    if safety_ids:
        action = CycleAdaptationAction.REDUCE
        reasons.extend(
            (
                CycleAdaptationReasonCode.SAFETY_OVERRIDES_PROGRESSION,
                CycleAdaptationReasonCode.SAFETY_OVERRIDES_PREFERENCE
                if preference_source_ids & set(safety_ids)
                else CycleAdaptationReasonCode.SAFETY_OVERRIDES_PROGRESSION,
            )
        )
    elif repeated_poor_recovery:
        action = CycleAdaptationAction.REDUCE
        reasons.append(CycleAdaptationReasonCode.POOR_RECOVERY_REQUIRES_REDUCTION)
    elif repeated_too_hard:
        action = CycleAdaptationAction.REDUCE
        reasons.append(CycleAdaptationReasonCode.TOO_HARD_REQUIRES_REDUCTION)
    elif adherence is None:
        reasons.append(CycleAdaptationReasonCode.INSUFFICIENT_RELIABLE_EVIDENCE)
    elif adherence < ruleset.adaptation_min_adherence_for_progression:
        reasons.append(CycleAdaptationReasonCode.LOW_ADHERENCE_BLOCKS_PROGRESSION)
    elif state.recovery_trend.summary is not AthleteStateRecoverySummary.GOOD:
        reasons.append(CycleAdaptationReasonCode.MIXED_SIGNAL_RESOLVED_CONSERVATIVELY)
    elif state.difficulty_trend.summary not in {
        AthleteStateDifficultySummary.APPROPRIATE,
        AthleteStateDifficultySummary.TOO_EASY,
    }:
        reasons.append(CycleAdaptationReasonCode.MIXED_SIGNAL_RESOLVED_CONSERVATIVELY)
    elif not baseline.effective_sets_by_muscle:
        reasons.append(CycleAdaptationReasonCode.HISTORY_BASELINE_REQUIRED_FOR_PROGRESSION)
    elif baseline.confidence < ruleset.adaptation_min_volume_confidence_for_progression:
        reasons.append(CycleAdaptationReasonCode.INSUFFICIENT_RELIABLE_EVIDENCE)
    else:
        action = CycleAdaptationAction.INCREASE
        reasons.append(
            CycleAdaptationReasonCode.PROGRESSION_SUPPORTED_BY_ADHERENCE_RECOVERY_DIFFICULTY
        )

    if adherence_conflict:
        reasons.append(CycleAdaptationReasonCode.MIXED_SIGNAL_RESOLVED_CONSERVATIVELY)
    if adherence is not None and adherence >= ruleset.adaptation_min_adherence_for_progression:
        reasons.append(CycleAdaptationReasonCode.HIGH_ADHERENCE)
    elif adherence is not None:
        reasons.append(CycleAdaptationReasonCode.LOW_ADHERENCE)
    if state.recovery_trend.summary is AthleteStateRecoverySummary.GOOD:
        reasons.append(CycleAdaptationReasonCode.GOOD_RECOVERY)
    elif poor_recovery:
        reasons.append(CycleAdaptationReasonCode.POOR_RECOVERY)
    if too_hard:
        reasons.append(CycleAdaptationReasonCode.DIFFICULTY_TOO_HARD)
    if poor_recovery or too_hard:
        reasons.append(CycleAdaptationReasonCode.RECOVERY_LIMITED)
    reasons.append(
        CycleAdaptationReasonCode.PROGRESSION_ALLOWED
        if action is CycleAdaptationAction.INCREASE
        else CycleAdaptationReasonCode.PROGRESSION_HELD
    )
    if state.progressing_muscles:
        reasons.append(CycleAdaptationReasonCode.PROGRESSING_MUSCLE_NOT_AUTOMATICALLY_INCREASED)
    if disliked_ids or unavailable_ids:
        reasons.append(CycleAdaptationReasonCode.PERSISTENT_PREFERENCES_PRESERVED)

    adjustments: tuple[CycleAdaptationMuscleAdjustment, ...] = ()
    if action is CycleAdaptationAction.INCREASE:
        adjustments = tuple(
            CycleAdaptationMuscleAdjustment(
                muscle=muscle,
                action=CycleAdaptationAction.INCREASE,
                volume_delta_sets=ruleset.adaptation_lagging_muscle_volume_delta_sets,
                priority_delta=ruleset.adaptation_lagging_muscle_priority_delta,
                reason_codes=(CycleAdaptationReasonCode.LAGGING_MUSCLE_SUPPORTED_CONSERVATIVELY,),
            )
            for muscle in sorted(set(state.lagging_muscles), key=lambda item: item.value)
        )
        if adjustments:
            reasons.append(CycleAdaptationReasonCode.LAGGING_MUSCLE_SUPPORTED_CONSERVATIVELY)

    reasons = list(dict.fromkeys(reasons))
    return CycleAdaptationDecision(
        overall_action=action,
        muscle_adjustments=adjustments,
        volume_context=CycleAdaptationVolumeContext(
            previous_direct_sets_by_muscle=baseline.direct_sets_by_muscle,
            previous_effective_sets_by_muscle=baseline.effective_sets_by_muscle,
            confidence=baseline.confidence,
            source=baseline.source,
        ),
        recovery_constraints=CycleAdaptationRecoveryConstraints(
            prevent_increase=action is not CycleAdaptationAction.INCREASE,
            max_volume_increase_ratio=(
                ruleset.adaptation_max_volume_increase_ratio
                if action is CycleAdaptationAction.INCREASE
                else 0.0
            ),
        ),
        preference_constraints=CycleAdaptationPreferenceConstraints(
            disliked_exercises=disliked_ids,
            unavailable_exercises=unavailable_ids,
        ),
        safety_constraints=CycleAdaptationSafetyConstraints(blocked_exercises=safety_ids),
        reason_codes=tuple(reasons),
        provenance=CycleAdaptationProvenance(
            cycle_ids=state.provenance.cycle_ids,
            weekly_check_in_ids=state.provenance.weekly_check_in_ids,
            end_feedback_ids=state.provenance.end_feedback_ids,
            preference_ids=state.provenance.preference_ids,
            safety_signal_ids=state.provenance.safety_signal_ids,
            workout_plan_ids=state.provenance.workout_plan_ids,
        ),
    )


def _adherence_ratio(
    state: AthleteState,
    history: RecentTrainingHistory,
) -> tuple[float | None, bool]:
    state_ratio = state.adherence.percent / 100 if state.adherence.percent is not None else None
    history_ratio = history.completed_session_ratio if history.completed_session_ratio > 0 else None
    if state_ratio is None:
        return history_ratio, False
    if history_ratio is None:
        return state_ratio, False
    return min(state_ratio, history_ratio), abs(state_ratio - history_ratio) > 0.01


def _sorted_ids(values: tuple[UUID, ...] | set[UUID]) -> tuple[UUID, ...]:
    return tuple(sorted(set(values), key=str))


def _signal_count(values: tuple[StrEnum, ...], expected: StrEnum) -> int:
    matching = sum(value is expected for value in values)
    return matching if matching else 1
