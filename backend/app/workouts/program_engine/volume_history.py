from __future__ import annotations

from dataclasses import dataclass

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.schemas import RecentTrainingHistory


@dataclass(frozen=True)
class PreviousVolumeBaseline:
    direct_sets_by_muscle: dict[MuscleGroup, float]
    effective_sets_by_muscle: dict[MuscleGroup, float]
    confidence: float
    source: str
    reason_codes: tuple[str, ...]


def derive_previous_volume_baseline(
    history: RecentTrainingHistory,
) -> PreviousVolumeBaseline:
    effective = _positive_values(history.previous_weekly_effective_sets_by_muscle)
    direct = _positive_values(
        history.previous_weekly_direct_sets_by_muscle
        or {
            muscle: float(value) for muscle, value in history.previous_weekly_sets_by_muscle.items()
        }
    )
    input_reasons = tuple(dict.fromkeys(history.previous_volume_reason_codes))

    if effective:
        if history.previous_volume_source == "prescribed_plan":
            adherence = history.completed_session_ratio
            if adherence <= 0:
                return _empty_baseline((*input_reasons, "HISTORY_NO_RELIABLE_COMPLETED_VOLUME"))
            return _scaled_baseline(
                direct,
                effective,
                adherence,
                history.previous_volume_confidence,
                "prescribed_plan",
                (*input_reasons, "HISTORY_SCALED_BY_ADHERENCE"),
            )
        if history.previous_volume_source == "observed_effective":
            return _scaled_baseline(
                direct,
                effective,
                1.0,
                history.previous_volume_confidence,
                "observed_effective",
                input_reasons,
            )
        return _empty_baseline((*input_reasons, "HISTORY_SOURCE_UNSUPPORTED"))

    if direct:
        if history.previous_volume_source == "prescribed_plan":
            adherence = history.completed_session_ratio
            if adherence <= 0:
                return _empty_baseline((*input_reasons, "HISTORY_NO_RELIABLE_COMPLETED_VOLUME"))
            return _scaled_baseline(
                direct,
                {},
                adherence,
                history.previous_volume_confidence,
                "prescribed_plan",
                (*input_reasons, "HISTORY_SCALED_BY_ADHERENCE"),
            )
        return PreviousVolumeBaseline(
            direct_sets_by_muscle=direct,
            effective_sets_by_muscle={},
            confidence=history.previous_volume_confidence or 1.0,
            source="legacy_direct",
            reason_codes=tuple(dict.fromkeys((*input_reasons, "HISTORY_DIRECT_VOLUME_FALLBACK"))),
        )
    return _empty_baseline(input_reasons)


def _scaled_baseline(
    direct: dict[MuscleGroup, float],
    effective: dict[MuscleGroup, float],
    scale: float,
    confidence: float | None,
    source: str,
    reason_codes: tuple[str, ...],
) -> PreviousVolumeBaseline:
    return PreviousVolumeBaseline(
        direct_sets_by_muscle=_scale(direct, scale),
        effective_sets_by_muscle=_scale(effective, scale),
        confidence=round(confidence if confidence is not None else scale, 2),
        source=source,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
    )


def _positive_values(values: dict[MuscleGroup, float]) -> dict[MuscleGroup, float]:
    return {muscle: round(float(value), 2) for muscle, value in values.items() if float(value) > 0}


def _scale(values: dict[MuscleGroup, float], factor: float) -> dict[MuscleGroup, float]:
    return {muscle: round(value * factor, 2) for muscle, value in values.items()}


def _empty_baseline(reason_codes: tuple[str, ...]) -> PreviousVolumeBaseline:
    return PreviousVolumeBaseline(
        direct_sets_by_muscle={},
        effective_sets_by_muscle={},
        confidence=0.0,
        source="none",
        reason_codes=tuple(dict.fromkeys(reason_codes)),
    )
