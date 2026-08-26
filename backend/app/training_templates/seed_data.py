# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass

from app.exercises.enums import MovementPattern, MuscleGroup
from app.profile.enums import ExperienceLevel
from app.training_templates.models import (
    StructureFamily,
    StructureSplitType,
    TrainingTemplateMethod,
    TrainingTemplateSlotPriority,
)
from app.training_templates.tags import (
    TemplateFocusTag,
    validate_focus_tags,
    validate_template_focus_tags,
)


@dataclass(frozen=True)
class TemplateSlotSeed:
    exercise_slug_hint: str
    catalog_slug_hints: tuple[str, ...]
    target_muscles: tuple[MuscleGroup, ...]
    movement_pattern: MovementPattern
    placeholder_name_en: str | None = None
    placeholder_name_fa: str | None = None
    sets: int = 3
    rep_min: int = 8
    rep_max: int = 12
    target_rir: int = 2
    rest_seconds: int = 90
    intensity_method: TrainingTemplateMethod = TrainingTemplateMethod.STANDARD
    adaptation_priority: TrainingTemplateSlotPriority = TrainingTemplateSlotPriority.ACCESSORY
    superset_group: str | None = None


@dataclass(frozen=True)
class TemplateDaySeed:
    title_en: str
    title_fa: str
    structure_focus: str
    direct_target_muscles: tuple[MuscleGroup, ...]
    slots: tuple[TemplateSlotSeed, ...]


@dataclass(frozen=True)
class TemplateProgrammingRationaleSeed:
    title_en: str
    title_fa: str
    detail_en: str
    detail_fa: str


@dataclass(frozen=True)
class TrainingProgramTemplateSeed:
    canonical_slug: str
    slug: str
    name_en: str
    name_fa: str
    description_en: str
    description_fa: str
    days_per_week: int
    supported_levels: tuple[ExperienceLevel, ...]
    focus_tags: tuple[TemplateFocusTag, ...]
    intensity_methods: tuple[TrainingTemplateMethod, ...]
    days: tuple[TemplateDaySeed, ...]
    programming_rationale: tuple[TemplateProgrammingRationaleSeed, ...]
    is_active: bool = True
    structure_slug: str = ""


@dataclass(frozen=True)
class TrainingProgramStructureSeed:
    slug: str
    name_en: str
    name_fa: str
    days_per_week: int
    family: StructureFamily
    split_type: StructureSplitType | None
    description_en: str
    description_fa: str
    days: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True)
class Movement:
    key: str
    exercise_slug: str
    target_muscles: tuple[MuscleGroup, ...]
    movement_pattern: MovementPattern


@dataclass(frozen=True)
class CanonicalTemplateDefinition:
    canonical_slug: str
    name_en: str
    name_fa: str
    description_en: str
    description_fa: str
    supported_levels: tuple[ExperienceLevel, ...]
    focus_tags: tuple[TemplateFocusTag, ...]
    days: tuple[TemplateDaySeed, ...]
    day_specs: tuple[tuple[tuple[Movement, str], ...], ...]
    guidance_en: str
    guidance_fa: str
    order_en: str
    order_fa: str
    recovery_en: str
    recovery_fa: str
    structure_slug: str = ""


M = MuscleGroup
P = MovementPattern
Level = ExperienceLevel
Tag = TemplateFocusTag
Method = TrainingTemplateMethod
Priority = TrainingTemplateSlotPriority

LEGACY_SOURCE_NAME = "Fitsho synthesis: Stronger By Science · Jeff Nippard · RP Strength"
LEGACY_SOURCE_URL = "https://www.strongerbyscience.com/exercise-order-video/"
SOURCE_NAME = "Fitsho canonical training template catalog"
SOURCE_URL = "https://fitsho.local/training-template-catalog"
NOVICE_DEFAULT_PRESCRIPTION = (3, 8, 12)
LEGACY_NOVICE_PRESCRIPTIONS = frozenset({(2, 10, 15), (2, 12, 15), (2, 12, 20)})

CANONICAL_TEMPLATE_SLUGS: tuple[str, ...] = (
    "t01-2-day-full-body-ab",
    "t02-3-day-upper-lower-full",
    "t03-3-day-upper-lower-upper",
    "t04-3-day-lower-upper-lower",
    "t05-4-day-upper-lower-2x",
    "t06-4-day-3-upper-1-lower",
    "t07-4-day-3-lower-1-upper",
    "t08-4-day-push-pull-quads-posterior",
    "t09-5-day-ppl-upper-lower",
    "t10-5-day-classic-body-part",
    "t11-5-day-ppl-upper-lower-priority",
    "t12-5-day-chest-specialization",
    "t13-5-day-back-specialization",
    "t14-5-day-leg-specialization",
    "t15-6-day-ppl-2x",
    "t16-6-day-advanced-body-part",
    "t17-6-day-balanced-specialization",
)


def _movement(
    key: str,
    slug: str,
    muscles: tuple[MuscleGroup, ...],
    pattern: MovementPattern,
) -> Movement:
    return Movement(
        key=key,
        exercise_slug=slug,
        target_muscles=muscles,
        movement_pattern=pattern,
    )


SQUAT = _movement(
    "squat",
    "fedb-1435-barbell-back-squat",
    (M.QUADRICEPS,),
    P.SQUAT,
)
FRONT_SQUAT = _movement(
    "front-squat",
    "fedb-0042-barbell-front-squat",
    (M.QUADRICEPS,),
    P.SQUAT,
)
LEG_PRESS = _movement(
    "leg-press",
    "fedb-2611-lever-horizontal-leg-press",
    (M.QUADRICEPS,),
    P.SQUAT,
)
LEG_EXTENSION = _movement(
    "leg-extension",
    "fedb-0585-lever-leg-extension",
    (M.QUADRICEPS,),
    P.KNEE_EXTENSION,
)
LUNGE = _movement("lunge", "fedb-0336-dumbbell-lunge", (M.QUADRICEPS, M.GLUTES), P.LUNGE)
RDL = _movement(
    "romanian-deadlift",
    "fedb-0300-dumbbell-deadlift",
    (M.HAMSTRINGS, M.GLUTES),
    P.HIP_HINGE,
)
SEATED_LEG_CURL = _movement(
    "seated-leg-curl",
    "fedb-0599-lever-seated-leg-curl",
    (M.HAMSTRINGS,),
    P.KNEE_FLEXION,
)
LYING_LEG_CURL = _movement(
    "lying-leg-curl",
    "fedb-0586-lever-lying-leg-curl",
    (M.HAMSTRINGS,),
    P.KNEE_FLEXION,
)
GLUTE_BRIDGE = _movement(
    "glute-bridge",
    "fedb-0668-rear-decline-bridge",
    (M.GLUTES,),
    P.HIP_EXTENSION,
)
CALF_RAISE = _movement(
    "calf-raise",
    "fedb-0605-lever-standing-calf-raise",
    (M.CALVES,),
    P.CALF_RAISE,
)

FLAT_PRESS = _movement(
    "flat-chest-press",
    "fedb-0025-barbell-bench-press",
    (M.CHEST,),
    P.HORIZONTAL_PUSH,
)
INCLINE_PRESS = _movement(
    "incline-chest-press",
    "fedb-0314-dumbbell-incline-bench-press",
    (M.CHEST,),
    P.HORIZONTAL_PUSH,
)
CHEST_FLY = _movement(
    "chest-fly",
    "fedb-1269-cable-standing-fly",
    (M.CHEST,),
    P.HORIZONTAL_PUSH,
)
ROW = _movement(
    "row",
    "owner-e0c26a271aac-barbell-bent-over-row",
    (M.BACK,),
    P.HORIZONTAL_PULL,
)
SEATED_CABLE_ROW = _movement(
    "seated-cable-row",
    "owner-2a5de4dc7ba3-seated-cable-row",
    (M.BACK,),
    P.HORIZONTAL_PULL,
)
LAT_PULLDOWN = _movement(
    "lat-pulldown",
    "fedb-0974-cable-close-grip-lat-pulldown",
    (M.BACK,),
    P.VERTICAL_PULL,
)
STRAIGHT_ARM_PULLDOWN = _movement(
    "straight-arm-pulldown",
    "fedb-0238-cable-straight-arm-pulldown",
    (M.BACK,),
    P.VERTICAL_PULL,
)

SHOULDER_PRESS = _movement(
    "shoulder-press",
    "fedb-0553-military-press",
    (M.SHOULDERS,),
    P.VERTICAL_PUSH,
)
LATERAL_RAISE = _movement(
    "lateral-raise",
    "fedb-0178-cable-lateral-raise",
    (M.SHOULDERS,),
    P.SHOULDER_ABDUCTION,
)
REAR_DELT_FLY = _movement(
    "rear-delt-fly",
    "fedb-0602-lever-seated-reverse-fly",
    (M.SHOULDERS,),
    P.HORIZONTAL_PULL,
)

PREACHER_CURL = _movement(
    "preacher-curl",
    "fedb-0592-lever-preacher-curl",
    (M.BICEPS,),
    P.ELBOW_FLEXION,
)
DUMBBELL_CURL = _movement(
    "dumbbell-curl",
    "fedb-0285-seated-alternating-dumbbell-curl",
    (M.BICEPS,),
    P.ELBOW_FLEXION,
)
HAMMER_CURL = _movement(
    "hammer-curl",
    "fedb-0298-dumbbell-cross-body-hammer-curl",
    (M.BICEPS,),
    P.ELBOW_FLEXION,
)
BARBELL_CURL = _movement("barbell-curl", "fedb-0031-barbell-curl", (M.BICEPS,), P.ELBOW_FLEXION)
CABLE_CURL = _movement(
    "cable-curl",
    "fedb-0229-cable-standing-inner-curl",
    (M.BICEPS,),
    P.ELBOW_FLEXION,
)
TRICEPS_PUSHDOWN = _movement(
    "triceps-pushdown",
    "fedb-1723-cable-triceps-pushdown",
    (M.TRICEPS,),
    P.ELBOW_EXTENSION,
)
ROPE_TRICEPS_PUSHDOWN = _movement(
    "rope-triceps-pushdown",
    "fedb-0200-cable-rope-triceps-pushdown",
    (M.TRICEPS,),
    P.ELBOW_EXTENSION,
)
OVERHEAD_TRICEPS_EXTENSION = _movement(
    "overhead-triceps-extension",
    "fedb-0194-cable-rope-overhead-triceps-extension",
    (M.TRICEPS,),
    P.ELBOW_EXTENSION,
)
SHRUG = _movement("barbell-shrug", "fedb-0095-barbell-shrug", (M.TRAPS,), P.SHRUG)
FRONT_PLANK = _movement("front-plank", "fedb-0464-front-plank", (M.ABS,), P.CORE_ANTI_EXTENSION)
SIDE_PLANK = _movement(
    "side-plank", "fedb-0705-side-plank", (M.OBLIQUES,), P.CORE_ANTI_LATERAL_FLEXION
)

# Shared structures that support First Month or Beginner use the reviewed,
# supported anchors below.  Advanced-only templates keep the broader movement
# pool declared above.
_SAFE_FIRST_MONTH_MOVEMENTS = {
    "squat": _movement("squat", "fedb-0750-smith-chair-squat", (M.QUADRICEPS,), P.SQUAT),
    "front-squat": _movement(
        "front-squat", "fedb-0750-smith-chair-squat", (M.QUADRICEPS,), P.SQUAT
    ),
    "leg-press": _movement(
        "leg-press", "fedb-2611-lever-horizontal-leg-press", (M.QUADRICEPS,), P.SQUAT
    ),
    "romanian-deadlift": _movement(
        "romanian-deadlift",
        "fedb-0668-rear-decline-bridge",
        (M.HAMSTRINGS, M.GLUTES),
        P.HIP_EXTENSION,
    ),
    "flat-chest-press": _movement(
        "flat-chest-press", "fedb-0577-lever-lying-chest-press", (M.CHEST,), P.HORIZONTAL_PUSH
    ),
    "incline-chest-press": _movement(
        "incline-chest-press",
        "fedb-1299-lever-incline-hammer-chest-press",
        (M.CHEST,),
        P.HORIZONTAL_PUSH,
    ),
    "chest-fly": _movement(
        "chest-fly",
        "fedb-drv-lever-pec-deck-fly-pec-deck-fly",
        (M.CHEST,),
        P.HORIZONTAL_PUSH,
    ),
    "row": _movement("row", "fedb-0581-lever-high-row", (M.BACK,), P.HORIZONTAL_PULL),
    "seated-cable-row": _movement(
        "seated-cable-row", "fedb-0581-lever-high-row", (M.BACK,), P.HORIZONTAL_PULL
    ),
    "shoulder-press": _movement(
        "shoulder-press", "fedb-0765-smith-seated-shoulder-press", (M.SHOULDERS,), P.VERTICAL_PUSH
    ),
    "lateral-raise": _movement(
        "lateral-raise", "fedb-0584-lever-lateral-raise", (M.SHOULDERS,), P.SHOULDER_ABDUCTION
    ),
    "dumbbell-curl": _movement(
        "dumbbell-curl", "fedb-0592-lever-preacher-curl", (M.BICEPS,), P.ELBOW_FLEXION
    ),
    "hammer-curl": _movement(
        "hammer-curl", "fedb-0592-lever-preacher-curl", (M.BICEPS,), P.ELBOW_FLEXION
    ),
    "overhead-triceps-extension": _movement(
        "overhead-triceps-extension",
        "fedb-1723-cable-triceps-pushdown",
        (M.TRICEPS,),
        P.ELBOW_EXTENSION,
    ),
}


def _shared_slot(
    movement: Movement,
    canonical_slot: TemplateSlotSeed,
    role: str,
    supported_levels: tuple[ExperienceLevel, ...],
) -> TemplateSlotSeed:
    sets, rep_min, rep_max, target_rir, rest_seconds = _prescription_for_role(
        role, supported_levels
    )
    return TemplateSlotSeed(
        exercise_slug_hint=movement.exercise_slug,
        catalog_slug_hints=(movement.exercise_slug,),
        target_muscles=movement.target_muscles,
        movement_pattern=movement.movement_pattern,
        placeholder_name_en=canonical_slot.placeholder_name_en,
        placeholder_name_fa=canonical_slot.placeholder_name_fa,
        sets=sets,
        rep_min=rep_min,
        rep_max=rep_max,
        target_rir=target_rir,
        rest_seconds=rest_seconds,
        intensity_method=canonical_slot.intensity_method,
        adaptation_priority=(
            Priority.CORE
            if role == "primary"
            else Priority.OPTIONAL
            if role == "core"
            else Priority.ACCESSORY
        ),
        superset_group=canonical_slot.superset_group,
    )


def _prescription_for_role(
    role: str,
    supported_levels: tuple[ExperienceLevel, ...],
) -> tuple[int, int, int, int, int]:
    """Return conservative role-specific prescription for the lowest level."""
    if Level.FIRST_MONTH in supported_levels or Level.BEGINNER in supported_levels:
        profiles = {
            "primary": (*NOVICE_DEFAULT_PRESCRIPTION, 3, 120),
            "secondary": (*NOVICE_DEFAULT_PRESCRIPTION, 3, 90),
            "isolation": (3, 10, 15, 3, 60),
            "core": (*NOVICE_DEFAULT_PRESCRIPTION, 3, 60),
        }
    elif Level.INTERMEDIATE in supported_levels:
        profiles = {
            "primary": (3, 6, 10, 2, 120),
            "secondary": (3, 8, 12, 2, 90),
            "isolation": (3, 10, 15, 2, 60),
            "core": (2, 12, 20, 2, 60),
        }
    else:
        profiles = {
            "primary": (4, 5, 8, 1, 150),
            "secondary": (3, 8, 12, 2, 120),
            "isolation": (3, 10, 15, 2, 75),
            "core": (2, 12, 20, 2, 60),
        }
    try:
        return profiles[role]
    except KeyError as error:
        raise ValueError(f"Unknown template slot role: {role}") from error


def _primary(movement: Movement) -> tuple[Movement, str]:
    return movement, "primary"


def _secondary(movement: Movement) -> tuple[Movement, str]:
    return movement, "secondary"


def _isolation(movement: Movement) -> tuple[Movement, str]:
    return movement, "isolation"


def _core(movement: Movement) -> tuple[Movement, str]:
    return movement, "core"


def _day(
    title_en: str,
    title_fa: str,
    structure_focus: str,
    direct_target_muscles: tuple[MuscleGroup, ...],
    *slot_specs: tuple[Movement, str],
    intensity_overrides: dict[str, tuple[TrainingTemplateMethod, str | None]] | None = None,
) -> TemplateDaySeed:
    intensity_overrides = intensity_overrides or {}
    ordered_specs = tuple(sorted(slot_specs, key=lambda item: item[1] == "core"))
    return TemplateDaySeed(
        title_en=title_en,
        title_fa=title_fa,
        structure_focus=structure_focus,
        direct_target_muscles=direct_target_muscles,
        slots=tuple(
            TemplateSlotSeed(
                exercise_slug_hint=movement.key,
                catalog_slug_hints=(movement.key,),
                target_muscles=movement.target_muscles,
                movement_pattern=movement.movement_pattern,
                intensity_method=intensity_overrides.get(movement.key, (Method.STANDARD, None))[0],
                superset_group=intensity_overrides.get(movement.key, (Method.STANDARD, None))[1],
            )
            for movement, _ in ordered_specs
        ),
    )


def _render_shared_day(
    day: TemplateDaySeed,
    specs: tuple[tuple[Movement, str], ...],
    supported_levels: tuple[ExperienceLevel, ...],
) -> TemplateDaySeed:
    use_safe_movements = Level.FIRST_MONTH in supported_levels or Level.BEGINNER in supported_levels
    return TemplateDaySeed(
        title_en=day.title_en,
        title_fa=day.title_fa,
        structure_focus=day.structure_focus,
        direct_target_muscles=day.direct_target_muscles,
        slots=tuple(
            _shared_slot(
                _SAFE_FIRST_MONTH_MOVEMENTS.get(movement.key, movement)
                if use_safe_movements
                else movement,
                canonical_slot,
                role,
                supported_levels,
            )
            for canonical_slot, (movement, role) in zip(day.slots, specs, strict=True)
        ),
    )


def _day_definition(
    title_en: str,
    title_fa: str,
    structure_focus: str,
    direct_target_muscles: tuple[MuscleGroup, ...],
    *slot_specs: tuple[Movement, str],
    intensity_overrides: dict[str, tuple[TrainingTemplateMethod, str | None]] | None = None,
) -> tuple[TemplateDaySeed, tuple[tuple[Movement, str], ...]]:
    ordered_specs = tuple(sorted(slot_specs, key=lambda item: item[1] == "core"))
    return (
        _day(
            title_en,
            title_fa,
            structure_focus,
            direct_target_muscles,
            *slot_specs,
            intensity_overrides=intensity_overrides,
        ),
        ordered_specs,
    )


def _rationale(
    definition: CanonicalTemplateDefinition,
) -> tuple[TemplateProgrammingRationaleSeed, ...]:
    volume_en = (
        "Use the shared sets, rep ranges, RIR, and rest shown for each slot; progress "
        "repetitions before adding load."
    )
    volume_fa = (
        "ست، دامنه تکرار، RIR و استراحت مشترک هر جایگاه را اجرا کن و پیش از افزایش "
        "وزنه، تکرارها را پیش ببر."
    )
    return (
        TemplateProgrammingRationaleSeed(
            "Structure",
            "ساختار",
            definition.guidance_en,
            definition.guidance_fa,
        ),
        TemplateProgrammingRationaleSeed(
            "Exercise order",
            "ترتیب حرکات",
            definition.order_en,
            definition.order_fa,
        ),
        TemplateProgrammingRationaleSeed(
            "Working sets and reps",
            "ست‌ها و تکرارهای کاری",
            volume_en,
            volume_fa,
        ),
        TemplateProgrammingRationaleSeed(
            "Progression",
            "پیشرفت",
            "Progress through the top of the rep range before adding load; keep technique stable across all working sets.",
            "ابتدا تا سقف دامنه تکرار پیش برو و سپس وزنه را اضافه کن؛ فرم را در تمام ست‌های کاری ثابت نگه دار.",
        ),
        TemplateProgrammingRationaleSeed(
            "Recovery and safety",
            "ریکاوری و ایمنی",
            definition.recovery_en,
            definition.recovery_fa,
        ),
    )


