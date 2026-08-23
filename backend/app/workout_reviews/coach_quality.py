from collections.abc import Sequence

from pydantic import ValidationError

from app.workout_reviews.schemas import CoachQualityMetricsResponse


def build_coach_quality_projection(
    decision_trace: object,
) -> CoachQualityMetricsResponse | None:
    if not isinstance(decision_trace, Sequence) or isinstance(decision_trace, (str, bytes)):
        return None
    entry = next(
        (
            item
            for item in decision_trace
            if isinstance(item, dict) and item.get("stage") == "coach_quality"
        ),
        None,
    )
    if entry is None or not isinstance(entry.get("metrics"), dict):
        return None
    try:
        return CoachQualityMetricsResponse.model_validate(entry["metrics"])
    except ValidationError:
        return None
