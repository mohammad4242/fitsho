from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from app.profile.enums import ExperienceLevel
from app.workouts.program_engine.enums import SplitType

BODYWEIGHT_TEMPLATE_LIBRARY_VERSION = "bodyweight_templates_v1"


@dataclass(frozen=True, slots=True)
class BodyweightTemplateExercise:
    exercise_slug: str
    sets: int
    rest_seconds: int
    rep_min: int | None = None
    rep_max: int | None = None
    target_rir: int | None = None
    duration_min_seconds: int | None = None
    duration_max_seconds: int | None = None

    def __post_init__(self) -> None:
        if not self.exercise_slug:
            raise ValueError("exercise_slug is required")
        if not 1 <= self.sets <= 10:
            raise ValueError("sets must be between 1 and 10")
        if not 0 <= self.rest_seconds <= 600:
            raise ValueError("rest_seconds must be between 0 and 600")
        has_reps = self.rep_min is not None or self.rep_max is not None
        has_duration = (
            self.duration_min_seconds is not None or self.duration_max_seconds is not None
        )
        if has_reps == has_duration:
            raise ValueError("template exercise must use exactly one prescription mode")
        if has_reps:
            if (
                self.rep_min is None
                or self.rep_max is None
                or not 1 <= self.rep_min <= self.rep_max <= 100
                or self.target_rir is None
                or not 0 <= self.target_rir <= 6
                or self.duration_min_seconds is not None
                or self.duration_max_seconds is not None
            ):
                raise ValueError("rep prescriptions require reps, no duration, and RIR")
            return
        if (
            self.duration_min_seconds is None
            or self.duration_max_seconds is None
            or not 1 <= self.duration_min_seconds <= self.duration_max_seconds <= 3600
            or self.rep_min is not None
            or self.rep_max is not None
            or self.target_rir is not None
        ):
            raise ValueError("duration prescriptions require duration, no reps, and null RIR")


@dataclass(frozen=True, slots=True)
class BodyweightTemplateDay:
    day_number: int
    title_en: str
    title_fa: str
    exercises: tuple[BodyweightTemplateExercise, ...]

    def __post_init__(self) -> None:
        if self.day_number < 1:
            raise ValueError("day_number must be positive")
        if not self.title_en or not self.title_fa:
            raise ValueError("template day titles are required")
        if not self.exercises:
            raise ValueError("template day must contain exercises")


@dataclass(frozen=True, slots=True)
class BodyweightProgramTemplate:
    slug: str
    experience_level: ExperienceLevel
    days_per_week: int
    split_type: SplitType
    days: tuple[BodyweightTemplateDay, ...]

    def __post_init__(self) -> None:
        if not self.slug or self.days_per_week not in {2, 3, 4}:
            raise ValueError("unsupported bodyweight template identity")
        if len(self.days) != self.days_per_week:
            raise ValueError("template day count must equal days_per_week")
        if tuple(day.day_number for day in self.days) != tuple(range(1, self.days_per_week + 1)):
            raise ValueError("template day numbers must be consecutive")


def _rep(
    exercise_slug: str,
    sets: int,
    rep_min: int,
    rep_max: int,
    target_rir: int,
    rest_seconds: int,
) -> BodyweightTemplateExercise:
    return BodyweightTemplateExercise(
        exercise_slug=exercise_slug,
        sets=sets,
        rep_min=rep_min,
        rep_max=rep_max,
        target_rir=target_rir,
        rest_seconds=rest_seconds,
    )


def _duration(
    exercise_slug: str,
    sets: int,
    duration_min_seconds: int,
    duration_max_seconds: int,
    rest_seconds: int,
) -> BodyweightTemplateExercise:
    return BodyweightTemplateExercise(
        exercise_slug=exercise_slug,
        sets=sets,
        duration_min_seconds=duration_min_seconds,
        duration_max_seconds=duration_max_seconds,
        rest_seconds=rest_seconds,
    )


def _day(
    day_number: int,
    title_en: str,
    title_fa: str,
    *exercises: BodyweightTemplateExercise,
) -> BodyweightTemplateDay:
    return BodyweightTemplateDay(
        day_number=day_number,
        title_en=title_en,
        title_fa=title_fa,
        exercises=exercises,
    )