def _definition(
    canonical_slug: str,
    name_en: str,
    name_fa: str,
    description_en: str,
    description_fa: str,
    supported_levels: tuple[ExperienceLevel, ...],
    focus_tags: tuple[TemplateFocusTag, ...],
    days: tuple[tuple[TemplateDaySeed, tuple[tuple[Movement, str], ...]], ...],
    guidance_en: str,
    guidance_fa: str,
    order_en: str,
    order_fa: str,
    recovery_en: str,
    recovery_fa: str,
) -> CanonicalTemplateDefinition:
    return CanonicalTemplateDefinition(
        canonical_slug=canonical_slug,
        name_en=name_en,
        name_fa=name_fa,
        description_en=description_en,
        description_fa=description_fa,
        supported_levels=supported_levels,
        focus_tags=validate_focus_tags(focus_tags),
        days=tuple(day for day, _ in days),
        day_specs=tuple(specs for _, specs in days),
        guidance_en=guidance_en,
        guidance_fa=guidance_fa,
        order_en=order_en,
        order_fa=order_fa,
        recovery_en=recovery_en,
        recovery_fa=recovery_fa,
    )


ALL_LEVELS = (Level.FIRST_MONTH, Level.BEGINNER, Level.INTERMEDIATE, Level.ADVANCED)
NO_FIRST_MONTH = (Level.BEGINNER, Level.INTERMEDIATE, Level.ADVANCED)
INTERMEDIATE_ADVANCED = (Level.INTERMEDIATE, Level.ADVANCED)


