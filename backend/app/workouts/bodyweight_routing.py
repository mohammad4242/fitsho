from dataclasses import dataclass
from enum import StrEnum

from app.exercises.enums import Equipment
from app.profile.enums import ExperienceLevel, TrainingLocation

BODYWEIGHT_MODE_EQUIPMENT: frozenset[Equipment] = frozenset(
    {Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR}
)
BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED = "BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED"
BODYWEIGHT_TEMPLATE_DAYS_NOT_SUPPORTED = "BODYWEIGHT_TEMPLATE_DAYS_NOT_SUPPORTED"
BODYWEIGHT_ENGINE_VERSION = "bodyweight_template_v1"


class BodyweightRoutingStatus(StrEnum):
    NOT_BODYWEIGHT_ROUTE = "not_bodyweight_route"
    FIXED_TEMPLATE = "fixed_template"
    UNSUPPORTED_LEVEL = "unsupported_level"
    UNSUPPORTED_DAYS = "unsupported_days"


@dataclass(frozen=True, slots=True)
class BodyweightRouteDecision:
    status: BodyweightRoutingStatus
    template_slug: str | None = None
    error_code: str | None = None

    @property
    def is_fixed_template(self) -> bool:
        return self.status is BodyweightRoutingStatus.FIXED_TEMPLATE

    @property
    def is_bodyweight_route(self) -> bool:
        return self.status is not BodyweightRoutingStatus.NOT_BODYWEIGHT_ROUTE


def is_pure_bodyweight_home(
    training_location: TrainingLocation,
    resolved_equipment: frozenset[Equipment],
) -> bool:
    """Return True if the user trains at home with only bodyweight/pull-up bar equipment."""
    return (
        training_location is TrainingLocation.HOME
        and Equipment.BODYWEIGHT in resolved_equipment
        and resolved_equipment.issubset(BODYWEIGHT_MODE_EQUIPMENT)
    )


def resolve_fixed_bodyweight_route(
    training_location: TrainingLocation | None,
    resolved_equipment: frozenset[Equipment],
    experience_level: ExperienceLevel | None,
    effective_days: int | None,
) -> BodyweightRouteDecision:
    """Pure helper answering routing decisions for bodyweight candidates.

    Returns:
    - NOT_BODYWEIGHT_ROUTE if location or equipment is not pure home bodyweight.
    - UNSUPPORTED_LEVEL if experience level is not FIRST_MONTH or BEGINNER.
    - UNSUPPORTED_DAYS if effective training days are not 2, 3, or 4.
    - FIXED_TEMPLATE with the exact canonical template slug if supported.
    """
    if training_location is None or not is_pure_bodyweight_home(training_location, resolved_equipment):
        return BodyweightRouteDecision(status=BodyweightRoutingStatus.NOT_BODYWEIGHT_ROUTE)

    if experience_level not in {ExperienceLevel.FIRST_MONTH, ExperienceLevel.BEGINNER}:
        return BodyweightRouteDecision(
            status=BodyweightRoutingStatus.UNSUPPORTED_LEVEL,
            error_code=BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED,
        )

    if effective_days not in {2, 3, 4}:
        return BodyweightRouteDecision(
            status=BodyweightRoutingStatus.UNSUPPORTED_DAYS,
            error_code=BODYWEIGHT_TEMPLATE_DAYS_NOT_SUPPORTED,
        )

    level_tag = "first-month" if experience_level is ExperienceLevel.FIRST_MONTH else "beginner"
    slug = f"bw-{level_tag}-{effective_days}d-v1"
    return BodyweightRouteDecision(
        status=BodyweightRoutingStatus.FIXED_TEMPLATE,
        template_slug=slug,
    )
