import hashlib
import json
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from enum import Enum
from uuid import UUID

from app.exercises.enums import ExerciseLabel, ExerciseType, MuscleGroup
from app.workouts.program_engine.duration_capacity import (
    SessionCapacity,
)
from app.workouts.program_engine.duration_policy import (
    SessionDurationPolicy,
    calculate_cardio_addon_minutes,
    calculate_main_training_minutes,
    calculate_main_training_minutes_from_exercises,
    calculate_total_session_minutes_from_exercises,
    get_session_duration_policy,
    get_session_exercise_count_policy,
    is_main_training_exercise,
)
from app.workouts.program_engine.effective_volume import calculate_effective_volume
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.equipment import effective_required_equipment
from app.workouts.program_engine.exercise_ranker import rank_exercises
from app.workouts.program_engine.exercise_semantics import has_near_equivalent
from app.workouts.program_engine.prescription import (
    ExercisePrescription,
    estimate_exercise_minutes,
    prescription_for,
)
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.safety import effective_caution_tags
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    ProgrammedExercise,
    RankedCandidate,
    WeeklyVolumePlan,
    WorkoutDay,
)
from app.workouts.program_engine.session_builder import exercise_fits_focus
from app.workouts.program_engine.session_coherence import (
    SessionCoherence,
    SessionCoherenceDecision,
    SessionMuscleRole,
    record_coherence_decision,
)
from app.workouts.program_engine.session_targets import english_session_title
from app.workouts.program_engine.strength_programming import (
    STRENGTH_PRIMARY_LIFT_SET_CAP_AUTHORIZED,
    StrengthExerciseRole,
    classify_strength_role,
    is_strength_set_cap_authorized,
)
from app.workouts.program_engine.supersets import (
    apply_duration_pressure_superset,
    apply_template_supersets,
)
from app.workouts.program_engine.supplemental_policy import (
    is_main_resistance_exercise,
    is_supplemental_muscle,
    main_exercise_count,
)
from app.workouts.program_engine.template_sessions import (
    adaptation_preservation_rank,
    template_removal_rank,
)
from app.workouts.program_engine.volume_policy import (
    session_hard_volume_cap,
    weekly_volume_constraint_maximum,
    weekly_volume_constraint_value,
)


@dataclass(frozen=True)
class SessionDurationRepairEvidence:
    """Immutable proof that one repaired session was inspected at a known shape."""

    day_index: int
    # Legacy field name retained for trace compatibility; value is canonical MAIN count.
    post_repair_exercise_count: int
    post_repair_main_training_minutes: int
    post_repair_total_session_minutes: int
    # Compatibility alias; it now has main-training semantics.
    post_repair_duration_minutes: int
    post_repair_exercise_fingerprint: str
    reason_codes: tuple[str, ...]

    @classmethod
    def from_day(
        cls,
        day: WorkoutDay,
        reason_codes: tuple[str, ...] = (),
    ) -> "SessionDurationRepairEvidence":
        return cls(
            day_index=day.day_index,
            post_repair_exercise_count=main_exercise_count(day.exercises),
            post_repair_main_training_minutes=calculate_main_training_minutes(day),
            post_repair_total_session_minutes=day.estimated_duration_minutes,
            post_repair_duration_minutes=calculate_main_training_minutes(day),
            post_repair_exercise_fingerprint=_resistance_session_fingerprint(day),
            reason_codes=tuple(dict.fromkeys(reason_codes)),
        )

    def matches(self, day: WorkoutDay) -> bool:
        current = SessionDurationRepairEvidence.from_day(day, self.reason_codes)
        current_cardio = calculate_cardio_addon_minutes(day) or 0
        total_matches = self.post_repair_total_session_minutes in {
            current.post_repair_total_session_minutes,
            current.post_repair_total_session_minutes - current_cardio,
        }
        return (
            self.day_index == current.day_index
            and self.post_repair_exercise_count == current.post_repair_exercise_count
            and self.post_repair_main_training_minutes == current.post_repair_main_training_minutes
            and total_matches
            and self.post_repair_exercise_fingerprint == current.post_repair_exercise_fingerprint
            and self.reason_codes == current.reason_codes
        )

    @classmethod
    def from_trace(cls, value: object) -> "SessionDurationRepairEvidence | None":
        if not isinstance(value, Mapping):
            return None
        day_index = value.get("day_index")
        exercise_count = value.get("post_repair_exercise_count")
        main_training = value.get("post_repair_main_training_minutes")
        duration = value.get("post_repair_duration_minutes")
        total_session = value.get("post_repair_total_session_minutes")
        raw_fingerprint = value.get("post_repair_exercise_fingerprint")
        raw_reasons = value.get("reason_codes")
        main_value = main_training if main_training is not None else duration
        if not (
            type(day_index) is int
            and day_index >= 0
            and type(exercise_count) is int
            and exercise_count >= 0
            and type(main_value) is int
            and main_value >= 0
            and (total_session is None or (type(total_session) is int and total_session >= 0))
            and isinstance(raw_fingerprint, str)
            and _is_session_fingerprint(raw_fingerprint)
            and isinstance(raw_reasons, (tuple, list))
        ):
            return None
        if not all(isinstance(reason, str) for reason in raw_reasons):
            return None
        evidence = cls(
            day_index=day_index,
            post_repair_exercise_count=exercise_count,
            post_repair_main_training_minutes=main_value,
            post_repair_total_session_minutes=(
                total_session if total_session is not None else main_value
            ),
            post_repair_duration_minutes=main_value,
            post_repair_exercise_fingerprint=raw_fingerprint,
            reason_codes=tuple(raw_reasons),
        )
        return evidence

    def as_trace(self) -> dict[str, object]:
        return {
            "day_index": self.day_index,
            "post_repair_exercise_count": self.post_repair_exercise_count,
            "post_repair_main_training_minutes": self.post_repair_main_training_minutes,
            "post_repair_total_session_minutes": self.post_repair_total_session_minutes,
            "post_repair_duration_minutes": self.post_repair_duration_minutes,
            "post_repair_exercise_fingerprint": self.post_repair_exercise_fingerprint,
            "reason_codes": self.reason_codes,
        }