_DEFINITIONS: tuple[CanonicalTemplateDefinition, ...] = (
    _definition(
        "t01-2-day-full-body-ab",
        "2-Day Full Body A/B",
        "تمام‌بدن دو روزه A/B",
        "Two full-body sessions for users training twice weekly.",
        "دو جلسه تمام‌بدن برای کاربرانی که هفته‌ای دو بار تمرین می‌کنند.",
        (Level.FIRST_MONTH, Level.BEGINNER, Level.INTERMEDIATE),
        (Tag.FULL_BODY,),
        (
            _day_definition(
                "Full Body A",
                "تمام‌بدن A",
                "full_body",
                (
                    M.QUADRICEPS,
                    M.HAMSTRINGS,
                    M.CHEST,
                    M.BACK,
                    M.SHOULDERS,
                    M.BICEPS,
                    M.TRICEPS,
                    M.CALVES,
                ),
                _primary(SQUAT),
                _secondary(SEATED_LEG_CURL),
                _primary(FLAT_PRESS),
                _primary(ROW),
                _secondary(LAT_PULLDOWN),
                _secondary(SHOULDER_PRESS),
            ),
            _day_definition(
                "Full Body B",
                "تمام‌بدن B",
                "full_body",
                (
                    M.QUADRICEPS,
                    M.HAMSTRINGS,
                    M.CHEST,
                    M.BACK,
                    M.SHOULDERS,
                    M.BICEPS,
                    M.TRICEPS,
                    M.CALVES,
                ),
                _primary(LEG_PRESS),
                _primary(RDL),
                _primary(INCLINE_PRESS),
                _primary(SEATED_CABLE_ROW),
                _secondary(LAT_PULLDOWN),
                _isolation(LATERAL_RAISE),
            ),
        ),
        "Two full-body sessions for users training twice weekly. Finish the lower-body block before upper-body work and keep the session practical.",
        "دو جلسه تمام‌بدن برای تمرین دو روز در هفته است. ابتدا بلوک پایین‌تنه را کامل کن، سپس سراغ بالاتنه برو و جلسه را عملی نگه دار.",
        "Complete the lower-body block, then chest, back, and shoulders; each region remains contiguous.",
        "بلوک پایین‌تنه را کامل کن و بعد به سینه، پشت و سرشانه برو؛ هر ناحیه پیوسته می‌ماند.",
        "Keep several recovery days between sessions when possible and progress repetitions before load.",
        "در صورت امکان بین دو جلسه چند روز برای ریکاوری بگذار و پیش از افزایش وزنه، تکرارها را پیش ببر.",
    ),
    _definition(
        "t02-3-day-upper-lower-full",
        "3-Day Upper / Lower / Full",
        "بالاتنه / پایین‌تنه / تمام‌بدن سه روزه",
        "A balanced three-day structure with a broad full-body exposure.",
        "ساختار متعادل سه‌روزه با یک مواجهه گسترده تمام‌بدن.",
        ALL_LEVELS,
        (Tag.UPPER_LOWER,),
        (
            _day_definition(
                "Upper",
                "بالاتنه",
                "upper",
                (M.CHEST, M.BACK, M.SHOULDERS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _primary(ROW),
                _secondary(LAT_PULLDOWN),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
            ),
            _day_definition(
                "Lower",
                "پایین‌تنه",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _primary(RDL),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Full Body",
                "تمام‌بدن",
                "full_body",
                (M.QUADRICEPS, M.HAMSTRINGS, M.CHEST, M.BACK, M.SHOULDERS),
                _primary(LEG_PRESS),
                _secondary(SEATED_LEG_CURL),
                _primary(FLAT_PRESS),
                _primary(SEATED_CABLE_ROW),
                _secondary(LAT_PULLDOWN),
                _isolation(LATERAL_RAISE),
            ),
        ),
        "Use the full-body day as a broad third exposure without adding unnecessary arm work.",
        "روز تمام‌بدن را به‌عنوان مواجهه سوم و گسترده اجرا کن و وقتی جلسه کامل است کار اضافه بازو نگذار.",
        "Upper and lower days use contiguous regional blocks; the full-body day finishes lower body before upper body.",
        "روزهای بالاتنه و پایین‌تنه بلوک‌های پیوسته دارند؛ روز تمام‌بدن ابتدا پایین‌تنه و سپس بالاتنه را کامل می‌کند.",
        "Keep the third exposure compact and leave recovery between related sessions.",
        "مواجهه سوم را فشرده نگه دار و بین جلسات مرتبط زمان ریکاوری بگذار.",
    ),
    _definition(
        "t03-3-day-upper-lower-upper",
        "3-Day Upper / Lower / Upper",
        "بالاتنه / پایین‌تنه / بالاتنه سه روزه",
        "An upper-priority three-day template with planned upper variation.",
        "قالب سه‌روزه با اولویت بالاتنه و تنوع برنامه‌ریزی‌شده در دو جلسه بالاتنه.",
        NO_FIRST_MONTH,
        (Tag.UPPER_LOWER, Tag.UPPER_PRIORITY),
        (
            _day_definition(
                "Upper A",
                "بالاتنه A",
                "upper",
                (M.CHEST, M.BACK, M.SHOULDERS, M.BICEPS, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _primary(ROW),
                _secondary(LAT_PULLDOWN),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(DUMBBELL_CURL),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Lower",
                "پایین‌تنه",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _primary(RDL),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Upper B",
                "بالاتنه B",
                "upper",
                (M.CHEST, M.BACK, M.SHOULDERS, M.BICEPS, M.TRICEPS),
                _primary(INCLINE_PRESS),
                _secondary(FLAT_PRESS),
                _primary(SEATED_CABLE_ROW),
                _secondary(LAT_PULLDOWN),
                _isolation(REAR_DELT_FLY),
                _isolation(LATERAL_RAISE),
                _isolation(HAMMER_CURL),
                _isolation(OVERHEAD_TRICEPS_EXTENSION),
            ),
        ),
        "Use only as an upper-priority catalog option and keep direct arm work after major upper-body muscles.",
        "این گزینه فقط برای اولویت بالاتنه است و کار مستقیم بازو باید بعد از عضلات اصلی بالاتنه بیاید.",
        "Presses lead chest, rows and pulldowns follow for back, then shoulders and arms; the two upper days vary angles deliberately.",
        "پرس‌ها ابتدا سینه، سپس روئینگ و لت پشت، بعد سرشانه و بازو را می‌آورند؛ دو روز بالاتنه عمداً زاویه‌های متفاوت دارند.",
        "Do not overload the single lower session; keep at least one recovery day before the next upper exposure when possible.",
        "جلسه تنها پایین‌تنه را بیش‌ازحد سنگین نکن و در صورت امکان پیش از مواجهه بعدی بالاتنه یک روز ریکاوری بگذار.",
    ),
    _definition(
        "t04-3-day-lower-upper-lower",
        "3-Day Lower / Upper / Lower",
        "پایین‌تنه / بالاتنه / پایین‌تنه سه روزه",
        "A lower-priority three-day template with distinct lower sessions.",
        "قالب سه‌روزه با اولویت پایین‌تنه و دو جلسه متفاوت پا.",
        NO_FIRST_MONTH,
        (Tag.UPPER_LOWER, Tag.LOWER_PRIORITY),
        (
            _day_definition(
                "Lower A",
                "پایین‌تنه A",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _primary(RDL),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Upper",
                "بالاتنه",
                "upper",
                (M.CHEST, M.BACK, M.SHOULDERS, M.BICEPS, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _primary(ROW),
                _secondary(LAT_PULLDOWN),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(DUMBBELL_CURL),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Lower B",
                "پایین‌تنه B",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                _primary(LEG_PRESS),
                _secondary(LUNGE),
                _primary(RDL),
                _secondary(LYING_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
        ),
        "The two lower sessions use different emphasis and should not be identical.",
        "دو جلسه پایین‌تنه تأکیدهای متفاوت دارند و نباید یکسان باشند.",
        "Compounds lead each lower day, followed by leg curls and calves; the upper day stays complete but compact.",
        "حرکات ترکیبی هر روز پایین‌تنه اول می‌آیند و بعد پشت‌پا و ساق قرار می‌گیرند؛ روز بالاتنه کامل اما فشرده است.",
        "Avoid making both lower days heavy for every lower-body muscle and keep recovery between them.",
        "هر دو روز پایین‌تنه را برای همه عضلات سنگین نکن و بین آن‌ها زمان ریکاوری بگذار.",
    ),
    _definition(
        "t05-4-day-upper-lower-2x",
        "4-Day Upper / Lower ×2",
        "بالاتنه / پایین‌تنه دو بار در هفته",
        "The main balanced four-day structure with two exposures per region.",
        "ساختار متعادل اصلی چهارروزه با دو مواجهه برای هر ناحیه.",
        ALL_LEVELS,
        (Tag.UPPER_LOWER,),
        (
            _day_definition(
                "Upper A",
                "بالاتنه A",
                "upper",
                (M.CHEST, M.BACK, M.SHOULDERS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _primary(ROW),
                _secondary(LAT_PULLDOWN),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
            ),
            _day_definition(
                "Lower A",
                "پایین‌تنه A",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _primary(RDL),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Upper B",
                "بالاتنه B",
                "upper",
                (M.CHEST, M.BACK, M.SHOULDERS),
                _primary(INCLINE_PRESS),
                _secondary(FLAT_PRESS),
                _primary(SEATED_CABLE_ROW),
                _secondary(LAT_PULLDOWN),
                _isolation(REAR_DELT_FLY),
                _isolation(LATERAL_RAISE),
            ),
            _day_definition(
                "Lower B",
                "پایین‌تنه B",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(FRONT_SQUAT),
                _isolation(LEG_EXTENSION),
                _primary(RDL),
                _secondary(LYING_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
        ),
        "Each region receives two weekly sessions with controlled A/B movement variation; machines remain valid at every level.",
        "هر ناحیه دو جلسه در هفته دارد و تنوع حرکتی A/B کنترل‌شده است؛ دستگاه‌ها در همه سطوح معتبر می‌مانند.",
        "Upper days group chest, back, and shoulders; lower days group squat or hinge work before isolation.",
        "روزهای بالاتنه سینه، پشت و سرشانه را گروه‌بندی می‌کنند؛ روزهای پایین‌تنه اسکوات یا هینج را پیش از تک‌مفصلی می‌آورند.",
        "Use recovery days between repeated regional exposures and do not add advanced intensity techniques by default.",
        "بین مواجهه‌های تکراری ناحیه‌ای روز ریکاوری بگذار و به‌صورت پیش‌فرض تکنیک‌های شدت پیشرفته اضافه نکن.",
    ),
    _definition(
        "t06-4-day-3-upper-1-lower",
        "4-Day 3 Upper + 1 Lower",
        "چهارروزه؛ سه بالاتنه و یک پایین‌تنه",
        "An upper-priority catalog structure with one complete lower-body session.",
        "ساختار چهارروزه با اولویت بالاتنه و یک جلسه کامل پایین‌تنه.",
        NO_FIRST_MONTH,
        (Tag.UPPER_LOWER, Tag.UPPER_PRIORITY),
        (
            _day_definition(
                "Upper A: Chest + Back",
                "بالاتنه A: سینه + پشت",
                "upper",
                (M.CHEST, M.BACK),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _primary(ROW),
                _secondary(LAT_PULLDOWN),
                _isolation(LATERAL_RAISE),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Lower",
                "پایین‌تنه",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _primary(RDL),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Upper B: Shoulders + Arms",
                "بالاتنه B: سرشانه + بازو",
                "other",
                (M.SHOULDERS, M.BICEPS, M.TRICEPS),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(REAR_DELT_FLY),
                _isolation(DUMBBELL_CURL),
                _isolation(HAMMER_CURL),
                _isolation(TRICEPS_PUSHDOWN),
                _isolation(OVERHEAD_TRICEPS_EXTENSION),
            ),
            _day_definition(
                "Upper C: Chest + Back",
                "بالاتنه C: سینه + پشت",
                "upper",
                (M.CHEST, M.BACK),
                _primary(INCLINE_PRESS),
                _secondary(FLAT_PRESS),
                _primary(SEATED_CABLE_ROW),
                _secondary(LAT_PULLDOWN),
                _isolation(DUMBBELL_CURL),
            ),
        ),
        "Do not make all three upper days identical; the dedicated shoulders-and-arms day limits chest/back repetition.",
        "هر سه روز بالاتنه نباید یکسان باشند؛ روز اختصاصی سرشانه و بازو تکرار سینه و پشت را کنترل می‌کند.",
        "Chest and back lead the first and last upper days; shoulders and arms are placed after the complete lower session.",
        "سینه و پشت روز اول و آخر بالاتنه را هدایت می‌کنند و سرشانه و بازو بعد از جلسه کامل پایین‌تنه قرار می‌گیرند.",
        "Keep the single lower day complete but practical, and use planned variation without forced failure or drop sets.",
        "روز تنها پایین‌تنه را کامل اما عملی نگه دار و از تنوع برنامه‌ریزی‌شده بدون شکست اجباری یا دراپ‌ست استفاده کن.",
    ),
    _definition(
        "t07-4-day-3-lower-1-upper",
        "4-Day 3 Lower + 1 Upper",
        "چهارروزه؛ سه پایین‌تنه و یک بالاتنه",
        "A lower-priority structure rotating quad, posterior, and quad-glute emphasis.",
        "ساختار با اولویت پایین‌تنه که تأکید چهارسر، خلفی و چهارسر-باسن را می‌چرخاند.",
        NO_FIRST_MONTH,
        (Tag.UPPER_LOWER, Tag.LOWER_PRIORITY),
        (
            _day_definition(
                "Lower A: Quad Bias",
                "پایین‌تنه A: تأکید چهارسر",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Upper",
                "بالاتنه",
                "upper",
                (M.CHEST, M.BACK, M.SHOULDERS, M.BICEPS, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _primary(ROW),
                _secondary(LAT_PULLDOWN),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(DUMBBELL_CURL),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Lower B: Posterior Bias",
                "پایین‌تنه B: تأکید خلفی",
                "posterior_chain_core",
                (M.HAMSTRINGS, M.GLUTES),
                _primary(RDL),
                _secondary(LYING_LEG_CURL),
                _primary(GLUTE_BRIDGE),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Lower C: Quad + Glute",
                "پایین‌تنه C: چهارسر + باسن",
                "lower",
                (M.QUADRICEPS, M.GLUTES),
                _primary(LEG_PRESS),
                _isolation(LEG_EXTENSION),
                _primary(GLUTE_BRIDGE),
                _isolation(CALF_RAISE),
            ),
        ),
        "Rotate quad, hamstring, and glute emphasis instead of making all three lower sessions heavy for every muscle.",
        "تأکید چهارسر، همسترینگ و باسن را بچرخان و هر سه روز پایین‌تنه را برای همه عضلات سنگین نکن.",
        "Lower compounds lead each emphasis block, then curls, extensions, and calves follow without scattering muscle work.",
        "حرکات ترکیبی هر بلوک پایین‌تنه اول می‌آیند و بعد پشت‌پا، جلوپا و ساق بدون پراکندگی عضله قرار می‌گیرند.",
        "Keep the upper day efficient and use recovery between the three distinct lower exposures.",
        "روز بالاتنه را کارآمد نگه دار و بین سه مواجهه متفاوت پایین‌تنه ریکاوری کافی بگذار.",
    ),
    _definition(
        "t08-4-day-push-pull-quads-posterior",
        "4-Day Push / Pull / Quads / Posterior",
        "پوش / پول / چهارسر / خلفی چهارروزه",
        "An intermediate and advanced bodybuilding split with distinct quad and posterior days.",
        "تقسیم بدنسازی متوسط و پیشرفته با روزهای جدا برای چهارسر و زنجیره خلفی.",
        INTERMEDIATE_ADVANCED,
        (Tag.PUSH_PULL_LEGS, Tag.BALANCED),
        (
            _day_definition(
                "Push",
                "پوش",
                "push",
                (M.CHEST, M.SHOULDERS, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Pull",
                "پول",
                "pull",
                (M.BACK, M.BICEPS, M.TRAPS),
                _primary(ROW),
                _primary(LAT_PULLDOWN),
                _isolation(DUMBBELL_CURL),
                _isolation(SHRUG),
            ),
            _day_definition(
                "Quads",
                "چهارسر",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS, M.CALVES),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _isolation(LEG_EXTENSION),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Posterior",
                "خلفی",
                "posterior_chain_core",
                (M.HAMSTRINGS, M.GLUTES),
                _primary(RDL),
                _secondary(LYING_LEG_CURL),
                _primary(GLUTE_BRIDGE),
                _secondary(LUNGE),
                _isolation(CALF_RAISE),
            ),
        ),
        "Push and pull stay compound-led while quad and posterior days retain distinct bodybuilding purposes.",
        "روزهای پوش و پول با حرکات ترکیبی شروع می‌شوند و روزهای چهارسر و خلفی هدف جداگانه بدنسازی خود را حفظ می‌کنند.",
        "Complete chest before shoulder isolation on push; complete horizontal and vertical pulling before biceps and traps.",
        "در پوش ابتدا سینه و سپس تک‌مفصلی سرشانه را کامل کن؛ در پول کشش افقی و عمودی پیش از جلو بازو و کول انجام می‌شود.",
        "Keep each session practical and separate the quad and posterior exposures with appropriate recovery.",
        "هر جلسه را عملی نگه دار و مواجهه‌های چهارسر و خلفی را با ریکاوری مناسب جدا کن.",
    ),
    _definition(
        "t09-5-day-ppl-upper-lower",
        "5-Day PPL + Upper + Lower",
        "پنج‌روزه PPL + بالاتنه + پایین‌تنه",
        "A balanced five-day bodybuilding structure combining focused and broad exposures.",
        "ساختار متعادل پنج‌روزه بدنسازی با ترکیب جلسات متمرکز و گسترده.",
        INTERMEDIATE_ADVANCED,
        (Tag.PUSH_PULL_LEGS, Tag.UPPER_LOWER),
        (
            _day_definition(
                "Push",
                "پوش",
                "push",
                (M.CHEST, M.SHOULDERS, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Pull",
                "پول",
                "pull",
                (M.BACK, M.BICEPS, M.TRAPS),
                _primary(ROW),
                _primary(LAT_PULLDOWN),
                _isolation(DUMBBELL_CURL),
                _isolation(HAMMER_CURL),
                _isolation(SHRUG),
            ),
            _day_definition(
                "Legs",
                "پا",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _primary(RDL),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Upper",
                "بالاتنه",
                "upper",
                (M.CHEST, M.BACK, M.SHOULDERS, M.BICEPS, M.TRICEPS),
                _primary(FLAT_PRESS),
                _primary(SEATED_CABLE_ROW),
                _secondary(LAT_PULLDOWN),
                _isolation(LATERAL_RAISE),
                _isolation(DUMBBELL_CURL),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Lower",
                "پایین‌تنه",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                _primary(FRONT_SQUAT),
                _secondary(LYING_LEG_CURL),
                _primary(GLUTE_BRIDGE),
                _isolation(CALF_RAISE),
            ),
        ),
        "PPL provides focused sessions and Upper/Lower adds another broad exposure without redundant extra work.",
        "PPL جلسات متمرکز می‌دهد و بالاتنه/پایین‌تنه یک مواجهه گسترده دیگر بدون کار اضافی تکراری اضافه می‌کند.",
        "Push, pull, and legs remain coherent blocks; upper and lower days keep their regional order and compound-first sequence.",
        "پوش، پول و پا بلوک‌های منسجم می‌مانند؛ روزهای بالاتنه و پایین‌تنه ترتیب ناحیه‌ای و ترکیبی-اول را حفظ می‌کنند.",
        "Avoid redundant exercises and keep at least one recovery day before repeating a demanding region.",
        "از حرکات تکراری غیرضروری پرهیز کن و پیش از تکرار ناحیه پرفشار دست‌کم یک روز ریکاوری بگذار.",
    ),
    _definition(
        "t10-5-day-classic-body-part",
        "5-Day Classic Body-Part",
        "پنج‌روزه کلاسیک عضله‌ای",
        "Classic body-part organization with controlled direct volume.",
        "سازمان‌دهی کلاسیک عضله‌ای با حجم مستقیم کنترل‌شده.",
        INTERMEDIATE_ADVANCED,
        (Tag.BODY_PART_ROTATION, Tag.BALANCED),
        (
            _day_definition(
                "Chest",
                "سینه",
                "chest_triceps",
                (M.CHEST, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _isolation(CHEST_FLY),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Back",
                "پشت",
                "back_biceps",
                (M.BACK, M.BICEPS),
                _primary(ROW),
                _primary(LAT_PULLDOWN),
                _secondary(SEATED_CABLE_ROW),
                _isolation(DUMBBELL_CURL),
            ),
            _day_definition(
                "Legs",
                "پا",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _primary(RDL),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Shoulders",
                "سرشانه",
                "shoulders_traps",
                (M.SHOULDERS, M.TRAPS),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(REAR_DELT_FLY),
                _isolation(SHRUG),
            ),
            _day_definition(
                "Arms",
                "بازو",
                "other",
                (M.BICEPS, M.TRICEPS),
                _isolation(BARBELL_CURL),
                _isolation(CABLE_CURL),
                _isolation(TRICEPS_PUSHDOWN),
                _isolation(OVERHEAD_TRICEPS_EXTENSION),
            ),
        ),
        "Major compounds lead dedicated days and direct arm work follows the larger-muscle training of the week.",
        "حرکات ترکیبی اصلی در ابتدای روزهای اختصاصی می‌آیند و کار مستقیم بازو در هفته بعد از عضلات بزرگ‌تر قرار می‌گیرد.",
        "Chest, back, and legs begin with multi-joint work; fly, curls, extensions, and calves stay after the main work.",
        "سینه، پشت و پا با کار چندمفصلی شروع می‌شوند؛ فلای، جلو بازو، پشت بازو و ساق بعد از کار اصلی می‌آیند.",
        "Keep direct volume controlled and do not require drop sets, rest-pause, or forced failure.",
        "حجم مستقیم را کنترل کن و دراپ‌ست، رست‌پاز یا شکست اجباری را الزامی نکن.",
    ),
    _definition(
        "t11-5-day-ppl-upper-lower-priority",
        "5-Day PPL + Upper Priority + Lower Priority",
        "پنج‌روزه PPL با اولویت بالاتنه و پایین‌تنه",
        "A higher-volume five-day structure with meaningful second exposures.",
        "ساختار پنج‌روزه با حجم بیشتر و مواجهه دوم معنادار.",
        INTERMEDIATE_ADVANCED,
        (Tag.PUSH_PULL_LEGS, Tag.UPPER_LOWER, Tag.UPPER_PRIORITY),
        (
            _day_definition(
                "Push",
                "پوش",
                "push",
                (M.CHEST, M.SHOULDERS, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Pull",
                "پول",
                "pull",
                (M.BACK, M.BICEPS, M.TRAPS),
                _primary(ROW),
                _primary(LAT_PULLDOWN),
                _isolation(DUMBBELL_CURL),
                _isolation(HAMMER_CURL),
                _isolation(SHRUG),
            ),
            _day_definition(
                "Legs",
                "پا",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _primary(RDL),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Upper Priority",
                "اولویت بالاتنه",
                "upper",
                (M.CHEST, M.BACK, M.SHOULDERS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _primary(ROW),
                _secondary(LAT_PULLDOWN),
                _isolation(LATERAL_RAISE),
            ),
            _day_definition(
                "Lower Priority",
                "اولویت پایین‌تنه",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _primary(RDL),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
        ),
        "Priority days are meaningful second exposures, not permission for excessive per-session volume.",
        "روزهای اولویت، مواجهه دوم معنادار هستند و مجوز حجم بیش‌ازحد در هر جلسه نیستند.",
        "Use compound-before-isolation ordering on every PPL and priority day, with no redundant extra exercise.",
        "در هر روز PPL و اولویت، ترتیب ترکیبی پیش از تک‌مفصلی را حفظ کن و حرکت اضافی تکراری نگذار.",
        "Use straightforward prescriptions and preserve recovery between the two lower exposures.",
        "نسخه‌نویسی ساده را حفظ کن و بین دو مواجهه پایین‌تنه ریکاوری کافی بگذار.",
    ),
    _definition(
        "t12-5-day-chest-specialization",
        "5-Day Chest Specialization",
        "پنج‌روزه تخصص سینه",
        "A chest-priority option that keeps all other major regions trained.",
        "گزینه با اولویت سینه که همه نواحی اصلی دیگر را نیز تمرین می‌دهد.",
        INTERMEDIATE_ADVANCED,
        (Tag.BODY_PART_ROTATION, Tag.CHEST_PRIORITY, Tag.SPECIALIZATION),
        (
            _day_definition(
                "Chest + Triceps",
                "سینه + پشت بازو",
                "other",
                (M.CHEST, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _isolation(CHEST_FLY),
                _isolation(TRICEPS_PUSHDOWN),
                _isolation(OVERHEAD_TRICEPS_EXTENSION),
            ),
            _day_definition(
                "Back + Biceps",
                "پشت + جلو بازو",
                "back_biceps",
                (M.BACK, M.BICEPS),
                _primary(ROW),
                _primary(LAT_PULLDOWN),
                _isolation(DUMBBELL_CURL),
                _isolation(HAMMER_CURL),
                _isolation(REAR_DELT_FLY),
            ),
            _day_definition(
                "Legs",
                "پا",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _primary(RDL),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Shoulders + Arms",
                "سرشانه + بازو",
                "other",
                (M.SHOULDERS, M.BICEPS, M.TRICEPS),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(REAR_DELT_FLY),
                _isolation(DUMBBELL_CURL),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Chest Priority",
                "اولویت سینه",
                "other",
                (M.CHEST,),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _isolation(CHEST_FLY),
                _isolation(CALF_RAISE),
            ),
        ),
        "Chest receives two direct weekly sessions; other regions remain trained without excessive direct chest volume.",
        "سینه دو جلسه مستقیم هفتگی دارد و نواحی دیگر نیز بدون حجم مستقیم بیش‌ازحد سینه تمرین می‌شوند.",
        "Finish both chest presses before fly work; place triceps after chest and keep the priority-day calf work last.",
        "هر دو پرس سینه را پیش از فلای تمام کن؛ پشت بازو بعد از سینه و کار ساق روز اولویت در انتها باشد.",
        "Use this only when chest priority is intended and keep the non-chest days recoverable.",
        "این قالب را فقط با قصد اولویت سینه استفاده کن و روزهای غیرسینه را قابل‌ریکاوری نگه دار.",
    ),
    _definition(
        "t13-5-day-back-specialization",
        "5-Day Back Specialization",
        "پنج‌روزه تخصص پشت",
        "A back-priority option with horizontal and vertical pulling on both exposures.",
        "گزینه با اولویت پشت و کشش افقی و عمودی در هر دو مواجهه.",
        INTERMEDIATE_ADVANCED,
        (Tag.BODY_PART_ROTATION, Tag.BACK_PRIORITY, Tag.SPECIALIZATION),
        (
            _day_definition(
                "Back + Biceps",
                "پشت + جلو بازو",
                "back_biceps",
                (M.BACK, M.BICEPS),
                _primary(ROW),
                _primary(LAT_PULLDOWN),
                _secondary(SEATED_CABLE_ROW),
                _isolation(DUMBBELL_CURL),
                _isolation(HAMMER_CURL),
            ),
            _day_definition(
                "Chest + Triceps",
                "سینه + پشت بازو",
                "chest_triceps",
                (M.CHEST, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _isolation(TRICEPS_PUSHDOWN),
                _isolation(OVERHEAD_TRICEPS_EXTENSION),
            ),
            _day_definition(
                "Legs",
                "پا",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _primary(RDL),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Shoulders + Arms",
                "سرشانه + بازو",
                "other",
                (M.SHOULDERS, M.BICEPS, M.TRICEPS),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(REAR_DELT_FLY),
                _isolation(DUMBBELL_CURL),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Back Priority",
                "اولویت پشت",
                "back_biceps",
                (M.BACK,),
                _primary(ROW),
                _primary(LAT_PULLDOWN),
                _secondary(STRAIGHT_ARM_PULLDOWN),
                _isolation(CALF_RAISE),
            ),
        ),
        "Back receives two direct sessions with both horizontal and vertical pulling; biceps follow back work.",
        "پشت دو جلسه مستقیم با کشش افقی و عمودی دارد و جلو بازو بعد از کار پشت قرار می‌گیرد.",
        "Rows and pulldowns lead both back exposures; straight-arm pulldown stays accessory after compounds.",
        "روئینگ و لت هر دو مواجهه پشت را هدایت می‌کنند و پلاور دست‌صاف بعد از حرکات ترکیبی کمکی می‌ماند.",
        "Use this only for a true back-priority goal and keep the priority day compact.",
        "این قالب را فقط برای هدف واقعی اولویت پشت استفاده کن و روز اولویت را فشرده نگه دار.",
    ),
    _definition(
        "t14-5-day-leg-specialization",
        "5-Day Leg Specialization",
        "پنج‌روزه تخصص پا",
        "A leg-priority option splitting quad and posterior-chain emphasis.",
        "گزینه با اولویت پا که تأکید چهارسر و زنجیره خلفی را جدا می‌کند.",
        INTERMEDIATE_ADVANCED,
        (Tag.BODY_PART_ROTATION, Tag.LOWER_PRIORITY, Tag.HAMSTRINGS_PRIORITY),
        (
            _day_definition(
                "Quads",
                "چهارسر",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS, M.CALVES),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _isolation(LEG_EXTENSION),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Chest",
                "سینه",
                "chest_triceps",
                (M.CHEST, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _isolation(CHEST_FLY),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Back",
                "پشت",
                "back_biceps",
                (M.BACK, M.BICEPS),
                _primary(ROW),
                _primary(LAT_PULLDOWN),
                _secondary(SEATED_CABLE_ROW),
                _isolation(DUMBBELL_CURL),
            ),
            _day_definition(
                "Shoulders + Arms",
                "سرشانه + بازو",
                "other",
                (M.SHOULDERS, M.BICEPS, M.TRICEPS),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(REAR_DELT_FLY),
                _isolation(DUMBBELL_CURL),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Posterior Chain",
                "زنجیره خلفی",
                "posterior_chain_core",
                (M.HAMSTRINGS, M.GLUTES),
                _primary(RDL),
                _secondary(LYING_LEG_CURL),
                _primary(GLUTE_BRIDGE),
                _secondary(LUNGE),
                _isolation(CALF_RAISE),
            ),
        ),
        "Split quad and posterior emphasis; hamstrings receive both hinge and curl patterns without excessive specialization volume.",
        "تأکید چهارسر و خلفی جداست؛ همسترینگ هم الگوی هینج و هم پشت‌پا را می‌گیرد، بدون حجم تخصصی افراطی.",
        "Lower-body compounds lead the quad and posterior days; isolation follows the relevant compound block.",
        "حرکات ترکیبی پایین‌تنه روزهای چهارسر و خلفی را هدایت می‌کنند و تک‌مفصلی بعد از بلوک ترکیبی مرتبط می‌آید.",
        "Use only as a leg-priority catalog option and preserve recovery before repeating lower-body stress.",
        "این قالب را فقط به‌عنوان گزینه اولویت پا استفاده کن و پیش از تکرار فشار پایین‌تنه ریکاوری را حفظ کن.",
    ),
    _definition(
        "t15-6-day-ppl-2x",
        "6-Day PPL ×2",
        "PPL دو بار در هفته",
        "Two planned push, pull, and legs rotations with purposeful A/B variation.",
        "دو چرخه برنامه‌ریزی‌شده پوش، پول و پا با تنوع هدفمند A/B.",
        INTERMEDIATE_ADVANCED,
        (Tag.PUSH_PULL_LEGS,),
        (
            _day_definition(
                "Push A",
                "پوش A",
                "push",
                (M.CHEST, M.SHOULDERS, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Pull A",
                "پول A",
                "pull",
                (M.BACK, M.BICEPS, M.TRAPS),
                _primary(ROW),
                _primary(LAT_PULLDOWN),
                _isolation(DUMBBELL_CURL),
                _isolation(HAMMER_CURL),
                _isolation(SHRUG),
            ),
            _day_definition(
                "Legs A",
                "پا A",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _primary(RDL),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Push B",
                "پوش B",
                "push",
                (M.CHEST, M.SHOULDERS, M.TRICEPS),
                _primary(FLAT_PRESS),
                _isolation(CHEST_FLY),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(OVERHEAD_TRICEPS_EXTENSION),
            ),
            _day_definition(
                "Pull B",
                "پول B",
                "pull",
                (M.BACK, M.BICEPS, M.TRAPS),
                _primary(SEATED_CABLE_ROW),
                _primary(LAT_PULLDOWN),
                _isolation(DUMBBELL_CURL),
                _isolation(HAMMER_CURL),
                _isolation(SHRUG),
            ),
            _day_definition(
                "Legs B",
                "پا B",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                _primary(RDL),
                _secondary(LYING_LEG_CURL),
                _primary(FRONT_SQUAT),
                _primary(GLUTE_BRIDGE),
                _isolation(CALF_RAISE),
            ),
        ),
        "A/B variation is purposeful; Push B completes chest before shoulders and posterior work does not replace later compounds.",
        "تنوع A/B هدفمند است؛ پوش B سینه را پیش از سرشانه کامل می‌کند و کار خلفی جای حرکات ترکیبی بعدی را نمی‌گیرد.",
        "Each day follows push, pull, or lower-body blocks; chest finishes before shoulders on both push days.",
        "هر روز بلوک پوش، پول یا پایین‌تنه خود را حفظ می‌کند؛ در هر دو روز پوش سینه پیش از سرشانه تمام می‌شود.",
        "Six days require planned recovery and no mandatory advanced intensity techniques.",
        "شش روز تمرین به ریکاوری برنامه‌ریزی‌شده نیاز دارد و تکنیک شدت پیشرفته الزامی نیست.",
    ),
    _definition(
        "t16-6-day-advanced-body-part",
        "6-Day Advanced Body-Part",
        "شش‌روزه پیشرفته عضله‌ای",
        "An advanced body-part option with a clear focus on every day.",
        "گزینه پیشرفته عضله‌ای با تمرکز روشن در هر روز.",
        (Level.ADVANCED,),
        (Tag.BODY_PART_ROTATION, Tag.BALANCED),
        (
            _day_definition(
                "Chest",
                "سینه",
                "chest_triceps",
                (M.CHEST, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _isolation(CHEST_FLY),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Back",
                "پشت",
                "back_biceps",
                (M.BACK, M.BICEPS),
                _primary(ROW),
                _primary(LAT_PULLDOWN),
                _secondary(SEATED_CABLE_ROW),
                _isolation(DUMBBELL_CURL),
            ),
            _day_definition(
                "Quads",
                "چهارسر",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS, M.CALVES),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _isolation(LEG_EXTENSION),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Shoulders",
                "سرشانه",
                "shoulders_traps",
                (M.SHOULDERS, M.TRAPS),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(REAR_DELT_FLY),
                _isolation(SHRUG),
            ),
            _day_definition(
                "Arms",
                "بازو",
                "other",
                (M.BICEPS, M.TRICEPS),
                _isolation(BARBELL_CURL),
                _isolation(CABLE_CURL),
                _isolation(TRICEPS_PUSHDOWN),
                _isolation(OVERHEAD_TRICEPS_EXTENSION),
                intensity_overrides={
                    "cable-curl": (Method.SUPERSET, "t16-arms-superset"),
                    "triceps-pushdown": (Method.SUPERSET, "t16-arms-superset"),
                    "overhead-triceps-extension": (Method.DROP_SET, None),
                },
            ),
            _day_definition(
                "Hamstrings + Glutes",
                "همسترینگ + باسن",
                "lower",
                (M.HAMSTRINGS, M.GLUTES, M.QUADRICEPS, M.CALVES),
                _primary(RDL),
                _secondary(LYING_LEG_CURL),
                _primary(GLUTE_BRIDGE),
                _secondary(LUNGE),
                _isolation(CALF_RAISE),
            ),
        ),
        "Each day has a clear focus and uses appropriate modalities without automatically adding advanced intensity methods.",
        "هر روز تمرکز روشن دارد و از وسایل مناسب استفاده می‌کند، بدون افزودن خودکار تکنیک‌های شدت پیشرفته.",
        "Dedicated days place major compounds before isolation; arms and calves remain after the main regional block.",
        "روزهای اختصاصی حرکات ترکیبی اصلی را پیش از تک‌مفصلی می‌آورند؛ بازو و ساق بعد از بلوک اصلی ناحیه‌ای می‌آیند.",
        "Use this advanced option only when six-day recovery is realistic and keep technique ahead of fatigue.",
        "این گزینه پیشرفته را فقط وقتی استفاده کن که ریکاوری شش‌روزه واقع‌بینانه باشد و فرم بر خستگی مقدم بماند.",
    ),
    _definition(
        "t17-6-day-balanced-specialization",
        "6-Day Balanced Specialization",
        "شش‌روزه تخصص متعادل",
        "An advanced high-frequency option with clear second-exposure emphasis.",
        "گزینه پیشرفته پرتکرار با تأکید روشن در مواجهه‌های دوم.",
        (Level.ADVANCED,),
        (Tag.PUSH_PULL_LEGS, Tag.CHEST_PRIORITY, Tag.BACK_PRIORITY, Tag.SPECIALIZATION),
        (
            _day_definition(
                "Push",
                "پوش",
                "push",
                (M.CHEST, M.SHOULDERS, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(TRICEPS_PUSHDOWN),
            ),
            _day_definition(
                "Pull",
                "پول",
                "pull",
                (M.BACK, M.BICEPS, M.TRAPS),
                _primary(ROW),
                _primary(LAT_PULLDOWN),
                _isolation(DUMBBELL_CURL),
                _isolation(HAMMER_CURL),
                _isolation(SHRUG),
            ),
            _day_definition(
                "Legs",
                "پا",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS),
                _primary(SQUAT),
                _primary(LEG_PRESS),
                _primary(RDL),
                _secondary(SEATED_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
            _day_definition(
                "Chest Priority",
                "اولویت سینه",
                "other",
                (M.CHEST, M.TRICEPS),
                _primary(FLAT_PRESS),
                _secondary(INCLINE_PRESS),
                _isolation(CHEST_FLY),
                _isolation(TRICEPS_PUSHDOWN),
                intensity_overrides={
                    "chest-fly": (Method.SUPERSET, "t17-chest-superset"),
                    "triceps-pushdown": (Method.SUPERSET, "t17-chest-superset"),
                },
            ),
            _day_definition(
                "Back + Delts Priority",
                "اولویت پشت + دلت",
                "other",
                (M.BACK, M.SHOULDERS),
                _primary(SEATED_CABLE_ROW),
                _primary(LAT_PULLDOWN),
                _secondary(STRAIGHT_ARM_PULLDOWN),
                _primary(SHOULDER_PRESS),
                _isolation(LATERAL_RAISE),
                _isolation(REAR_DELT_FLY),
                intensity_overrides={"lateral-raise": (Method.DROP_SET, None)},
            ),
            _day_definition(
                "Legs Priority",
                "اولویت پا",
                "lower",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                _primary(FRONT_SQUAT),
                _primary(LEG_PRESS),
                _secondary(LUNGE),
                _primary(RDL),
                _secondary(LYING_LEG_CURL),
                _isolation(CALF_RAISE),
            ),
        ),
        "Second exposures have clear emphasis while chest, back, and lower-body volume stays controlled.",
        "مواجهه‌های دوم تأکید روشن دارند و حجم سینه، پشت و پایین‌تنه کنترل‌شده باقی می‌ماند.",
        "Finish chest before shoulders on push days, back before delts on the priority day, and lower-body blocks before accessories.",
        "در روز پوش سینه را پیش از سرشانه، در روز اولویت پشت را پیش از دلت و در روز پا بلوک پایین‌تنه را پیش از کمکی‌ها تمام کن.",
        "Use planned movement variation and only choose this six-day option when recovery is reliable.",
        "تنوع حرکتی برنامه‌ریزی‌شده داشته باش و این گزینه شش‌روزه را فقط با ریکاوری قابل‌اعتماد انتخاب کن.",
    ),
)


CANONICAL_TEMPLATE_DEFINITIONS = _DEFINITIONS


def _seed_from_definition(
    definition: CanonicalTemplateDefinition,
) -> TrainingProgramTemplateSeed:
    days = tuple(
        _render_shared_day(day, specs, definition.supported_levels)
        for day, specs in zip(
            definition.days,
            definition.day_specs,
            strict=True,
        )
    )
    intensity_methods = tuple(
        dict.fromkeys(slot.intensity_method for day in days for slot in day.slots)
    )
    seed = TrainingProgramTemplateSeed(
        canonical_slug=definition.canonical_slug,
        slug=definition.canonical_slug,
        name_en=definition.name_en,
        name_fa=definition.name_fa,
        description_en=definition.description_en,
        description_fa=definition.description_fa,
        days_per_week=len(days),
        supported_levels=definition.supported_levels,
        focus_tags=definition.focus_tags,
        intensity_methods=intensity_methods,
        days=days,
        programming_rationale=_rationale(definition),
    )
    validate_template_focus_tags(
        seed.focus_tags,
        intensity_methods=seed.intensity_methods,
        days=seed.days,
    )
    return seed


TRAINING_PROGRAM_TEMPLATE_SEEDS = tuple(
    _seed_from_definition(definition) for definition in CANONICAL_TEMPLATE_DEFINITIONS
)


# The Default Program Library is intentionally level-specific.  The existing
# TrainingProgramTemplate tables remain the storage model; each approved
# program is one deterministic template row with one supported level.
SMITH_CHAIR_SQUAT = _movement(
    "smith-chair-squat",
    "fedb-0750-smith-chair-squat",
    (M.QUADRICEPS,),
    P.SQUAT,
)
MACHINE_CHEST_PRESS = _movement(
    "machine-chest-press",
    "fedb-0577-lever-lying-chest-press",
    (M.CHEST,),
    P.HORIZONTAL_PUSH,
)
MACHINE_INCLINE_PRESS = _movement(
    "machine-incline-press",
    "fedb-1299-lever-incline-hammer-chest-press",
    (M.CHEST,),
    P.HORIZONTAL_PUSH,
)
HIGH_ROW = _movement(
    "high-row",
    "fedb-0581-lever-high-row",
    (M.BACK,),
    P.HORIZONTAL_PULL,
)
SMITH_SHOULDER_PRESS = _movement(
    "smith-shoulder-press",
    "fedb-0765-smith-seated-shoulder-press",
    (M.SHOULDERS,),
    P.VERTICAL_PUSH,
)
LEVER_LATERAL_RAISE = _movement(
    "lever-lateral-raise",
    "fedb-0584-lever-lateral-raise",
    (M.SHOULDERS,),
    P.SHOULDER_ABDUCTION,
)

_ROLE_NAMES = {"P": "primary", "S": "secondary", "I": "isolation"}
_APPROVED_STRUCTURE_NAMES = {
    "2d-full-body-ab": ("2-Day Full Body A/B", "تمام‌بدن دو روزه A/B"),
    "3d-upper-lower-full-body": (
        "3-Day Upper / Lower / Full",
        "بالاتنه / پایین‌تنه / تمام‌بدن سه روزه",
    ),
    "3d-upper-lower-upper": (
        "3-Day Upper / Lower / Upper",
        "بالاتنه / پایین‌تنه / بالاتنه سه روزه",
    ),
    "3d-lower-upper-lower": (
        "3-Day Lower / Upper / Lower",
        "پایین‌تنه / بالاتنه / پایین‌تنه سه روزه",
    ),
    "4d-upper-lower-2x": (
        "4-Day Upper / Lower / Upper / Lower",
        "بالاتنه / پایین‌تنه / بالاتنه / پایین‌تنه چهار روزه",
    ),
    "4d-3-upper-1-lower": (
        "4-Day 3 Upper + 1 Lower",
        "چهارروزه؛ سه بالاتنه و یک پایین‌تنه",
    ),
    "4d-3-lower-1-upper": (
        "4-Day 3 Lower + 1 Upper",
        "چهارروزه؛ سه پایین‌تنه و یک بالاتنه",
    ),
    "4d-push-pull-quads-posterior": (
        "4-Day Push / Pull / Quads / Posterior",
        "پوش / پول / چهارسر / خلفی چهارروزه",
    ),
}
_LEVEL_NAMES = {
    Level.FIRST_MONTH: ("First Month", "ماه اول"),
    Level.BEGINNER: ("Beginner", "مبتدی"),
    Level.INTERMEDIATE: ("Intermediate", "متوسط"),
    Level.ADVANCED: ("Advanced", "پیشرفته"),
}
_LEVEL_SLUG_SUFFIX = {
    Level.FIRST_MONTH: "first-month",
    Level.BEGINNER: "beginner",
    Level.INTERMEDIATE: "intermediate",
    Level.ADVANCED: "advanced",
}
_APPROVED_TAGS = {
    "2d-full-body-ab": (Tag.FULL_BODY,),
    "3d-upper-lower-full-body": (Tag.UPPER_LOWER,),
    "3d-upper-lower-upper": (Tag.UPPER_LOWER, Tag.UPPER_PRIORITY),
    "3d-lower-upper-lower": (Tag.UPPER_LOWER, Tag.LOWER_PRIORITY),
    "4d-upper-lower-2x": (Tag.UPPER_LOWER,),
    "4d-3-upper-1-lower": (Tag.UPPER_LOWER, Tag.UPPER_PRIORITY),
    "4d-3-lower-1-upper": (Tag.UPPER_LOWER, Tag.LOWER_PRIORITY),
    "4d-push-pull-quads-posterior": (Tag.PUSH_PULL_LEGS, Tag.BALANCED),
}
_APPROVED_DAY_TITLES_FA = {
    "Full Body A": "تمام‌بدن A",
    "Full Body B": "تمام‌بدن B",
    "Upper": "بالاتنه",
    "Upper A": "بالاتنه A",
    "Upper B": "بالاتنه B",
    "Lower": "پایین‌تنه",
    "Lower A": "پایین‌تنه A",
    "Lower B": "پایین‌تنه B",
    "Lower C": "پایین‌تنه C",
    "Full": "تمام‌بدن",
    "Upper C": "بالاتنه C",
    "Push": "پوش",
    "Pull": "پول",
    "Quads": "چهارسر",
    "Posterior": "خلفی",
}

_UPPER_MUSCLES = (M.CHEST, M.BACK, M.SHOULDERS, M.BICEPS, M.TRICEPS)
_LOWER_MUSCLES = (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES)
_FULL_BODY_MUSCLES = _LOWER_MUSCLES + _UPPER_MUSCLES


def _approved_day(
    title_en: str,
    structure_focus: str,
    direct_target_muscles: tuple[MuscleGroup, ...],
    *slot_specs: tuple[Movement, str],
) -> tuple[TemplateDaySeed, tuple[tuple[Movement, str], ...]]:
    specs = tuple(slot_specs)
    return (
        TemplateDaySeed(
            title_en=title_en,
            title_fa=_APPROVED_DAY_TITLES_FA[title_en],
            structure_focus=structure_focus,
            direct_target_muscles=direct_target_muscles,
            slots=tuple(
                TemplateSlotSeed(
                    exercise_slug_hint=movement.exercise_slug,
                    catalog_slug_hints=(movement.exercise_slug,),
                    target_muscles=movement.target_muscles,
                    movement_pattern=movement.movement_pattern,
                )
                for movement, _ in specs
            ),
        ),
        specs,
    )


def _approved_definition(
    slug: str,
    structure_slug: str,
    level: ExperienceLevel,
    days: tuple[tuple[TemplateDaySeed, tuple[tuple[Movement, str], ...]], ...],
) -> CanonicalTemplateDefinition:
    structure_name_en, structure_name_fa = _APPROVED_STRUCTURE_NAMES[structure_slug]
    level_name_en, level_name_fa = _LEVEL_NAMES[level]
    return CanonicalTemplateDefinition(
        canonical_slug=slug,
        name_en=f"{structure_name_en} — {level_name_en}",
        name_fa=f"{structure_name_fa} — {level_name_fa}",
        description_en=f"Approved Fitsho default program: {structure_name_en} for {level_name_en} trainees.",
        description_fa=f"برنامه پیش‌فرض تأییدشده فیتشو: {structure_name_fa} برای سطح {level_name_fa}.",
        supported_levels=(level,),
        focus_tags=_APPROVED_TAGS[structure_slug],
        days=tuple(day for day, _ in days),
        day_specs=tuple(specs for _, specs in days),
        guidance_en="Follow the approved day order and keep the prescribed effort target for this level.",
        guidance_fa="ترتیب روزهای تأییدشده را اجرا کن و هدف تلاش تعیین‌شده برای این سطح را حفظ کن.",
        order_en="Complete exercises in the listed order.",
        order_fa="حرکت‌ها را به همان ترتیب فهرست‌شده اجرا کن.",
        recovery_en="Keep recovery days between repeated regional exposures when possible.",
        recovery_fa="در صورت امکان بین مواجهه‌های تکراری ناحیه‌ای روزهای ریکاوری بگذار.",
        structure_slug=structure_slug,
    )


def _approved_seed_from_definition(
    definition: CanonicalTemplateDefinition,
) -> TrainingProgramTemplateSeed:
    level = definition.supported_levels[0]
    days = tuple(
        TemplateDaySeed(
            title_en=day.title_en,
            title_fa=day.title_fa,
            structure_focus=day.structure_focus,
            direct_target_muscles=day.direct_target_muscles,
            slots=tuple(
                _shared_slot(
                    movement,
                    canonical_slot,
                    _ROLE_NAMES[role],
                    (level,),
                )
                for canonical_slot, (movement, role) in zip(
                    day.slots,
                    specs,
                    strict=True,
                )
            ),
        )
        for day, specs in zip(definition.days, definition.day_specs, strict=True)
    )
    seed = TrainingProgramTemplateSeed(
        canonical_slug=definition.canonical_slug,
        slug=definition.canonical_slug,
        name_en=definition.name_en,
        name_fa=definition.name_fa,
        description_en=definition.description_en,
        description_fa=definition.description_fa,
        days_per_week=len(days),
        supported_levels=definition.supported_levels,
        focus_tags=definition.focus_tags,
        intensity_methods=(Method.STANDARD,),
        days=days,
        programming_rationale=(
            TemplateProgrammingRationaleSeed(
                "Structure",
                "ساختار",
                definition.guidance_en,
                definition.guidance_fa,
            ),
            TemplateProgrammingRationaleSeed(
                "Exercise order",
                "ترتیب حرکات",
                definition.order_en,
                definition.order_fa,
            ),
            TemplateProgrammingRationaleSeed(
                "Working sets and reps",
                "ست‌ها و تکرارهای کاری",
                "Use the prescribed sets, rep range, RIR, and rest for this training level.",
                "ست‌ها، دامنه تکرار، RIR و استراحت تعیین‌شده برای این سطح را اجرا کن.",
            ),
            TemplateProgrammingRationaleSeed(
                "Progression",
                "پیشرفت",
                "Progress through the top of the rep range before adding load.",
                "پیش از افزایش وزنه، در دامنه تکرار تا سقف پیشرفت کن.",
            ),
            TemplateProgrammingRationaleSeed(
                "Recovery and safety",
                "ریکاوری و ایمنی",
                definition.recovery_en,
                definition.recovery_fa,
            ),
        ),
        structure_slug=definition.structure_slug,
    )
    validate_template_focus_tags(
        seed.focus_tags,
        intensity_methods=seed.intensity_methods,
        days=seed.days,
    )
    return seed


_FULL_BODY_FIRST_MONTH = (
    _approved_day(
        "Full Body A",
        "full_body",
        _FULL_BODY_MUSCLES,
        (SMITH_CHAIR_SQUAT, "P"),
        (SEATED_LEG_CURL, "S"),
        (MACHINE_CHEST_PRESS, "P"),
        (HIGH_ROW, "P"),
        (LAT_PULLDOWN, "S"),
        (SMITH_SHOULDER_PRESS, "S"),
    ),
    _approved_day(
        "Full Body B",
        "full_body",
        _FULL_BODY_MUSCLES,
        (LEG_PRESS, "P"),
        (GLUTE_BRIDGE, "P"),
        (MACHINE_INCLINE_PRESS, "P"),
        (HIGH_ROW, "P"),
        (LAT_PULLDOWN, "S"),
        (LEVER_LATERAL_RAISE, "I"),
    ),
)
_FULL_BODY_BEGINNER = (
    _approved_day(
        "Full Body A",
        "full_body",
        _FULL_BODY_MUSCLES,
        (SMITH_CHAIR_SQUAT, "P"),
        (SEATED_LEG_CURL, "S"),
        (MACHINE_CHEST_PRESS, "P"),
        (HIGH_ROW, "P"),
        (LAT_PULLDOWN, "S"),
        (SMITH_SHOULDER_PRESS, "S"),
    ),
    _approved_day(
        "Full Body B",
        "full_body",
        _FULL_BODY_MUSCLES,
        (LEG_PRESS, "P"),
        (RDL, "P"),
        (INCLINE_PRESS, "P"),
        (SEATED_CABLE_ROW, "P"),
        (LAT_PULLDOWN, "S"),
        (LATERAL_RAISE, "I"),
    ),
)
_FULL_BODY_INTERMEDIATE = (
    _approved_day(
        "Full Body A",
        "full_body",
        _FULL_BODY_MUSCLES,
        (SQUAT, "P"),
        (SEATED_LEG_CURL, "S"),
        (FLAT_PRESS, "P"),
        (ROW, "P"),
        (LAT_PULLDOWN, "S"),
        (SHOULDER_PRESS, "S"),
    ),
    _approved_day(
        "Full Body B",
        "full_body",
        _FULL_BODY_MUSCLES,
        (LEG_PRESS, "P"),
        (RDL, "P"),
        (INCLINE_PRESS, "P"),
        (SEATED_CABLE_ROW, "P"),
        (LAT_PULLDOWN, "S"),
        (LATERAL_RAISE, "I"),
    ),
)


def _upper_lower_full(level: ExperienceLevel) -> tuple[tuple[TemplateDaySeed, tuple[tuple[Movement, str], ...]], ...]:
    if level is Level.FIRST_MONTH:
        upper = (
            (MACHINE_CHEST_PRESS, "P"),
            (MACHINE_INCLINE_PRESS, "S"),
            (HIGH_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (SMITH_SHOULDER_PRESS, "P"),
            (LEVER_LATERAL_RAISE, "I"),
        )
        lower = (
            (SMITH_CHAIR_SQUAT, "P"),
            (LEG_PRESS, "P"),
            (GLUTE_BRIDGE, "P"),
            (SEATED_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
        full = (
            (LEG_PRESS, "P"),
            (SEATED_LEG_CURL, "S"),
            (MACHINE_CHEST_PRESS, "P"),
            (HIGH_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (LEVER_LATERAL_RAISE, "I"),
        )
    elif level is Level.BEGINNER:
        upper = (
            (MACHINE_CHEST_PRESS, "P"),
            (INCLINE_PRESS, "S"),
            (HIGH_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (SMITH_SHOULDER_PRESS, "P"),
            (LATERAL_RAISE, "I"),
        )
        lower = (
            (SMITH_CHAIR_SQUAT, "P"),
            (LEG_PRESS, "P"),
            (RDL, "P"),
            (SEATED_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
        full = (
            (LEG_PRESS, "P"),
            (SEATED_LEG_CURL, "S"),
            (MACHINE_CHEST_PRESS, "P"),
            (SEATED_CABLE_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (LATERAL_RAISE, "I"),
        )
    else:
        upper = (
            (FLAT_PRESS, "P"),
            (INCLINE_PRESS, "S"),
            (ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (SHOULDER_PRESS, "P"),
            (LATERAL_RAISE, "I"),
        )
        lower = (
            (SQUAT, "P"),
            (LEG_PRESS, "P"),
            (RDL, "P"),
            (SEATED_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
        full = (
            (LEG_PRESS, "P"),
            (SEATED_LEG_CURL, "S"),
            (FLAT_PRESS, "P"),
            (SEATED_CABLE_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (LATERAL_RAISE, "I"),
        )
    return (
        _approved_day("Upper", "upper", _UPPER_MUSCLES, *upper),
        _approved_day("Lower", "lower", _LOWER_MUSCLES, *lower),
        _approved_day("Full", "full_body", _FULL_BODY_MUSCLES, *full),
    )


def _upper_lower_upper(level: ExperienceLevel) -> tuple[tuple[TemplateDaySeed, tuple[tuple[Movement, str], ...]], ...]:
    upper_a = (
        (MACHINE_CHEST_PRESS, "P"),
        (INCLINE_PRESS, "S"),
        (HIGH_ROW, "P"),
        (LAT_PULLDOWN, "S"),
        (SMITH_SHOULDER_PRESS, "P"),
        (LATERAL_RAISE, "I"),
        (PREACHER_CURL, "I"),
        (TRICEPS_PUSHDOWN, "I"),
    )
    upper_b = (
        (INCLINE_PRESS, "P"),
        (MACHINE_CHEST_PRESS, "S"),
        (SEATED_CABLE_ROW, "P"),
        (LAT_PULLDOWN, "S"),
        (REAR_DELT_FLY, "I"),
        (LATERAL_RAISE, "I"),
        (HAMMER_CURL, "I"),
        (ROPE_TRICEPS_PUSHDOWN, "I"),
    )
    lower = (
        (SMITH_CHAIR_SQUAT, "P"),
        (LEG_PRESS, "P"),
        (RDL, "P"),
        (SEATED_LEG_CURL, "S"),
        (CALF_RAISE, "I"),
    )
    if level is not Level.BEGINNER:
        upper_a = (
            (FLAT_PRESS, "P"),
            (INCLINE_PRESS, "S"),
            (ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (SHOULDER_PRESS, "P"),
            (LATERAL_RAISE, "I"),
            (DUMBBELL_CURL, "I"),
            (TRICEPS_PUSHDOWN, "I"),
        )
        upper_b = (
            (INCLINE_PRESS, "P"),
            (FLAT_PRESS, "S"),
            (SEATED_CABLE_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (REAR_DELT_FLY, "I"),
            (LATERAL_RAISE, "I"),
            (HAMMER_CURL, "I"),
            (OVERHEAD_TRICEPS_EXTENSION, "I"),
        )
        lower = (
            (SQUAT, "P"),
            (LEG_PRESS, "P"),
            (RDL, "P"),
            (SEATED_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
    return (
        _approved_day("Upper A", "upper", _UPPER_MUSCLES, *upper_a),
        _approved_day("Lower", "lower", _LOWER_MUSCLES, *lower),
        _approved_day("Upper B", "upper", _UPPER_MUSCLES, *upper_b),
    )


def _lower_upper_lower(level: ExperienceLevel) -> tuple[tuple[TemplateDaySeed, tuple[tuple[Movement, str], ...]], ...]:
    if level is Level.BEGINNER:
        lower_a = (
            (SMITH_CHAIR_SQUAT, "P"),
            (LEG_PRESS, "P"),
            (RDL, "P"),
            (SEATED_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
        upper = (
            (MACHINE_CHEST_PRESS, "P"),
            (INCLINE_PRESS, "S"),
            (HIGH_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (SMITH_SHOULDER_PRESS, "P"),
            (LATERAL_RAISE, "I"),
            (PREACHER_CURL, "I"),
            (TRICEPS_PUSHDOWN, "I"),
        )
        lower_b = (
            (LEG_PRESS, "P"),
            (LUNGE, "S"),
            (RDL, "P"),
            (LYING_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
    else:
        lower_a = (
            (SQUAT, "P"),
            (LEG_PRESS, "P"),
            (RDL, "P"),
            (SEATED_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
        upper = (
            (FLAT_PRESS, "P"),
            (INCLINE_PRESS, "S"),
            (ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (SHOULDER_PRESS, "P"),
            (LATERAL_RAISE, "I"),
            (DUMBBELL_CURL, "I"),
            (TRICEPS_PUSHDOWN, "I"),
        )
        lower_b = (
            (LEG_PRESS, "P"),
            (LUNGE, "S"),
            (RDL, "P"),
            (LYING_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
    return (
        _approved_day("Lower A", "lower", _LOWER_MUSCLES, *lower_a),
        _approved_day("Upper", "upper", _UPPER_MUSCLES, *upper),
        _approved_day("Lower B", "lower", _LOWER_MUSCLES, *lower_b),
    )


def _upper_lower_2x(level: ExperienceLevel) -> tuple[tuple[TemplateDaySeed, tuple[tuple[Movement, str], ...]], ...]:
    if level is Level.FIRST_MONTH:
        upper_a = (
            (MACHINE_CHEST_PRESS, "P"),
            (MACHINE_INCLINE_PRESS, "S"),
            (HIGH_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (SMITH_SHOULDER_PRESS, "P"),
            (LEVER_LATERAL_RAISE, "I"),
        )
        lower_a = (
            (SMITH_CHAIR_SQUAT, "P"),
            (LEG_PRESS, "P"),
            (GLUTE_BRIDGE, "P"),
            (SEATED_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
        upper_b = (
            (MACHINE_INCLINE_PRESS, "P"),
            (MACHINE_CHEST_PRESS, "S"),
            (HIGH_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (REAR_DELT_FLY, "I"),
            (LEVER_LATERAL_RAISE, "I"),
        )
        lower_b = (
            (SMITH_CHAIR_SQUAT, "P"),
            (LEG_EXTENSION, "I"),
            (GLUTE_BRIDGE, "P"),
            (LYING_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
    elif level is Level.BEGINNER:
        upper_a = (
            (MACHINE_CHEST_PRESS, "P"),
            (INCLINE_PRESS, "S"),
            (HIGH_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (SMITH_SHOULDER_PRESS, "P"),
            (LATERAL_RAISE, "I"),
        )
        lower_a = (
            (SMITH_CHAIR_SQUAT, "P"),
            (LEG_PRESS, "P"),
            (RDL, "P"),
            (SEATED_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
        upper_b = (
            (INCLINE_PRESS, "P"),
            (MACHINE_CHEST_PRESS, "S"),
            (SEATED_CABLE_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (REAR_DELT_FLY, "I"),
            (LATERAL_RAISE, "I"),
        )
        lower_b = (
            (SMITH_CHAIR_SQUAT, "P"),
            (LEG_EXTENSION, "I"),
            (RDL, "P"),
            (LYING_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
    else:
        upper_a = (
            (FLAT_PRESS, "P"),
            (INCLINE_PRESS, "S"),
            (ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (SHOULDER_PRESS, "P"),
            (LATERAL_RAISE, "I"),
        )
        lower_a = (
            (SQUAT, "P"),
            (LEG_PRESS, "P"),
            (RDL, "P"),
            (SEATED_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
        upper_b = (
            (INCLINE_PRESS, "P"),
            (FLAT_PRESS, "S"),
            (SEATED_CABLE_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (REAR_DELT_FLY, "I"),
            (LATERAL_RAISE, "I"),
        )
        lower_b = (
            (FRONT_SQUAT, "P"),
            (LEG_EXTENSION, "I"),
            (RDL, "P"),
            (LYING_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
    return (
        _approved_day("Upper A", "upper", _UPPER_MUSCLES, *upper_a),
        _approved_day("Lower A", "lower", _LOWER_MUSCLES, *lower_a),
        _approved_day("Upper B", "upper", _UPPER_MUSCLES, *upper_b),
        _approved_day("Lower B", "lower", _LOWER_MUSCLES, *lower_b),
    )


def _three_upper_one_lower(level: ExperienceLevel) -> tuple[tuple[TemplateDaySeed, tuple[tuple[Movement, str], ...]], ...]:
    if level is Level.BEGINNER:
        upper_a = (
            (MACHINE_CHEST_PRESS, "P"),
            (INCLINE_PRESS, "S"),
            (HIGH_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (LATERAL_RAISE, "I"),
            (TRICEPS_PUSHDOWN, "I"),
        )
        lower = (
            (SMITH_CHAIR_SQUAT, "P"),
            (LEG_PRESS, "P"),
            (RDL, "P"),
            (SEATED_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
        upper_b = (
            (SMITH_SHOULDER_PRESS, "P"),
            (LATERAL_RAISE, "I"),
            (REAR_DELT_FLY, "I"),
            (PREACHER_CURL, "I"),
            (HAMMER_CURL, "I"),
            (TRICEPS_PUSHDOWN, "I"),
            (ROPE_TRICEPS_PUSHDOWN, "I"),
        )
        upper_c = (
            (INCLINE_PRESS, "P"),
            (MACHINE_CHEST_PRESS, "S"),
            (SEATED_CABLE_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (PREACHER_CURL, "I"),
        )
    else:
        upper_a = (
            (FLAT_PRESS, "P"),
            (INCLINE_PRESS, "S"),
            (ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (LATERAL_RAISE, "I"),
            (TRICEPS_PUSHDOWN, "I"),
        )
        lower = (
            (SQUAT, "P"),
            (LEG_PRESS, "P"),
            (RDL, "P"),
            (SEATED_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
        upper_b = (
            (SHOULDER_PRESS, "P"),
            (LATERAL_RAISE, "I"),
            (REAR_DELT_FLY, "I"),
            (DUMBBELL_CURL, "I"),
            (HAMMER_CURL, "I"),
            (TRICEPS_PUSHDOWN, "I"),
            (OVERHEAD_TRICEPS_EXTENSION, "I"),
        )
        upper_c = (
            (INCLINE_PRESS, "P"),
            (FLAT_PRESS, "S"),
            (SEATED_CABLE_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (DUMBBELL_CURL, "I"),
        )
    return (
        _approved_day("Upper A", "upper", _UPPER_MUSCLES, *upper_a),
        _approved_day("Lower", "lower", _LOWER_MUSCLES, *lower),
        _approved_day("Upper B", "other", _UPPER_MUSCLES, *upper_b),
        _approved_day("Upper C", "upper", _UPPER_MUSCLES, *upper_c),
    )


def _three_lower_one_upper(level: ExperienceLevel) -> tuple[tuple[TemplateDaySeed, tuple[tuple[Movement, str], ...]], ...]:
    if level is Level.BEGINNER:
        lower_a = (
            (SMITH_CHAIR_SQUAT, "P"),
            (LEG_PRESS, "P"),
            (SEATED_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
        upper = (
            (MACHINE_CHEST_PRESS, "P"),
            (INCLINE_PRESS, "S"),
            (HIGH_ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (SMITH_SHOULDER_PRESS, "P"),
            (LATERAL_RAISE, "I"),
            (PREACHER_CURL, "I"),
            (TRICEPS_PUSHDOWN, "I"),
        )
        lower_b = (
            (RDL, "P"),
            (LYING_LEG_CURL, "S"),
            (GLUTE_BRIDGE, "P"),
            (CALF_RAISE, "I"),
        )
        lower_c = (
            (LEG_PRESS, "P"),
            (LEG_EXTENSION, "I"),
            (GLUTE_BRIDGE, "P"),
            (CALF_RAISE, "I"),
        )
    else:
        lower_a = (
            (SQUAT, "P"),
            (LEG_PRESS, "P"),
            (SEATED_LEG_CURL, "S"),
            (CALF_RAISE, "I"),
        )
        upper = (
            (FLAT_PRESS, "P"),
            (INCLINE_PRESS, "S"),
            (ROW, "P"),
            (LAT_PULLDOWN, "S"),
            (SHOULDER_PRESS, "P"),
            (LATERAL_RAISE, "I"),
            (DUMBBELL_CURL, "I"),
            (TRICEPS_PUSHDOWN, "I"),
        )
        lower_b = (
            (RDL, "P"),
            (LYING_LEG_CURL, "S"),
            (GLUTE_BRIDGE, "P"),
            (CALF_RAISE, "I"),
        )
        lower_c = (
            (LEG_PRESS, "P"),
            (LEG_EXTENSION, "I"),
            (GLUTE_BRIDGE, "P"),
            (CALF_RAISE, "I"),
        )
    return (
        _approved_day("Lower A", "lower", _LOWER_MUSCLES, *lower_a),
        _approved_day("Upper", "upper", _UPPER_MUSCLES, *upper),
        _approved_day("Lower B", "posterior_chain_core", (M.HAMSTRINGS, M.GLUTES), *lower_b),
        _approved_day("Lower C", "quadriceps_calves", (M.QUADRICEPS, M.GLUTES), *lower_c),
    )


_PUSH_PULL_QUADS_POSTERIOR = (
    _approved_day(
        "Push",
        "push",
        (M.CHEST, M.SHOULDERS, M.TRICEPS),
        (FLAT_PRESS, "P"),
        (INCLINE_PRESS, "S"),
        (SHOULDER_PRESS, "P"),
        (LATERAL_RAISE, "I"),
        (TRICEPS_PUSHDOWN, "I"),
    ),
    _approved_day(
        "Pull",
        "pull",
        (M.BACK, M.BICEPS, M.TRAPS),
        (ROW, "P"),
        (LAT_PULLDOWN, "P"),
        (DUMBBELL_CURL, "I"),
        (SHRUG, "I"),
    ),
    _approved_day(
        "Quads",
        "quadriceps_calves",
        (M.QUADRICEPS, M.CALVES),
        (SQUAT, "P"),
        (LEG_PRESS, "P"),
        (LEG_EXTENSION, "I"),
        (SEATED_LEG_CURL, "S"),
        (CALF_RAISE, "I"),
    ),
    _approved_day(
        "Posterior",
        "posterior_chain_core",
        (M.HAMSTRINGS, M.GLUTES),
        (RDL, "P"),
        (LYING_LEG_CURL, "S"),
        (GLUTE_BRIDGE, "P"),
        (LUNGE, "S"),
        (CALF_RAISE, "I"),
    ),
)


_APPROVED_PROGRAM_BLUEPRINTS = (
    ("p01-2-day-full-body-ab-first-month", "2d-full-body-ab", Level.FIRST_MONTH, _FULL_BODY_FIRST_MONTH),
    ("p02-2-day-full-body-ab-beginner", "2d-full-body-ab", Level.BEGINNER, _FULL_BODY_BEGINNER),
    ("p03-2-day-full-body-ab-intermediate", "2d-full-body-ab", Level.INTERMEDIATE, _FULL_BODY_INTERMEDIATE),
    *(
        (
            f"p{index:02d}-3-day-upper-lower-full-{_LEVEL_SLUG_SUFFIX[level]}",
            "3d-upper-lower-full-body",
            level,
            _upper_lower_full(level),
        )
        for index, level in ((4, Level.FIRST_MONTH), (5, Level.BEGINNER), (6, Level.INTERMEDIATE), (7, Level.ADVANCED))
    ),
    *(
        (
            f"p{index:02d}-3-day-upper-lower-upper-{_LEVEL_SLUG_SUFFIX[level]}",
            "3d-upper-lower-upper",
            level,
            _upper_lower_upper(level),
        )
        for index, level in ((8, Level.BEGINNER), (9, Level.INTERMEDIATE), (10, Level.ADVANCED))
    ),
    *(
        (
            f"p{index:02d}-3-day-lower-upper-lower-{_LEVEL_SLUG_SUFFIX[level]}",
            "3d-lower-upper-lower",
            level,
            _lower_upper_lower(level),
        )
        for index, level in ((11, Level.BEGINNER), (12, Level.INTERMEDIATE), (13, Level.ADVANCED))
    ),
    *(
        (
            f"p{index:02d}-4-day-upper-lower-upper-lower-{_LEVEL_SLUG_SUFFIX[level]}",
            "4d-upper-lower-2x",
            level,
            _upper_lower_2x(level),
        )
        for index, level in ((14, Level.FIRST_MONTH), (15, Level.BEGINNER), (16, Level.INTERMEDIATE), (17, Level.ADVANCED))
    ),
    *(
        (
            f"p{index:02d}-4-day-3-upper-1-lower-{_LEVEL_SLUG_SUFFIX[level]}",
            "4d-3-upper-1-lower",
            level,
            _three_upper_one_lower(level),
        )
        for index, level in ((18, Level.BEGINNER), (19, Level.INTERMEDIATE), (20, Level.ADVANCED))
    ),
    *(
        (
            f"p{index:02d}-4-day-3-lower-1-upper-{_LEVEL_SLUG_SUFFIX[level]}",
            "4d-3-lower-1-upper",
            level,
            _three_lower_one_upper(level),
        )
        for index, level in ((21, Level.BEGINNER), (22, Level.INTERMEDIATE), (23, Level.ADVANCED))
    ),
    ("p24-4-day-push-pull-quads-posterior-intermediate", "4d-push-pull-quads-posterior", Level.INTERMEDIATE, _PUSH_PULL_QUADS_POSTERIOR),
    ("p25-4-day-push-pull-quads-posterior-advanced", "4d-push-pull-quads-posterior", Level.ADVANCED, _PUSH_PULL_QUADS_POSTERIOR),
)

CANONICAL_TEMPLATE_DEFINITIONS = tuple(
    _approved_definition(slug, structure_slug, level, days)
    for slug, structure_slug, level, days in _APPROVED_PROGRAM_BLUEPRINTS
)
CANONICAL_TEMPLATE_SLUGS = tuple(
    definition.canonical_slug for definition in CANONICAL_TEMPLATE_DEFINITIONS
)
TRAINING_PROGRAM_TEMPLATE_SEEDS = tuple(
    _approved_seed_from_definition(definition)
    for definition in CANONICAL_TEMPLATE_DEFINITIONS
)


# The 5- and 6-day catalog below is a separate approved expansion.  It keeps
# the existing 2-, 3-, and 4-day definitions above byte-for-byte stable while
# using the same template seed and exercise-linking architecture.
DUMBBELL_BENCH_PRESS = _movement(
    "dumbbell-bench-press",
    "owner-cb58d2dbac7f-dumbbell-bench-press",
    (M.CHEST,),
    P.HORIZONTAL_PUSH,
)
DUMBBELL_LATERAL_RAISE = _movement(
    "dumbbell-lateral-raise",
    "fedb-0334-dumbbell-lateral-raise",
    (M.SHOULDERS,),
    P.SHOULDER_ABDUCTION,
)


@dataclass(frozen=True)
class _ApprovedSlotSpec:
    movement: Movement
    role: str
    rest_seconds: int
    intensity_method: TrainingTemplateMethod = Method.STANDARD
    superset_group: str | None = None


def _approved_slot(
    movement: Movement,
    role: str,
    rest_seconds: int,
    *,
    intensity_method: TrainingTemplateMethod = Method.STANDARD,
    superset_group: str | None = None,
) -> _ApprovedSlotSpec:
    return _ApprovedSlotSpec(
        movement=movement,
        role=role,
        rest_seconds=rest_seconds,
        intensity_method=intensity_method,
        superset_group=superset_group,
    )


def _approved_prescription(
    role: str,
    level: ExperienceLevel,
) -> tuple[int, int, int, int]:
    if role == "large_primary":
        sets, rep_min, rep_max = 4, 6, 12
    elif role in {"large_compound", "small_main", "superset"}:
        sets, rep_min, rep_max = 3, 8, 12
    elif role == "fst7":
        sets, rep_min, rep_max = 7, 8, 12
    elif role == "front_plank":
        sets, rep_min, rep_max = 3, 45, 60
    elif role == "side_plank":
        sets, rep_min, rep_max = 3, 30, 45
    elif role in {"large_isolation", "small_isolation"}:
        sets, rep_min, rep_max = 3, 10, 12
    else:
        raise ValueError(f"Unknown approved catalog slot role: {role}")
    target_rir = 1 if level is Level.ADVANCED and role == "large_primary" else 2
    return sets, rep_min, rep_max, target_rir


def _approved_catalog_day(
    title_en: str,
    structure_focus: str,
    direct_target_muscles: tuple[MuscleGroup, ...],
    level: ExperienceLevel,
    *slot_specs: _ApprovedSlotSpec,
) -> TemplateDaySeed:
    return TemplateDaySeed(
        title_en=title_en,
        title_fa=_APPROVED_DAY_TITLES_FA[title_en],
        structure_focus=structure_focus,
        direct_target_muscles=direct_target_muscles,
        slots=tuple(
            TemplateSlotSeed(
                exercise_slug_hint=spec.movement.exercise_slug,
                catalog_slug_hints=(spec.movement.exercise_slug,),
                target_muscles=spec.movement.target_muscles,
                movement_pattern=spec.movement.movement_pattern,
                sets=_approved_prescription(spec.role, level)[0],
                rep_min=_approved_prescription(spec.role, level)[1],
                rep_max=_approved_prescription(spec.role, level)[2],
                target_rir=_approved_prescription(spec.role, level)[3],
                rest_seconds=spec.rest_seconds,
                intensity_method=spec.intensity_method,
                superset_group=spec.superset_group,
            )
            for spec in slot_specs
        ),
    )


def _approved_catalog_definition(
    slug: str,
    structure_slug: str,
    level: ExperienceLevel,
    days: tuple[tuple[str, str, tuple[MuscleGroup, ...], tuple[_ApprovedSlotSpec, ...]], ...],
) -> CanonicalTemplateDefinition:
    structure_name_en, structure_name_fa = _NEW_STRUCTURE_NAMES[structure_slug]
    rendered_days = tuple(
        _approved_catalog_day(title, focus, muscles, level, *slots)
        for title, focus, muscles, slots in days
    )
    tags = validate_focus_tags(_NEW_STRUCTURE_TAGS[structure_slug])
    return CanonicalTemplateDefinition(
        canonical_slug=slug,
        name_en=f"{structure_name_en} — {_LEVEL_NAMES[level][0]}",
        name_fa=f"{structure_name_fa} — {_LEVEL_NAMES[level][1]}",
        description_en=f"Approved Fitsho default program: {structure_name_en} for {_LEVEL_NAMES[level][0]} trainees.",
        description_fa=f"برنامه پیش‌فرض تأییدشده فیتشو: {structure_name_fa} برای سطح {_LEVEL_NAMES[level][1]}.",
        supported_levels=(level,),
        focus_tags=tags,
        days=rendered_days,
        day_specs=tuple(
            tuple((slot.movement, slot.role) for slot in slots) for _, _, _, slots in days
        ),
        guidance_en=(
            "Follow the approved day order and the descending 12/10/8/6 pyramid ranges. "
            "FST-7, where present, is represented by its approved seven-set range."
        ),
        guidance_fa=(
            "ترتیب روزهای تأییدشده و دامنه‌های نزولی ۱۲/۱۰/۸/۶ را اجرا کن. "
            "در صورت وجود FST-7، هفت ست آن با دامنه تأییدشده نمایش داده می‌شود."
        ),
        order_en="Complete exercises in the listed order and keep each approved superset paired.",
        order_fa="حرکت‌ها را به ترتیب فهرست‌شده اجرا کن و هر سوپرست تأییدشده را به‌صورت جفت نگه دار.",
        recovery_en="Use the prescribed rest and leave recovery between repeated regional exposures when possible.",
        recovery_fa="استراحت تعیین‌شده را رعایت کن و در صورت امکان بین مواجهه‌های تکراری ناحیه‌ای زمان ریکاوری بگذار.",
        structure_slug=structure_slug,
    )


def _advanced_rest(level: ExperienceLevel, intermediate: int, advanced: int) -> int:
    return advanced if level is Level.ADVANCED else intermediate


CHEST_MUSCLES = (M.CHEST,)
BACK_MUSCLES = (M.BACK,)
SHOULDER_MUSCLES = (M.SHOULDERS, M.TRAPS)
ARM_MUSCLES = (M.BICEPS, M.TRICEPS)
LEG_MUSCLES = (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES)
UPPER_MUSCLES_APPROVED = (M.CHEST, M.BACK, M.SHOULDERS, M.BICEPS, M.TRICEPS)
LOWER_MUSCLES_APPROVED = (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES)
CHEST_BACK_MUSCLES = (M.CHEST, M.BACK)
SHOULDERS_ARMS_MUSCLES = (M.SHOULDERS, M.BICEPS, M.TRICEPS)
POSTERIOR_MUSCLES = (M.HAMSTRINGS, M.GLUTES, M.CALVES)


_APPROVED_DAY_TITLES_FA.update(
    {
        "Chest": "سینه",
        "Back": "پشت",
        "Shoulders": "سرشانه",
        "Arms": "بازو",
        "Legs": "پا",
        "Chest + Triceps": "سینه + پشت بازو",
        "Back + Biceps": "پشت + جلو بازو",
        "Shoulders + Core": "سرشانه + میان‌تنه",
        "Weak Point / Light Full Body": "نقطه ضعف / تمام‌بدن سبک",
        "Shoulders + Biceps": "سرشانه + جلو بازو",
        "Legs + Core": "پا + میان‌تنه",
        "Upper Chest + Biceps": "بالاسینه + جلو بازو",
        "Back + Core": "پشت + میان‌تنه",
        "Arms + Delts Specialty": "تخصص بازو + دلت",
        "Chest + Biceps": "سینه + جلو بازو",
        "Back + Triceps": "پشت + پشت بازو",
        "Shoulders + Calves": "سرشانه + ساق",
        "Chest + Back": "سینه + پشت",
        "Posterior + Core": "خلفی + میان‌تنه",
        "Chest + Back A": "سینه + پشت A",
        "Shoulders + Arms A": "سرشانه + بازو A",
        "Legs A": "پا A",
        "Push A": "پوش A",
        "Pull A": "پول A",
        "Push B": "پوش B",
        "Pull B": "پول B",
        "Chest + Back B": "سینه + پشت B",
        "Shoulders + Arms B": "سرشانه + بازو B",
        "Legs B": "پا B",
        "Biceps": "جلو بازو",
        "Triceps": "پشت بازو",
        "Back + Biceps + Shoulders A": "پشت + جلو بازو + سرشانه A",
        "Chest + Triceps A": "سینه + پشت بازو A",
        "Back + Biceps + Shoulders B": "پشت + جلو بازو + سرشانه B",
        "Chest + Triceps B": "سینه + پشت بازو B",
        "Compound Day": "روز حرکات ترکیبی",
    }
)


_NEW_STRUCTURE_NAMES = {
    "5d-classic-body-part-approved": ("5-Day Classic Body-Part Split", "تقسیم کلاسیک عضله‌ای پنج‌روزه"),
    "5d-split-weak-point": ("5-Day Split + Weak Point", "تقسیم پنج‌روزه با نقطه ضعف"),
    "5d-upper-priority-iranian": ("5-Day Upper-Priority Iranian Split", "تقسیم ایرانی پنج‌روزه با اولویت بالاتنه"),
    "5d-upper-lower-specialty": ("5-Day Upper / Lower + Specialty", "بالاتنه / پایین‌تنه پنج‌روزه با تخصص"),
    "5d-fst7-arms-priority": ("5-Day FST-7 / Arms Priority", "پنج‌روزه FST-7 با اولویت بازو"),
    "5d-professional-compound": ("5-Day Professional Split + Compound Day", "تقسیم حرفه‌ای پنج‌روزه با روز ترکیبی"),
    "6d-upper-lower-x3": ("6-Day Upper / Lower ×3", "بالاتنه / پایین‌تنه سه‌بار در هفته"),
    "6d-fitclub-hybrid": ("6-Day FitClub Hybrid", "ترکیبی شش‌روزه فیت‌کلاب"),
    "6d-arnold-split": ("6-Day Arnold Split", "تقسیم آرنولد شش‌روزه"),
    "6d-classic-body-part": ("6-Day Classic Six Body-Part", "تقسیم کلاسیک شش‌روزه عضله‌ای"),
    "6d-ronnie-double-exposure": ("6-Day Ronnie Double Exposure", "مواجهه دوگانه رانـی شش‌روزه"),
}
_NEW_STRUCTURE_NAMES["6d-ppl-2x"] = ("PPL A/B", "پوش / پول / پا A/B")

_NEW_STRUCTURE_TAGS = {
    "5d-classic-body-part-approved": (Tag.BODY_PART_ROTATION,),
    "5d-split-weak-point": (Tag.BODY_PART_ROTATION, Tag.UPPER_PRIORITY),
    "5d-upper-priority-iranian": (Tag.UPPER_LOWER, Tag.UPPER_PRIORITY),
    "5d-upper-lower-specialty": (Tag.UPPER_LOWER, Tag.UPPER_PRIORITY),
    "5d-fst7-arms-priority": (Tag.BODY_PART_ROTATION, Tag.ARMS_PRIORITY, Tag.SPECIALIZATION),
    "5d-professional-compound": (Tag.BODY_PART_ROTATION,),
    "6d-ppl-2x": (Tag.PUSH_PULL_LEGS,),
    "6d-upper-lower-x3": (Tag.UPPER_LOWER,),
    "6d-fitclub-hybrid": (Tag.PUSH_PULL_LEGS,),
    "6d-arnold-split": (Tag.BODY_PART_ROTATION,),
    "6d-classic-body-part": (Tag.BODY_PART_ROTATION,),
    "6d-ronnie-double-exposure": (Tag.BODY_PART_ROTATION,),
}


def _level_method(
    level: ExperienceLevel,
    advanced_method: TrainingTemplateMethod,
) -> TrainingTemplateMethod:
    return advanced_method if level is Level.ADVANCED else Method.STANDARD


def _classic_body_part_5d(
    level: ExperienceLevel,
) -> tuple[tuple[str, str, tuple[MuscleGroup, ...], tuple[_ApprovedSlotSpec, ...]], ...]:
    chest_second = MACHINE_INCLINE_PRESS if level is Level.ADVANCED else INCLINE_PRESS
    chest_third = DUMBBELL_BENCH_PRESS if level is Level.ADVANCED else MACHINE_CHEST_PRESS
    shoulders_press = SMITH_SHOULDER_PRESS if level is Level.ADVANCED else SHOULDER_PRESS
    lateral = DUMBBELL_LATERAL_RAISE if level is Level.ADVANCED else LATERAL_RAISE
    row_second = LAT_PULLDOWN
    third_back = SEATED_CABLE_ROW if level is Level.ADVANCED else HIGH_ROW
    arms_specs = (
        _approved_slot(BARBELL_CURL, "small_main", _advanced_rest(level, 60, 90)),
        _approved_slot(
            CABLE_CURL if level is Level.ADVANCED else PREACHER_CURL,
            "superset" if level is Level.ADVANCED else "small_isolation",
            _advanced_rest(level, 60, 90),
            intensity_method=_level_method(level, Method.SUPERSET),
            superset_group="SS-A" if level is Level.ADVANCED else None,
        ),
        _approved_slot(
            ROPE_TRICEPS_PUSHDOWN if level is Level.ADVANCED else TRICEPS_PUSHDOWN,
            "superset" if level is Level.ADVANCED else "small_main",
            _advanced_rest(level, 60, 90),
            intensity_method=_level_method(level, Method.SUPERSET),
            superset_group="SS-A" if level is Level.ADVANCED else None,
        ),
        _approved_slot(
            OVERHEAD_TRICEPS_EXTENSION,
            "small_main" if level is Level.ADVANCED else "small_isolation",
            _advanced_rest(level, 60, 90),
        ),
        _approved_slot(HAMMER_CURL, "small_isolation", _advanced_rest(level, 60, 75)),
    )
    return (
        (
            "Chest",
            "chest",
            CHEST_MUSCLES,
            (
                _approved_slot(FLAT_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(chest_second, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(chest_third, "large_compound", _advanced_rest(level, 120, 120)),
                _approved_slot(
                    CHEST_FLY,
                    "large_isolation",
                    _advanced_rest(level, 60, 75),
                    intensity_method=_level_method(level, Method.DROP_SET),
                ),
            ),
        ),
        (
            "Back",
            "back",
            BACK_MUSCLES,
            (
                _approved_slot(ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(row_second, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(third_back, "large_compound", _advanced_rest(level, 120, 120)),
                _approved_slot(STRAIGHT_ARM_PULLDOWN, "large_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Shoulders",
            "shoulders",
            SHOULDER_MUSCLES,
            (
                _approved_slot(shoulders_press, "small_main", _advanced_rest(level, 90, 120)),
                _approved_slot(lateral, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(REAR_DELT_FLY, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(SHRUG, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        ("Arms", "arms", ARM_MUSCLES, arms_specs),
        (
            "Legs",
            "lower",
            LEG_MUSCLES,
            (
                _approved_slot(
                    FRONT_SQUAT if level is Level.ADVANCED else SQUAT,
                    "large_primary",
                    150,
                ),
                _approved_slot(LEG_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(RDL, "large_compound", 120),
                _approved_slot(
                    LYING_LEG_CURL if level is Level.ADVANCED else SEATED_LEG_CURL,
                    "large_isolation",
                    _advanced_rest(level, 60, 75),
                ),
                *((_approved_slot(LUNGE, "large_compound", 120),) if level is Level.ADVANCED else ()),
                _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        )
    )


def _split_weak_point_5d(
    level: ExperienceLevel,
) -> tuple[tuple[str, str, tuple[MuscleGroup, ...], tuple[_ApprovedSlotSpec, ...]], ...]:
    return (
        (
            "Chest + Triceps", "upper", (M.CHEST, M.TRICEPS),
            (
                _approved_slot(FLAT_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(MACHINE_INCLINE_PRESS if level is Level.ADVANCED else INCLINE_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(CHEST_FLY, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(ROPE_TRICEPS_PUSHDOWN if level is Level.ADVANCED else TRICEPS_PUSHDOWN, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(OVERHEAD_TRICEPS_EXTENSION, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Back + Biceps", "upper", (M.BACK, M.BICEPS),
            (
                _approved_slot(HIGH_ROW if level is Level.ADVANCED else ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(LAT_PULLDOWN, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(SEATED_CABLE_ROW, "large_compound", 120),
                _approved_slot(BARBELL_CURL, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(CABLE_CURL if level is Level.ADVANCED else DUMBBELL_CURL, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Legs", "lower", LEG_MUSCLES,
            (
                _approved_slot(FRONT_SQUAT if level is Level.ADVANCED else SQUAT, "large_primary", 150),
                _approved_slot(RDL, "large_primary", 150),
                _approved_slot(LEG_PRESS, "large_compound", 120),
                _approved_slot(LYING_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Shoulders + Core", "upper", SHOULDER_MUSCLES,
            (
                _approved_slot(SHOULDER_PRESS if level is Level.INTERMEDIATE else SMITH_SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
                _approved_slot(DUMBBELL_LATERAL_RAISE if level is Level.ADVANCED else LATERAL_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(REAR_DELT_FLY, "small_isolation", _advanced_rest(level, 60, 75)),
                *((_approved_slot(SHRUG, "small_isolation", _advanced_rest(level, 60, 75)),) if level is Level.ADVANCED else ()),
                _approved_slot(FRONT_PLANK, "front_plank", 60),
                *((_approved_slot(SIDE_PLANK, "side_plank", 60),) if level is Level.INTERMEDIATE else ()),
            ),
        ),
        (
            "Weak Point / Light Full Body", "full_body", _FULL_BODY_MUSCLES,
            (
                _approved_slot(DUMBBELL_BENCH_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(ROW if level is Level.ADVANCED else HIGH_ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(GLUTE_BRIDGE, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(LUNGE, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(
                    LATERAL_RAISE,
                    "small_isolation",
                    _advanced_rest(level, 60, 75),
                    intensity_method=_level_method(level, Method.DROP_SET),
                ) if level is Level.ADVANCED else _approved_slot(
                    LEVER_LATERAL_RAISE,
                    "small_isolation",
                    _advanced_rest(level, 60, 75),
                ),
            ),
        ),
    )


def _upper_priority_iranian_5d(
    level: ExperienceLevel,
) -> tuple[tuple[str, str, tuple[MuscleGroup, ...], tuple[_ApprovedSlotSpec, ...]], ...]:
    return (
        (
            "Chest + Triceps", "upper", UPPER_MUSCLES_APPROVED,
            (
                _approved_slot(FLAT_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(MACHINE_INCLINE_PRESS if level is Level.ADVANCED else INCLINE_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(CHEST_FLY, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(ROPE_TRICEPS_PUSHDOWN if level is Level.ADVANCED else TRICEPS_PUSHDOWN, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(OVERHEAD_TRICEPS_EXTENSION, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Shoulders + Biceps", "upper", UPPER_MUSCLES_APPROVED,
            (
                _approved_slot(SMITH_SHOULDER_PRESS if level is Level.INTERMEDIATE else SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
                _approved_slot(LEVER_LATERAL_RAISE if level is Level.ADVANCED else LATERAL_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(REAR_DELT_FLY, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(BARBELL_CURL if level is Level.ADVANCED else PREACHER_CURL, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(HAMMER_CURL, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Legs + Core", "lower", LEG_MUSCLES,
            (
                _approved_slot(FRONT_SQUAT if level is Level.ADVANCED else SQUAT, "large_primary", 150),
                _approved_slot(LEG_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(LYING_LEG_CURL if level is Level.ADVANCED else SEATED_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(FRONT_PLANK, "front_plank", 60),
            ),
        ),
        (
            "Upper Chest + Biceps", "upper", UPPER_MUSCLES_APPROVED,
            (
                _approved_slot(INCLINE_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(MACHINE_CHEST_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(CHEST_FLY, "large_isolation", _advanced_rest(level, 60, 75), intensity_method=_level_method(level, Method.DROP_SET)),
                _approved_slot(PREACHER_CURL if level is Level.ADVANCED else CABLE_CURL, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(CABLE_CURL if level is Level.ADVANCED else DUMBBELL_CURL, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Back + Core", "upper", UPPER_MUSCLES_APPROVED,
            (
                _approved_slot(ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(HIGH_ROW if level is Level.ADVANCED else LAT_PULLDOWN, "large_primary", _advanced_rest(level, 120, 150)),
                *((_approved_slot(LAT_PULLDOWN, "large_compound", 120),) if level is Level.ADVANCED else (_approved_slot(SEATED_CABLE_ROW, "large_compound", 120),)),
                _approved_slot(STRAIGHT_ARM_PULLDOWN, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(FRONT_PLANK if level is Level.ADVANCED else SIDE_PLANK, "front_plank" if level is Level.ADVANCED else "side_plank", 60),
            ),
        ),
    )


def _upper_lower_specialty_5d(
    level: ExperienceLevel,
) -> tuple[tuple[str, str, tuple[MuscleGroup, ...], tuple[_ApprovedSlotSpec, ...]], ...]:
    advanced = level is Level.ADVANCED
    return (
        (
            "Upper A", "upper", UPPER_MUSCLES_APPROVED,
            (
                _approved_slot(FLAT_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(LAT_PULLDOWN, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
                *((_approved_slot(BARBELL_CURL, "small_main", _advanced_rest(level, 60, 90)),
                   _approved_slot(TRICEPS_PUSHDOWN, "small_main", _advanced_rest(level, 60, 90))) if not advanced else ()),
            ),
        ),
        (
            "Lower A", "lower", LEG_MUSCLES,
            (
                _approved_slot(SQUAT, "large_primary", 150),
                _approved_slot(RDL, "large_primary", 150),
                *((_approved_slot(LEG_PRESS, "large_compound", 120),) if not advanced else ()),
                _approved_slot(SEATED_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Upper B", "upper", UPPER_MUSCLES_APPROVED,
            (
                _approved_slot(MACHINE_INCLINE_PRESS if advanced else INCLINE_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(SEATED_CABLE_ROW, "large_primary", _advanced_rest(level, 120, 150)),
                *(
                    (
                        _approved_slot(DUMBBELL_BENCH_PRESS, "large_primary", 150),
                        _approved_slot(HIGH_ROW, "large_primary", 150),
                        _approved_slot(LATERAL_RAISE, "small_isolation", 75),
                    )
                    if advanced
                    else (
                        _approved_slot(HIGH_ROW, "large_primary", 120),
                        _approved_slot(LATERAL_RAISE, "small_isolation", 60),
                        _approved_slot(PREACHER_CURL, "small_main", 60),
                        _approved_slot(OVERHEAD_TRICEPS_EXTENSION, "small_main", 60),
                    )
                ),
            ),
        ),
        (
            "Lower B", "lower", LEG_MUSCLES,
            (
                _approved_slot(FRONT_SQUAT, "large_primary", 150),
                _approved_slot(GLUTE_BRIDGE, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(LUNGE, "large_compound", 120),
                _approved_slot(LYING_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
                *((_approved_slot(CALF_RAISE, "small_isolation", 60),) if not advanced else ()),
            ),
        ),
        (
            "Arms + Delts Specialty", "upper", SHOULDERS_ARMS_MUSCLES,
            (
                _approved_slot(SMITH_SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
                *(
                    (
                        _approved_slot(LEVER_LATERAL_RAISE, "small_isolation", 60),
                        _approved_slot(REAR_DELT_FLY, "small_isolation", 60),
                    )
                    if not advanced
                    else (
                        _approved_slot(REAR_DELT_FLY, "small_isolation", 75),
                        _approved_slot(
                            LATERAL_RAISE,
                            "small_isolation",
                            75,
                            intensity_method=Method.DROP_SET,
                        ),
                    )
                ),
                *((_approved_slot(BARBELL_CURL, "small_main", 60),
                   _approved_slot(ROPE_TRICEPS_PUSHDOWN, "small_main", 60),
                   _approved_slot(HAMMER_CURL, "small_isolation", 60)) if not advanced else (
                    _approved_slot(CABLE_CURL, "superset", 90, intensity_method=Method.SUPERSET, superset_group="SS-A"),
                    _approved_slot(ROPE_TRICEPS_PUSHDOWN, "superset", 90, intensity_method=Method.SUPERSET, superset_group="SS-A"),
                    _approved_slot(HAMMER_CURL, "small_main", 90),
                )),
            ),
        ),
    )


def _fst7_arms_priority_5d(
    level: ExperienceLevel,
) -> tuple[tuple[str, str, tuple[MuscleGroup, ...], tuple[_ApprovedSlotSpec, ...]], ...]:
    advanced = level is Level.ADVANCED

    def fst(movement: Movement, rest: int) -> _ApprovedSlotSpec:
        return _approved_slot(movement, "fst7", rest)

    return (
        (
            "Chest + Biceps", "upper", UPPER_MUSCLES_APPROVED,
            (
                _approved_slot(FLAT_PRESS if advanced else DUMBBELL_BENCH_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(MACHINE_INCLINE_PRESS if advanced else INCLINE_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                fst(CHEST_FLY, 60) if advanced else _approved_slot(CHEST_FLY, "large_isolation", 60),
                _approved_slot(BARBELL_CURL if advanced else DUMBBELL_CURL, "small_main", _advanced_rest(level, 60, 90)),
                *((_approved_slot(PREACHER_CURL, "small_isolation", 60),) if not advanced else ()),
            ),
        ),
        (
            "Back + Triceps", "upper", UPPER_MUSCLES_APPROVED,
            (
                _approved_slot(ROW if advanced else HIGH_ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(LAT_PULLDOWN, "large_primary", _advanced_rest(level, 120, 150)),
                fst(STRAIGHT_ARM_PULLDOWN, 60) if advanced else _approved_slot(STRAIGHT_ARM_PULLDOWN, "large_isolation", 60),
                _approved_slot(ROPE_TRICEPS_PUSHDOWN if advanced else TRICEPS_PUSHDOWN, "small_main", _advanced_rest(level, 60, 90)),
                *((_approved_slot(OVERHEAD_TRICEPS_EXTENSION, "small_isolation", 60),) if not advanced else ()),
            ),
        ),
        (
            "Legs", "lower", LEG_MUSCLES,
            (
                _approved_slot(FRONT_SQUAT if advanced else SQUAT, "large_primary", 150),
                *(
                    (
                        _approved_slot(RDL, "large_primary", 150),
                        _approved_slot(LEG_PRESS, "large_compound", 120),
                    )
                    if advanced
                    else (
                        _approved_slot(LEG_PRESS, "large_primary", 120),
                        _approved_slot(RDL, "large_compound", 120),
                    )
                ),
                fst(LEG_EXTENSION, 60) if advanced else _approved_slot(LEG_EXTENSION, "large_isolation", 60),
                _approved_slot(LYING_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
                *((_approved_slot(CALF_RAISE, "small_isolation", 60),) if not advanced else ()),
            ),
        ),
        (
            "Shoulders + Calves", "shoulders", SHOULDER_MUSCLES,
            (
                _approved_slot(SMITH_SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
                *(
                    (
                        _approved_slot(REAR_DELT_FLY, "small_isolation", 75),
                        fst(LEVER_LATERAL_RAISE, 45),
                        _approved_slot(CALF_RAISE, "small_isolation", 75),
                    )
                    if advanced
                    else (
                        _approved_slot(LATERAL_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
                        _approved_slot(REAR_DELT_FLY, "small_isolation", _advanced_rest(level, 60, 75)),
                        _approved_slot(SHRUG, "small_isolation", _advanced_rest(level, 60, 75)),
                        _approved_slot(CALF_RAISE, "small_isolation", 60),
                    )
                ),
            ),
        ),
        (
            "Arms", "arms", ARM_MUSCLES,
            (
                _approved_slot(BARBELL_CURL, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(ROPE_TRICEPS_PUSHDOWN, "small_main", _advanced_rest(level, 60, 90)),
                fst(PREACHER_CURL, 45) if advanced else _approved_slot(CABLE_CURL, "small_isolation", 60),
                _approved_slot(OVERHEAD_TRICEPS_EXTENSION, "small_isolation", _advanced_rest(level, 60, 75)),
                *((_approved_slot(HAMMER_CURL, "small_isolation", 60),) if not advanced else ()),
            ),
        ),
    )


def _professional_compound_5d(
    level: ExperienceLevel,
) -> tuple[tuple[str, str, tuple[MuscleGroup, ...], tuple[_ApprovedSlotSpec, ...]], ...]:
    advanced = level is Level.ADVANCED
    return (
        (
            "Chest + Triceps", "upper", UPPER_MUSCLES_APPROVED,
            (
                _approved_slot(FLAT_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(MACHINE_INCLINE_PRESS if advanced else INCLINE_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(CHEST_FLY, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(ROPE_TRICEPS_PUSHDOWN if advanced else TRICEPS_PUSHDOWN, "small_main", _advanced_rest(level, 60, 90)),
            ),
        ),
        (
            "Legs + Core", "lower", LEG_MUSCLES,
            (
                _approved_slot(FRONT_SQUAT if advanced else SQUAT, "large_primary", 150),
                *(
                    (
                        _approved_slot(LEG_PRESS, "large_primary", 150),
                        _approved_slot(RDL, "large_compound", 120),
                        _approved_slot(LYING_LEG_CURL, "large_isolation", 75),
                        _approved_slot(CALF_RAISE, "small_isolation", 75),
                    )
                    if advanced
                    else (
                        _approved_slot(RDL, "large_primary", 150),
                        _approved_slot(LUNGE, "large_compound", 120),
                        _approved_slot(CALF_RAISE, "small_isolation", 60),
                        _approved_slot(FRONT_PLANK, "front_plank", 60),
                    )
                ),
            ),
        ),
        (
            "Back + Biceps", "upper", UPPER_MUSCLES_APPROVED,
            (
                _approved_slot(LAT_PULLDOWN, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(HIGH_ROW, "large_compound", _advanced_rest(level, 120, 120)),
                _approved_slot(BARBELL_CURL, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(HAMMER_CURL if advanced else DUMBBELL_CURL, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Shoulders", "shoulders", SHOULDER_MUSCLES,
            (
                _approved_slot(SMITH_SHOULDER_PRESS if advanced else SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
                _approved_slot(
                    DUMBBELL_LATERAL_RAISE if not advanced else LATERAL_RAISE,
                    "small_isolation",
                    _advanced_rest(level, 60, 75),
                ),
                _approved_slot(REAR_DELT_FLY, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(SHRUG, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Compound Day", "full_body", _FULL_BODY_MUSCLES,
            (
                *(
                    (
                        _approved_slot(DUMBBELL_BENCH_PRESS, "large_primary", 150),
                        _approved_slot(HIGH_ROW, "large_primary", 150),
                        _approved_slot(GLUTE_BRIDGE, "large_primary", 150),
                        _approved_slot(LUNGE, "large_primary", 150),
                        _approved_slot(LEVER_LATERAL_RAISE, "small_isolation", 75),
                    )
                    if advanced
                    else (
                        _approved_slot(RDL, "large_primary", 150),
                        _approved_slot(DUMBBELL_BENCH_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                        _approved_slot(SEATED_CABLE_ROW, "large_primary", _advanced_rest(level, 120, 150)),
                        _approved_slot(FRONT_SQUAT, "large_primary", 150),
                        _approved_slot(SMITH_SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
                    )
                ),
            ),
        ),
    )


def _ppl_ab_6d(
    level: ExperienceLevel,
) -> tuple[tuple[str, str, tuple[MuscleGroup, ...], tuple[_ApprovedSlotSpec, ...]], ...]:
    advanced = level is Level.ADVANCED
    return (
        (
            "Push A", "push", (M.CHEST, M.SHOULDERS, M.TRICEPS),
            (
                _approved_slot(FLAT_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(MACHINE_INCLINE_PRESS if advanced else INCLINE_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                *((
                    _approved_slot(CHEST_FLY, "large_isolation", 75),
                ) if advanced else ()),
                *((_approved_slot(SHOULDER_PRESS, "small_main", 90),) if not advanced else ()),
                _approved_slot(LATERAL_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(ROPE_TRICEPS_PUSHDOWN if advanced else TRICEPS_PUSHDOWN, "small_main", _advanced_rest(level, 60, 90)),
            ),
        ),
        (
            "Pull A", "pull", (M.BACK, M.BICEPS, M.TRAPS),
            (
                _approved_slot(LAT_PULLDOWN, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(HIGH_ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(REAR_DELT_FLY, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(BARBELL_CURL if advanced else DUMBBELL_CURL, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(SHRUG, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Legs A", "lower", LEG_MUSCLES,
            (
                _approved_slot(SQUAT, "large_primary", 150),
                _approved_slot(LEG_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(
                    LEG_EXTENSION,
                    "large_isolation",
                    _advanced_rest(level, 60, 75),
                    intensity_method=_level_method(level, Method.DROP_SET),
                ),
                _approved_slot(SEATED_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Push B", "push", (M.CHEST, M.SHOULDERS, M.TRICEPS),
            (
                _approved_slot(SMITH_SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
                _approved_slot(DUMBBELL_BENCH_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(CHEST_FLY if advanced else MACHINE_INCLINE_PRESS, "large_isolation" if advanced else "large_primary", _advanced_rest(level, 60, 75) if advanced else _advanced_rest(level, 120, 150)),
                _approved_slot(DUMBBELL_LATERAL_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(OVERHEAD_TRICEPS_EXTENSION, "small_main", _advanced_rest(level, 60, 90)),
            ),
        ),
        (
            "Pull B", "pull", (M.BACK, M.BICEPS, M.SHOULDERS),
            (
                _approved_slot(SEATED_CABLE_ROW if not advanced else ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(ROW if not advanced else SEATED_CABLE_ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(STRAIGHT_ARM_PULLDOWN, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(HAMMER_CURL, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(REAR_DELT_FLY, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Legs B", "lower", LEG_MUSCLES,
            (
                _approved_slot(RDL, "large_primary", 150),
                _approved_slot(LYING_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(FRONT_SQUAT if advanced else GLUTE_BRIDGE, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(GLUTE_BRIDGE if advanced else FRONT_SQUAT, "large_compound", _advanced_rest(level, 120, 120)),
                _approved_slot(LUNGE, "large_compound", 120),
                _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
    )


def _upper_lower_x3_6d(
    level: ExperienceLevel,
) -> tuple[tuple[str, str, tuple[MuscleGroup, ...], tuple[_ApprovedSlotSpec, ...]], ...]:
    advanced = level is Level.ADVANCED
    upper_a = (
        _approved_slot(FLAT_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
        _approved_slot(ROW, "large_primary", _advanced_rest(level, 120, 150)),
        _approved_slot(SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
        _approved_slot(LAT_PULLDOWN, "large_primary", _advanced_rest(level, 120, 150)),
        *((_approved_slot(BARBELL_CURL, "small_main", 60), _approved_slot(TRICEPS_PUSHDOWN, "small_main", 60)) if not advanced else ()),
    )
    upper_b = (
        _approved_slot(MACHINE_INCLINE_PRESS if advanced else INCLINE_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
        _approved_slot(SEATED_CABLE_ROW, "large_primary", _advanced_rest(level, 120, 150)),
        _approved_slot(HIGH_ROW, "large_primary", _advanced_rest(level, 120, 150)),
        _approved_slot(
            LATERAL_RAISE,
            "small_isolation",
            _advanced_rest(level, 60, 75),
            intensity_method=_level_method(level, Method.DROP_SET),
        ),
        *((_approved_slot(PREACHER_CURL, "small_main", 60), _approved_slot(OVERHEAD_TRICEPS_EXTENSION, "small_main", 60)) if not advanced else ()),
        *((_approved_slot(PREACHER_CURL, "small_main", 90), _approved_slot(OVERHEAD_TRICEPS_EXTENSION, "small_main", 90)) if advanced else ()),
    )
    upper_c = (
        _approved_slot(DUMBBELL_BENCH_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
        _approved_slot(LAT_PULLDOWN, "large_primary", _advanced_rest(level, 120, 150)),
        _approved_slot(SMITH_SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
        _approved_slot(STRAIGHT_ARM_PULLDOWN, "large_isolation", _advanced_rest(level, 60, 75)),
        *((_approved_slot(HAMMER_CURL, "small_main", 60), _approved_slot(ROPE_TRICEPS_PUSHDOWN, "small_main", 60)) if not advanced else ()),
        *((
            _approved_slot(CABLE_CURL, "superset", 90, intensity_method=Method.SUPERSET, superset_group="SS-A"),
            _approved_slot(ROPE_TRICEPS_PUSHDOWN, "superset", 90, intensity_method=Method.SUPERSET, superset_group="SS-A"),
        ) if advanced else ()),
    )
    lower_a = (
        _approved_slot(SQUAT, "large_primary", 150),
        _approved_slot(LEG_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
        _approved_slot(LEG_EXTENSION, "large_isolation", _advanced_rest(level, 60, 75)),
        _approved_slot(SEATED_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
        _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
    )
    lower_b = (
        _approved_slot(RDL, "large_primary", 150),
        _approved_slot(LYING_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
        _approved_slot(GLUTE_BRIDGE, "large_primary", _advanced_rest(level, 120, 150)),
        _approved_slot(LUNGE, "large_compound", 120),
        _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
    )
    lower_c = (
        _approved_slot(FRONT_SQUAT, "large_primary", 150),
        _approved_slot(LEG_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
        _approved_slot(SEATED_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
        _approved_slot(LUNGE, "large_compound", 120),
        _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
        _approved_slot(SIDE_PLANK, "side_plank", 60),
    )
    return (
        ("Upper A", "upper", UPPER_MUSCLES_APPROVED, upper_a),
        ("Lower A", "lower", LEG_MUSCLES, lower_a),
        ("Upper B", "upper", UPPER_MUSCLES_APPROVED, upper_b),
        ("Lower B", "lower", LEG_MUSCLES, lower_b),
        ("Upper C", "upper", UPPER_MUSCLES_APPROVED, upper_c),
        ("Lower C", "lower", LEG_MUSCLES, lower_c),
    )


def _fitclub_hybrid_6d(
    level: ExperienceLevel,
) -> tuple[tuple[str, str, tuple[MuscleGroup, ...], tuple[_ApprovedSlotSpec, ...]], ...]:
    advanced = level is Level.ADVANCED
    return (
        (
            "Chest + Triceps", "upper", (M.CHEST, M.TRICEPS),
            (
                _approved_slot(FLAT_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(INCLINE_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(CHEST_FLY, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(ROPE_TRICEPS_PUSHDOWN if advanced else TRICEPS_PUSHDOWN, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(OVERHEAD_TRICEPS_EXTENSION, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Back + Biceps", "upper", (M.BACK, M.BICEPS),
            (
                _approved_slot(ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(LAT_PULLDOWN, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(HIGH_ROW, "large_compound", _advanced_rest(level, 120, 120)),
                _approved_slot(CABLE_CURL, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(HAMMER_CURL, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Legs", "lower", LEG_MUSCLES,
            (
                _approved_slot(SQUAT, "large_primary", 150),
                _approved_slot(LEG_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(LEG_EXTENSION, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(SEATED_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Shoulders + Core", "shoulders", SHOULDER_MUSCLES,
            (
                _approved_slot(SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
                _approved_slot(LATERAL_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(REAR_DELT_FLY, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(SHRUG, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(FRONT_PLANK, "front_plank", 60),
            ),
        ),
        (
            "Chest + Back", "upper", CHEST_BACK_MUSCLES,
            (
                _approved_slot(MACHINE_CHEST_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(SEATED_CABLE_ROW, "large_primary", _advanced_rest(level, 120, 150)),
                *(
                    (
                        _approved_slot(CHEST_FLY, "superset", 90, intensity_method=Method.SUPERSET, superset_group="SS-A"),
                        _approved_slot(STRAIGHT_ARM_PULLDOWN, "superset", 90, intensity_method=Method.SUPERSET, superset_group="SS-A"),
                        _approved_slot(MACHINE_INCLINE_PRESS, "large_primary", 150),
                        _approved_slot(LAT_PULLDOWN, "large_primary", 150),
                    )
                    if advanced
                    else (
                        _approved_slot(MACHINE_INCLINE_PRESS, "large_primary", 120),
                        _approved_slot(LAT_PULLDOWN, "large_primary", 120),
                        _approved_slot(CHEST_FLY, "large_isolation", 60),
                        _approved_slot(STRAIGHT_ARM_PULLDOWN, "large_isolation", 60),
                    )
                ),
            ),
        ),
        (
            "Posterior + Core", "lower", POSTERIOR_MUSCLES,
            (
                _approved_slot(RDL, "large_primary", 150),
                _approved_slot(LYING_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(GLUTE_BRIDGE, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(LUNGE, "large_compound", 120),
                _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(SIDE_PLANK, "side_plank", 60),
            ),
        ),
    )


def _arnold_split_6d(
    level: ExperienceLevel,
) -> tuple[tuple[str, str, tuple[MuscleGroup, ...], tuple[_ApprovedSlotSpec, ...]], ...]:
    advanced = level is Level.ADVANCED
    day1 = (
        _approved_slot(FLAT_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
        _approved_slot(ROW, "large_primary", _advanced_rest(level, 120, 150)),
        *(
            (
                _approved_slot(INCLINE_PRESS, "superset", 120, intensity_method=Method.SUPERSET, superset_group="SS-A"),
                _approved_slot(LAT_PULLDOWN, "superset", 120, intensity_method=Method.SUPERSET, superset_group="SS-A"),
                _approved_slot(CHEST_FLY, "superset", 90, intensity_method=Method.SUPERSET, superset_group="SS-B"),
                _approved_slot(STRAIGHT_ARM_PULLDOWN, "superset", 90, intensity_method=Method.SUPERSET, superset_group="SS-B"),
            )
            if advanced
            else (
                _approved_slot(INCLINE_PRESS, "large_primary", 120),
                _approved_slot(LAT_PULLDOWN, "large_primary", 120),
                _approved_slot(CHEST_FLY, "large_isolation", 60),
                _approved_slot(STRAIGHT_ARM_PULLDOWN, "large_isolation", 60),
            )
        ),
    )
    day2 = (
        _approved_slot(SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
        _approved_slot(LATERAL_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
        _approved_slot(REAR_DELT_FLY, "small_isolation", _advanced_rest(level, 60, 75)),
        *(
            (
                _approved_slot(BARBELL_CURL, "superset", 90, intensity_method=Method.SUPERSET, superset_group="SS-A"),
                _approved_slot(ROPE_TRICEPS_PUSHDOWN, "superset", 90, intensity_method=Method.SUPERSET, superset_group="SS-A"),
            )
            if advanced
            else (
                _approved_slot(BARBELL_CURL, "small_main", 60),
                _approved_slot(TRICEPS_PUSHDOWN, "small_main", 60),
                _approved_slot(HAMMER_CURL, "small_isolation", 60),
            )
        ),
    )
    day4 = (
        _approved_slot(DUMBBELL_BENCH_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
        _approved_slot(SEATED_CABLE_ROW, "large_primary", _advanced_rest(level, 120, 150)),
        *(
            (
                _approved_slot(MACHINE_INCLINE_PRESS, "superset", 120, intensity_method=Method.SUPERSET, superset_group="SS-A"),
                _approved_slot(HIGH_ROW, "superset", 120, intensity_method=Method.SUPERSET, superset_group="SS-A"),
                _approved_slot(CHEST_FLY, "large_isolation", 75),
                _approved_slot(LAT_PULLDOWN, "large_compound", 120),
            )
            if advanced
            else (
                _approved_slot(MACHINE_INCLINE_PRESS, "large_primary", 120),
                _approved_slot(HIGH_ROW, "large_primary", 120),
                _approved_slot(CHEST_FLY, "large_isolation", 60),
                _approved_slot(LAT_PULLDOWN, "large_compound", 120),
            )
        ),
    )
    day5 = (
        _approved_slot(SMITH_SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
        _approved_slot(LEVER_LATERAL_RAISE if advanced else DUMBBELL_LATERAL_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
        *(
            (
                _approved_slot(PREACHER_CURL, "superset", 90, intensity_method=Method.SUPERSET, superset_group="SS-A"),
                _approved_slot(OVERHEAD_TRICEPS_EXTENSION, "superset", 90, intensity_method=Method.SUPERSET, superset_group="SS-A"),
                _approved_slot(HAMMER_CURL, "small_main", 90),
            )
            if advanced
            else (
                _approved_slot(REAR_DELT_FLY, "small_isolation", 60),
                _approved_slot(PREACHER_CURL, "small_main", 60),
                _approved_slot(OVERHEAD_TRICEPS_EXTENSION, "small_main", 60),
                _approved_slot(CABLE_CURL, "small_isolation", 60),
            )
        ),
    )
    day6 = (
        _approved_slot(RDL, "large_primary", 150),
        _approved_slot(FRONT_SQUAT, "large_primary", 150),
        _approved_slot(LYING_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
        _approved_slot(GLUTE_BRIDGE, "large_compound", _advanced_rest(level, 120, 120)),
        _approved_slot(LUNGE, "large_compound", 120),
        _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
    )
    return (
        ("Chest + Back A", "upper", CHEST_BACK_MUSCLES, day1),
        ("Shoulders + Arms A", "upper", SHOULDERS_ARMS_MUSCLES, day2),
        ("Legs A", "lower", LEG_MUSCLES, (
            _approved_slot(SQUAT, "large_primary", 150),
            _approved_slot(LEG_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
            _approved_slot(SEATED_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
            _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
        )),
        ("Chest + Back B", "upper", CHEST_BACK_MUSCLES, day4),
        ("Shoulders + Arms B", "upper", SHOULDERS_ARMS_MUSCLES, day5),
        ("Legs B", "lower", LEG_MUSCLES, day6),
    )


def _classic_six_body_part_6d(
    level: ExperienceLevel,
) -> tuple[tuple[str, str, tuple[MuscleGroup, ...], tuple[_ApprovedSlotSpec, ...]], ...]:
    advanced = level is Level.ADVANCED
    return (
        (
            "Chest", "chest", CHEST_MUSCLES,
            (
                _approved_slot(FLAT_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(MACHINE_INCLINE_PRESS if advanced else INCLINE_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(DUMBBELL_BENCH_PRESS if advanced else MACHINE_CHEST_PRESS, "large_compound", _advanced_rest(level, 120, 120)),
                _approved_slot(CHEST_FLY, "large_isolation", _advanced_rest(level, 60, 75), intensity_method=_level_method(level, Method.DROP_SET)),
            ),
        ),
        (
            "Biceps", "arms", (M.BICEPS,),
            (
                _approved_slot(BARBELL_CURL, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(PREACHER_CURL, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(HAMMER_CURL if not advanced else CABLE_CURL, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(CABLE_CURL if not advanced else HAMMER_CURL, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Legs", "lower", LEG_MUSCLES,
            (
                _approved_slot(FRONT_SQUAT if advanced else SQUAT, "large_primary", 150),
                _approved_slot(LEG_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(RDL, "large_compound", 120),
                _approved_slot(LYING_LEG_CURL if advanced else SEATED_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Triceps", "arms", (M.TRICEPS,),
            (
                _approved_slot(TRICEPS_PUSHDOWN, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(ROPE_TRICEPS_PUSHDOWN, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(OVERHEAD_TRICEPS_EXTENSION, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Back", "back", BACK_MUSCLES,
            (
                _approved_slot(ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(LAT_PULLDOWN, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(SEATED_CABLE_ROW, "large_compound", _advanced_rest(level, 120, 120)),
                *((_approved_slot(HIGH_ROW, "large_compound", _advanced_rest(level, 120, 120)),) if not advanced else ()),
                _approved_slot(STRAIGHT_ARM_PULLDOWN, "large_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Shoulders", "shoulders", SHOULDER_MUSCLES,
            (
                _approved_slot(SMITH_SHOULDER_PRESS if advanced else SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
                _approved_slot(LATERAL_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(REAR_DELT_FLY, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(SHRUG, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
    )


def _ronnie_double_exposure_6d(
    level: ExperienceLevel,
) -> tuple[tuple[str, str, tuple[MuscleGroup, ...], tuple[_ApprovedSlotSpec, ...]], ...]:
    advanced = level is Level.ADVANCED
    return (
        (
            "Back + Biceps + Shoulders A", "upper", (M.BACK, M.BICEPS, M.SHOULDERS),
            (
                _approved_slot(LAT_PULLDOWN, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(REAR_DELT_FLY, "small_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(BARBELL_CURL if advanced else DUMBBELL_CURL, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(LATERAL_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Legs A", "lower", LEG_MUSCLES,
            (
                _approved_slot(SQUAT, "large_primary", 150),
                _approved_slot(LEG_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(LEG_EXTENSION, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(SEATED_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Chest + Triceps A", "upper", (M.CHEST, M.TRICEPS),
            (
                _approved_slot(FLAT_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(MACHINE_INCLINE_PRESS if advanced else INCLINE_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(CHEST_FLY, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(TRICEPS_PUSHDOWN, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(OVERHEAD_TRICEPS_EXTENSION, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Back + Biceps + Shoulders B", "upper", (M.BACK, M.BICEPS, M.SHOULDERS),
            (
                _approved_slot(SEATED_CABLE_ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(HIGH_ROW, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(STRAIGHT_ARM_PULLDOWN, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(HAMMER_CURL, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(SMITH_SHOULDER_PRESS, "small_main", _advanced_rest(level, 90, 120)),
                *((_approved_slot(LATERAL_RAISE, "small_isolation", _advanced_rest(level, 60, 75), intensity_method=Method.DROP_SET),) if advanced else ()),
            ),
        ),
        (
            "Legs B", "lower", LEG_MUSCLES,
            (
                _approved_slot(RDL, "large_primary", 150),
                *(
                    (_approved_slot(FRONT_SQUAT, "large_primary", 150),)
                    if advanced
                    else (
                        _approved_slot(LYING_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
                        _approved_slot(GLUTE_BRIDGE, "large_primary", _advanced_rest(level, 120, 120)),
                        _approved_slot(FRONT_SQUAT, "large_compound", 120),
                    )
                ),
                *(
                    (
                        _approved_slot(LYING_LEG_CURL, "large_isolation", _advanced_rest(level, 60, 75)),
                        _approved_slot(GLUTE_BRIDGE, "large_compound", 120),
                    )
                    if advanced
                    else ()
                ),
                _approved_slot(LUNGE, "large_compound", 120),
                _approved_slot(CALF_RAISE, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
        (
            "Chest + Triceps B", "upper", (M.CHEST, M.TRICEPS),
            (
                _approved_slot(DUMBBELL_BENCH_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(INCLINE_PRESS if advanced else MACHINE_INCLINE_PRESS, "large_primary", _advanced_rest(level, 120, 150)),
                _approved_slot(CHEST_FLY, "large_isolation", _advanced_rest(level, 60, 75)),
                _approved_slot(ROPE_TRICEPS_PUSHDOWN, "small_main", _advanced_rest(level, 60, 90)),
                _approved_slot(OVERHEAD_TRICEPS_EXTENSION, "small_isolation", _advanced_rest(level, 60, 75)),
            ),
        ),
    )


def _catalog_seed_from_definition(
    definition: CanonicalTemplateDefinition,
) -> TrainingProgramTemplateSeed:
    methods = tuple(
        method
        for method in (Method.STANDARD, Method.SUPERSET, Method.DROP_SET)
        if any(slot.intensity_method is method for day in definition.days for slot in day.slots)
    )
    seed = TrainingProgramTemplateSeed(
        canonical_slug=definition.canonical_slug,
        slug=definition.canonical_slug,
        name_en=definition.name_en,
        name_fa=definition.name_fa,
        description_en=definition.description_en,
        description_fa=definition.description_fa,
        days_per_week=len(definition.days),
        supported_levels=definition.supported_levels,
        focus_tags=definition.focus_tags,
        intensity_methods=methods,
        days=definition.days,
        programming_rationale=_rationale(definition),
        structure_slug=definition.structure_slug,
    )
    validate_template_focus_tags(
        seed.focus_tags,
        intensity_methods=seed.intensity_methods,
        days=seed.days,
    )
    return seed


APPROVED_STRUCTURE_SEEDS = (
    TrainingProgramStructureSeed(
        "5d-classic-body-part-approved",
        "5-Day Classic Body-Part Split",
        "تقسیم کلاسیک عضله‌ای پنج‌روزه",
        5,
        StructureFamily.SPLIT,
        StructureSplitType.BODY_PART,
        "Approved five-day classic body-part order.",
        "ترتیب کلاسیک عضله‌ای پنج‌روزه تأییدشده.",
        (
            ("chest", "Chest", "سینه"),
            ("back", "Back", "پشت"),
            ("shoulders", "Shoulders", "سرشانه"),
            ("arms", "Arms", "بازو"),
            ("lower", "Legs", "پا"),
        ),
    ),
    TrainingProgramStructureSeed(
        "5d-split-weak-point",
        "5-Day Split + Weak Point",
        "تقسیم پنج‌روزه با نقطه ضعف",
        5,
        StructureFamily.SPLIT,
        StructureSplitType.BODY_PART,
        "Approved five-day split with a weak-point session.",
        "تقسیم پنج‌روزه تأییدشده با جلسه نقطه ضعف.",
        (
            ("upper", "Chest + Triceps", "سینه + پشت بازو"),
            ("upper", "Back + Biceps", "پشت + جلو بازو"),
            ("lower", "Legs", "پا"),
            ("upper", "Shoulders + Core", "سرشانه + میان‌تنه"),
            ("full_body", "Weak Point / Light Full Body", "نقطه ضعف / تمام‌بدن سبک"),
        ),
    ),
    TrainingProgramStructureSeed(
        "5d-upper-priority-iranian",
        "5-Day Upper-Priority Iranian Split",
        "تقسیم ایرانی پنج‌روزه با اولویت بالاتنه",
        5,
        StructureFamily.UPPER_LOWER,
        None,
        "Approved upper-priority Iranian five-day split.",
        "تقسیم ایرانی پنج‌روزه با اولویت بالاتنه تأییدشده.",
        (
            ("upper", "Chest + Triceps", "سینه + پشت بازو"),
            ("upper", "Shoulders + Biceps", "سرشانه + جلو بازو"),
            ("lower", "Legs + Core", "پا + میان‌تنه"),
            ("upper", "Upper Chest + Biceps", "بالاسینه + جلو بازو"),
            ("upper", "Back + Core", "پشت + میان‌تنه"),
        ),
    ),
    TrainingProgramStructureSeed(
        "5d-upper-lower-specialty",
        "5-Day Upper / Lower + Specialty",
        "بالاتنه / پایین‌تنه پنج‌روزه با تخصص",
        5,
        StructureFamily.UPPER_LOWER,
        None,
        "Approved five-day upper/lower split with an arms and delts specialty day.",
        "تقسیم پنج‌روزه بالاتنه/پایین‌تنه با روز تخصص بازو و دلت.",
        (
            ("upper", "Upper A", "بالاتنه A"),
            ("lower", "Lower A", "پایین‌تنه A"),
            ("upper", "Upper B", "بالاتنه B"),
            ("lower", "Lower B", "پایین‌تنه B"),
            ("upper", "Arms + Delts Specialty", "تخصص بازو + دلت"),
        ),
    ),
    TrainingProgramStructureSeed(
        "5d-fst7-arms-priority",
        "5-Day FST-7 / Arms Priority",
        "پنج‌روزه FST-7 با اولویت بازو",
        5,
        StructureFamily.SPLIT,
        StructureSplitType.BODY_PART,
        "Approved five-day arms-priority catalog with an FST-7 advanced exception.",
        "کاتالوگ پنج‌روزه با اولویت بازو و استثنای FST-7 برای پیشرفته.",
        (
            ("upper", "Chest + Biceps", "سینه + جلو بازو"),
            ("upper", "Back + Triceps", "پشت + پشت بازو"),
            ("lower", "Legs", "پا"),
            ("shoulders", "Shoulders + Calves", "سرشانه + ساق"),
            ("arms", "Arms", "بازو"),
        ),
    ),
    TrainingProgramStructureSeed(
        "5d-professional-compound",
        "5-Day Professional Split + Compound Day",
        "تقسیم حرفه‌ای پنج‌روزه با روز ترکیبی",
        5,
        StructureFamily.SPLIT,
        StructureSplitType.BODY_PART,
        "Approved five-day professional split with a compound day.",
        "تقسیم حرفه‌ای پنج‌روزه تأییدشده با روز حرکات ترکیبی.",
        (
            ("upper", "Chest + Triceps", "سینه + پشت بازو"),
            ("lower", "Legs + Core", "پا + میان‌تنه"),
            ("upper", "Back + Biceps", "پشت + جلو بازو"),
            ("shoulders", "Shoulders", "سرشانه"),
            ("full_body", "Compound Day", "روز حرکات ترکیبی"),
        ),
    ),
    TrainingProgramStructureSeed(
        "6d-ppl-2x",
        "PPL A/B",
        "پوش / پول / پا A/B",
        6,
        StructureFamily.SPLIT,
        StructureSplitType.PPL,
        "Approved six-day push, pull, and legs A/B split.",
        "تقسیم شش‌روزه پوش، پول و پا A/B تأییدشده.",
        (
            ("push", "Push A", "پوش A"),
            ("pull", "Pull A", "پول A"),
            ("lower", "Legs A", "پا A"),
            ("push", "Push B", "پوش B"),
            ("pull", "Pull B", "پول B"),
            ("lower", "Legs B", "پا B"),
        ),
    ),
    TrainingProgramStructureSeed(
        "6d-upper-lower-x3",
        "6-Day Upper / Lower ×3",
        "بالاتنه / پایین‌تنه سه‌بار در هفته",
        6,
        StructureFamily.UPPER_LOWER,
        None,
        "Approved six-day upper/lower split repeated three times.",
        "تقسیم شش‌روزه بالاتنه/پایین‌تنه در سه چرخه تأییدشده.",
        (
            ("upper", "Upper A", "بالاتنه A"),
            ("lower", "Lower A", "پایین‌تنه A"),
            ("upper", "Upper B", "بالاتنه B"),
            ("lower", "Lower B", "پایین‌تنه B"),
            ("upper", "Upper C", "بالاتنه C"),
            ("lower", "Lower C", "پایین‌تنه C"),
        ),
    ),
    TrainingProgramStructureSeed(
        "6d-fitclub-hybrid",
        "6-Day FitClub Hybrid",
        "ترکیبی شش‌روزه فیت‌کلاب",
        6,
        StructureFamily.SPLIT,
        StructureSplitType.PPL,
        "Approved six-day FitClub hybrid split.",
        "تقسیم ترکیبی شش‌روزه فیت‌کلاب تأییدشده.",
        (
            ("upper", "Chest + Triceps", "سینه + پشت بازو"),
            ("upper", "Back + Biceps", "پشت + جلو بازو"),
            ("lower", "Legs", "پا"),
            ("shoulders", "Shoulders + Core", "سرشانه + میان‌تنه"),
            ("upper", "Chest + Back", "سینه + پشت"),
            ("lower", "Posterior + Core", "خلفی + میان‌تنه"),
        ),
    ),
    TrainingProgramStructureSeed(
        "6d-arnold-split",
        "6-Day Arnold Split",
        "تقسیم آرنولد شش‌روزه",
        6,
        StructureFamily.SPLIT,
        StructureSplitType.BODY_PART,
        "Approved six-day Arnold-style chest/back and shoulders/arms split.",
        "تقسیم شش‌روزه سبک آرنولد برای سینه/پشت و سرشانه/بازو.",
        (
            ("upper", "Chest + Back A", "سینه + پشت A"),
            ("upper", "Shoulders + Arms A", "سرشانه + بازو A"),
            ("lower", "Legs A", "پا A"),
            ("upper", "Chest + Back B", "سینه + پشت B"),
            ("upper", "Shoulders + Arms B", "سرشانه + بازو B"),
            ("lower", "Legs B", "پا B"),
        ),
    ),
    TrainingProgramStructureSeed(
        "6d-classic-body-part",
        "6-Day Classic Six Body-Part",
        "تقسیم کلاسیک شش‌روزه عضله‌ای",
        6,
        StructureFamily.SPLIT,
        StructureSplitType.BODY_PART,
        "Approved six-day classic six body-part order.",
        "ترتیب کلاسیک شش‌روزه عضله‌ای تأییدشده.",
        (
            ("chest", "Chest", "سینه"),
            ("arms", "Biceps", "جلو بازو"),
            ("lower", "Legs", "پا"),
            ("arms", "Triceps", "پشت بازو"),
            ("back", "Back", "پشت"),
            ("shoulders", "Shoulders", "سرشانه"),
        ),
    ),
    TrainingProgramStructureSeed(
        "6d-ronnie-double-exposure",
        "6-Day Ronnie Double Exposure",
        "مواجهه دوگانه رانی شش‌روزه",
        6,
        StructureFamily.SPLIT,
        StructureSplitType.BODY_PART,
        "Approved six-day double-exposure split.",
        "تقسیم شش‌روزه با مواجهه دوگانه تأییدشده.",
        (
            ("upper", "Back + Biceps + Shoulders A", "پشت + جلو بازو + سرشانه A"),
            ("lower", "Legs A", "پا A"),
            ("upper", "Chest + Triceps A", "سینه + پشت بازو A"),
            ("upper", "Back + Biceps + Shoulders B", "پشت + جلو بازو + سرشانه B"),
            ("lower", "Legs B", "پا B"),
            ("upper", "Chest + Triceps B", "سینه + پشت بازو B"),
        ),
    ),
)


_NEW_CATALOG_PROGRAM_BLUEPRINTS = (
    ("p26-5-day-classic-body-part-intermediate", "5d-classic-body-part-approved", Level.INTERMEDIATE, _classic_body_part_5d),
    ("p27-5-day-classic-body-part-advanced", "5d-classic-body-part-approved", Level.ADVANCED, _classic_body_part_5d),
    ("p28-5-day-split-weak-point-intermediate", "5d-split-weak-point", Level.INTERMEDIATE, _split_weak_point_5d),
    ("p29-5-day-split-weak-point-advanced", "5d-split-weak-point", Level.ADVANCED, _split_weak_point_5d),
    ("p30-5-day-upper-priority-iranian-intermediate", "5d-upper-priority-iranian", Level.INTERMEDIATE, _upper_priority_iranian_5d),
    ("p31-5-day-upper-priority-iranian-advanced", "5d-upper-priority-iranian", Level.ADVANCED, _upper_priority_iranian_5d),
    ("p32-5-day-upper-lower-specialty-intermediate", "5d-upper-lower-specialty", Level.INTERMEDIATE, _upper_lower_specialty_5d),
    ("p33-5-day-upper-lower-specialty-advanced", "5d-upper-lower-specialty", Level.ADVANCED, _upper_lower_specialty_5d),
    ("p34-5-day-fst7-arms-priority-intermediate", "5d-fst7-arms-priority", Level.INTERMEDIATE, _fst7_arms_priority_5d),
    ("p35-5-day-fst7-arms-priority-advanced", "5d-fst7-arms-priority", Level.ADVANCED, _fst7_arms_priority_5d),
    ("p36-5-day-professional-compound-intermediate", "5d-professional-compound", Level.INTERMEDIATE, _professional_compound_5d),
    ("p37-5-day-professional-compound-advanced", "5d-professional-compound", Level.ADVANCED, _professional_compound_5d),
    ("p38-6-day-ppl-ab-intermediate", "6d-ppl-2x", Level.INTERMEDIATE, _ppl_ab_6d),
    ("p39-6-day-ppl-ab-advanced", "6d-ppl-2x", Level.ADVANCED, _ppl_ab_6d),
    ("p40-6-day-upper-lower-x3-intermediate", "6d-upper-lower-x3", Level.INTERMEDIATE, _upper_lower_x3_6d),
    ("p41-6-day-upper-lower-x3-advanced", "6d-upper-lower-x3", Level.ADVANCED, _upper_lower_x3_6d),
    ("p42-6-day-fitclub-hybrid-intermediate", "6d-fitclub-hybrid", Level.INTERMEDIATE, _fitclub_hybrid_6d),
    ("p43-6-day-fitclub-hybrid-advanced", "6d-fitclub-hybrid", Level.ADVANCED, _fitclub_hybrid_6d),
    ("p44-6-day-arnold-split-intermediate", "6d-arnold-split", Level.INTERMEDIATE, _arnold_split_6d),
    ("p45-6-day-arnold-split-advanced", "6d-arnold-split", Level.ADVANCED, _arnold_split_6d),
    ("p46-6-day-classic-body-part-intermediate", "6d-classic-body-part", Level.INTERMEDIATE, _classic_six_body_part_6d),
    ("p47-6-day-classic-body-part-advanced", "6d-classic-body-part", Level.ADVANCED, _classic_six_body_part_6d),
    ("p48-6-day-ronnie-double-exposure-intermediate", "6d-ronnie-double-exposure", Level.INTERMEDIATE, _ronnie_double_exposure_6d),
    ("p49-6-day-ronnie-double-exposure-advanced", "6d-ronnie-double-exposure", Level.ADVANCED, _ronnie_double_exposure_6d),
)

_NEW_CANONICAL_TEMPLATE_DEFINITIONS = tuple(
    _approved_catalog_definition(slug, structure_slug, level, builder(level))
    for slug, structure_slug, level, builder in _NEW_CATALOG_PROGRAM_BLUEPRINTS
)
CANONICAL_TEMPLATE_DEFINITIONS = CANONICAL_TEMPLATE_DEFINITIONS + _NEW_CANONICAL_TEMPLATE_DEFINITIONS
CANONICAL_TEMPLATE_SLUGS = tuple(
    definition.canonical_slug for definition in CANONICAL_TEMPLATE_DEFINITIONS
)
TRAINING_PROGRAM_TEMPLATE_SEEDS = tuple(
    _approved_seed_from_definition(definition)
    if definition in CANONICAL_TEMPLATE_DEFINITIONS[:25]
    else _catalog_seed_from_definition(definition)
    for definition in CANONICAL_TEMPLATE_DEFINITIONS
)
