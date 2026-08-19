from __future__ import annotations

import json
from enum import StrEnum
from typing import Any, cast
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
    WorkoutExerciseReplacementReason,
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


class CycleAdaptationChangeType(StrEnum):
    OVERALL_TRAINING_DEMAND = "overall_training_demand"
    MUSCLE_VOLUME = "muscle_volume"
    PRIORITY_MUSCLE = "priority_muscle"
    SCHEDULE = "schedule"
    EXERCISE_AVOIDANCE = "exercise_avoidance"
    EXERCISE_REPLACEMENT = "exercise_replacement"
    EQUIPMENT_CONSTRAINT = "equipment_constraint"
    SAFETY_CONSTRAINT = "safety_constraint"


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
    PERSISTENT_EXERCISE_DISLIKE = "PERSISTENT_EXERCISE_DISLIKE"
    PERSISTENT_EXERCISE_DISCOMFORT = "PERSISTENT_EXERCISE_DISCOMFORT"
    EQUIPMENT_UNAVAILABLE = "EQUIPMENT_UNAVAILABLE"
    REPEATED_REPLACEMENT = "REPEATED_REPLACEMENT"
    PREFERRED_ALTERNATIVE = "PREFERRED_ALTERNATIVE"
    PREFERENCE_OVERRIDDEN_BY_SAFETY = "PREFERENCE_OVERRIDDEN_BY_SAFETY"
    PREFERENCE_OVERRIDDEN_BY_AVAILABILITY = "PREFERENCE_OVERRIDDEN_BY_AVAILABILITY"
    PAIN_SIGNAL_PRESENT = "PAIN_SIGNAL_PRESENT"
    REPEATED_PAIN_SIGNAL = "REPEATED_PAIN_SIGNAL"
    EXERCISE_BLOCKED_FOR_SAFETY = "EXERCISE_BLOCKED_FOR_SAFETY"
    SAFE_SUBSTITUTION_REQUIRED = "SAFE_SUBSTITUTION_REQUIRED"
    PROGRESSION_HELD_FOR_SAFETY = "PROGRESSION_HELD_FOR_SAFETY"


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