SQUAT = "fedb-drv-squat-squat"
INCLINE_PUSH_UP = "fedb-0493-incline-push-up"
PUSH_UP = "fedb-drv-push-ups-push-up"
CLOSE_GRIP_PUSH_UP = "fedb-0259-close-grip-push-up"
INVERTED_ROW = "fedb-0499-inverted-row-between-chairs"
SHOULDER_WIDTH_PULL_UP = "fedb-0651-shoulder-width-pull-up"
REVERSE_GRIP_PULL_UP = "fedb-2327-reverse-grip-pull-up"
CLOSE_GRIP_CHIN_UP = "fedb-2987-close-grip-chin-up"
WIDE_GRIP_PULL_UP = "fedb-1429-pull-up-wide-grip"
GLUTE_BRIDGE = "fedb-0668-rear-decline-bridge"
FRONT_PLANK = "fedb-0464-front-plank"
SIDE_PLANK = "fedb-0705-side-plank"
REVERSE_CRUNCH = "fedb-0872-reverse-crunch"


def _first_month_template(days: int) -> BodyweightProgramTemplate:
    squat = _rep(SQUAT, 2, 10, 15, 4, 75)
    incline_push_up = _rep(INCLINE_PUSH_UP, 2, 8, 12, 4, 60)
    push_up = _rep(PUSH_UP, 2, 6, 10, 4, 60)
    inverted_row = _rep(INVERTED_ROW, 2, 6, 10, 4, 75)
    glute_bridge = _rep(GLUTE_BRIDGE, 2, 10, 15, 4, 60)
    front_plank = _duration(FRONT_PLANK, 2, 20, 30, 45)
    side_plank = _duration(SIDE_PLANK, 2, 20, 30, 45)
    if days == 2:
        template_days = (
            _day(
                1,
                "Full Body A",
                "تمام بدن A",
                squat,
                incline_push_up,
                inverted_row,
                glute_bridge,
                front_plank,
            ),
            _day(
                2,
                "Full Body B",
                "تمام بدن B",
                squat,
                push_up,
                inverted_row,
                glute_bridge,
                side_plank,
            ),
        )
    elif days == 3:
        template_days = (
            _day(
                1,
                "Full Body A",
                "تمام بدن A",
                squat,
                incline_push_up,
                inverted_row,
                glute_bridge,
                front_plank,
            ),
            _day(
                2,
                "Full Body B",
                "تمام بدن B",
                squat,
                push_up,
                inverted_row,
                glute_bridge,
                _rep(REVERSE_CRUNCH, 2, 10, 15, 4, 45),
            ),
            _day(
                3,
                "Full Body C",
                "تمام بدن C",
                squat,
                incline_push_up,
                inverted_row,
                glute_bridge,
                side_plank,
            ),
        )
    else:
        template_days = (
            _day(
                1,
                "Upper A",
                "بالاتنه A",
                incline_push_up,
                inverted_row,
                _rep(CLOSE_GRIP_PUSH_UP, 2, 6, 10, 4, 60),
                front_plank,
            ),
            _day(
                2,
                "Lower A",
                "پایین تنه A",
                squat,
                glute_bridge,
                _rep(REVERSE_CRUNCH, 2, 10, 15, 4, 45),
                side_plank,
            ),
            _day(
                3,
                "Upper B",
                "بالاتنه B",
                push_up,
                inverted_row,
                _rep(CLOSE_GRIP_PUSH_UP, 2, 6, 10, 4, 60),
                front_plank,
            ),
            _day(
                4,
                "Lower B",
                "پایین تنه B",
                squat,
                _rep(GLUTE_BRIDGE, 2, 12, 15, 4, 60),
                _rep(REVERSE_CRUNCH, 2, 10, 15, 4, 45),
                side_plank,
            ),
        )
    return BodyweightProgramTemplate(
        slug=f"bw-first-month-{days}d-v1",
        experience_level=ExperienceLevel.FIRST_MONTH,
        days_per_week=days,
        split_type=SplitType.FULL_BODY if days < 4 else SplitType.UPPER_LOWER,
        days=template_days,
    )


