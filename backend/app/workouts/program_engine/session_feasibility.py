"""Central session-count policy and bounded feasibility evidence."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from app.workouts.program_engine.duration_policy import (
    SessionExerciseCountPolicy,
    get_session_exercise_count_policy,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.supplemental_policy import main_exercise_count

SESSION_COUNT_OUT_OF_RANGE_REASON = "SESSION_EXERCISE_COUNT_OUT_OF_RANGE"
SESSION_COUNT_CONSTRAINED_REASON = "SESSION_EXERCISE_COUNT_CONSTRAINED_BY_SAFE_CAPACITY"


class SessionCountStatus(StrEnum):
    IN_RANGE = "in_range"
    CONSTRAINED = "constrained"
    UNPROVEN = "unproven"


@dataclass(frozen=True, slots=True)
class CandidateSearchObservation:
    """Bounded results of one complete safe-candidate search."""

    candidate_pool_count: int
    classified_candidate_count: int
    feasible_candidate_count: int
    rejection_reason_counts: tuple[tuple[str, int], ...]
    search_exhausted: bool
    candidate_pool_complete: bool

    @classmethod
    def from_outcomes(
        cls,
        candidate_pool_count: int,
        outcomes: Mapping[object, Iterable[str]],
        *,
        feasible_candidate_count: int = 0,
        search_exhausted: bool = True,
        candidate_pool_complete: bool = True,
    ) -> CandidateSearchObservation:
        reason_counts: Counter[str] = Counter()
        classified = 0
        for reasons in outcomes.values():
            normalized = tuple(dict.fromkeys(reason for reason in reasons if reason))
            if normalized:
                classified += 1
                reason_counts.update(normalized)
        return cls(
            candidate_pool_count=max(0, candidate_pool_count),
            classified_candidate_count=classified,
            feasible_candidate_count=max(0, feasible_candidate_count),
            rejection_reason_counts=tuple(sorted(reason_counts.items())),
            search_exhausted=search_exhausted,
            candidate_pool_complete=candidate_pool_complete,
        )


@dataclass(frozen=True, slots=True)
class SessionFeasibilityEvidence:
    """Proof that all remaining additions were checked against hard rules."""

    day_index: int
    requested_minutes: int
    minimum_main_exercises: int
    maximum_main_exercises: int
    actual_main_exercises: int
    candidate_pool_count: int
    classified_candidate_count: int
    feasible_candidate_count: int
    rejection_reason_counts: tuple[tuple[str, int], ...]
    search_exhausted: bool
    candidate_pool_complete: bool

    @classmethod
    def from_day(
        cls,
        day: object,
        *,
        requested_minutes: int,
        ruleset: ProgramRuleset,
        candidate_pool_count: int,
        classified_candidate_count: int,
        feasible_candidate_count: int,
        rejection_reason_counts: Mapping[str, int] | Sequence[tuple[str, int]],
        search_exhausted: bool,
        candidate_pool_complete: bool,
    ) -> SessionFeasibilityEvidence:
        policy = session_count_policy(requested_minutes, ruleset)
        if isinstance(rejection_reason_counts, Mapping):
            reason_items: Sequence[tuple[object, object]] = tuple(rejection_reason_counts.items())
        else:
            reason_items = tuple(rejection_reason_counts)
        normalized_reasons = tuple(
            sorted(
                (str(reason), int(count))
                for reason, count in reason_items
                if isinstance(reason, str) and type(count) is int and count > 0
            )
        )
        return cls(
            day_index=_day_index(day),
            requested_minutes=requested_minutes,
            minimum_main_exercises=policy.minimum_main_exercises,
            maximum_main_exercises=policy.maximum_main_exercises,
            actual_main_exercises=main_exercise_count(_exercises(day)),
            candidate_pool_count=max(0, candidate_pool_count),
            classified_candidate_count=max(0, classified_candidate_count),
            feasible_candidate_count=max(0, feasible_candidate_count),
            rejection_reason_counts=normalized_reasons,
            search_exhausted=search_exhausted,
            candidate_pool_complete=candidate_pool_complete,
        )

    @classmethod
    def from_observation(
        cls,
        day: object,
        *,
        requested_minutes: int,
        ruleset: ProgramRuleset,
        observation: CandidateSearchObservation,
    ) -> SessionFeasibilityEvidence:
        return cls.from_day(
            day,
            requested_minutes=requested_minutes,
            ruleset=ruleset,
            candidate_pool_count=observation.candidate_pool_count,
            classified_candidate_count=observation.classified_candidate_count,
            feasible_candidate_count=observation.feasible_candidate_count,
            rejection_reason_counts=observation.rejection_reason_counts,
            search_exhausted=observation.search_exhausted,
            candidate_pool_complete=observation.candidate_pool_complete,
        )

    @property
    def evidence_complete(self) -> bool:
        reason_total = sum(count for _, count in self.rejection_reason_counts)
        return bool(
            self.candidate_pool_complete
            and self.search_exhausted
            and self.actual_main_exercises > 0
            and self.actual_main_exercises < self.minimum_main_exercises
            and self.feasible_candidate_count == 0
            and self.classified_candidate_count == self.candidate_pool_count
            and reason_total >= self.candidate_pool_count
        )

    @property
    def status(self) -> SessionCountStatus:
        if self.minimum_main_exercises <= self.actual_main_exercises <= self.maximum_main_exercises:
            return SessionCountStatus.IN_RANGE
        if self.evidence_complete:
            return SessionCountStatus.CONSTRAINED
        return SessionCountStatus.UNPROVEN

    @property
    def reason_codes(self) -> tuple[str, ...]:
        if self.status is SessionCountStatus.CONSTRAINED:
            return (SESSION_COUNT_CONSTRAINED_REASON,)
        if self.status is SessionCountStatus.UNPROVEN:
            return (SESSION_COUNT_OUT_OF_RANGE_REASON,)
        return ()

    def matches(self, day: object) -> bool:
        return self.day_index == _day_index(
            day
        ) and self.actual_main_exercises == main_exercise_count(_exercises(day))

    @classmethod
    def from_trace(cls, value: object) -> SessionFeasibilityEvidence | None:
        if not isinstance(value, Mapping):
            return None
        scalar_fields = (
            "day_index",
            "requested_minutes",
            "minimum_main_exercises",
            "maximum_main_exercises",
            "actual_main_exercises",
            "candidate_pool_count",
            "classified_candidate_count",
            "feasible_candidate_count",
        )
        values = tuple(value.get(field) for field in scalar_fields)
        if any(type(item) is not int or item < 0 for item in values):
            return None
        raw_reasons = value.get("rejection_reason_counts")
        if not isinstance(raw_reasons, (tuple, list)):
            return None
        reasons: list[tuple[str, int]] = []
        for item in raw_reasons:
            if (
                not isinstance(item, (tuple, list))
                or len(item) != 2
                or not isinstance(item[0], str)
                or type(item[1]) is not int
                or item[1] <= 0
            ):
                return None
            reasons.append((item[0], item[1]))
        search_exhausted = value.get("search_exhausted")
        candidate_pool_complete = value.get("candidate_pool_complete")
        if type(search_exhausted) is not bool or type(candidate_pool_complete) is not bool:
            return None
        parsed_values = cast(tuple[int, ...], values)
        return cls(
            day_index=parsed_values[0],
            requested_minutes=parsed_values[1],
            minimum_main_exercises=parsed_values[2],
            maximum_main_exercises=parsed_values[3],
            actual_main_exercises=parsed_values[4],
            candidate_pool_count=parsed_values[5],
            classified_candidate_count=parsed_values[6],
            feasible_candidate_count=parsed_values[7],
            rejection_reason_counts=tuple(reasons),
            search_exhausted=search_exhausted,
            candidate_pool_complete=candidate_pool_complete,
        )

    def as_trace(self) -> dict[str, object]:
        return {
            "day_index": self.day_index,
            "requested_minutes": self.requested_minutes,
            "minimum_main_exercises": self.minimum_main_exercises,
            "maximum_main_exercises": self.maximum_main_exercises,
            "actual_main_exercises": self.actual_main_exercises,
            "candidate_pool_count": self.candidate_pool_count,
            "classified_candidate_count": self.classified_candidate_count,
            "feasible_candidate_count": self.feasible_candidate_count,
            "rejection_reason_counts": self.rejection_reason_counts,
            "search_exhausted": self.search_exhausted,
            "candidate_pool_complete": self.candidate_pool_complete,
            "evidence_complete": self.evidence_complete,
            "status": self.status.value,
            "reason_codes": self.reason_codes,
        }


@dataclass(frozen=True, slots=True)
class SessionCountAssessment:
    status: SessionCountStatus
    actual_main_exercises: int
    minimum_main_exercises: int
    maximum_main_exercises: int
    evidence_complete: bool
    reason_codes: tuple[str, ...]


def session_count_policy(
    requested_minutes: int,
    ruleset: ProgramRuleset | None = None,
) -> SessionExerciseCountPolicy:
    """Return the single count policy used by construction and validation."""

    return get_session_exercise_count_policy(requested_minutes, ruleset)


def assess_session_count(
    day: object,
    *,
    requested_minutes: int,
    ruleset: ProgramRuleset,
    evidence: SessionFeasibilityEvidence | None = None,
) -> SessionCountAssessment:
    policy = session_count_policy(requested_minutes, ruleset)
    actual = main_exercise_count(_exercises(day))
    if policy.contains(actual):
        status = SessionCountStatus.IN_RANGE
        evidence_complete = True
        reason_codes: tuple[str, ...] = ()
    elif evidence is not None and _evidence_matches_policy(evidence, day, policy):
        status = evidence.status
        evidence_complete = status is SessionCountStatus.CONSTRAINED
        reason_codes = evidence.reason_codes
    else:
        status = SessionCountStatus.UNPROVEN
        evidence_complete = False
        reason_codes = (SESSION_COUNT_OUT_OF_RANGE_REASON,)
    return SessionCountAssessment(
        status=status,
        actual_main_exercises=actual,
        minimum_main_exercises=policy.minimum_main_exercises,
        maximum_main_exercises=policy.maximum_main_exercises,
        evidence_complete=evidence_complete,
        reason_codes=reason_codes,
    )


def session_feasibility_evidence_from_trace(
    trace: Sequence[Mapping[str, object]],
    day: object,
) -> SessionFeasibilityEvidence | None:
    """Read only structured count evidence from a session-duration trace."""

    matches: list[SessionFeasibilityEvidence] = []
    for entry in trace:
        if entry.get("stage") != "session_duration":
            continue
        raw_items = entry.get("per_session_evidence")
        if not isinstance(raw_items, (tuple, list)):
            continue
        for raw_item in raw_items:
            if not isinstance(raw_item, Mapping):
                continue
            evidence = SessionFeasibilityEvidence.from_trace(raw_item.get("session_feasibility"))
            if evidence is not None and evidence.matches(day):
                matches.append(evidence)
    return matches[0] if len(matches) == 1 else None


def _evidence_matches_policy(
    evidence: SessionFeasibilityEvidence,
    day: object,
    policy: SessionExerciseCountPolicy,
) -> bool:
    return (
        evidence.matches(day)
        and evidence.requested_minutes == policy.requested_minutes
        and evidence.minimum_main_exercises == policy.minimum_main_exercises
        and evidence.maximum_main_exercises == policy.maximum_main_exercises
    )


def _exercises(day: object) -> Iterable[object]:
    if isinstance(day, Mapping):
        value = day.get("exercises", ())
    else:
        value = getattr(day, "exercises", ())
    return value if isinstance(value, Iterable) else ()


def _day_index(day: object) -> int:
    value = day.get("day_index", 0) if isinstance(day, Mapping) else getattr(day, "day_index", 0)
    return value if type(value) is int and value >= 0 else 0
