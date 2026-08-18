from dataclasses import replace

from app.workouts.program_engine.enums import (
    Goal,
    PhysicalJobDemand,
    RecoveryRating,
    SplitType,
    TrainingStatus,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    NormalizedProgramRequest,
    SplitCandidate,
    SplitPlan,
)


def select_split(request: NormalizedProgramRequest, ruleset: ProgramRuleset) -> SplitPlan:
    available_days = min(request.resistance_training_days, ruleset.max_resistance_days)
    recovery_limited = _recovery_is_limited(request)
    preferred_days = min(
        available_days,
        ruleset.recommended_resistance_days[request.training_status],
    )
    if recovery_limited:
        preferred_days = max(1, preferred_days - ruleset.poor_recovery_session_reduction)
    if request.training_status is TrainingStatus.NOVICE and recovery_limited:
        preferred_days = min(preferred_days, ruleset.maximum_novice_recovery_days)

    candidates = tuple(
        candidate
        for days in range(1, available_days + 1)
        for candidate in generate_split_candidates(days)
    )
    scored = score_split_candidates(request, candidates, ruleset, preferred_days)
    selected = scored[0]
    reasons = list(selected.reason_codes)
    if request.source.available_training_days > ruleset.max_resistance_days:
        reasons.append("RESISTANCE_DAYS_CAPPED_AT_RULESET_MAXIMUM")
    if len(selected.day_focuses) < request.source.available_training_days:
        reasons.append("SPLIT_SELECTED_FOR_APPROPRIATE_SESSION_COUNT")
    if recovery_limited and len(selected.day_focuses) < available_days:
        reasons.append("SPLIT_REDUCED_FOR_RECOVERY")
    return replace(selected, reason_codes=tuple(dict.fromkeys(reasons)))


def generate_split_candidates(days: int) -> tuple[SplitCandidate, ...]:
    structures: dict[int, tuple[SplitCandidate, ...]] = {
        1: (SplitCandidate(SplitType.FULL_BODY, ("full_body",)),),
        2: (
            SplitCandidate(
                SplitType.FULL_BODY_AB,
                ("full_body_a", "full_body_b"),
            ),
        ),
        3: (
            SplitCandidate(
                SplitType.FULL_BODY_ABC,
                ("full_body_a", "full_body_b", "full_body_c"),
            ),
        ),
        4: (
            SplitCandidate(
                SplitType.UPPER_LOWER,
                ("upper", "lower", "upper", "lower"),
            ),
            SplitCandidate(
                SplitType.FULL_BODY_FOUR,
                ("full_body", "full_body_b", "full_body_c", "full_body_d"),
            ),
            SplitCandidate(
                SplitType.UPPER_LOWER_FULL,
                ("upper", "lower", "full_body", "full_body"),
            ),
            SplitCandidate(
                SplitType.PHUL,
                ("upper", "lower", "upper", "lower"),
            ),
            SplitCandidate(
                SplitType.BODY_PART_ROTATION,
                ("chest_triceps", "back_biceps", "legs", "shoulders_traps"),
            ),
        ),
        5: (
            SplitCandidate(
                SplitType.UPPER_LOWER_SPECIALIZATION,
                ("upper", "lower", "upper", "lower", "specialization"),
            ),
            SplitCandidate(
                SplitType.PUSH_PULL_LEGS_UPPER_LOWER,
                ("push", "pull", "legs", "upper", "lower"),
            ),
            SplitCandidate(
                SplitType.BODY_PART_ROTATION,
                ("chest_triceps", "back_biceps", "shoulders_traps", "legs", "specialization"),
            ),
        ),
        6: (
            SplitCandidate(
                SplitType.PUSH_PULL_LEGS_X2,
                ("push", "pull", "legs", "push", "pull", "legs"),
            ),
            SplitCandidate(
                SplitType.UPPER_LOWER_X3,
                ("upper", "lower", "upper", "lower", "upper", "lower"),
            ),
            SplitCandidate(
                SplitType.BODY_PART_ROTATION,
                (
                    "chest_triceps",
                    "back_biceps",
                    "quadriceps_calves",
                    "shoulders_traps",
                    "posterior_chain_core",
                    "specialization",
                ),
            ),
        ),
    }
    if days not in structures:
        raise ValueError("split candidates require one through six resistance days")
    return structures[days]