class CycleAdaptationPreferredAlternative(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    original_exercise_id: UUID
    replacement_exercise_id: UUID
    strength: int = Field(ge=1, le=10)
    source_replacement_ids: tuple[UUID, ...] = ()
    reason_codes: tuple[CycleAdaptationReasonCode, ...] = ()


class CycleAdaptationPreferenceConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    disliked_exercises: tuple[UUID, ...] = ()
    unavailable_exercises: tuple[UUID, ...] = ()
    preferred_alternatives: tuple[CycleAdaptationPreferredAlternative, ...] = ()


class CycleAdaptationSafetySubstitution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    blocked_exercise_id: UUID
    replacement_exercise_id: UUID
    strength: int = Field(ge=1, le=10)
    source_replacement_ids: tuple[UUID, ...] = ()
    source_safety_signal_ids: tuple[UUID, ...] = ()
    reason_codes: tuple[CycleAdaptationReasonCode, ...] = ()


class CycleAdaptationSafetyConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    blocked_exercises: tuple[UUID, ...] = ()
    signal_counts_by_exercise: dict[UUID, int] = Field(default_factory=dict)
    safe_substitutions: tuple[CycleAdaptationSafetySubstitution, ...] = ()


class CycleAdaptationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cycle_ids: tuple[UUID, ...] = ()
    weekly_check_in_ids: tuple[UUID, ...] = ()
    end_feedback_ids: tuple[UUID, ...] = ()
    replacement_ids: tuple[UUID, ...] = ()
    preference_ids: tuple[UUID, ...] = ()
    safety_signal_ids: tuple[UUID, ...] = ()
    workout_plan_ids: tuple[UUID, ...] = ()


class CycleAdaptationProgramSnapshot(BaseModel):
    """Small, raw-record-free comparison contract for two cycle programs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    program_id: UUID | None = None
    cycle_id: UUID | None = None
    weekly_effective_sets_by_muscle: dict[MuscleGroup, float] = Field(default_factory=dict)
    priority_muscles: tuple[MuscleGroup, ...] = ()
    training_days: int | None = Field(default=None, ge=1, le=7)
    session_duration_minutes: int | None = Field(default=None, ge=20, le=180)
    disliked_exercises: tuple[UUID, ...] = ()
    unavailable_exercises: tuple[UUID, ...] = ()
    blocked_exercises: tuple[UUID, ...] = ()
    preferred_alternatives: tuple[CycleAdaptationPreferredAlternative, ...] = ()


class CycleAdaptationDifference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    change: CycleAdaptationChangeType
    target: str
    previous: Any | None = None
    next: Any | None = None
    reason_codes: tuple[CycleAdaptationReasonCode, ...] = ()
    provenance: CycleAdaptationProvenance


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
    difference_summary: tuple[CycleAdaptationDifference, ...] = ()
    decision_trace: tuple[dict[str, object], ...] = ()

    def to_snapshot(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def to_snapshot_json(self) -> str:
        return json.dumps(
            self.to_snapshot(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    def with_program_comparison(
        self,
        previous: CycleAdaptationProgramSnapshot,
        proposed: CycleAdaptationProgramSnapshot,
    ) -> CycleAdaptationDecision:
        differences = build_cycle_difference_summary(self, previous, proposed)
        return self.model_copy(
            update={
                "difference_summary": differences,
                "decision_trace": _decision_trace(self, differences),
            }
        )


def decide_cycle_adaptation(
    state: AthleteState,
    history: RecentTrainingHistory | None = None,
    ruleset: ProgramRuleset = RULESET,
    *,
    previous_program: CycleAdaptationProgramSnapshot | None = None,
    proposed_program: CycleAdaptationProgramSnapshot | None = None,
) -> CycleAdaptationDecision:
    recent_history = history or RecentTrainingHistory()
    baseline = derive_previous_volume_baseline(recent_history)
    adherence, adherence_conflict = _adherence_ratio(state, recent_history)
    safety_ids = _sorted_ids(
        set(state.pain_sensitive_exercises)
        | {context.exercise_id for context in state.safety_context}
    )
    raw_preference_ids = set(state.persistent_disliked_exercises) | set(
        state.uncomfortable_exercises
    )
    disliked_ids, unavailable_ids, preferred_alternatives, preference_reasons = (
        _replacement_preference_constraints(state, set(safety_ids), ruleset)
    )
    safety_constraints, safety_reasons = _safety_constraints(
        state,
        set(safety_ids),
        set(unavailable_ids),
        ruleset,
    )
    reasons: list[CycleAdaptationReasonCode] = list(safety_reasons)
    poor_recovery = state.recovery_trend.summary is AthleteStateRecoverySummary.POOR
    repeated_poor_recovery = (
        poor_recovery
        and _signal_count(
            state.recovery_trend.values,
            WorkoutCycleWeeklyCheckInRecovery.POOR,
        )
        >= ruleset.adaptation_repeated_poor_recovery_weeks
    )
    too_hard = state.difficulty_trend.summary is AthleteStateDifficultySummary.TOO_HARD
    repeated_too_hard = (
        too_hard
        and _signal_count(
            state.difficulty_trend.values,
            WorkoutCycleWeeklyCheckInDifficulty.TOO_HARD,
        )
        >= ruleset.adaptation_repeated_too_hard_weeks
    )

    action = CycleAdaptationAction.MAINTAIN
    if safety_ids:
        action = CycleAdaptationAction.REDUCE
        reasons.extend(
            (
                CycleAdaptationReasonCode.SAFETY_OVERRIDES_PROGRESSION,
                CycleAdaptationReasonCode.SAFETY_OVERRIDES_PREFERENCE
                if raw_preference_ids & set(safety_ids)
                else CycleAdaptationReasonCode.SAFETY_OVERRIDES_PROGRESSION,
            )
        )
        if raw_preference_ids & set(safety_ids):
            reasons.append(CycleAdaptationReasonCode.PREFERENCE_OVERRIDDEN_BY_SAFETY)
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
    reasons.extend(preference_reasons)

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
    decision = CycleAdaptationDecision(
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
            preferred_alternatives=preferred_alternatives,
        ),
        safety_constraints=safety_constraints,
        reason_codes=tuple(reasons),
        provenance=CycleAdaptationProvenance(
            cycle_ids=state.provenance.cycle_ids,
            weekly_check_in_ids=state.provenance.weekly_check_in_ids,
            end_feedback_ids=state.provenance.end_feedback_ids,
            replacement_ids=_sorted_ids(
                set(state.provenance.replacement_ids)
                | {
                    replacement_id
                    for context in state.replacement_context
                    for replacement_id in context.source_replacement_ids
                }
            ),
            preference_ids=state.provenance.preference_ids,
            safety_signal_ids=_sorted_ids(
                set(state.provenance.safety_signal_ids)
                | {
                    signal_id
                    for context in state.safety_context
                    for signal_id in context.source_safety_signal_ids
                }
            ),
            workout_plan_ids=state.provenance.workout_plan_ids,
        ),
    )
    if previous_program is not None and proposed_program is not None:
        return decision.with_program_comparison(previous_program, proposed_program)
    return decision.model_copy(update={"decision_trace": _decision_trace(decision, ())})


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


def _replacement_preference_constraints(
    state: AthleteState,
    safety_ids: set[UUID],
    ruleset: ProgramRuleset,
) -> tuple[
    tuple[UUID, ...],
    tuple[UUID, ...],
    tuple[CycleAdaptationPreferredAlternative, ...],
    tuple[CycleAdaptationReasonCode, ...],
]:
    raw_disliked = set(state.persistent_disliked_exercises) | set(state.uncomfortable_exercises)
    unavailable_source_ids = set(state.unavailable_exercises)
    disliked_ids = _sorted_ids(raw_disliked - safety_ids - unavailable_source_ids)
    unavailable_ids = _sorted_ids(unavailable_source_ids - safety_ids)
    reasons: list[CycleAdaptationReasonCode] = []
    if state.persistent_disliked_exercises:
        reasons.append(CycleAdaptationReasonCode.PERSISTENT_EXERCISE_DISLIKE)
    if state.uncomfortable_exercises:
        reasons.append(CycleAdaptationReasonCode.PERSISTENT_EXERCISE_DISCOMFORT)
    if state.unavailable_exercises:
        reasons.append(CycleAdaptationReasonCode.EQUIPMENT_UNAVAILABLE)

    grouped: dict[tuple[UUID, UUID], dict[str, object]] = {}
    for context in state.replacement_context:
        key = (context.original_exercise_id, context.replacement_exercise_id)
        entry = grouped.setdefault(
            key,
            {
                "persistent_count": 0,
                "reasons": set(),
                "source_replacement_ids": set(),
            },
        )
        entry["persistent_count"] = cast(int, entry["persistent_count"]) + context.persistent_count
        context_reasons = entry["reasons"]
        source_ids = entry["source_replacement_ids"]
        assert isinstance(context_reasons, set)
        assert isinstance(source_ids, set)
        context_reasons.update(context.reasons)
        source_ids.update(context.source_replacement_ids)

    preferred: list[CycleAdaptationPreferredAlternative] = []
    for (original_id, replacement_id), entry in grouped.items():
        persistent_count = cast(int, entry["persistent_count"])
        context_reasons = entry["reasons"]
        source_ids = entry["source_replacement_ids"]
        assert isinstance(context_reasons, set)
        assert isinstance(source_ids, set)
        if persistent_count < ruleset.adaptation_repeated_replacement_count:
            continue
        if not context_reasons.intersection(
            {
                WorkoutExerciseReplacementReason.DISLIKE,
                WorkoutExerciseReplacementReason.UNCOMFORTABLE,
                WorkoutExerciseReplacementReason.EQUIPMENT_UNAVAILABLE,
            }
        ):
            continue
        if replacement_id in safety_ids:
            reasons.append(CycleAdaptationReasonCode.PREFERENCE_OVERRIDDEN_BY_SAFETY)
            continue
        if replacement_id in set(unavailable_ids):
            reasons.append(CycleAdaptationReasonCode.PREFERENCE_OVERRIDDEN_BY_AVAILABILITY)
            continue
        preferred_reasons = [
            CycleAdaptationReasonCode.REPEATED_REPLACEMENT,
            CycleAdaptationReasonCode.PREFERRED_ALTERNATIVE,
        ]
        preferred.append(
            CycleAdaptationPreferredAlternative(
                original_exercise_id=original_id,
                replacement_exercise_id=replacement_id,
                strength=min(
                    persistent_count,
                    ruleset.adaptation_max_replacement_preference_strength,
                ),
                source_replacement_ids=tuple(sorted(source_ids, key=str)),
                reason_codes=tuple(preferred_reasons),
            )
        )
        reasons.extend(preferred_reasons)

    preferred.sort(
        key=lambda alternative: (
            -alternative.strength,
            str(alternative.original_exercise_id),
            str(alternative.replacement_exercise_id),
        )
    )
    return disliked_ids, unavailable_ids, tuple(preferred), tuple(dict.fromkeys(reasons))


def _safety_constraints(
    state: AthleteState,
    safety_ids: set[UUID],
    unavailable_ids: set[UUID],
    ruleset: ProgramRuleset,
) -> tuple[CycleAdaptationSafetyConstraints, tuple[CycleAdaptationReasonCode, ...]]:
    signal_counts = {context.exercise_id: context.signal_count for context in state.safety_context}
    signal_counts.update(
        {exercise_id: signal_counts.get(exercise_id, 1) for exercise_id in safety_ids}
    )
    reasons: list[CycleAdaptationReasonCode] = []
    if safety_ids:
        reasons.extend(
            (
                CycleAdaptationReasonCode.PAIN_SIGNAL_PRESENT,
                CycleAdaptationReasonCode.EXERCISE_BLOCKED_FOR_SAFETY,
                CycleAdaptationReasonCode.SAFE_SUBSTITUTION_REQUIRED,
                CycleAdaptationReasonCode.PROGRESSION_HELD_FOR_SAFETY,
            )
        )
    if any(
        count >= ruleset.adaptation_repeated_pain_signal_count for count in signal_counts.values()
    ):
        reasons.append(CycleAdaptationReasonCode.REPEATED_PAIN_SIGNAL)

    contexts_by_exercise = {context.exercise_id: context for context in state.safety_context}
    substitutions: list[CycleAdaptationSafetySubstitution] = []
    for replacement in state.replacement_context:
        if replacement.original_exercise_id not in safety_ids:
            continue
        if not replacement.safe:
            continue
        if replacement.replacement_exercise_id in safety_ids:
            continue
        if replacement.replacement_exercise_id in unavailable_ids:
            continue
        if WorkoutExerciseReplacementReason.PAIN_OR_DISCOMFORT not in replacement.reasons:
            continue
        source_context = contexts_by_exercise.get(replacement.original_exercise_id)
        if source_context is None:
            continue
        source_replacement_ids = tuple(
            sorted(
                set(replacement.source_replacement_ids)
                & set(source_context.source_replacement_ids),
                key=str,
            )
        )
        if not source_replacement_ids:
            continue
        substitutions.append(
            CycleAdaptationSafetySubstitution(
                blocked_exercise_id=replacement.original_exercise_id,
                replacement_exercise_id=replacement.replacement_exercise_id,
                strength=min(len(source_replacement_ids), 10),
                source_replacement_ids=source_replacement_ids,
                source_safety_signal_ids=source_context.source_safety_signal_ids,
                reason_codes=(CycleAdaptationReasonCode.SAFE_SUBSTITUTION_REQUIRED,),
            )
        )

    substitutions.sort(
        key=lambda substitution: (
            str(substitution.blocked_exercise_id),
            -substitution.strength,
            str(substitution.replacement_exercise_id),
        )
    )
    return (
        CycleAdaptationSafetyConstraints(
            blocked_exercises=_sorted_ids(safety_ids),
            signal_counts_by_exercise={
                exercise_id: signal_counts[exercise_id]
                for exercise_id in sorted(signal_counts, key=str)
            },
            safe_substitutions=tuple(substitutions),
        ),
        tuple(dict.fromkeys(reasons)),
    )


def build_cycle_difference_summary(
    decision: CycleAdaptationDecision,
    previous: CycleAdaptationProgramSnapshot,
    proposed: CycleAdaptationProgramSnapshot,
) -> tuple[CycleAdaptationDifference, ...]:
    """Compare effective programming choices without copying source records."""

    provenance = _comparison_provenance(decision, previous, proposed)
    differences: list[CycleAdaptationDifference] = []
    previous_total = sum(previous.weekly_effective_sets_by_muscle.values())
    proposed_total = sum(proposed.weekly_effective_sets_by_muscle.values())
    if previous_total != proposed_total:
        differences.append(
            CycleAdaptationDifference(
                change=CycleAdaptationChangeType.OVERALL_TRAINING_DEMAND,
                target="weekly_effective_sets_total",
                previous=previous_total,
                next=proposed_total,
                reason_codes=_change_reasons(
                    decision,
                    {
                        CycleAdaptationReasonCode.HIGH_ADHERENCE,
                        CycleAdaptationReasonCode.LOW_ADHERENCE,
                        CycleAdaptationReasonCode.GOOD_RECOVERY,
                        CycleAdaptationReasonCode.POOR_RECOVERY,
                        CycleAdaptationReasonCode.DIFFICULTY_TOO_HARD,
                        CycleAdaptationReasonCode.PROGRESSION_ALLOWED,
                        CycleAdaptationReasonCode.PROGRESSION_HELD,
                        CycleAdaptationReasonCode.PROGRESSION_HELD_FOR_SAFETY,
                    },
                ),
                provenance=provenance,
            )
        )

    previous_muscles = previous.weekly_effective_sets_by_muscle
    proposed_muscles = proposed.weekly_effective_sets_by_muscle
    adjustments = {item.muscle: item for item in decision.muscle_adjustments}
    for muscle in sorted(
        set(previous_muscles) | set(proposed_muscles), key=lambda item: item.value
    ):
        previous_value = previous_muscles.get(muscle, 0.0)
        proposed_value = proposed_muscles.get(muscle, 0.0)
        if previous_value == proposed_value:
            continue
        adjustment = adjustments.get(muscle)
        extra_reasons = adjustment.reason_codes if adjustment else ()
        differences.append(
            CycleAdaptationDifference(
                change=CycleAdaptationChangeType.MUSCLE_VOLUME,
                target=muscle.value,
                previous=previous_value,
                next=proposed_value,
                reason_codes=_change_reasons(
                    decision,
                    {
                        CycleAdaptationReasonCode.HIGH_ADHERENCE,
                        CycleAdaptationReasonCode.LOW_ADHERENCE,
                        CycleAdaptationReasonCode.GOOD_RECOVERY,
                        CycleAdaptationReasonCode.POOR_RECOVERY,
                        CycleAdaptationReasonCode.LAGGING_MUSCLE_SUPPORTED_CONSERVATIVELY,
                        CycleAdaptationReasonCode.PROGRESSING_MUSCLE_NOT_AUTOMATICALLY_INCREASED,
                        CycleAdaptationReasonCode.PROGRESSION_ALLOWED,
                        CycleAdaptationReasonCode.PROGRESSION_HELD,
                        CycleAdaptationReasonCode.PROGRESSION_HELD_FOR_SAFETY,
                    },
                    extra=extra_reasons,
                ),
                provenance=provenance,
            )
        )

    previous_priorities = set(previous.priority_muscles)
    proposed_priorities = set(proposed.priority_muscles)
    for muscle in sorted(previous_priorities ^ proposed_priorities, key=lambda item: item.value):
        differences.append(
            CycleAdaptationDifference(
                change=CycleAdaptationChangeType.PRIORITY_MUSCLE,
                target=muscle.value,
                previous=muscle in previous_priorities,
                next=muscle in proposed_priorities,
                reason_codes=_change_reasons(
                    decision,
                    {
                        CycleAdaptationReasonCode.LAGGING_MUSCLE_SUPPORTED_CONSERVATIVELY,
                        CycleAdaptationReasonCode.PROGRESSING_MUSCLE_NOT_AUTOMATICALLY_INCREASED,
                        CycleAdaptationReasonCode.HIGH_ADHERENCE,
                        CycleAdaptationReasonCode.GOOD_RECOVERY,
                        CycleAdaptationReasonCode.PROGRESSION_ALLOWED,
                        CycleAdaptationReasonCode.PROGRESSION_HELD,
                    },
                ),
                provenance=provenance,
            )
        )

    schedule_previous: dict[str, int] = {}
    schedule_proposed: dict[str, int] = {}
    for field_name in ("training_days", "session_duration_minutes"):
        previous_value = getattr(previous, field_name)
        proposed_value = getattr(proposed, field_name)
        if previous_value != proposed_value:
            schedule_previous[field_name] = previous_value
            schedule_proposed[field_name] = proposed_value
    if schedule_previous:
        differences.append(
            CycleAdaptationDifference(
                change=CycleAdaptationChangeType.SCHEDULE,
                target="schedule",
                previous=schedule_previous,
                next=schedule_proposed,
                reason_codes=_change_reasons(
                    decision,
                    {
                        CycleAdaptationReasonCode.HIGH_ADHERENCE,
                        CycleAdaptationReasonCode.LOW_ADHERENCE,
                        CycleAdaptationReasonCode.PROGRESSION_ALLOWED,
                        CycleAdaptationReasonCode.PROGRESSION_HELD,
                    },
                ),
                provenance=provenance,
            )
        )

    _append_exercise_membership_differences(
        differences,
        decision,
        provenance,
        CycleAdaptationChangeType.EXERCISE_AVOIDANCE,
        previous.disliked_exercises,
        proposed.disliked_exercises,
        {
            CycleAdaptationReasonCode.PERSISTENT_EXERCISE_DISLIKE,
            CycleAdaptationReasonCode.PERSISTENT_EXERCISE_DISCOMFORT,
            CycleAdaptationReasonCode.PREFERENCE_OVERRIDDEN_BY_SAFETY,
        },
    )
    _append_exercise_membership_differences(
        differences,
        decision,
        provenance,
        CycleAdaptationChangeType.EQUIPMENT_CONSTRAINT,
        previous.unavailable_exercises,
        proposed.unavailable_exercises,
        {CycleAdaptationReasonCode.EQUIPMENT_UNAVAILABLE},
    )
    _append_exercise_membership_differences(
        differences,
        decision,
        provenance,
        CycleAdaptationChangeType.SAFETY_CONSTRAINT,
        previous.blocked_exercises,
        proposed.blocked_exercises,
        {
            CycleAdaptationReasonCode.PAIN_SIGNAL_PRESENT,
            CycleAdaptationReasonCode.REPEATED_PAIN_SIGNAL,
            CycleAdaptationReasonCode.EXERCISE_BLOCKED_FOR_SAFETY,
            CycleAdaptationReasonCode.SAFE_SUBSTITUTION_REQUIRED,
            CycleAdaptationReasonCode.PROGRESSION_HELD_FOR_SAFETY,
            CycleAdaptationReasonCode.PREFERENCE_OVERRIDDEN_BY_SAFETY,
        },
    )

    previous_replacements = {
        (item.original_exercise_id, item.replacement_exercise_id): item
        for item in previous.preferred_alternatives
    }
    proposed_replacements = {
        (item.original_exercise_id, item.replacement_exercise_id): item
        for item in proposed.preferred_alternatives
    }
    for pair in sorted(
        set(previous_replacements) | set(proposed_replacements),
        key=lambda value: (str(value[0]), str(value[1])),
    ):
        previous_item = previous_replacements.get(pair)
        proposed_item = proposed_replacements.get(pair)
        previous_replacement_value = _alternative_snapshot(previous_item)
        proposed_replacement_value = _alternative_snapshot(proposed_item)
        if previous_replacement_value == proposed_replacement_value:
            continue
        differences.append(
            CycleAdaptationDifference(
                change=CycleAdaptationChangeType.EXERCISE_REPLACEMENT,
                target=str(pair[0]),
                previous=previous_replacement_value,
                next=proposed_replacement_value,
                reason_codes=_change_reasons(
                    decision,
                    {
                        CycleAdaptationReasonCode.REPEATED_REPLACEMENT,
                        CycleAdaptationReasonCode.PREFERRED_ALTERNATIVE,
                        CycleAdaptationReasonCode.PREFERENCE_OVERRIDDEN_BY_SAFETY,
                        CycleAdaptationReasonCode.PREFERENCE_OVERRIDDEN_BY_AVAILABILITY,
                    },
                    extra=proposed_item.reason_codes if proposed_item else (),
                ),
                provenance=provenance,
            )
        )

    return tuple(
        sorted(
            differences,
            key=lambda item: (
                item.change.value,
                item.target,
                json.dumps(item.next, sort_keys=True, default=str),
            ),
        )
    )


def _append_exercise_membership_differences(
    differences: list[CycleAdaptationDifference],
    decision: CycleAdaptationDecision,
    provenance: CycleAdaptationProvenance,
    change: CycleAdaptationChangeType,
    previous_values: tuple[UUID, ...],
    proposed_values: tuple[UUID, ...],
    allowed_reasons: set[CycleAdaptationReasonCode],
) -> None:
    previous_set = set(previous_values)
    proposed_set = set(proposed_values)
    for exercise_id in sorted(previous_set ^ proposed_set, key=str):
        differences.append(
            CycleAdaptationDifference(
                change=change,
                target=str(exercise_id),
                previous=exercise_id in previous_set,
                next=exercise_id in proposed_set,
                reason_codes=_change_reasons(decision, allowed_reasons),
                provenance=provenance,
            )
        )


def _alternative_snapshot(
    alternative: CycleAdaptationPreferredAlternative | None,
) -> dict[str, object] | None:
    if alternative is None:
        return None
    return {
        "replacement_exercise_id": str(alternative.replacement_exercise_id),
        "strength": alternative.strength,
    }


def _change_reasons(
    decision: CycleAdaptationDecision,
    allowed: set[CycleAdaptationReasonCode],
    *,
    extra: tuple[CycleAdaptationReasonCode, ...] = (),
) -> tuple[CycleAdaptationReasonCode, ...]:
    reasons = list(extra)
    reasons.extend(code for code in decision.reason_codes if code in allowed)
    if not reasons:
        reasons.extend(decision.reason_codes)
    return tuple(dict.fromkeys(reasons))


def _comparison_provenance(
    decision: CycleAdaptationDecision,
    previous: CycleAdaptationProgramSnapshot,
    proposed: CycleAdaptationProgramSnapshot,
) -> CycleAdaptationProvenance:
    return decision.provenance.model_copy(
        update={
            "cycle_ids": _sorted_ids(
                set(decision.provenance.cycle_ids)
                | {value for value in (previous.cycle_id, proposed.cycle_id) if value}
            ),
            "workout_plan_ids": _sorted_ids(
                set(decision.provenance.workout_plan_ids)
                | {value for value in (previous.program_id, proposed.program_id) if value}
            ),
        }
    )


def _decision_trace(
    decision: CycleAdaptationDecision,
    differences: tuple[CycleAdaptationDifference, ...],
) -> tuple[dict[str, object], ...]:
    trace: list[dict[str, object]] = [
        {
            "stage": "cycle_adaptation",
            "action": decision.overall_action.value,
            "reason_codes": [code.value for code in decision.reason_codes],
            "provenance": decision.provenance.model_dump(mode="json"),
        }
    ]
    if differences:
        trace.append(
            {
                "stage": "difference_summary",
                "change_count": len(differences),
                "changes": [item.model_dump(mode="json") for item in differences],
            }
        )
    return tuple(trace)
