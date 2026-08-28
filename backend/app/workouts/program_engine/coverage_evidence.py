from __future__ import annotations

from collections.abc import Iterable

from app.workouts.program_engine.schemas import ExerciseCandidate

_AVAILABILITY_REJECTION_REASONS = frozenset(
    "EXERCISE_REJECTED_INACTIVE EXERCISE_REJECTED_NOT_PROGRAMMABLE "
    "EXERCISE_REJECTED_NEEDS_REVIEW EXERCISE_REJECTED_MISSING_METADATA "
    "EXERCISE_REJECTED_NOT_RESISTANCE_TRAINING EXERCISE_REJECTED_MISSING_EQUIPMENT "
    "EXERCISE_REJECTED_SKILL_TOO_HIGH EXERCISE_REJECTED_BLOCKED_CAUTION_TAG "
    "EXERCISE_REJECTED_IMPACT_LIMIT EXERCISE_REJECTED_AXIAL_LOAD_LIMIT "
    "EXERCISE_REJECTED_BALANCE_DEMAND EXERCISE_REJECTED_OVERHEAD_LIMIT "
    "EXERCISE_REJECTED_RANGE_OF_MOTION".split()
)


def candidate_availability_evidence(
    records: Iterable[tuple[ExerciseCandidate, tuple[str, ...] | None]],
) -> dict[str, object]:
    """Summarize eligible and rejected candidates without inferring user constraints."""
    entries = tuple(records)
    eligible = tuple(candidate for candidate, reasons in entries if reasons is None)
    rejected = tuple((candidate, reasons) for candidate, reasons in entries if reasons is not None)
    rejection_reason_codes = tuple(
        sorted({reason for _candidate, reasons in rejected for reason in reasons})
    )
    availability_reason_codes = tuple(
        sorted(
            {
                reason
                for _candidate, reasons in rejected
                for reason in reasons
                if reason in _AVAILABILITY_REJECTION_REASONS
            }
        )
    )
    return {
        "candidate_count": len(entries),
        "eligible_candidate_count": len(eligible),
        "rejected_candidate_count": len(rejected),
        "eligible_candidate_ids": tuple(str(candidate.id) for candidate in eligible),
        "rejected_candidates": tuple(
            {"exercise_id": str(candidate.id), "reason_codes": reasons}
            for candidate, reasons in rejected
        ),
        "rejection_reason_codes": rejection_reason_codes,
        "availability_reason_codes": (
            ("COVERAGE_CATALOG_NO_COMPATIBLE_CANDIDATE",)
            if not entries
            else availability_reason_codes
        ),
        "unavailable": not eligible
        and (
            not rejected
            or all(
                set(reasons).intersection(_AVAILABILITY_REJECTION_REASONS)
                for _candidate, reasons in rejected
            )
        ),
    }


__all__ = ["candidate_availability_evidence"]