def score_split_candidates(
    request: NormalizedProgramRequest,
    candidates: tuple[SplitCandidate, ...],
    ruleset: ProgramRuleset,
    preferred_days: int | None = None,
) -> tuple[SplitPlan, ...]:
    weights = ruleset.split_weights
    scored: list[tuple[SplitPlan, int]] = []
    recovery_limited = _recovery_is_limited(request)
    goal_specific = request.primary_goal in {
        Goal.HYPERTROPHY,
        Goal.MUSCLE_GAIN,
        Goal.STRENGTH,
    }
    for candidate in candidates:
        complexity = ruleset.split_complexity[candidate.split_type]
        score = weights["base"] - complexity
        reasons: list[str] = []
        if preferred_days is not None:
            score -= (
                abs(len(candidate.day_focuses) - preferred_days)
                * ruleset.session_count_distance_penalty
            )
        full_body = candidate.split_type in {
            SplitType.FULL_BODY,
            SplitType.FULL_BODY_AB,
            SplitType.FULL_BODY_ABC,
            SplitType.FULL_BODY_FOUR,
        }
        if request.training_status is TrainingStatus.NOVICE and full_body:
            score += weights["simplicity"]
            reasons.append("SPLIT_SIMPLIFIED_FOR_NOVICE")
        if full_body and len(candidate.day_focuses) <= 3:
            reasons.append("SPLIT_FULL_BODY_FOR_LOW_FREQUENCY")
        if candidate.split_type in {
            SplitType.UPPER_LOWER,
            SplitType.UPPER_LOWER_SPECIALIZATION,
            SplitType.PUSH_PULL_LEGS_UPPER_LOWER,
            SplitType.PUSH_PULL_LEGS_X2,
            SplitType.UPPER_LOWER_X3,
            SplitType.PHUL,
        }:
            score += weights["twice_weekly_frequency"]
            reasons.append("SPLIT_SELECTED_FOR_TWICE_WEEKLY_EXPOSURE")
        if goal_specific and candidate.split_type in {
            SplitType.UPPER_LOWER_FULL,
            SplitType.UPPER_LOWER,
            SplitType.UPPER_LOWER_SPECIALIZATION,
            SplitType.PUSH_PULL_LEGS_UPPER_LOWER,
            SplitType.PUSH_PULL_LEGS_X2,
            SplitType.PHUL,
        }:
            score += weights["goal_specificity"]
            reasons.append("SPLIT_SELECTED_FOR_GOAL_SPECIFICITY")
        if (
            request.source.priority_muscles
            and candidate.split_type is SplitType.UPPER_LOWER_SPECIALIZATION
        ):
            score += weights["priority_specialization"]
            reasons.append("SPLIT_SELECTED_FOR_PRIORITY_MUSCLE")
        if (
            request.source.session_duration_minutes <= ruleset.short_session_minutes
            and candidate.split_type is SplitType.FULL_BODY_FOUR
        ):
            score += weights["short_session_full_body"]
            reasons.append("SPLIT_SELECTED_FOR_SHORT_SESSIONS")
        if recovery_limited:
            score -= complexity * weights["recovery_complexity_penalty"]
        if (
            request.training_status is not TrainingStatus.ADVANCED
            and candidate.split_type is SplitType.UPPER_LOWER_X3
        ):
            score += weights["simplicity"]
        if (
            request.training_status is TrainingStatus.ADVANCED
            and candidate.split_type is SplitType.PUSH_PULL_LEGS_X2
        ):
            score += weights["goal_specificity"]
            reasons.append("SPLIT_SELECTED_FOR_ADVANCED_STATUS")
        if (
            candidate.split_type is SplitType.PHUL
            and request.primary_goal
            in {
                Goal.HYPERTROPHY,
                Goal.MUSCLE_GAIN,
                Goal.STRENGTH,
            }
            and request.training_status is TrainingStatus.ADVANCED
        ):
            score += ruleset.phul_bonus
            reasons.append("SPLIT_SELECTED_FOR_PERIODIZED_UPPER_LOWER")
        if candidate.split_type is SplitType.BODY_PART_ROTATION and (
            len(candidate.day_focuses) < 6
            or (request.training_status is TrainingStatus.ADVANCED and not recovery_limited)
        ):
            score += ruleset.body_part_rotation_bonus
            reasons.append("SPLIT_SELECTED_FOR_SPECIALIZED_DIRECT_TARGETS")

        weekdays = _select_weekdays(
            len(candidate.day_focuses),
            request.source.preferred_weekdays,
            candidate.day_focuses,
            ruleset,
        )
        if len(request.source.preferred_weekdays) >= len(
            candidate.day_focuses
        ) and weekdays != tuple(
            sorted(request.source.preferred_weekdays[: len(candidate.day_focuses)])
        ):
            reasons.append("SPLIT_PREFERRED_DAYS_ADJUSTED_FOR_RECOVERY")
        scored.append(
            (
                SplitPlan(
                    split_type=candidate.split_type,
                    day_focuses=candidate.day_focuses,
                    weekdays=weekdays,
                    score=score,
                    reason_codes=tuple(dict.fromkeys(reasons)),
                ),
                complexity,
            )
        )
    scored.sort(key=lambda item: (-item[0].score, item[1], item[0].split_type.value))
    return tuple(item[0] for item in scored)


def _recovery_is_limited(request: NormalizedProgramRequest) -> bool:
    source = request.source
    return (
        source.sleep_quality is RecoveryRating.POOR
        or source.stress_level is RecoveryRating.POOR
        or source.physical_job_demand is PhysicalJobDemand.HIGH
        or source.recent_training_history.recovery_problems
    )


def _select_weekdays(
    days: int,
    preferred: tuple[int, ...],
    focuses: tuple[str, ...],
    ruleset: ProgramRuleset,
) -> tuple[int, ...]:
    if len(preferred) >= days:
        selected = tuple(sorted(preferred[:days]))
        if _spacing_is_acceptable(selected, focuses, ruleset):
            return selected
    return ruleset.default_weekdays[days]


def _spacing_is_acceptable(
    weekdays: tuple[int, ...],
    focuses: tuple[str, ...],
    ruleset: ProgramRuleset,
) -> bool:
    if len(weekdays) <= 1:
        return True
    ordered = sorted(zip(weekdays, focuses, strict=True))
    circular = ordered + [(ordered[0][0] + ruleset.days_per_week, ordered[0][1])]
    for current, following in zip(circular, circular[1:], strict=False):
        gap = following[0] - current[0]
        recovery_sensitive = (
            current[1].startswith("full_body")
            or following[1].startswith("full_body")
            or current[1] == following[1]
        )
        if recovery_sensitive and gap < ruleset.minimum_recovery_gap_days:
            return False
    return True