_SESSION_FINGERPRINT_SCHEMA = "resistance_session_v1"


def _canonicalize_fingerprint_value(value: object) -> object:
    """Convert nested engine values into a deterministic JSON value."""
    if isinstance(value, Enum):
        return _canonicalize_fingerprint_value(value.value)
    if isinstance(value, UUID):
        return str(value)
    if is_dataclass(value):
        return {
            item.name: _canonicalize_fingerprint_value(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize_fingerprint_value(value[key]) for key in sorted(value, key=str)
        }
    if isinstance(value, (tuple, list)):
        return [_canonicalize_fingerprint_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        canonical_items = [_canonicalize_fingerprint_value(item) for item in value]
        return sorted(canonical_items, key=_canonical_fingerprint_json)
    return value


def _canonical_fingerprint_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _resistance_session_fingerprint(day: WorkoutDay) -> str:
    """Digest every resistance-relevant day and exercise field.

    Cardio is intentionally appended after duration repair, so it is excluded
    here and only its contribution to the day estimate is normalized away.
    """
    day_payload = {
        field.name: getattr(day, field.name) for field in fields(day) if field.name != "cardio"
    }
    day_payload["estimated_duration_minutes"] = max(
        0,
        day.estimated_duration_minutes
        - (day.cardio.duration_minutes if day.cardio is not None else 0),
    )
    day_payload["exercises"] = tuple(
        {field.name: getattr(exercise, field.name) for field in fields(exercise)}
        | {"strength_role": _programmed_strength_role(exercise).value}
        for exercise in day.exercises
    )
    canonical = _canonicalize_fingerprint_value(
        {"schema": _SESSION_FINGERPRINT_SCHEMA, "day": day_payload}
    )
    return hashlib.sha256(_canonical_fingerprint_json(canonical).encode("utf-8")).hexdigest()


def _is_session_fingerprint(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


@dataclass(frozen=True)
class DurationRepairResult:
    days: tuple[WorkoutDay, ...]
    reasons: tuple[str, ...]
    evidence: tuple[SessionDurationRepairEvidence, ...]
    coherence_decisions: tuple[SessionCoherenceDecision, ...] = ()

    def __iter__(self) -> Iterator[tuple[WorkoutDay, ...] | tuple[str, ...]]:
        """Preserve the historical ``days, reasons = ...`` call contract."""
        yield self.days
        yield self.reasons


def repair_session_durations(
    days: tuple[WorkoutDay, ...],
    request: NormalizedProgramRequest,
    candidates: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
    *,
    volume: WeeklyVolumePlan | None = None,
    prefer_acceptable_volume_for_minimum_fill: bool = False,
    session_capacity: SessionCapacity | None = None,
    _certification: bool = False,
) -> DurationRepairResult:
    """Repair real session estimates while preserving hard program constraints."""

    policy = get_session_duration_policy(request.source.session_duration_minutes)
    resistance_budget = request.source.session_duration_minutes  # pure resistance budget
    count_policy = get_session_exercise_count_policy(resistance_budget, ruleset)
    repaired: list[WorkoutDay] = []
    reasons: list[str] = []
    day_reason_codes: list[tuple[str, ...]] = []
    coherence_decisions: list[SessionCoherenceDecision] = []
    for day_index, day in enumerate(days):
        day_reason_start = len(reasons)
        # -------------------------------------------------------------------
        # Minimum exercises policy:
        #   30-min budget  → allow 3-4 when 5 cannot fit, floor = 3
        #   45+ min budget → minimum 5 (duration alone never lowers this)
        # -------------------------------------------------------------------
        if resistance_budget <= ruleset.short_session_minutes:
            capacity_floor = count_policy.minimum_main_exercises
            planned_minimum_exercises = (
                count_policy.minimum_main_exercises
                if prefer_acceptable_volume_for_minimum_fill
                and volume is not None
                and _duration_shortfall_is_hard_constrained(request, volume)
                else capacity_floor
            )
        else:
            # 45+ min: duration alone MUST NOT reduce below 5
            planned_minimum_exercises = count_policy.minimum_main_exercises

        template_adjusted: tuple[ProgrammedExercise, ...]
        template_superset_reasons: tuple[str, ...]
        if _certification:
            template_adjusted, template_superset_reasons = day.exercises, ()
        else:
            template_adjusted, template_superset_reasons = apply_template_supersets(day.exercises)
        reasons.extend(template_superset_reasons)
        current = _rebuild_day(day, template_adjusted, ruleset)
        current, capacity_trim_reasons = _trim_optional_capacity_overflow(current, ruleset)
        reasons.extend(capacity_trim_reasons)
        other_days = tuple(repaired) + days[day_index + 1 :]

        # Underfill repair is structural only.  A short session with a valid
        # MAIN exercise count is accepted as a preferred-range miss and is not
        # padded with extra sets or exercises.
        if main_exercise_count(current.exercises) < planned_minimum_exercises:
            reasons.append("SESSION_DURATION_UNDERFILLED")
            hard_volume_status: list[bool] = []
            current = _repair_underfill(
                current,
                request,
                candidates,
                policy,
                ruleset,
                other_days=other_days,
                volume=volume,
                prefer_acceptable_volume_for_minimum_fill=(
                    prefer_acceptable_volume_for_minimum_fill
                ),
                minimum_exercises=planned_minimum_exercises,
                hard_volume_status=hard_volume_status,
                coherence_decisions=coherence_decisions,
            )
            if hard_volume_status and hard_volume_status[0]:
                reasons.append("SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS")
            elif main_exercise_count(current.exercises) < planned_minimum_exercises:
                reasons.append("SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD")

        # Overfill is measured from main-training exercises only.  General
        # warm-up, anatomical core, and attached cardio are add-ons.
        if (
            calculate_main_training_minutes(current) > policy.maximum_minutes
            or main_exercise_count(current.exercises) > count_policy.maximum_main_exercises
        ):
            if calculate_main_training_minutes(current) > policy.maximum_minutes:
                reasons.append("SESSION_DURATION_OVERFILLED")
            current, overfill_reasons = _repair_overfill(
                current,
                request,
                policy,
                ruleset,
                minimum_exercises=planned_minimum_exercises,
                maximum_exercises=count_policy.maximum_main_exercises,
            )
            reasons.extend(overfill_reasons)

        main_training_after = calculate_main_training_minutes(current)
        # The lower target is a soft quality signal; only the upper target is
        # a hard duration invariant.
        if policy.exceeds_hard_maximum(main_training_after):
            reasons.extend(
                ("SESSION_DURATION_OVER_TARGET", "SESSION_DURATION_TARGET_UNSATISFIED")
            )
        elif policy.below_preferred_minimum(main_training_after):
            reasons.append("SESSION_DURATION_UNDER_TARGET")
            if volume is not None and _duration_shortfall_is_hard_constrained(request, volume):
                reasons.append("SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS")
            elif main_exercise_count(current.exercises) < planned_minimum_exercises:
                reasons.append("SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD")
        else:
            if current.estimated_duration_minutes != day.estimated_duration_minutes:
                reasons.append("SESSION_DURATION_REPAIR_APPLIED")
            reasons.append("SESSION_DURATION_TARGET_SATISFIED")

        repaired.append(current)
        day_reason_codes.append(tuple(dict.fromkeys(reasons[day_reason_start:])))

    repaired_tuple = _justify_duration_repeats(tuple(repaired))
    evidence_items: list[SessionDurationRepairEvidence] = []
    for index, day in enumerate(repaired_tuple):
        evidence_reasons = list(day_reason_codes[index])
        evidence_items.append(SessionDurationRepairEvidence.from_day(day, tuple(evidence_reasons)))
    evidence = tuple(evidence_items)
    return DurationRepairResult(
        days=repaired_tuple,
        reasons=tuple(dict.fromkeys(reasons)),
        evidence=evidence,
        coherence_decisions=tuple(coherence_decisions),
    )


def _trim_optional_capacity_overflow(
    day: WorkoutDay,
    ruleset: ProgramRuleset,
) -> tuple[WorkoutDay, tuple[str, ...]]:
    """Keep optional non-core tail work within the existing total exercise cap."""
    exercises = list(day.exercises)
    removed = False
    while len(exercises) > ruleset.max_exercises_per_session:
        optional = [
            (index, item)
            for index, item in enumerate(exercises)
            if "OPTIONAL_SUPPLEMENTAL_WORK" in item.reason_codes
            and item.exercise_type is not ExerciseType.CORE
        ]
        if not optional:
            break
        index, _ = min(
            optional,
            key=lambda pair: (-pair[1].estimated_minutes, str(pair[1].exercise_id)),
        )
        exercises.pop(index)
        removed = True
    if not removed:
        return day, ()
    return _rebuild_day(day, tuple(exercises), ruleset), ("SUPPLEMENTAL_WORK_TRIMMED_FOR_DURATION",)


def _repair_underfill(
    day: WorkoutDay,
    request: NormalizedProgramRequest,
    candidates: tuple[ExerciseCandidate, ...],
    policy: SessionDurationPolicy,
    ruleset: ProgramRuleset,
    *,
    other_days: tuple[WorkoutDay, ...],
    volume: WeeklyVolumePlan | None,
    prefer_acceptable_volume_for_minimum_fill: bool,
    minimum_exercises: int,
    hard_volume_status: list[bool] | None = None,
    coherence_decisions: list[SessionCoherenceDecision] | None = None,
) -> WorkoutDay:
    """Add safe main-training work only until the structural floor is satisfied."""
    exercises = list(day.exercises)
    while main_exercise_count(exercises) < minimum_exercises:
        addition = _select_exercise_addition(
            day,
            exercises,
            request,
            candidates,
            policy,
            ruleset,
            other_days=other_days,
            volume=volume,
            prefer_acceptable_volume_for_minimum_fill=(prefer_acceptable_volume_for_minimum_fill),
            minimum_exercises=minimum_exercises,
            coherence_decisions=coherence_decisions,
        )
        if addition is not None:
            muscle = addition.primary_muscle
            assert muscle is not None
            coherence = SessionCoherence.from_workout_day(day)
            record_coherence_decision(
                coherence_decisions,
                SessionCoherenceDecision(
                    stage="duration_repair",
                    muscle_requested=muscle,
                    candidate_day=day.day_index,
                    candidate_day_role=coherence.role_for(muscle),
                    status="accepted",
                    reason=_duration_coherence_reason(coherence, muscle),
                ),
            )
            exercises.append(addition)
            day = _rebuild_day(day, tuple(exercises), ruleset)
            continue
        # Cannot add a safe, useful, compatible exercise — stop.
        # Do NOT increase sets to substitute for missing exercise count.
        if volume is not None:
            strict_hard_status: list[bool] = []
            _select_exercise_addition(
                day,
                exercises,
                request,
                candidates,
                policy,
                ruleset,
                other_days=other_days,
                volume=volume,
                prefer_acceptable_volume_for_minimum_fill=False,
                minimum_exercises=minimum_exercises,
                hard_volume_rejection=strict_hard_status,
                coherence_decisions=coherence_decisions,
            )
            if hard_volume_status is not None and strict_hard_status == [True]:
                hard_volume_status.append(True)
        break
    return day


def _select_set_addition(
    day: WorkoutDay,
    exercises: list[ProgrammedExercise],
    request: NormalizedProgramRequest,
    policy: SessionDurationPolicy,
    ruleset: ProgramRuleset,
    *,
    other_days: tuple[WorkoutDay, ...],
    volume: WeeklyVolumePlan | None,
) -> tuple[int, ProgrammedExercise] | None:
    """Select one useful set without exceeding the hard duration or volume limits."""
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    coherence = SessionCoherence.from_workout_day(day)
    options: list[tuple[tuple[object, ...], int, ProgrammedExercise]] = []
    for index, exercise in enumerate(exercises):
        if not is_main_training_exercise(exercise) or exercise.primary_muscle is None:
            continue
        is_primary_strength = (
            request.primary_goal is Goal.STRENGTH
            and _programmed_strength_role(exercise) is StrengthExerciseRole.PRIMARY_STRENGTH
        )
        strength_set_cap_authorized = is_strength_set_cap_authorized(
            goal=request.primary_goal,
            exercise_type=exercise.exercise_type,
            exercise_slug=exercise.exercise_slug,
            is_primary_strength=is_primary_strength,
        )
        set_cap = ruleset.max_working_sets_for_exercise(
            training_status=request.training_status,
            goal=request.primary_goal,
            exercise_type=exercise.exercise_type,
            is_priority=exercise.primary_muscle in priority_policy.priorities,
            weekly_exposure_count=1,
            is_primary_strength=is_primary_strength,
            is_approved_primary_strength_lift=strength_set_cap_authorized,
        )
        if exercise.sets >= set_cap:
            continue
        direct_sets = sum(
            item.sets for item in exercises if item.primary_muscle is exercise.primary_muscle
        )
        sess_max = session_hard_volume_cap(request.source.training_age_months)
        if direct_sets + 1 > sess_max:
            continue
        updated = _with_additional_set(exercise, ruleset)
        updated = replace(
            updated,
            reason_codes=tuple(
                dict.fromkeys(
                    (
                        *updated.reason_codes,
                        _duration_coherence_reason(coherence, exercise.primary_muscle),
                    )
                )
            ),
        )
        simulated = [*exercises]
        simulated[index] = updated
        if calculate_main_training_minutes_from_exercises(simulated) > policy.maximum_minutes:
            continue
        weekly = [item for other_day in other_days for item in other_day.exercises] + simulated
        if not _within_weekly_hard_volume(weekly, ruleset, request, volume):
            continue
        options.append(
            (
                (
                    coherence.role_rank(exercise.primary_muscle),
                    priority_policy.precedence_key(exercise.primary_muscle),
                    adaptation_preservation_rank(exercise, priority_policy),
                    -exercise.estimated_minutes,
                    str(exercise.exercise_id),
                ),
                index,
                updated,
            )
        )
    if not options:
        return None
    selected = min(options, key=lambda item: item[0])
    return selected[1], selected[2]


# _select_rest_extension_for_underfill intentionally removed.
# Artificially extending rest merely to satisfy the duration floor is prohibited.
# The upper main-training limit remains hard; the lower target is a preferred
# quality signal. Fake rest time must not be used to satisfy it.


def _select_exercise_addition(
    day: WorkoutDay,
    exercises: list[ProgrammedExercise],
    request: NormalizedProgramRequest,
    candidates: tuple[ExerciseCandidate, ...],
    policy: SessionDurationPolicy,
    ruleset: ProgramRuleset,
    *,
    other_days: tuple[WorkoutDay, ...],
    volume: WeeklyVolumePlan | None,
    prefer_acceptable_volume_for_minimum_fill: bool,
    minimum_exercises: int,
    hard_volume_rejection: list[bool] | None = None,
    coherence_decisions: list[SessionCoherenceDecision] | None = None,
) -> ProgrammedExercise | None:
    if (
        main_exercise_count(exercises)
        >= get_session_exercise_count_policy(
            policy.requested_minutes, ruleset
        ).maximum_main_exercises
    ):
        return None
    existing_ids = {item.exercise_id for item in exercises}
    coherence = SessionCoherence.from_workout_day(day)
    for item in candidates:
        if (
            item.primary_muscle is not None
            and not is_supplemental_muscle(item.primary_muscle)
            and not coherence.allows_direct(item.primary_muscle)
        ):
            record_coherence_decision(
                coherence_decisions,
                SessionCoherenceDecision(
                    stage="duration_repair",
                    muscle_requested=item.primary_muscle,
                    candidate_day=day.day_index,
                    candidate_day_role=SessionMuscleRole.DISALLOWED,
                    status="rejected",
                    reason="SESSION_DIRECT_MUSCLE_OUTSIDE_FOCUS_REJECTED",
                ),
            )
    options = tuple(
        item
        for item in candidates
        if item.id not in existing_ids
        and not is_supplemental_muscle(item.primary_muscle)
        and coherence.allows_direct(item.primary_muscle)
        and (
            item.primary_muscle in day.template_target_muscles
            if day.focus.startswith("template_reference") and day.template_target_muscles
            else exercise_fits_focus(item, day.focus)
        )
        and _candidate_is_safe(item, request)
        and is_main_training_exercise(item)
        and ExerciseLabel.CARDIO not in item.labels
        and not has_near_equivalent(item, exercises)
    )
    training_days = len(other_days) + 1
    frequency_cap = ruleset.maximum_direct_sessions_per_muscle_per_week
    if training_days == 5:
        frequency_cap += 1
    elif training_days >= 6:
        frequency_cap += 2
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)

    def _candidate_ranking_key(item: RankedCandidate) -> tuple[object, ...]:
        candidate_exercise = item.exercise
        if candidate_exercise.primary_muscle is None:
            exceeds_frequency = 0
        else:
            other_frequency = sum(
                any(e.primary_muscle is candidate_exercise.primary_muscle for e in d.exercises)
                for d in other_days
            )
            has_cur = any(e.primary_muscle is candidate_exercise.primary_muscle for e in exercises)
            new_frequency = other_frequency + (0 if has_cur else 1)
            exceeds_frequency = 1 if (training_days >= 4 and new_frequency > frequency_cap) else 0
        return (
            exceeds_frequency,
            coherence.role_rank(candidate_exercise.primary_muscle),
            0
            if any(
                exercise.primary_muscle is candidate_exercise.primary_muscle
                for exercise in exercises
            )
            else 1,
            *priority_policy.precedence_key(item.exercise.primary_muscle),
            -item.score,
            str(item.exercise.id),
        )

    ranked = tuple(
        sorted(
            rank_exercises(request, options, ruleset),
            key=_candidate_ranking_key,
        )
    )
    hard_volume_fallback: ProgrammedExercise | None = None
    hard_volume_rejected = False
    for ranked_item in ranked:
        candidate = ranked_item.exercise
        if candidate.primary_muscle is None:
            continue
        direct_sets_for_muscle = sum(
            item.sets for item in exercises if item.primary_muscle is candidate.primary_muscle
        )
        sess_max = session_hard_volume_cap(request.source.training_age_months)
        strength_role = (
            classify_strength_role(candidate, request, ruleset)
            if request.primary_goal is Goal.STRENGTH
            else None
        )
        is_primary_strength = (
            strength_role is not None
            and strength_role.role is StrengthExerciseRole.PRIMARY_STRENGTH
        )
        strength_set_cap_authorized = is_strength_set_cap_authorized(
            goal=request.primary_goal,
            exercise_type=candidate.exercise_type,
            exercise_slug=candidate.slug,
            is_primary_strength=is_primary_strength,
        )
        sets = min(
            ruleset.minimum_working_sets,
            sess_max,
            ruleset.max_working_sets_for_exercise(
                training_status=request.training_status,
                goal=request.primary_goal,
                exercise_type=candidate.exercise_type,
                is_priority=candidate.primary_muscle in priority_policy.priorities,
                weekly_exposure_count=1,
                is_primary_strength=is_primary_strength,
                is_approved_primary_strength_lift=strength_set_cap_authorized,
            ),
        )
        if sets < 1:
            continue
        if direct_sets_for_muscle + sets > sess_max:
            continue
        prescription = prescription_for(
            request.primary_goal,
            candidate.exercise_type,
            request.training_status,
            ruleset,
            prescription_mode=candidate.prescription_mode,
            duration_min_seconds=candidate.duration_min_seconds,
            duration_max_seconds=candidate.duration_max_seconds,
            strength_role=strength_role.role if strength_role is not None else None,
            fatigue_cost=candidate.fatigue_cost,
        )
        estimated = estimate_exercise_minutes(sets, prescription.rest_seconds, 0, ruleset)
        repeated = any(
            item.exercise_id == candidate.id
            for other_day in other_days
            for item in other_day.exercises
        )
        ranked_reasons = ranked_item.reason_codes + (
            (STRENGTH_PRIMARY_LIFT_SET_CAP_AUTHORIZED,)
            if strength_set_cap_authorized
            else ()
        ) + (_duration_coherence_reason(coherence, candidate.primary_muscle),)
        programmed = _program_candidate(
            candidate,
            sets,
            estimated,
            ranked_reasons,
            prescription,
            ruleset,
            repeated=repeated,
        )
        simulated = [*exercises, programmed]
        if calculate_main_training_minutes_from_exercises(simulated) > policy.maximum_minutes:
            continue
        weekly_exercises = [item for day in other_days for item in day.exercises] + simulated
        within_hard_volume = _within_weekly_hard_volume(weekly_exercises, ruleset, request, volume)
        if not within_hard_volume:
            hard_volume_rejected = True
        if main_exercise_count(exercises) < minimum_exercises and within_hard_volume:
            return simulated[-1]
        if _acceptable_volume_change(
            [item for day in other_days for item in day.exercises] + exercises,
            weekly_exercises,
            ruleset,
            request,
            volume,
        ):
            return simulated[-1]
        if (
            hard_volume_fallback is None
            and main_exercise_count(exercises) < minimum_exercises
            and within_hard_volume
        ):
            hard_volume_fallback = simulated[-1]
    if hard_volume_rejection is not None:
        hard_volume_rejection.append(hard_volume_rejected)
    return hard_volume_fallback


def _duration_coherence_reason(
    coherence: SessionCoherence,
    muscle: MuscleGroup,
) -> str:
    if coherence.role_for(muscle) is SessionMuscleRole.PRIMARY:
        return "DURATION_REPAIR_PRIMARY_BLOCK_EXTENDED"
    return "SESSION_GROUPED_MUSCLE_FALLBACK"


def _programmed_strength_role(exercise: ProgrammedExercise) -> StrengthExerciseRole:
    if "STRENGTH_PRIMARY_COMPOUND" in exercise.reason_codes:
        return StrengthExerciseRole.PRIMARY_STRENGTH
    if "STRENGTH_SECONDARY_COMPOUND" in exercise.reason_codes:
        return StrengthExerciseRole.SECONDARY_COMPOUND
    return StrengthExerciseRole.ACCESSORY


def _duration_shortfall_is_hard_constrained(
    request: NormalizedProgramRequest,
    volume: WeeklyVolumePlan,
) -> bool:
    return bool(
        set(volume.reason_codes).intersection(
            {
                "VOLUME_REDUCED_FOR_RECOVERY",
                "VOLUME_REDUCED_FOR_TIME_LIMIT",
                "VOLUME_CAPPED_FOR_SPLIT_FREQUENCY",
                "VOLUME_CAPPED_FOR_PREVIOUS_EFFECTIVE_VOLUME",
                "VOLUME_CAPPED_FOR_PREVIOUS_VOLUME",
            }
        )
        or request.constraints.blocked_exercises
        or request.constraints.blocked_movement_patterns
        or request.constraints.blocked_caution_tags
        or request.constraints.allowed_range_of_motion
        or request.resistance_training_days >= 5
    )


def _repair_overfill(
    day: WorkoutDay,
    request: NormalizedProgramRequest,
    policy: SessionDurationPolicy,
    ruleset: ProgramRuleset,
    *,
    minimum_exercises: int,
    maximum_exercises: int | None = None,
) -> tuple[WorkoutDay, tuple[str, ...]]:
    exercises = list(day.exercises)
    reasons: list[str] = []
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    effective_maximum_exercises = (
        ruleset.max_exercises_per_session if maximum_exercises is None else maximum_exercises
    )
    while main_exercise_count(exercises) > effective_maximum_exercises:
        removable = [
            (index, item)
            for index, item in enumerate(exercises)
            if is_main_resistance_exercise(item)
            and not any(code.startswith("REQUIRED_") for code in item.reason_codes)
            and template_removal_rank(item) < 3
            and priority_policy.preservation_rank(item.primary_muscle) == 0
            and (
                template_removal_rank(item) in {0, 1}
                or "SESSION_SIZE_ACCESSORY" in item.reason_codes
                or "OPTIONAL_SUPPLEMENTAL_WORK" in item.reason_codes
            )
        ]
        if not removable:
            break
        index, removed = min(
            removable,
            key=lambda pair: (
                adaptation_preservation_rank(pair[1], priority_policy),
                -pair[1].estimated_minutes,
                str(pair[1].exercise_id),
            ),
        )
        exercises.pop(index)
        reasons.append("MAIN_EXERCISE_TRIMMED_FOR_COUNT")
        day = _rebuild_day(day, tuple(exercises), ruleset)
    while calculate_main_training_minutes(day) > policy.maximum_minutes:
        low_value_removable = [
            (index, item)
            for index, item in enumerate(exercises)
            if is_main_training_exercise(item)
            and (
                is_supplemental_muscle(item.primary_muscle)
                or (
                    _can_remove_for_floor(item, exercises, minimum_exercises)
                    and not any(code.startswith("REQUIRED_") for code in item.reason_codes)
                    and template_removal_rank(item) < 3
                    and priority_policy.preservation_rank(item.primary_muscle) == 0
                    and (
                        template_removal_rank(item) in {0, 1}
                        or "SESSION_SIZE_ACCESSORY" in item.reason_codes
                        or "OPTIONAL_SUPPLEMENTAL_WORK" in item.reason_codes
                    )
                )
            )
        ]
        if low_value_removable:
            index, removed = min(
                low_value_removable,
                key=lambda pair: (
                    not is_supplemental_muscle(pair[1].primary_muscle),
                    adaptation_preservation_rank(pair[1], priority_policy),
                    -pair[1].estimated_minutes,
                    str(pair[1].exercise_id),
                ),
            )
            exercises.pop(index)
            if is_supplemental_muscle(removed.primary_muscle):
                reasons.append("SUPPLEMENTAL_WORK_TRIMMED_FOR_DURATION")
            day = _rebuild_day(day, tuple(exercises), ruleset)
            continue
        options = [
            (index, item)
            for index, item in enumerate(exercises)
            if is_main_training_exercise(item)
            and item.sets > ruleset.minimum_working_sets
            and not any(code.startswith("REQUIRED_") for code in item.reason_codes)
            and template_removal_rank(item) < 3
            and priority_policy.preservation_rank(item.primary_muscle) == 0
        ]
        if options:
            index, item = min(
                options,
                key=lambda pair: (
                    adaptation_preservation_rank(pair[1], priority_policy),
                    "SESSION_SIZE_ACCESSORY" not in pair[1].reason_codes,
                    pair[1].sets,
                    -pair[1].estimated_minutes,
                    str(pair[1].exercise_id),
                ),
            )
            exercises[index] = _with_fewer_sets(item, ruleset)
            day = _rebuild_day(day, tuple(exercises), ruleset)
            continue
        removable = [
            (index, item)
            for index, item in enumerate(exercises)
            if is_main_training_exercise(item)
            and _can_remove_for_floor(item, exercises, minimum_exercises)
            and not any(code.startswith("REQUIRED_") for code in item.reason_codes)
            and template_removal_rank(item) < 3
            and priority_policy.preservation_rank(item.primary_muscle) == 0
        ]
        if not removable:
            supersetted, superset_reasons = apply_duration_pressure_superset(
                tuple(exercises), request, ruleset
            )
            if superset_reasons and _non_main_shape(supersetted) == _non_main_shape(
                tuple(exercises)
            ):
                exercises = list(supersetted)
                reasons.extend(superset_reasons)
                day = _rebuild_day(day, tuple(exercises), ruleset)
                continue
            rest_reduction = _select_rest_reduction_for_overfill(
                exercises,
                request,
                priority_policy,
                ruleset,
            )
            if rest_reduction is None:
                break
            index, updated = rest_reduction
            exercises[index] = updated
            day = _rebuild_day(day, tuple(exercises), ruleset)
            continue
        index, _ = min(
            removable,
            key=lambda pair: (
                adaptation_preservation_rank(pair[1], priority_policy),
                "SESSION_SIZE_ACCESSORY" not in pair[1].reason_codes,
                -pair[1].estimated_minutes,
                str(pair[1].exercise_id),
            ),
        )
        exercises.pop(index)
        day = _rebuild_day(day, tuple(exercises), ruleset)
    return day, tuple(dict.fromkeys(reasons))


def _non_main_shape(
    exercises: tuple[ProgrammedExercise, ...],
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.exercise_id,
            item.exercise_type,
            item.sets,
            item.rest_seconds,
            item.estimated_minutes,
        )
        for item in exercises
        if not is_main_training_exercise(item)
    )


def _can_remove_for_floor(
    exercise: ProgrammedExercise,
    exercises: list[ProgrammedExercise],
    minimum_exercises: int,
) -> bool:
    return is_supplemental_muscle(exercise.primary_muscle) or (
        main_exercise_count(exercises) > minimum_exercises
    )


def _select_rest_reduction_for_overfill(
    exercises: list[ProgrammedExercise],
    request: NormalizedProgramRequest,
    priority_policy: PriorityAllocationPolicy,
    ruleset: ProgramRuleset,
) -> tuple[int, ProgrammedExercise] | None:
    options: list[tuple[int, int, int, str, int, ProgrammedExercise]] = []
    for index, exercise in enumerate(exercises):
        if not is_main_training_exercise(exercise):
            continue
        minimum_rest = _duration_repair_minimum_rest(exercise, request, ruleset)
        if exercise.rest_seconds <= minimum_rest:
            continue
        rest_seconds = max(
            minimum_rest,
            exercise.rest_seconds - ruleset.duration_repair_rest_increment_seconds,
        )
        updated = replace(
            exercise,
            rest_seconds=rest_seconds,
            estimated_minutes=_estimate_preserving_time_saving(
                exercise,
                sets=exercise.sets,
                rest_seconds=rest_seconds,
                ruleset=ruleset,
            ),
            reason_codes=tuple(
                dict.fromkeys(exercise.reason_codes + ("ACCESSORY_REST_REDUCED_FOR_DURATION",))
            ),
        )
        options.append(
            (
                adaptation_preservation_rank(exercise, priority_policy),
                exercise.exercise_type is not ExerciseType.ISOLATION,
                -exercise.rest_seconds,
                str(exercise.exercise_id),
                index,
                updated,
            )
        )
    if not options:
        return None
    selected = min(options)
    return selected[4], selected[5]


def _duration_repair_minimum_rest(
    exercise: ProgrammedExercise,
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> int:
    return prescription_for(
        request.primary_goal,
        exercise.exercise_type,
        request.training_status,
        ruleset,
        prescription_mode=exercise.prescription_mode,
        duration_min_seconds=exercise.duration_min_seconds,
        duration_max_seconds=exercise.duration_max_seconds,
        strength_role=(
            _programmed_strength_role(exercise) if request.primary_goal is Goal.STRENGTH else None
        ),
    ).minimum_rest_seconds


def _program_candidate(
    candidate: ExerciseCandidate,
    sets: int,
    estimated: int,
    ranked_reasons: tuple[str, ...],
    prescription: ExercisePrescription,
    ruleset: ProgramRuleset,
    *,
    repeated: bool = False,
) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=candidate.id,
        exercise_name=candidate.name,
        order=1,
        sets=sets,
        rep_min=prescription.rep_min,
        rep_max=prescription.rep_max,
        target_rir=prescription.target_rir,
        rest_seconds=prescription.rest_seconds,
        estimated_minutes=estimated,
        reason_codes=(
            *ranked_reasons,
            *(("CORE_MOVEMENT_REPEATED_FOR_PROGRESSION",) if repeated else ()),
            "SESSION_SIZE_ACCESSORY",
            "SESSION_DURATION_REPAIR_APPLIED",
        ),
        prescription_mode=prescription.mode,
        duration_min_seconds=prescription.duration_min_seconds,
        duration_max_seconds=prescription.duration_max_seconds,
        movement_pattern=candidate.movement_pattern,
        primary_muscle=candidate.primary_muscle,
        secondary_muscles=candidate.secondary_muscles,
        equipment=candidate.equipment,
        caution_tags=candidate.caution_tags,
        range_of_motion_profile=candidate.range_of_motion_profile,
        impact_level=candidate.impact_level,
        axial_loading_level=candidate.axial_loading_level,
        stability_demand=candidate.stability_demand,
        muscle_focus=candidate.muscle_focus,
        body_position=candidate.body_position,
        laterality=candidate.laterality,
        substitution_group=candidate.substitution_group,
        exercise_slug=candidate.slug,
        is_active=candidate.is_active,
        is_programmable=candidate.is_programmable,
        needs_review=candidate.needs_review,
        exercise_type=candidate.exercise_type,
        counts_toward_volume=True,
    )


def _with_additional_set(
    exercise: ProgrammedExercise, ruleset: ProgramRuleset
) -> ProgrammedExercise:
    sets = exercise.sets + 1
    return replace(
        exercise,
        sets=sets,
        estimated_minutes=_estimate_preserving_time_saving(
            exercise,
            sets=sets,
            rest_seconds=exercise.rest_seconds,
            ruleset=ruleset,
        ),
        reason_codes=exercise.reason_codes + ("SESSION_DURATION_REPAIR_APPLIED",),
    )


def _with_fewer_sets(exercise: ProgrammedExercise, ruleset: ProgramRuleset) -> ProgrammedExercise:
    sets = exercise.sets - 1
    return replace(
        exercise,
        sets=sets,
        estimated_minutes=_estimate_preserving_time_saving(
            exercise,
            sets=sets,
            rest_seconds=exercise.rest_seconds,
            ruleset=ruleset,
        ),
        reason_codes=exercise.reason_codes + ("SESSION_DURATION_REPAIR_APPLIED",),
    )


def _candidate_is_safe(candidate: ExerciseCandidate, request: NormalizedProgramRequest) -> bool:
    return (
        candidate.is_active
        and candidate.is_programmable
        and not candidate.needs_review
        and candidate.id not in request.constraints.blocked_exercises
        and candidate.movement_pattern not in request.constraints.blocked_movement_patterns
        and not effective_caution_tags(candidate).intersection(
            request.constraints.blocked_caution_tags
        )
        and effective_required_equipment(candidate.equipment, candidate.movement_pattern).issubset(
            request.constraints.available_equipment
        )
    )


def _estimate_preserving_time_saving(
    exercise: ProgrammedExercise,
    *,
    sets: int,
    rest_seconds: int,
    ruleset: ProgramRuleset,
) -> int:
    straight_before = estimate_exercise_minutes(
        exercise.sets,
        exercise.rest_seconds,
        exercise.warmup_sets,
        ruleset,
    )
    existing_saving = (
        max(0, straight_before - exercise.estimated_minutes)
        if "SAFE_SUPERSET_DURATION_SAVING" in exercise.reason_codes
        else 0
    )
    straight_after = estimate_exercise_minutes(
        sets,
        rest_seconds,
        exercise.warmup_sets,
        ruleset,
    )
    return max(1, straight_after - existing_saving)


def _within_weekly_hard_volume(
    exercises: list[ProgrammedExercise],
    ruleset: ProgramRuleset,
    request: NormalizedProgramRequest,
    volume: WeeklyVolumePlan | None,
) -> bool:
    effective = calculate_effective_volume(exercises, ruleset)
    legacy_maximum = ruleset.maximum_sets[request.training_status]
    for muscle_key in set(effective.direct_sets_by_muscle).union(
        effective.effective_sets_by_muscle
    ):
        muscle = _muscle_group(muscle_key)
        if muscle is None:
            actual = effective.effective_sets_by_muscle.get(muscle_key, 0)
            maximum = legacy_maximum
        else:
            actual = _weekly_constraint_value_for_key(
                muscle_key,
                effective.direct_sets_by_muscle,
                effective.effective_sets_by_muscle,
                request,
            )
            maximum = weekly_volume_constraint_maximum(
                muscle,
                request.source.training_age_months,
                legacy_maximum,
            )
        if actual > maximum:
            return False
    if volume is None:
        return True
    return all(
        _weekly_constraint_value_for_key(
            target.muscle.value,
            effective.direct_sets_by_muscle,
            effective.effective_sets_by_muscle,
            request,
        )
        <= target.maximum_hard
        for target in volume.targets
    )


def _within_weekly_acceptable_volume(
    exercises: list[ProgrammedExercise],
    ruleset: ProgramRuleset,
    request: NormalizedProgramRequest,
    volume: WeeklyVolumePlan | None,
) -> bool:
    if not _within_weekly_hard_volume(exercises, ruleset, request, volume):
        return False
    if volume is None:
        return True
    effective = calculate_effective_volume(exercises, ruleset)
    return all(
        _weekly_constraint_value_for_key(
            target.muscle.value,
            effective.direct_sets_by_muscle,
            effective.effective_sets_by_muscle,
            request,
        )
        <= target.acceptable_maximum
        for target in volume.targets
    )


def _acceptable_volume_change(
    before: list[ProgrammedExercise],
    after: list[ProgrammedExercise],
    ruleset: ProgramRuleset,
    request: NormalizedProgramRequest,
    volume: WeeklyVolumePlan | None,
) -> bool:
    if not _within_weekly_hard_volume(after, ruleset, request, volume):
        return False
    if volume is None:
        return True
    before_effective = calculate_effective_volume(before, ruleset)
    after_effective = calculate_effective_volume(after, ruleset)
    return all(
        _weekly_constraint_value_for_key(
            target.muscle.value,
            after_effective.direct_sets_by_muscle,
            after_effective.effective_sets_by_muscle,
            request,
        )
        <= target.acceptable_maximum
        or _weekly_constraint_value_for_key(
            target.muscle.value,
            after_effective.direct_sets_by_muscle,
            after_effective.effective_sets_by_muscle,
            request,
        )
        <= _weekly_constraint_value_for_key(
            target.muscle.value,
            before_effective.direct_sets_by_muscle,
            before_effective.effective_sets_by_muscle,
            request,
        )
        for target in volume.targets
    )


def _within_weekly_minimum_volume(
    exercises: list[ProgrammedExercise],
    ruleset: ProgramRuleset,
    volume: WeeklyVolumePlan | None,
) -> bool:
    if volume is None:
        return True
    effective = calculate_effective_volume(exercises, ruleset)
    return all(
        (
            not target.direct_minimum_required
            or effective.direct_sets_by_muscle.get(target.muscle.value, 0)
            >= target.minimum_direct_sets
        )
        and (
            not target.minimum_coverage_required
            or effective.effective_sets_by_muscle.get(target.muscle.value, 0)
            >= target.minimum_effective_sets
        )
        for target in volume.targets
    )


def _muscle_group(value: str) -> MuscleGroup | None:
    try:
        return MuscleGroup(value)
    except ValueError:
        return None


def _weekly_constraint_value_for_key(
    muscle_key: str,
    direct_sets: Mapping[str, int],
    effective_sets: Mapping[str, float],
    request: NormalizedProgramRequest,
) -> int | float:
    muscle = _muscle_group(muscle_key)
    if muscle is None:
        return effective_sets.get(muscle_key, 0)
    return weekly_volume_constraint_value(
        muscle,
        request.source.training_age_months,
        direct_sets=direct_sets.get(muscle_key, 0),
        effective_sets=effective_sets.get(muscle_key, 0),
    )


def _justify_duration_repeats(days: tuple[WorkoutDay, ...]) -> tuple[WorkoutDay, ...]:
    duration_repaired_ids = {
        item.exercise_id
        for day in days
        for item in day.exercises
        if "SESSION_DURATION_REPAIR_APPLIED" in item.reason_codes
    }
    seen: set[object] = set()
    updated_days: list[WorkoutDay] = []
    for day in days:
        exercises: list[ProgrammedExercise] = []
        for item in day.exercises:
            if item.exercise_id in duration_repaired_ids and item.exercise_id in seen:
                item = replace(
                    item,
                    reason_codes=tuple(
                        dict.fromkeys(
                            item.reason_codes + ("CORE_MOVEMENT_REPEATED_FOR_PROGRESSION",)
                        )
                    ),
                )
            seen.add(item.exercise_id)
            exercises.append(item)
        updated_days.append(replace(day, exercises=tuple(exercises)))
    return tuple(updated_days)


def _weekly_exposure_count(days: tuple[WorkoutDay, ...]) -> Counter[MuscleGroup]:
    return Counter(
        muscle
        for day in days
        for muscle in {
            item.primary_muscle for item in day.exercises if item.primary_muscle is not None
        }
    )


def _rebuild_day_for_exercises(exercises: list[ProgrammedExercise]) -> WorkoutDay:
    return WorkoutDay(
        day_index=0,
        weekday=None,
        title="",
        focus="",
        estimated_duration_minutes=0,
        exercises=tuple(exercises),
    )


def _rebuild_day(
    original: WorkoutDay,
    exercises: tuple[ProgrammedExercise, ...],
    ruleset: ProgramRuleset,
) -> WorkoutDay:
    ordered = tuple(replace(item, order=index + 1) for index, item in enumerate(exercises))
    return replace(
        original,
        exercises=ordered,
        title=english_session_title(original.day_index, ordered),
        estimated_duration_minutes=calculate_total_session_minutes_from_exercises(
            ordered,
            ruleset.general_warmup_minutes,
            calculate_cardio_addon_minutes(original) or 0,
        ),
    )