def _beginner_template(days: int) -> BodyweightProgramTemplate:
    squat_3 = _rep(SQUAT, 3, 10, 15, 3, 75)
    squat_2 = _rep(SQUAT, 2, 10, 15, 3, 75)
    push_up_3 = _rep(PUSH_UP, 3, 6, 12, 3, 75)
    push_up_2 = _rep(PUSH_UP, 2, 6, 12, 3, 75)
    incline_push_up_2 = _rep(INCLINE_PUSH_UP, 2, 10, 15, 3, 60)
    incline_push_up_3 = _rep(INCLINE_PUSH_UP, 3, 8, 15, 3, 75)
    close_grip_push_up_2 = _rep(CLOSE_GRIP_PUSH_UP, 2, 6, 12, 3, 75)
    close_grip_push_up_3 = _rep(CLOSE_GRIP_PUSH_UP, 3, 6, 12, 3, 75)
    shoulder_width_pull_up = _rep(SHOULDER_WIDTH_PULL_UP, 3, 3, 8, 3, 90)
    reverse_grip_pull_up_2 = _rep(REVERSE_GRIP_PULL_UP, 3, 3, 8, 3, 90)
    close_grip_chin_up = _rep(CLOSE_GRIP_CHIN_UP, 2, 3, 8, 3, 90)
    wide_grip_pull_up = _rep(WIDE_GRIP_PULL_UP, 2, 3, 6, 3, 90)
    glute_bridge_3 = _rep(GLUTE_BRIDGE, 3, 10, 15, 3, 75)
    glute_bridge_2 = _rep(GLUTE_BRIDGE, 2, 12, 15, 3, 60)
    glute_bridge_3_12_75 = _rep(GLUTE_BRIDGE, 3, 12, 15, 3, 75)
    front_plank_2 = _duration(FRONT_PLANK, 2, 25, 40, 45)
    front_plank_4 = _duration(FRONT_PLANK, 2, 30, 40, 45)
    side_plank = _duration(SIDE_PLANK, 2, 20, 30, 45)
    reverse_crunch = _rep(REVERSE_CRUNCH, 2, 10, 15, 3, 45)

    if days == 2:
        template_days = (
            _day(
                1,
                "Full Body A",
                "تمام بدن A",
                squat_3,
                push_up_3,
                shoulder_width_pull_up,
                glute_bridge_3,
                front_plank_2,
            ),
            _day(
                2,
                "Full Body B",
                "تمام بدن B",
                squat_3,
                close_grip_push_up_2,
                _rep(REVERSE_GRIP_PULL_UP, 3, 3, 8, 3, 90),
                glute_bridge_3,
                side_plank,
            ),
        )
    elif days == 3:
        template_days = (
            _day(
                1,
                "Full Body A",
                "تمام بدن A",
                squat_3,
                push_up_3,
                shoulder_width_pull_up,
                glute_bridge_3,
                front_plank_2,
            ),
            _day(
                2,
                "Full Body B",
                "تمام بدن B",
                squat_2,
                incline_push_up_2,
                close_grip_chin_up,
                glute_bridge_2,
                reverse_crunch,
            ),
            _day(
                3,
                "Full Body C",
                "تمام بدن C",
                squat_3,
                close_grip_push_up_3,
                reverse_grip_pull_up_2,
                glute_bridge_3,
                side_plank,
            ),
        )
    else:
        template_days = (
            _day(
                1,
                "Upper A",
                "بالاتنه A",
                push_up_3,
                shoulder_width_pull_up,
                close_grip_push_up_2,
                close_grip_chin_up,
                front_plank_4,
            ),
            _day(2, "Lower A", "پایین تنه A", squat_3, glute_bridge_3, reverse_crunch, side_plank),
            _day(
                3,
                "Upper B",
                "بالاتنه B",
                incline_push_up_3,
                reverse_grip_pull_up_2,
                push_up_2,
                wide_grip_pull_up,
                front_plank_4,
            ),
            _day(
                4,
                "Lower B",
                "پایین تنه B",
                squat_3,
                glute_bridge_3_12_75,
                reverse_crunch,
                side_plank,
            ),
        )
    return BodyweightProgramTemplate(
        slug=f"bw-beginner-{days}d-v1",
        experience_level=ExperienceLevel.BEGINNER,
        days_per_week=days,
        split_type=SplitType.FULL_BODY if days < 4 else SplitType.UPPER_LOWER,
        days=template_days,
    )


BODYWEIGHT_TEMPLATE_LIBRARY: tuple[BodyweightProgramTemplate, ...] = tuple(
    template
    for level_factory in (_first_month_template, _beginner_template)
    for template in (level_factory(2), level_factory(3), level_factory(4))
)


def get_bodyweight_template(
    experience_level: ExperienceLevel,
    days_per_week: int,
) -> BodyweightProgramTemplate | None:
    return next(
        (
            template
            for template in BODYWEIGHT_TEMPLATE_LIBRARY
            if template.experience_level is experience_level
            and template.days_per_week == days_per_week
        ),
        None,
    )


def bodyweight_template_fingerprint(template: BodyweightProgramTemplate) -> str:
    payload = {
        "library_version": BODYWEIGHT_TEMPLATE_LIBRARY_VERSION,
        "template": asdict(template),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "BODYWEIGHT_TEMPLATE_LIBRARY",
    "BODYWEIGHT_TEMPLATE_LIBRARY_VERSION",
    "BodyweightProgramTemplate",
    "BodyweightTemplateDay",
    "BodyweightTemplateExercise",
    "bodyweight_template_fingerprint",
    "get_bodyweight_template",
]
