from dataclasses import dataclass, replace

from app.exercises.enums import MovementPattern, MuscleGroup
from app.profile.enums import ExperienceLevel, FitnessGoal
from app.training_templates.models import TrainingTemplateMethod, TrainingTemplateSlotPriority
from app.training_templates.tags import (
    TemplateFocusTag,
    validate_focus_tags,
    validate_template_focus_tags,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import (
    MAXIMUM_EXERCISES_PER_SESSION,
    MINIMUM_EXERCISES_PER_SESSION,
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
    adaptation_priority: TrainingTemplateSlotPriority = TrainingTemplateSlotPriority.CORE
    superset_group: str | None = None


@dataclass(frozen=True)
class TemplateDaySeed:
    title_en: str
    title_fa: str
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
    slug: str
    name_en: str
    name_fa: str
    description_en: str
    description_fa: str
    days_per_week: int
    training_level: ExperienceLevel
    focus_tags: tuple[TemplateFocusTag, ...]
    intensity_methods: tuple[TrainingTemplateMethod, ...]
    days: tuple[TemplateDaySeed, ...]
    programming_rationale: tuple[TemplateProgrammingRationaleSeed, ...]
    fitness_goal: FitnessGoal = FitnessGoal.BUILD_MUSCLE
    is_active: bool = True


M = MuscleGroup
P = MovementPattern
Method = TrainingTemplateMethod
Priority = TrainingTemplateSlotPriority
Level = ExperienceLevel
Tag = TemplateFocusTag

SOURCE_NAME = "Fitsho synthesis: Stronger By Science · Jeff Nippard · RP Strength"
SOURCE_URL = "https://www.strongerbyscience.com/exercise-order-video/"

# Phase 4 structural-library audit. These legacy entries are either exact
# Goal-era duplicates or belong to unsupported Days x ExperienceLevel cells.
RETIRED_REDUNDANT_TEMPLATE_SLUGS = frozenset(
    {
        "two-day-full-body-fat-loss-beginner",
        "two-day-full-body-general-fitness-beginner",
        "three-day-full-body-fat-loss-beginner",
        "three-day-full-body-general-fitness-beginner",
        "five-day-ppl-fat-loss-intermediate",
        "six-day-ppl-fat-loss-advanced",
    }
)
RETIRED_UNSUPPORTED_TEMPLATE_SLUGS = frozenset(
    {
        "two-day-full-body-superset",
        "five-day-beginner-body-part-foundation",
    }
)
STRUCTURAL_RECLASSIFIED_TEMPLATE_SLUGS = frozenset(
    {
        "two-day-full-body-strength-beginner",
        "three-day-full-body-strength-beginner",
        "three-day-full-body-strength-intermediate",
        "four-day-upper-lower-strength-intermediate",
        "four-day-upper-lower-strength-advanced",
        "five-day-strength-intermediate",
        "five-day-strength-advanced",
        "six-day-push-pull-legs-strength",
        "three-day-full-body-fat-loss-intermediate",
        "four-day-upper-lower-fat-loss-intermediate",
        "four-day-upper-lower-fat-loss-advanced",
        "five-day-ppl-fat-loss-advanced",
        "three-day-full-body-general-fitness-intermediate",
        "four-day-upper-lower-general-fitness-intermediate",
    }
)


def _reclassify_goal_template(template: TrainingProgramTemplateSeed) -> TrainingProgramTemplateSeed:
    if template.fitness_goal is FitnessGoal.BUILD_MUSCLE:
        return template
    return replace(template, fitness_goal=FitnessGoal.BUILD_MUSCLE)


CATALOG_SLUG_ALIASES: dict[str, tuple[str, ...]] = {
    "barbell-bench-press": ("fedb-0025-barbell-bench-press",),
    "barbell-back-squat": ("fedb-1435-barbell-back-squat",),
    "barbell-straight-leg-deadlift": ("fedb-0116-barbell-straight-leg-deadlift",),
    "dumbbell-bench-press": ("fedb-0025-barbell-bench-press",),
    "incline-dumbbell-bench-press": ("fedb-0314-dumbbell-incline-bench-press",),
    "cable-fly": ("fedb-1269-cable-standing-fly",),
    "barbell-bent-over-row": ("fedb-0027-barbell-underhand-bent-over-row",),
    "lat-pulldown": ("fedb-0974-cable-close-grip-lat-pulldown",),
    "smith-machine-shoulder-press": ("fedb-0765-smith-seated-shoulder-press",),
    "dumbbell-lateral-raise": ("fedb-0334-dumbbell-lateral-raise",),
    "dumbbell-curl": ("fedb-0294-dumbbell-biceps-curl",),
    "hammer-curl": ("fedb-0298-dumbbell-cross-body-hammer-curl",),
    "cable-triceps-pushdown": ("fedb-1723-cable-triceps-pushdown",),
    "goblet-squat": ("fedb-1760-dumbbell-goblet-squat",),
    "leg-press": ("fedb-2611-lever-horizontal-leg-press",),
    "leg-extension": ("fedb-0585-lever-leg-extension",),
    "dumbbell-lunge": ("fedb-0336-dumbbell-lunge",),
    "seated-leg-curl": ("fedb-0599-lever-seated-leg-curl",),
    "glute-bridge": ("fedb-drv-hip-raise-bridge-glute-bridge",),
    "standing-calf-raise": ("fedb-0417-dumbbell-standing-calf-raise",),
}


def _slot(
    slug: str,
    muscles: tuple[MuscleGroup, ...],
    pattern: MovementPattern,
    *,
    placeholder_en: str | None = None,
    placeholder_fa: str | None = None,
    sets: int = 3,
    reps: tuple[int, int] = (8, 12),
    rir: int = 2,
    rest: int = 90,
    method: TrainingTemplateMethod = Method.STANDARD,
    priority: TrainingTemplateSlotPriority = Priority.CORE,
    superset_group: str | None = None,
) -> TemplateSlotSeed:
    return TemplateSlotSeed(
        exercise_slug_hint=slug,
        catalog_slug_hints=(slug, *CATALOG_SLUG_ALIASES.get(slug, ())),
        target_muscles=muscles,
        movement_pattern=pattern,
        placeholder_name_en=placeholder_en,
        placeholder_name_fa=placeholder_fa,
        sets=sets,
        rep_min=reps[0],
        rep_max=reps[1],
        target_rir=rir,
        rest_seconds=rest,
        intensity_method=method,
        adaptation_priority=priority,
        superset_group=superset_group,
    )


CHEST = _slot("dumbbell-bench-press", (M.CHEST,), P.HORIZONTAL_PUSH, sets=4)
BARBELL_BENCH = _slot(
    "barbell-bench-press",
    (M.CHEST,),
    P.HORIZONTAL_PUSH,
    placeholder_en="Barbell Bench Press",
    placeholder_fa="پرس سینه هالتر",
    sets=4,
    reps=(6, 10),
    rest=120,
)
INCLINE_CHEST = _slot(
    "incline-dumbbell-bench-press",
    (M.CHEST,),
    P.HORIZONTAL_PUSH,
    placeholder_en="Incline Dumbbell Bench Press",
    placeholder_fa="پرس سینه بالا سینه دمبل",
)
CABLE_FLY = _slot(
    "cable-fly",
    (M.CHEST,),
    P.HORIZONTAL_PUSH,
    placeholder_en="Cable Fly",
    placeholder_fa="فلای کابل",
    reps=(12, 15),
    rest=60,
)
BACK_ROW = _slot("barbell-bent-over-row", (M.BACK,), P.HORIZONTAL_PULL, sets=4)
LAT_PULLDOWN = _slot(
    "lat-pulldown",
    (M.BACK,),
    P.VERTICAL_PULL,
    placeholder_en="Lat Pulldown",
    placeholder_fa="لت پول‌داون",
)
CABLE_PULLDOWN = _slot(
    "cable-pullover",
    (M.BACK,),
    P.VERTICAL_PULL,
    placeholder_en="Cable Pullover",
    placeholder_fa="پلاور کابل",
    reps=(12, 15),
    rest=60,
)
SHOULDER_PRESS = _slot("smith-machine-shoulder-press", (M.SHOULDERS,), P.VERTICAL_PUSH)
LATERAL_RAISE = _slot(
    "dumbbell-lateral-raise", (M.SHOULDERS,), P.SHOULDER_ABDUCTION, reps=(12, 20), rest=60
)
REAR_DELT = _slot("rear-delt-fly", (M.SHOULDERS,), P.HORIZONTAL_PULL, reps=(12, 20), rest=60)
SHRUG = _slot(
    "dumbbell-shrug",
    (M.TRAPS,),
    P.SHRUG,
    placeholder_en="Dumbbell Shrug",
    placeholder_fa="شراگ دمبل",
    reps=(10, 15),
)
BICEPS = _slot("dumbbell-curl", (M.BICEPS,), P.ELBOW_FLEXION, reps=(10, 15), rest=60)
HAMMER_CURL = _slot("hammer-curl", (M.BICEPS,), P.ELBOW_FLEXION, reps=(10, 15), rest=60)
TRICEPS = _slot(
    "overhead-dumbbell-extension", (M.TRICEPS,), P.ELBOW_EXTENSION, reps=(10, 15), rest=60
)
PUSH_DOWN = _slot(
    "cable-triceps-pushdown",
    (M.TRICEPS,),
    P.ELBOW_EXTENSION,
    placeholder_en="Cable Triceps Pushdown",
    placeholder_fa="پشت بازو سیم‌کش",
    reps=(10, 15),
    rest=60,
)
SQUAT = _slot("goblet-squat", (M.QUADRICEPS,), P.SQUAT, sets=4)
BARBELL_BACK_SQUAT = _slot(
    "barbell-back-squat",
    (M.QUADRICEPS,),
    P.SQUAT,
    placeholder_en="Barbell Back Squat",
    placeholder_fa="اسکوات پشت هالتر",
    sets=4,
    reps=(6, 10),
    rest=120,
)
LEG_PRESS = _slot("leg-press", (M.QUADRICEPS,), P.SQUAT, sets=4)
LEG_EXTENSION = _slot("leg-extension", (M.QUADRICEPS,), P.KNEE_EXTENSION, reps=(12, 15), rest=60)
LUNGE = _slot("dumbbell-lunge", (M.QUADRICEPS, M.GLUTES), P.LUNGE)
RDL = _slot("romanian-deadlift", (M.HAMSTRINGS, M.GLUTES), P.HIP_HINGE, sets=4)
BARBELL_STRAIGHT_LEG_DEADLIFT = _slot(
    "barbell-straight-leg-deadlift",
    (M.HAMSTRINGS, M.GLUTES),
    P.HIP_HINGE,
    placeholder_en="Barbell Straight Leg Deadlift",
    placeholder_fa="ددلیفت پا صاف هالتر",
    sets=3,
    reps=(8, 10),
    rest=120,
)
LEG_CURL = _slot(
    "seated-leg-curl",
    (M.HAMSTRINGS,),
    P.KNEE_FLEXION,
    placeholder_en="Seated Leg Curl",
    placeholder_fa="پشت پا دستگاه نشسته",
    reps=(10, 15),
)
GLUTE_BRIDGE = _slot("glute-bridge", (M.GLUTES,), P.HIP_EXTENSION)
CALF = _slot("standing-calf-raise", (M.CALVES,), P.CALF_RAISE, reps=(10, 20), rest=60)
CORE = _slot(
    "dead-bug",
    (M.ABS,),
    P.CORE_ANTI_EXTENSION,
    placeholder_en="Dead Bug",
    placeholder_fa="ددباگ",
    reps=(8, 12),
    rest=45,
)
MACHINE_CHEST = _slot(
    "machine-chest-press",
    (M.CHEST,),
    P.HORIZONTAL_PUSH,
    placeholder_en="Machine Chest Press",
    placeholder_fa="پرس سینه دستگاه",
    sets=3,
)
PEC_DECK = _slot(
    "pec-deck-fly",
    (M.CHEST,),
    P.HORIZONTAL_PUSH,
    placeholder_en="Pec Deck Fly",
    placeholder_fa="فلای پک‌دک",
    reps=(12, 15),
    rest=60,
)
CHEST_SUPPORTED_ROW = _slot(
    "chest-supported-row",
    (M.BACK,),
    P.HORIZONTAL_PULL,
    placeholder_en="Chest-Supported Row",
    placeholder_fa="قایقی سینه‌تکیه‌گاه",
)
SINGLE_ARM_CABLE_ROW = _slot(
    "single-arm-cable-row",
    (M.BACK,),
    P.HORIZONTAL_PULL,
    placeholder_en="Single-Arm Cable Row",
    placeholder_fa="قایقی تک‌دست سیم‌کش",
)
NEUTRAL_LAT_PULLDOWN = _slot(
    "neutral-grip-lat-pulldown",
    (M.BACK,),
    P.VERTICAL_PULL,
    placeholder_en="Neutral-Grip Lat Pulldown",
    placeholder_fa="لت پول‌داون دست خنثی",
)
CABLE_LATERAL_RAISE = _slot(
    "cable-lateral-raise",
    (M.SHOULDERS,),
    P.SHOULDER_ABDUCTION,
    placeholder_en="Cable Lateral Raise",
    placeholder_fa="نشر جانب سیم‌کش",
    reps=(12, 20),
    rest=60,
)
FACE_PULL = _slot(
    "face-pull",
    (M.SHOULDERS,),
    P.HORIZONTAL_PULL,
    placeholder_en="Face Pull",
    placeholder_fa="فیس پول",
    reps=(12, 20),
    rest=60,
)
PREACHER_CURL = _slot(
    "preacher-curl",
    (M.BICEPS,),
    P.ELBOW_FLEXION,
    placeholder_en="Preacher Curl",
    placeholder_fa="جلو بازو لاری",
    reps=(10, 15),
    rest=60,
)
CABLE_CURL = _slot(
    "cable-curl",
    (M.BICEPS,),
    P.ELBOW_FLEXION,
    placeholder_en="Cable Curl",
    placeholder_fa="جلو بازو سیم‌کش",
    reps=(12, 15),
    rest=60,
)
SKULL_CRUSHER = _slot(
    "skull-crusher",
    (M.TRICEPS,),
    P.ELBOW_EXTENSION,
    placeholder_en="Skull Crusher",
    placeholder_fa="پشت بازو خوابیده",
    reps=(10, 15),
    rest=60,
)
ROPE_OVERHEAD_EXTENSION = _slot(
    "rope-overhead-extension",
    (M.TRICEPS,),
    P.ELBOW_EXTENSION,
    placeholder_en="Rope Overhead Extension",
    placeholder_fa="پشت بازو بالای سر طناب",
    reps=(12, 15),
    rest=60,
)
HACK_SQUAT = _slot(
    "hack-squat",
    (M.QUADRICEPS,),
    P.SQUAT,
    placeholder_en="Hack Squat",
    placeholder_fa="هک اسکوات",
    sets=4,
)
BULGARIAN_SPLIT_SQUAT = _slot(
    "bulgarian-split-squat",
    (M.QUADRICEPS, M.GLUTES),
    P.LUNGE,
    placeholder_en="Bulgarian Split Squat",
    placeholder_fa="اسپلیت اسکوات بلغاری",
)
LYING_LEG_CURL = _slot(
    "lying-leg-curl",
    (M.HAMSTRINGS,),
    P.KNEE_FLEXION,
    placeholder_en="Lying Leg Curl",
    placeholder_fa="پشت پا خوابیده",
    reps=(10, 15),
)
HIP_THRUST = _slot(
    "barbell-hip-thrust",
    (M.GLUTES,),
    P.HIP_EXTENSION,
    placeholder_en="Barbell Hip Thrust",
    placeholder_fa="هیپ تراست هالتر",
    sets=4,
)
BARBELL_SHRUG = _slot(
    "barbell-shrug",
    (M.TRAPS,),
    P.SHRUG,
    placeholder_en="Barbell Shrug",
    placeholder_fa="شراگ هالتر",
    reps=(10, 15),
)
SEATED_CALF_RAISE = _slot(
    "seated-calf-raise",
    (M.CALVES,),
    P.CALF_RAISE,
    placeholder_en="Seated Calf Raise",
    placeholder_fa="ساق نشسته",
    reps=(10, 20),
    rest=60,
)
SIDE_PLANK = _slot(
    "side-plank",
    (M.ABS,),
    P.CORE_ANTI_LATERAL_FLEXION,
    placeholder_en="Side Plank",
    placeholder_fa="پلانک بغل",
    reps=(8, 12),
    rest=45,
)
PALLOF_PRESS = _slot(
    "pallof-press",
    (M.ABS,),
    P.CORE_ANTI_ROTATION,
    placeholder_en="Pallof Press",
    placeholder_fa="پالوف پرس",
    reps=(10, 15),
    rest=45,
)

_SPECIALIZED_LARGE_TARGETS: tuple[tuple[str, tuple[MuscleGroup, ...]], ...] = (
    ("Chest", (M.CHEST,)),
    ("Back", (M.BACK,)),
    ("Shoulder", (M.SHOULDERS,)),
    ("Delts", (M.SHOULDERS,)),
    ("Quadriceps", (M.QUADRICEPS,)),
    ("Hamstrings", (M.HAMSTRINGS,)),
    ("Glutes", (M.GLUTES,)),
    ("Legs", (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES)),
)
_SPECIALIZED_SMALL_TARGETS: tuple[tuple[str, tuple[MuscleGroup, ...]], ...] = (
    ("Arms", (M.BICEPS, M.TRICEPS)),
    ("Biceps", (M.BICEPS,)),
    ("Triceps", (M.TRICEPS,)),
    ("Traps", (M.TRAPS,)),
    ("Calves", (M.CALVES,)),
    ("Core", (M.ABS,)),
)
_MOVEMENT_FLOOR_SLOTS: dict[tuple[MuscleGroup, ...], tuple[TemplateSlotSeed, ...]] = {
    (M.CHEST,): (CHEST, INCLINE_CHEST, MACHINE_CHEST, CABLE_FLY, PEC_DECK),
    (M.BACK,): (BACK_ROW, LAT_PULLDOWN, CABLE_PULLDOWN, CHEST_SUPPORTED_ROW, SINGLE_ARM_CABLE_ROW),
    (M.SHOULDERS,): (SHOULDER_PRESS, LATERAL_RAISE, REAR_DELT, CABLE_LATERAL_RAISE, FACE_PULL),
    (M.QUADRICEPS,): (SQUAT, LEG_PRESS, LEG_EXTENSION, HACK_SQUAT, BULGARIAN_SPLIT_SQUAT),
    (M.HAMSTRINGS,): (RDL, LEG_CURL, LYING_LEG_CURL),
    (M.GLUTES,): (GLUTE_BRIDGE, HIP_THRUST, LUNGE, BULGARIAN_SPLIT_SQUAT),
    (M.BICEPS,): (BICEPS, HAMMER_CURL, PREACHER_CURL, CABLE_CURL),
    (M.TRICEPS,): (TRICEPS, PUSH_DOWN, SKULL_CRUSHER, ROPE_OVERHEAD_EXTENSION),
    (M.TRAPS,): (SHRUG, BARBELL_SHRUG),
    (M.CALVES,): (CALF, SEATED_CALF_RAISE),
    (M.ABS,): (CORE, SIDE_PLANK, PALLOF_PRESS),
}


def _specialized_template_movement_floors(
    template: TrainingProgramTemplateSeed,
) -> TrainingProgramTemplateSeed:
    if template.days_per_week < 4 or Tag.BODY_PART_ROTATION not in template.focus_tags:
        return template
    return replace(
        template,
        days=tuple(_specialized_day_movement_floors(day) for day in template.days),
    )


def _specialized_day_movement_floors(day: TemplateDaySeed) -> TemplateDaySeed:
    minimums: dict[tuple[MuscleGroup, ...], int] = {}
    for label, muscles in _SPECIALIZED_LARGE_TARGETS:
        if label in day.title_en:
            minimums[muscles] = max(minimums.get(muscles, 0), 3)
    for label, muscles in _SPECIALIZED_SMALL_TARGETS:
        if label not in day.title_en:
            continue
        if label == "Arms":
            for muscle in muscles:
                minimums[(muscle,)] = 2
        else:
            minimums[muscles] = max(minimums.get(muscles, 0), 2)

    slots = list(day.slots)
    for muscles, minimum in minimums.items():
        existing = sum(bool(set(slot.target_muscles).intersection(muscles)) for slot in slots)
        for candidate in _MOVEMENT_FLOOR_SLOTS.get(muscles, ()):
            if existing >= minimum:
                break
            if any(slot.exercise_slug_hint == candidate.exercise_slug_hint for slot in slots):
                continue
            slots.append(candidate)
            existing += 1
    return replace(day, slots=tuple(slots))


def _fit_template_session_exercise_count(
    template: TrainingProgramTemplateSeed,
) -> TrainingProgramTemplateSeed:
    return replace(
        template,
        days=tuple(_fit_template_day_exercise_count(day) for day in template.days),
    )


def _fit_template_day_exercise_count(day: TemplateDaySeed) -> TemplateDaySeed:
    slots = list(day.slots)
    minimums = _direct_movement_minimums(day)
    while len(slots) > MAXIMUM_EXERCISES_PER_SESSION:
        removable = next(
            (
                index
                for index in range(len(slots) - 1, -1, -1)
                if _can_remove_slot(slots, index, minimums)
            ),
            None,
        )
        if removable is None:
            raise ValueError(f"Template session cannot fit exercise limit: {day.title_en}")
        slots.pop(removable)

    candidates = tuple(
        candidate
        for muscle in day.direct_target_muscles
        for candidate in _MOVEMENT_FLOOR_SLOTS.get((muscle,), ())
    )
    while len(slots) < MINIMUM_EXERCISES_PER_SESSION:
        candidate = next(
            (
                item
                for item in candidates
                if all(slot.exercise_slug_hint != item.exercise_slug_hint for slot in slots)
            ),
            None,
        )
        if candidate is None:
            raise ValueError(f"Template session lacks eligible exercise variety: {day.title_en}")
        slots.append(candidate)
    return replace(day, slots=tuple(slots))


def _direct_movement_minimums(day: TemplateDaySeed) -> dict[tuple[MuscleGroup, ...], int]:
    minimums: dict[tuple[MuscleGroup, ...], int] = {}
    for label, muscles in _SPECIALIZED_LARGE_TARGETS:
        if label in day.title_en:
            minimums[muscles] = 3
    for label, muscles in _SPECIALIZED_SMALL_TARGETS:
        if label in day.title_en:
            if label == "Arms":
                for muscle in muscles:
                    minimums[(muscle,)] = 2
            else:
                minimums[muscles] = 2
    return minimums


def _can_remove_slot(
    slots: list[TemplateSlotSeed],
    index: int,
    minimums: dict[tuple[MuscleGroup, ...], int],
) -> bool:
    remaining = slots[:index] + slots[index + 1 :]
    return all(
        sum(bool(set(slot.target_muscles).intersection(muscles)) for slot in remaining) >= minimum
        for muscles, minimum in minimums.items()
    )


_MAIN_MOVEMENT_PATTERNS = frozenset(
    {
        P.SQUAT,
        P.HIP_HINGE,
        P.LUNGE,
        P.HORIZONTAL_PUSH,
        P.HORIZONTAL_PULL,
        P.VERTICAL_PUSH,
        P.VERTICAL_PULL,
        P.HIP_EXTENSION,
    }
)
_ISOLATION_SLOT_SLUGS = frozenset(
    {
        "cable-fly",
        "pec-deck-fly",
        "cable-pullover",
        "rear-delt-fly",
        "face-pull",
    }
)
_DEFAULT_MOVEMENT_ORDER = {
    P.SQUAT: 0,
    P.HIP_HINGE: 1,
    P.LUNGE: 2,
    P.HORIZONTAL_PUSH: 3,
    P.HORIZONTAL_PULL: 4,
    P.VERTICAL_PULL: 5,
    P.VERTICAL_PUSH: 6,
    P.HIP_EXTENSION: 7,
}
_ISOLATION_MOVEMENT_ORDER = {
    P.KNEE_EXTENSION: 0,
    P.KNEE_FLEXION: 1,
    P.SHOULDER_ABDUCTION: 2,
    P.ELBOW_FLEXION: 3,
    P.ELBOW_EXTENSION: 4,
    P.SHRUG: 5,
    P.CALF_RAISE: 6,
    P.CORE_ANTI_EXTENSION: 7,
    P.CORE_ANTI_ROTATION: 8,
    P.CORE_ANTI_LATERAL_FLEXION: 9,
}


def _evidence_informed_template_order(
    template: TrainingProgramTemplateSeed,
) -> TrainingProgramTemplateSeed:
    return replace(
        template,
        days=tuple(_evidence_informed_day_order(day) for day in template.days),
    )


def _evidence_informed_day_order(day: TemplateDaySeed) -> TemplateDaySeed:
    focus_order = _day_focus_order(day.title_en)
    ordered_slots = tuple(
        slot
        for _, slot in sorted(
            enumerate(day.slots),
            key=lambda item: _slot_ordering_key(item[1], focus_order, item[0]),
        )
    )
    return replace(day, slots=ordered_slots)


def _slot_ordering_key(
    slot: TemplateSlotSeed,
    focus_order: dict[MovementPattern, int],
    original_index: int,
) -> tuple[int, int, int, int]:
    method_phase = 0 if slot.intensity_method is Method.STANDARD else 1
    movement_phase = (
        0
        if slot.movement_pattern in _MAIN_MOVEMENT_PATTERNS
        and slot.exercise_slug_hint not in _ISOLATION_SLOT_SLUGS
        else 1
    )
    fallback_order = (
        _DEFAULT_MOVEMENT_ORDER.get(slot.movement_pattern, 99)
        if movement_phase == 0
        else _ISOLATION_MOVEMENT_ORDER.get(slot.movement_pattern, 99)
    )
    return (
        method_phase,
        movement_phase,
        focus_order.get(slot.movement_pattern, fallback_order),
        original_index,
    )


def _day_focus_order(title_en: str) -> dict[MovementPattern, int]:
    if "Width" in title_en:
        return {P.VERTICAL_PULL: 0, P.HORIZONTAL_PULL: 1}
    if "Thickness" in title_en:
        return {P.HORIZONTAL_PULL: 0, P.VERTICAL_PULL: 1}
    if "Chest" in title_en:
        return {P.HORIZONTAL_PUSH: 0}
    if "Back" in title_en:
        return {P.HORIZONTAL_PULL: 0, P.VERTICAL_PULL: 1}
    if "Quadriceps" in title_en or "Quads" in title_en:
        return {P.SQUAT: 0, P.LUNGE: 1, P.KNEE_EXTENSION: 2}
    if "Hamstrings" in title_en:
        return {P.HIP_HINGE: 0, P.KNEE_FLEXION: 1, P.HIP_EXTENSION: 2}
    if "Shoulders" in title_en or "Delts" in title_en:
        return {P.VERTICAL_PUSH: 0, P.SHOULDER_ABDUCTION: 1}
    return _DEFAULT_MOVEMENT_ORDER


def _programming_rationale(
    template: TrainingProgramTemplateSeed,
) -> tuple[TemplateProgrammingRationaleSeed, ...]:
    focus_en, focus_fa = _priority_focus(template.focus_tags)
    split_en, split_fa = _split_focus(template.focus_tags, template.days_per_week)
    volume_en, volume_fa = _volume_guidance(template.training_level)
    intensity_en, intensity_fa = _intensity_guidance(template.intensity_methods)
    return (
        TemplateProgrammingRationaleSeed(
            "Exercise order",
            "ترتیب حرکات",
            (
                f"{focus_en} is placed before lower-priority work; "
                "main multi-joint movements lead each session."
            ),
            (
                f"{focus_fa} پیش از کار کم‌اولویت قرار می‌گیرد و هر جلسه با "
                "حرکت‌های اصلی چندمفصلی شروع می‌شود."
            ),
        ),
        TemplateProgrammingRationaleSeed(
            "Main movements",
            "حرکت‌های اصلی",
            (
                "The first movements use stable, repeatable loading; "
                "complementary angles follow before isolation work."
            ),
            (
                "حرکت‌های اول با بارگذاری پایدار و قابل‌پیگیری انتخاب شده‌اند؛ "
                "زاویه‌های مکمل بعد از آن و حرکات تک‌مفصلی در ادامه می‌آیند."
            ),
        ),
        TemplateProgrammingRationaleSeed(
            "Working sets and reps",
            "ست‌ها و تکرارهای کاری",
            volume_en,
            volume_fa,
        ),
        TemplateProgrammingRationaleSeed(
            "Program focus",
            "تمرکز برنامه",
            split_en,
            split_fa,
        ),
        TemplateProgrammingRationaleSeed(
            "Fatigue and progression",
            "مدیریت خستگی و پیشرفت",
            intensity_en,
            intensity_fa,
        ),
    )


def _priority_focus(tags: tuple[TemplateFocusTag, ...]) -> tuple[str, str]:
    priorities = {
        Tag.CHEST_PRIORITY: ("Chest priority", "اولویت سینه"),
        Tag.BACK_PRIORITY: ("Back priority", "اولویت زیربغل"),
        Tag.SHOULDERS_PRIORITY: ("Shoulder priority", "اولویت سرشانه"),
        Tag.QUAD_PRIORITY: ("Quadriceps priority", "اولویت چهارسر"),
        Tag.LOWER_PRIORITY: ("Lower-body priority", "اولویت پا"),
        Tag.ARMS_PRIORITY: ("Arm priority", "اولویت بازو"),
        Tag.HAMSTRINGS_PRIORITY: ("Hamstrings priority", "اولویت همسترینگ"),
        Tag.GLUTE_PRIORITY: ("Glute priority", "اولویت باسن"),
        Tag.UPPER_PRIORITY: ("Upper-body priority", "اولویت بالاتنه"),
    }
    return next(
        (priorities[tag] for tag in tags if tag in priorities),
        ("The session target", "عضلهٔ هدف جلسه"),
    )


def _split_focus(tags: tuple[TemplateFocusTag, ...], days_per_week: int) -> tuple[str, str]:
    if Tag.FULL_BODY in tags:
        return (
            (
                f"Full-body exposure is distributed across {days_per_week} days "
                "so practice and volume stay manageable."
            ),
            f"فشار تمام‌بدن در {days_per_week} روز پخش شده تا تمرین و حجم قابل‌مدیریت بماند.",
        )
    if Tag.PUSH_PULL_LEGS in tags:
        return (
            (
                "Push, pull, and lower-body work are separated to limit overlap "
                "and preserve performance."
            ),
            "پوش، پول و پا جدا شده‌اند تا هم‌پوشانی خستگی کم و کیفیت ست‌ها حفظ شود.",
        )
    if Tag.BODY_PART_ROTATION in tags:
        return (
            (
                "Direct target-muscle days concentrate useful work while leaving "
                "recovery before the next exposure."
            ),
            "روزهای عضلهٔ هدف، ست‌های مفید را متمرکز می‌کنند و تا نوبت بعدی فرصت ریکاوری می‌دهند.",
        )
    return (
        "The weekly split balances direct target work with recovery between related sessions.",
        "تقسیم هفتگی بین کار مستقیم عضلهٔ هدف و ریکاوری جلسات مرتبط تعادل ایجاد می‌کند.",
    )


def _volume_guidance(level: ExperienceLevel) -> tuple[str, str]:
    if level is Level.BEGINNER:
        return (
            (
                "Main movements use 3–4 quality working sets and controlled repetitions, "
                "leaving room to learn technique and recover."
            ),
            (
                "حرکت‌های اصلی ۳ تا ۴ ست کاری با تکرار کنترل‌شده دارند تا برای "
                "یادگیری فرم و ریکاوری فضا بماند."
            ),
        )
    if level is Level.INTERMEDIATE:
        return (
            (
                "Main lifts use 3–4 working sets; isolation work uses moderate repetitions "
                "to add volume without unnecessary joint stress."
            ),
            (
                "حرکت‌های اصلی ۳ تا ۴ ست کاری دارند و حرکات تک‌مفصلی با تکرار متوسط "
                "حجم می‌سازند، بدون فشار اضافه به مفصل‌ها."
            ),
        )
    return (
        (
            "Main lifts retain 3–4 high-quality working sets; higher-repetition isolation "
            "work adds targeted volume after the main work."
        ),
        (
            "حرکت‌های اصلی ۳ تا ۴ ست باکیفیت دارند و تکرار بالاتر در حرکات تک‌مفصلی "
            "پس از کار اصلی، حجم هدفمند اضافه می‌کند."
        ),
    )


def _intensity_guidance(
    methods: tuple[TrainingTemplateMethod, ...],
) -> tuple[str, str]:
    if Method.DROP_SET in methods or Method.SUPERSET in methods:
        return (
            (
                "Supersets and drop sets are reserved for the end of a session, "
                "after primary performance work is complete."
            ),
            "سوپرست و دراپ‌ست فقط پس از پایان کار اصلی و در انتهای جلسه قرار گرفته‌اند.",
        )
    return (
        (
            "Progress by adding repetitions or load with good form; accessory work stays "
            "after the demanding movements to manage fatigue."
        ),
        (
            "با حفظ فرم، تکرار یا وزنه را تدریجی بالا ببر؛ حرکات کمکی پس از حرکات پرفشار "
            "قرار دارند تا خستگی مدیریت شود."
        ),
    )


def _day(
    title_en: str,
    title_fa: str,
    muscles: tuple[MuscleGroup, ...],
    *slots: TemplateSlotSeed,
) -> TemplateDaySeed:
    return TemplateDaySeed(title_en, title_fa, muscles, slots)


def _template(
    slug: str,
    name_en: str,
    name_fa: str,
    description_en: str,
    description_fa: str,
    days_per_week: int,
    level: ExperienceLevel,
    tags: tuple[TemplateFocusTag, ...],
    methods: tuple[TrainingTemplateMethod, ...],
    *days: TemplateDaySeed,
    fitness_goal: FitnessGoal = FitnessGoal.BUILD_MUSCLE,
    is_active: bool = True,
) -> TrainingProgramTemplateSeed:
    template = TrainingProgramTemplateSeed(
        slug=slug,
        name_en=name_en,
        name_fa=name_fa,
        description_en=description_en,
        description_fa=description_fa,
        days_per_week=days_per_week,
        training_level=level,
        fitness_goal=fitness_goal,
        focus_tags=validate_focus_tags(tags),
        intensity_methods=methods,
        days=days,
        programming_rationale=(),
        is_active=is_active,
    )
    return replace(template, programming_rationale=_programming_rationale(template))


def _validate_template_tags(
    template: TrainingProgramTemplateSeed,
) -> TrainingProgramTemplateSeed:
    validate_template_focus_tags(
        template.focus_tags,
        intensity_methods=template.intensity_methods,
        days=template.days,
    )
    return template


TRAINING_PROGRAM_TEMPLATE_SEEDS: tuple[TrainingProgramTemplateSeed, ...] = tuple(
    _validate_template_tags(
    _reclassify_goal_template(
        _evidence_informed_template_order(
                _fit_template_session_exercise_count(
                    _specialized_template_movement_floors(template)
                )
            )
        )
    )
    for template in (
        _template(
            "two-day-full-body-foundation",
            "Two-Day Full Body Foundation",
            "پایه تمام‌بدن دو روزه",
            "Alternating full-body sessions for a beginner building consistent movement practice.",
            "جلسات تمام‌بدن چرخشی برای مبتدی که روی تکرار باکیفیت حرکات پایه تمرکز دارد.",
            2,
            Level.BEGINNER,
            (Tag.FULL_BODY, Tag.BALANCED),
            (Method.STANDARD,),
            _day(
                "Full Body A",
                "تمام‌بدن A",
                (M.CHEST, M.BACK, M.QUADRICEPS, M.GLUTES),
                CHEST,
                BACK_ROW,
                SQUAT,
                GLUTE_BRIDGE,
            ),
            _day(
                "Full Body B",
                "تمام‌بدن B",
                (M.CHEST, M.BACK, M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                INCLINE_CHEST,
                LAT_PULLDOWN,
                LEG_PRESS,
                RDL,
                CORE,
            ),
        ),
        _template(
            "two-day-upper-lower-foundation",
            "Two-Day Full Body Barbell Foundation",
            "پایه هالتر تمام‌بدن دو روزه",
            "A full-body A/B plan built around fundamental barbell and cable movement patterns.",
            "برنامهٔ A/B تمام‌بدن بر پایهٔ الگوهای اصلی هالتر و سیم‌کش.",
            2,
            Level.BEGINNER,
            (Tag.FULL_BODY, Tag.BALANCED),
            (Method.STANDARD,),
            _day(
                "Full Body A",
                "تمام‌بدن A",
                (M.CHEST, M.BACK, M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                BARBELL_BACK_SQUAT,
                BARBELL_BENCH,
                LAT_PULLDOWN,
                GLUTE_BRIDGE,
            ),
            _day(
                "Full Body B",
                "تمام‌بدن B",
                (M.CHEST, M.BACK, M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                LEG_PRESS,
                INCLINE_CHEST,
                BACK_ROW,
                BARBELL_STRAIGHT_LEG_DEADLIFT,
                CORE,
            ),
        ),
        _template(
            "two-day-full-body-hypertrophy",
            "Two-Day Full Body Hypertrophy",
            "هایپرتروفی تمام‌بدن دو روزه",
            "A higher-volume full-body A/B structure for an intermediate lifter "
            "with two training days.",
            "ساختار A/B تمام‌بدن با حجم بیشتر برای ورزشکار متوسط با دو روز تمرین.",
            2,
            Level.INTERMEDIATE,
            (Tag.FULL_BODY, Tag.BALANCED),
            (Method.STANDARD,),
            _day(
                "Full Body A",
                "تمام‌بدن A",
                (M.CHEST, M.BACK, M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                BARBELL_BACK_SQUAT,
                BARBELL_BENCH,
                BACK_ROW,
                RDL,
                LEG_EXTENSION,
            ),
            _day(
                "Full Body B",
                "تمام‌بدن B",
                (M.CHEST, M.BACK, M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                LEG_PRESS,
                INCLINE_CHEST,
                LAT_PULLDOWN,
                HIP_THRUST,
                LEG_CURL,
                CALF,
            ),
        ),
        _template(
            "two-day-upper-lower-strength-hypertrophy",
            "Two-Day Full Body Compound Hypertrophy",
            "هایپرتروفی چندمفصلی تمام‌بدن دو روزه",
            "Compound-first full-body sessions that keep each major movement pattern in both days.",
            "جلسات تمام‌بدن با اولویت حرکات چندمفصلی که الگوهای اصلی را در هر دو روز حفظ می‌کند.",
            2,
            Level.INTERMEDIATE,
            (Tag.FULL_BODY, Tag.COMPOUND_FOCUS, Tag.BALANCED),
            (Method.STANDARD,),
            _day(
                "Full Body A",
                "تمام‌بدن A",
                (M.CHEST, M.BACK, M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                BARBELL_BACK_SQUAT,
                BARBELL_BENCH,
                BACK_ROW,
                BARBELL_STRAIGHT_LEG_DEADLIFT,
                CORE,
            ),
            _day(
                "Full Body B",
                "تمام‌بدن B",
                (M.CHEST, M.BACK, M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                LEG_PRESS,
                INCLINE_CHEST,
                LAT_PULLDOWN,
                LUNGE,
                HIP_THRUST,
                CALF,
            ),
        ),
        _template(
            "two-day-full-body-superset",
            "Two-Day Full Body Supersets",
            "تمام‌بدن سوپرست دو روزه",
            "Time-efficient antagonist pairings for an experienced trainee "
            "with limited weekly access.",
            "جفت‌کردن عضلات مخالف برای ورزشکار باتجربه با زمان محدود در هفته.",
            2,
            Level.ADVANCED,
            (Tag.FULL_BODY,),
            (Method.STANDARD, Method.SUPERSET),
            _day(
                "Full Body A",
                "تمام‌بدن A",
                (M.CHEST, M.BACK, M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                BARBELL_BACK_SQUAT,
                BARBELL_BENCH,
                BACK_ROW,
                RDL,
                _slot("dumbbell-curl", (M.BICEPS,), P.ELBOW_FLEXION, method=Method.SUPERSET),
                _slot(
                    "overhead-dumbbell-extension",
                    (M.TRICEPS,),
                    P.ELBOW_EXTENSION,
                    method=Method.SUPERSET,
                ),
            ),
            _day(
                "Full Body B",
                "تمام‌بدن B",
                (M.CHEST, M.BACK, M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                LEG_PRESS,
                INCLINE_CHEST,
                LAT_PULLDOWN,
                GLUTE_BRIDGE,
                _slot(
                    "dumbbell-lateral-raise",
                    (M.SHOULDERS,),
                    P.SHOULDER_ABDUCTION,
                    method=Method.SUPERSET,
                ),
                _slot("standing-calf-raise", (M.CALVES,), P.CALF_RAISE, method=Method.SUPERSET),
            ),
        ),
        _template(
            "three-day-full-body-foundation",
            "Three-Day Full Body Foundation",
            "پایه تمام‌بدن سه روزه",
            "Three low-complexity full-body exposures for a new lifter.",
            "سه مواجههٔ تمام‌بدن کم‌پیچیدگی برای ورزشکار تازه‌کار.",
            3,
            Level.BEGINNER,
            (Tag.FULL_BODY, Tag.BALANCED),
            (Method.STANDARD,),
            _day(
                "Full Body A",
                "تمام‌بدن A",
                (M.CHEST, M.BACK, M.QUADRICEPS),
                CHEST,
                BACK_ROW,
                SQUAT,
                CORE,
            ),
            _day(
                "Full Body B",
                "تمام‌بدن B",
                (M.SHOULDERS, M.HAMSTRINGS, M.GLUTES),
                SHOULDER_PRESS,
                LAT_PULLDOWN,
                RDL,
                CALF,
            ),
            _day(
                "Full Body C",
                "تمام‌بدن C",
                (M.CHEST, M.BACK, M.QUADRICEPS),
                INCLINE_CHEST,
                LAT_PULLDOWN,
                LEG_PRESS,
                GLUTE_BRIDGE,
                BICEPS,
            ),
        ),
        _template(
            "three-day-push-pull-legs",
            "Three-Day Push / Pull / Legs",
            "پوش / پول / پا سه روزه",
            "A classic three-day push, pull, and lower-body rotation.",
            "چرخش کلاسیک سه‌روزهٔ پوش، پول و پایین‌تنه.",
            3,
            Level.INTERMEDIATE,
            (Tag.PUSH_PULL_LEGS, Tag.BALANCED),
            (Method.STANDARD,),
            _day(
                "Push",
                "پوش",
                (M.CHEST, M.SHOULDERS, M.TRICEPS),
                CHEST,
                SHOULDER_PRESS,
                LATERAL_RAISE,
                TRICEPS,
            ),
            _day(
                "Pull",
                "پول",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                CABLE_PULLDOWN,
                BICEPS,
                HAMMER_CURL,
            ),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES),
                SQUAT,
                RDL,
                LEG_EXTENSION,
                CALF,
            ),
        ),
        _template(
            "three-day-chest-priority",
            "Three-Day Chest Priority",
            "تأکید سینه سه روزه",
            "A full-body rotation that gives chest two direct priority exposures.",
            "چرخش تمام‌بدن که به سینه دو مواجههٔ مستقیم با اولویت می‌دهد.",
            3,
            Level.INTERMEDIATE,
            (Tag.FULL_BODY, Tag.CHEST_PRIORITY),
            (Method.STANDARD,),
            _day(
                "Chest + Quads",
                "سینه + چهارسر",
                (M.CHEST, M.QUADRICEPS),
                CHEST,
                INCLINE_CHEST,
                LEG_PRESS,
                LEG_EXTENSION,
            ),
            _day(
                "Back + Hamstrings",
                "زیربغل + همسترینگ",
                (M.BACK, M.HAMSTRINGS),
                BACK_ROW,
                LAT_PULLDOWN,
                RDL,
                LEG_CURL,
                BICEPS,
            ),
            _day(
                "Chest + Shoulders",
                "سینه + سرشانه",
                (M.CHEST, M.SHOULDERS),
                CABLE_FLY,
                CHEST,
                SHOULDER_PRESS,
                LATERAL_RAISE,
                TRICEPS,
            ),
        ),
        _template(
            "three-day-back-priority",
            "Three-Day Back Priority",
            "تأکید زیربغل سه روزه",
            "A full-body rotation that gives back two direct priority exposures.",
            "چرخش تمام‌بدن که به زیربغل دو مواجههٔ مستقیم با اولویت می‌دهد.",
            3,
            Level.INTERMEDIATE,
            (Tag.FULL_BODY, Tag.BACK_PRIORITY),
            (Method.STANDARD,),
            _day(
                "Back + Quads",
                "زیربغل + چهارسر",
                (M.BACK, M.QUADRICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                LEG_PRESS,
                LEG_EXTENSION,
            ),
            _day(
                "Chest + Hamstrings",
                "سینه + همسترینگ",
                (M.CHEST, M.HAMSTRINGS),
                CHEST,
                INCLINE_CHEST,
                RDL,
                LEG_CURL,
            ),
            _day(
                "Back + Arms",
                "زیربغل + بازو",
                (M.BACK, M.BICEPS),
                CABLE_PULLDOWN,
                BACK_ROW,
                BICEPS,
                HAMMER_CURL,
                TRICEPS,
            ),
        ),
        _template(
            "three-day-full-body-drop-set",
            "Three-Day Full Body Drop Set",
            "تمام‌بدن دراپ‌ست سه روزه",
            "An advanced three-day structure that reserves drop sets for low-risk isolation work.",
            "ساختار پیشرفتهٔ سه‌روزه که دراپ‌ست را برای حرکات ایزولهٔ کم‌ریسک نگه می‌دارد.",
            3,
            Level.ADVANCED,
            (Tag.FULL_BODY, Tag.BALANCED),
            (Method.STANDARD, Method.DROP_SET),
            _day(
                "Full Body A",
                "تمام‌بدن A",
                (M.CHEST, M.QUADRICEPS),
                CHEST,
                SQUAT,
                _slot(
                    "leg-extension",
                    (M.QUADRICEPS,),
                    P.KNEE_EXTENSION,
                    method=Method.DROP_SET,
                    reps=(12, 15),
                ),
            ),
            _day(
                "Full Body B",
                "تمام‌بدن B",
                (M.BACK, M.HAMSTRINGS),
                BACK_ROW,
                RDL,
                _slot(
                    "cable-curl",
                    (M.BICEPS,),
                    P.ELBOW_FLEXION,
                    method=Method.DROP_SET,
                    reps=(12, 15),
                ),
            ),
            _day(
                "Full Body C",
                "تمام‌بدن C",
                (M.SHOULDERS, M.GLUTES),
                SHOULDER_PRESS,
                GLUTE_BRIDGE,
                _slot(
                    "dumbbell-lateral-raise",
                    (M.SHOULDERS,),
                    P.SHOULDER_ABDUCTION,
                    method=Method.DROP_SET,
                    reps=(12, 20),
                ),
            ),
        ),
        _template(
            "four-day-classic-body-part",
            "Four-Day Classic Body-Part Rotation",
            "تفکیک کلاسیک چهار روزه",
            "Direct-muscle pairing for lifters ready to separate upper-body targets "
            "across four sessions.",
            "جفت‌کردن عضلات هدف برای ورزشکاری که در چهار جلسه آمادهٔ تفکیک بالاتنه است.",
            4,
            Level.INTERMEDIATE,
            (Tag.BODY_PART_ROTATION, Tag.BALANCED),
            (Method.STANDARD,),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                CABLE_FLY,
                TRICEPS,
                PUSH_DOWN,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                CABLE_PULLDOWN,
                BICEPS,
                HAMMER_CURL,
            ),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES),
                LEG_PRESS,
                RDL,
                LEG_EXTENSION,
                LEG_CURL,
                CALF,
            ),
            _day(
                "Shoulders + Traps",
                "سرشانه + کول",
                (M.SHOULDERS, M.TRAPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                REAR_DELT,
                SHRUG,
            ),
        ),
        _template(
            "four-day-chest-priority",
            "Four-Day Chest Priority Rotation",
            "تفکیک چهار روزه با تأکید سینه",
            "A body-part rotation with two chest exposures while keeping arm work "
            "directly assigned.",
            "تفکیک عضلات با دو مواجههٔ سینه و حفظ تمرین مستقیم بازوها.",
            4,
            Level.INTERMEDIATE,
            (Tag.BODY_PART_ROTATION, Tag.CHEST_PRIORITY),
            (Method.STANDARD,),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                TRICEPS,
                PUSH_DOWN,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                BICEPS,
                HAMMER_CURL,
            ),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES),
                LEG_PRESS,
                RDL,
                LEG_EXTENSION,
                CALF,
            ),
            _day(
                "Chest + Shoulders",
                "سینه + سرشانه",
                (M.CHEST, M.SHOULDERS),
                CABLE_FLY,
                CHEST,
                SHOULDER_PRESS,
                LATERAL_RAISE,
            ),
        ),
        _template(
            "four-day-back-priority",
            "Four-Day Back Priority Rotation",
            "تفکیک چهار روزه با تأکید زیربغل",
            "A body-part rotation with two direct back exposures and separated biceps work.",
            "تفکیک عضلات با دو مواجههٔ مستقیم زیربغل و جلو بازوی جداشده.",
            4,
            Level.INTERMEDIATE,
            (Tag.BODY_PART_ROTATION, Tag.BACK_PRIORITY),
            (Method.STANDARD,),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                TRICEPS,
                PUSH_DOWN,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                CABLE_PULLDOWN,
                BICEPS,
            ),
            _day("Legs", "پا", (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES), SQUAT, RDL, LEG_CURL, CALF),
            _day(
                "Back + Shoulders",
                "زیربغل + سرشانه",
                (M.BACK, M.SHOULDERS),
                BACK_ROW,
                LAT_PULLDOWN,
                LATERAL_RAISE,
                REAR_DELT,
            ),
        ),
        _template(
            "four-day-quad-hamstring-split",
            "Four-Day Quad / Hamstring Split",
            "تفکیک چهار روزهٔ چهارسر / همسترینگ",
            "An advanced upper/lower variant that separates knee-dominant and "
            "posterior-chain work.",
            "گونهٔ پیشرفتهٔ بالاتنه/پایین‌تنه که چهارسر و زنجیرهٔ خلفی را جدا می‌کند.",
            4,
            Level.ADVANCED,
            (Tag.UPPER_LOWER, Tag.QUAD_PRIORITY),
            (Method.STANDARD,),
            _day(
                "Chest + Back",
                "سینه + زیربغل",
                (M.CHEST, M.BACK),
                CHEST,
                BACK_ROW,
                INCLINE_CHEST,
                LAT_PULLDOWN,
            ),
            _day(
                "Quadriceps + Calves",
                "چهارسر + ساق",
                (M.QUADRICEPS, M.CALVES),
                LEG_PRESS,
                SQUAT,
                LEG_EXTENSION,
                CALF,
            ),
            _day(
                "Shoulders + Arms",
                "سرشانه + بازو",
                (M.SHOULDERS, M.BICEPS, M.TRICEPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                BICEPS,
                TRICEPS,
            ),
            _day(
                "Hamstrings + Glutes",
                "همسترینگ + باسن",
                (M.HAMSTRINGS, M.GLUTES),
                RDL,
                LEG_CURL,
                GLUTE_BRIDGE,
                LUNGE,
            ),
        ),
        _template(
            "four-day-phul",
            "Four-Day Power Hypertrophy Upper / Lower",
            "بالا / پایین قدرت و هایپرتروفی چهار روزه",
            "A higher-skill four-day upper/lower pattern with compound and hypertrophy exposures.",
            "الگوی بالاتنه/پایین‌تنهٔ چهارروزه با ترکیب حرکات پایه و هایپرتروفی.",
            4,
            Level.ADVANCED,
            (Tag.UPPER_LOWER, Tag.COMPOUND_FOCUS, Tag.BALANCED),
            (Method.STANDARD,),
            _day(
                "Upper Compound",
                "بالاتنه چندمفصلی",
                (M.CHEST, M.BACK, M.SHOULDERS),
                CHEST,
                BACK_ROW,
                SHOULDER_PRESS,
                BICEPS,
            ),
            _day(
                "Lower Compound",
                "پایین‌تنه چندمفصلی",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                LEG_PRESS,
                RDL,
                LUNGE,
                CALF,
            ),
            _day(
                "Upper Hypertrophy",
                "هایپرتروفی بالاتنه",
                (M.CHEST, M.BACK, M.SHOULDERS, M.ARMS if False else M.BICEPS),
                INCLINE_CHEST,
                LAT_PULLDOWN,
                LATERAL_RAISE,
                BICEPS,
                TRICEPS,
            ),
            _day(
                "Lower Hypertrophy",
                "هایپرتروفی پایین‌تنه",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES),
                SQUAT,
                LEG_EXTENSION,
                LEG_CURL,
                GLUTE_BRIDGE,
                CALF,
            ),
        ),
        _template(
            "five-day-classic-body-part",
            "Five-Day Classic Body-Part Rotation",
            "تفکیک کلاسیک پنج روزه",
            "A conventional five-day rotation with one clear direct target group per session.",
            "چرخش متعارف پنج‌روزه با گروه عضلانی هدف روشن در هر جلسه.",
            5,
            Level.INTERMEDIATE,
            (Tag.BODY_PART_ROTATION, Tag.BALANCED),
            (Method.STANDARD,),
            _day("Chest", "سینه", (M.CHEST,), CHEST, INCLINE_CHEST, CABLE_FLY),
            _day("Back", "زیربغل", (M.BACK,), BACK_ROW, LAT_PULLDOWN, CABLE_PULLDOWN),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES),
                LEG_PRESS,
                RDL,
                LEG_EXTENSION,
                LEG_CURL,
                CALF,
            ),
            _day(
                "Shoulders + Traps",
                "سرشانه + کول",
                (M.SHOULDERS, M.TRAPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                REAR_DELT,
                SHRUG,
            ),
            _day("Arms", "بازو", (M.BICEPS, M.TRICEPS), BICEPS, HAMMER_CURL, TRICEPS, PUSH_DOWN),
        ),
        _template(
            "five-day-ppl-upper-lower",
            "Five-Day Push Pull Legs Upper Lower",
            "پوش پول پا بالاتنه پایین‌تنه پنج روزه",
            "A five-day hybrid that adds an upper/lower exposure after a push-pull-legs base.",
            "ترکیب پنج‌روزه که بعد از پایهٔ پوش پول پا، یک مواجههٔ بالاتنه/پایین‌تنه اضافه می‌کند.",
            5,
            Level.INTERMEDIATE,
            (Tag.PUSH_PULL_LEGS, Tag.UPPER_LOWER, Tag.UPPER_PRIORITY),
            (Method.STANDARD,),
            _day("Push", "پوش", (M.CHEST, M.SHOULDERS, M.TRICEPS), CHEST, SHOULDER_PRESS, TRICEPS),
            _day("Pull", "پول", (M.BACK, M.BICEPS), BACK_ROW, LAT_PULLDOWN, BICEPS),
            _day("Legs", "پا", (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES), SQUAT, RDL, CALF),
            _day(
                "Upper",
                "بالاتنه",
                (M.CHEST, M.BACK, M.SHOULDERS),
                INCLINE_CHEST,
                CABLE_PULLDOWN,
                LATERAL_RAISE,
                HAMMER_CURL,
            ),
            _day(
                "Lower",
                "پایین‌تنه",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                LEG_PRESS,
                LEG_EXTENSION,
                LEG_CURL,
                GLUTE_BRIDGE,
            ),
        ),
        _template(
            "five-day-chest-specialization",
            "Five-Day Chest Specialization",
            "تخصصی سینه پنج روزه",
            "Extra direct chest exposure placed early in two weekly sessions "
            "for a chest priority block.",
            "مواجههٔ مستقیم اضافهٔ سینه در ابتدای دو جلسهٔ هفتگی برای دورهٔ اولویت سینه.",
            5,
            Level.ADVANCED,
            (Tag.BODY_PART_ROTATION, Tag.CHEST_PRIORITY, Tag.SPECIALIZATION),
            (Method.STANDARD,),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                CABLE_FLY,
                TRICEPS,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                BICEPS,
            ),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                LEG_PRESS,
                RDL,
                LEG_EXTENSION,
                LEG_CURL,
            ),
            _day(
                "Chest + Shoulders",
                "سینه + سرشانه",
                (M.CHEST, M.SHOULDERS),
                CHEST,
                CABLE_FLY,
                SHOULDER_PRESS,
                LATERAL_RAISE,
            ),
            _day(
                "Arms + Calves",
                "بازو + ساق",
                (M.BICEPS, M.TRICEPS, M.CALVES),
                HAMMER_CURL,
                PUSH_DOWN,
                TRICEPS,
                CALF,
            ),
        ),
        _template(
            "five-day-back-specialization",
            "Five-Day Back Specialization",
            "تخصصی زیربغل پنج روزه",
            "Extra direct back exposure without moving biceps into every back session.",
            "مواجههٔ مستقیم اضافهٔ زیربغل بدون قراردادن جلو بازو در تمام جلسات پشت.",
            5,
            Level.ADVANCED,
            (Tag.BODY_PART_ROTATION, Tag.BACK_PRIORITY, Tag.SPECIALIZATION),
            (Method.STANDARD,),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                TRICEPS,
                PUSH_DOWN,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                CABLE_PULLDOWN,
                BICEPS,
            ),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                SQUAT,
                RDL,
                LEG_EXTENSION,
                LEG_CURL,
            ),
            _day(
                "Back + Rear Delts",
                "زیربغل + پشت سرشانه",
                (M.BACK, M.SHOULDERS),
                BACK_ROW,
                LAT_PULLDOWN,
                REAR_DELT,
                CABLE_PULLDOWN,
            ),
            _day(
                "Shoulders + Arms",
                "سرشانه + بازو",
                (M.SHOULDERS, M.BICEPS, M.TRICEPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                HAMMER_CURL,
                PUSH_DOWN,
            ),
        ),
        _template(
            "five-day-posterior-chain-superset",
            "Five-Day Posterior Chain Supersets",
            "سوپرست زنجیرهٔ خلفی پنج روزه",
            "An advanced posterior-chain emphasis with compatible isolation supersets.",
            "تأکید پیشرفتهٔ زنجیرهٔ خلفی با سوپرست‌های سازگارِ ایزوله.",
            5,
            Level.ADVANCED,
            (
                Tag.BODY_PART_ROTATION,
                Tag.LOWER_PRIORITY,
                Tag.HAMSTRINGS_PRIORITY,
                Tag.GLUTE_PRIORITY,
            ),
            (Method.STANDARD, Method.SUPERSET),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                TRICEPS,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                BICEPS,
            ),
            _day(
                "Quadriceps + Calves",
                "چهارسر + ساق",
                (M.QUADRICEPS, M.CALVES),
                LEG_PRESS,
                LEG_EXTENSION,
                _slot("standing-calf-raise", (M.CALVES,), P.CALF_RAISE, method=Method.SUPERSET),
            ),
            _day(
                "Hamstrings + Glutes",
                "همسترینگ + باسن",
                (M.HAMSTRINGS, M.GLUTES),
                RDL,
                LEG_CURL,
                GLUTE_BRIDGE,
                LUNGE,
            ),
            _day(
                "Shoulders + Rear Delts",
                "سرشانه + پشت سرشانه",
                (M.SHOULDERS,),
                SHOULDER_PRESS,
                _slot(
                    "dumbbell-lateral-raise",
                    (M.SHOULDERS,),
                    P.SHOULDER_ABDUCTION,
                    method=Method.SUPERSET,
                ),
                _slot("rear-delt-fly", (M.SHOULDERS,), P.HORIZONTAL_PULL, method=Method.SUPERSET),
            ),
        ),
        _template(
            "four-day-beginner-body-part-foundation",
            "Four-Day Beginner Body-Part Foundation",
            "پایه تفکیک عضلات چهارروزه مبتدی",
            "A conservative body-part introduction with three direct large-muscle slots "
            "and two direct arm slots.",
            "شروع محافظه‌کارانهٔ تفکیک عضلات با سه حرکت مستقیم عضلات بزرگ و دو حرکت مستقیم بازو.",
            4,
            Level.BEGINNER,
            (Tag.BODY_PART_ROTATION, Tag.BALANCED),
            (Method.STANDARD,),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                CABLE_FLY,
                TRICEPS,
                PUSH_DOWN,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                CABLE_PULLDOWN,
                BICEPS,
                HAMMER_CURL,
            ),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES),
                SQUAT,
                RDL,
                LEG_EXTENSION,
                LEG_CURL,
                CALF,
            ),
            _day(
                "Shoulders + Traps",
                "سرشانه + کول",
                (M.SHOULDERS, M.TRAPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                REAR_DELT,
                SHRUG,
                CORE,
            ),
        ),
        _template(
            "four-day-shoulder-priority",
            "Four-Day Shoulder Priority Rotation",
            "تفکیک چهارروزه با تأکید سرشانه",
            "An intermediate rotation that gives all shoulder regions direct work while "
            "retaining separated chest and back days.",
            "تفکیک متوسط با تمرین مستقیم تمام بخش‌های سرشانه و حفظ روزهای جدا برای سینه و زیربغل.",
            4,
            Level.INTERMEDIATE,
            (Tag.BODY_PART_ROTATION, Tag.SHOULDERS_PRIORITY),
            (Method.STANDARD,),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                MACHINE_CHEST,
                CABLE_FLY,
                TRICEPS,
                PUSH_DOWN,
                SKULL_CRUSHER,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                CHEST_SUPPORTED_ROW,
                CABLE_PULLDOWN,
                BICEPS,
                HAMMER_CURL,
                PREACHER_CURL,
            ),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES),
                LEG_PRESS,
                RDL,
                LEG_EXTENSION,
                LEG_CURL,
                LUNGE,
                CALF,
            ),
            _day(
                "Shoulders + Traps",
                "سرشانه + کول",
                (M.SHOULDERS, M.TRAPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                CABLE_LATERAL_RAISE,
                REAR_DELT,
                FACE_PULL,
                SHRUG,
            ),
        ),
        _template(
            "four-day-arms-priority",
            "Four-Day Arm Priority Rotation",
            "تفکیک چهارروزه با تأکید بازو",
            "An intermediate rotation that preserves body-part days and adds a direct "
            "three-movement biceps and triceps focus.",
            "تفکیک متوسط با حفظ روزهای عضلانی و یک تمرکز مستقیم سه‌حرکتی برای جلو بازو و پشت بازو.",
            4,
            Level.INTERMEDIATE,
            (Tag.BODY_PART_ROTATION, Tag.ARMS_PRIORITY),
            (Method.STANDARD,),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                MACHINE_CHEST,
                CABLE_FLY,
                TRICEPS,
                PUSH_DOWN,
                SKULL_CRUSHER,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                CHEST_SUPPORTED_ROW,
                CABLE_PULLDOWN,
                BICEPS,
                HAMMER_CURL,
                PREACHER_CURL,
            ),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES),
                SQUAT,
                RDL,
                LEG_EXTENSION,
                LEG_CURL,
                CALF,
            ),
            _day(
                "Arms + Delts",
                "بازو + سرشانه",
                (M.BICEPS, M.TRICEPS, M.SHOULDERS),
                CABLE_CURL,
                PREACHER_CURL,
                HAMMER_CURL,
                ROPE_OVERHEAD_EXTENSION,
                PUSH_DOWN,
                SKULL_CRUSHER,
                LATERAL_RAISE,
            ),
        ),
        _template(
            "four-day-advanced-chest-specialization",
            "Four-Day Advanced Chest Specialization",
            "تخصصی سینه چهارروزه پیشرفته",
            "A long-session advanced chest block with five direct chest movements and "
            "three triceps movements.",
            "دورهٔ پیشرفتهٔ سینه برای جلسات طولانی با پنج حرکت مستقیم سینه و سه حرکت پشت بازو.",
            4,
            Level.ADVANCED,
            (Tag.BODY_PART_ROTATION, Tag.CHEST_PRIORITY, Tag.SPECIALIZATION),
            (Method.STANDARD, Method.DROP_SET),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                MACHINE_CHEST,
                CABLE_FLY,
                PEC_DECK,
                TRICEPS,
                PUSH_DOWN,
                _slot(
                    "rope-overhead-extension",
                    (M.TRICEPS,),
                    P.ELBOW_EXTENSION,
                    placeholder_en="Rope Overhead Extension",
                    placeholder_fa="پشت بازو بالای سر طناب",
                    reps=(12, 15),
                    rest=60,
                    method=Method.DROP_SET,
                    priority=Priority.ACCESSORY,
                ),
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                CHEST_SUPPORTED_ROW,
                SINGLE_ARM_CABLE_ROW,
                BICEPS,
                HAMMER_CURL,
                PREACHER_CURL,
            ),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES),
                HACK_SQUAT,
                RDL,
                LEG_PRESS,
                LEG_CURL,
                HIP_THRUST,
                CALF,
            ),
            _day(
                "Shoulders + Traps",
                "سرشانه + کول",
                (M.SHOULDERS, M.TRAPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                CABLE_LATERAL_RAISE,
                REAR_DELT,
                FACE_PULL,
                SHRUG,
            ),
        ),
        _template(
            "four-day-advanced-posterior-chain",
            "Four-Day Advanced Posterior Chain",
            "زنجیره خلفی پیشرفته چهارروزه",
            "An advanced split that separates quadriceps and posterior-chain volume and "
            "pairs compatible accessories as supersets.",
            "تفکیک پیشرفته با جداسازی حجم چهارسر و زنجیرهٔ خلفی و سوپرست حرکات کمکی سازگار.",
            4,
            Level.ADVANCED,
            (
                Tag.BODY_PART_ROTATION,
                Tag.SPECIALIZATION,
                Tag.LOWER_PRIORITY,
                Tag.HAMSTRINGS_PRIORITY,
                Tag.GLUTE_PRIORITY,
            ),
            (Method.STANDARD, Method.SUPERSET),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                MACHINE_CHEST,
                CABLE_FLY,
                TRICEPS,
                PUSH_DOWN,
                SKULL_CRUSHER,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                CHEST_SUPPORTED_ROW,
                SINGLE_ARM_CABLE_ROW,
                CABLE_PULLDOWN,
                BICEPS,
                HAMMER_CURL,
                PREACHER_CURL,
            ),
            _day(
                "Quadriceps + Calves",
                "چهارسر + ساق",
                (M.QUADRICEPS, M.CALVES),
                HACK_SQUAT,
                LEG_PRESS,
                SQUAT,
                LEG_EXTENSION,
                BULGARIAN_SPLIT_SQUAT,
                _slot(
                    "standing-calf-raise",
                    (M.CALVES,),
                    P.CALF_RAISE,
                    reps=(10, 20),
                    rest=60,
                    method=Method.SUPERSET,
                    priority=Priority.ACCESSORY,
                    superset_group="quad-calf",
                ),
                _slot(
                    "seated-calf-raise",
                    (M.CALVES,),
                    P.CALF_RAISE,
                    placeholder_en="Seated Calf Raise",
                    placeholder_fa="ساق نشسته",
                    reps=(10, 20),
                    rest=60,
                    method=Method.SUPERSET,
                    priority=Priority.ACCESSORY,
                    superset_group="quad-calf",
                ),
            ),
            _day(
                "Hamstrings + Glutes",
                "همسترینگ + باسن",
                (M.HAMSTRINGS, M.GLUTES),
                RDL,
                LEG_CURL,
                LYING_LEG_CURL,
                HIP_THRUST,
                GLUTE_BRIDGE,
                LUNGE,
                CORE,
            ),
        ),
        _template(
            "five-day-beginner-body-part-foundation",
            "Five-Day Beginner Body-Part Foundation",
            "پایه تفکیک عضلات پنج‌روزه مبتدی",
            "A beginner five-day rotation with conservative three-movement large-muscle "
            "work and two-movement direct arm work.",
            "چرخش پنج‌روزهٔ مبتدی با سه حرکت محافظه‌کارانه برای عضلات بزرگ و دو حرکت مستقیم بازو.",
            5,
            Level.BEGINNER,
            (Tag.BODY_PART_ROTATION, Tag.BALANCED),
            (Method.STANDARD,),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                CABLE_FLY,
                TRICEPS,
                PUSH_DOWN,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                CABLE_PULLDOWN,
                BICEPS,
                HAMMER_CURL,
            ),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES),
                SQUAT,
                RDL,
                LEG_EXTENSION,
                LEG_CURL,
                CALF,
            ),
            _day(
                "Shoulders + Traps",
                "سرشانه + کول",
                (M.SHOULDERS, M.TRAPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                REAR_DELT,
                SHRUG,
            ),
            _day(
                "Arms + Core",
                "بازو + شکم",
                (M.BICEPS, M.TRICEPS, M.ABS),
                BICEPS,
                TRICEPS,
                HAMMER_CURL,
                PUSH_DOWN,
                CORE,
            ),
        ),
        _template(
            "five-day-shoulder-priority",
            "Five-Day Shoulder Priority",
            "تأکید سرشانه پنج‌روزه",
            "An intermediate body-part rotation with a complete direct shoulder day and "
            "separated chest and arm work.",
            "چرخش متوسط با روز کامل سرشانه و تمرین جدا برای سینه و بازو.",
            5,
            Level.INTERMEDIATE,
            (Tag.BODY_PART_ROTATION, Tag.SHOULDERS_PRIORITY),
            (Method.STANDARD,),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                MACHINE_CHEST,
                CABLE_FLY,
                TRICEPS,
                PUSH_DOWN,
                SKULL_CRUSHER,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                CHEST_SUPPORTED_ROW,
                CABLE_PULLDOWN,
                BICEPS,
                HAMMER_CURL,
                PREACHER_CURL,
            ),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.CALVES),
                LEG_PRESS,
                RDL,
                LEG_EXTENSION,
                LEG_CURL,
                CALF,
            ),
            _day(
                "Shoulders + Traps",
                "سرشانه + کول",
                (M.SHOULDERS, M.TRAPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                CABLE_LATERAL_RAISE,
                REAR_DELT,
                FACE_PULL,
                SHRUG,
            ),
            _day(
                "Arms",
                "بازو",
                (M.BICEPS, M.TRICEPS),
                CABLE_CURL,
                PREACHER_CURL,
                HAMMER_CURL,
                ROPE_OVERHEAD_EXTENSION,
                PUSH_DOWN,
                SKULL_CRUSHER,
            ),
        ),
        _template(
            "five-day-quad-priority",
            "Five-Day Quadriceps Priority",
            "تأکید چهارسر پنج‌روزه",
            "An intermediate five-day rotation with a complete direct quadriceps day and "
            "posterior-chain maintenance.",
            "چرخش پنج‌روزهٔ متوسط با روز کامل چهارسر و نگهداری زنجیرهٔ خلفی.",
            5,
            Level.INTERMEDIATE,
            (Tag.BODY_PART_ROTATION, Tag.QUAD_PRIORITY, Tag.LOWER_PRIORITY),
            (Method.STANDARD,),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                MACHINE_CHEST,
                CABLE_FLY,
                TRICEPS,
                PUSH_DOWN,
                SKULL_CRUSHER,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                CHEST_SUPPORTED_ROW,
                CABLE_PULLDOWN,
                BICEPS,
                HAMMER_CURL,
                PREACHER_CURL,
            ),
            _day(
                "Quadriceps + Calves",
                "چهارسر + ساق",
                (M.QUADRICEPS, M.CALVES),
                HACK_SQUAT,
                LEG_PRESS,
                SQUAT,
                LEG_EXTENSION,
                BULGARIAN_SPLIT_SQUAT,
                CALF,
            ),
            _day(
                "Hamstrings + Glutes",
                "همسترینگ + باسن",
                (M.HAMSTRINGS, M.GLUTES),
                RDL,
                LEG_CURL,
                LYING_LEG_CURL,
                HIP_THRUST,
                GLUTE_BRIDGE,
            ),
            _day(
                "Shoulders + Arms",
                "سرشانه + بازو",
                (M.SHOULDERS, M.BICEPS, M.TRICEPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                REAR_DELT,
                CABLE_CURL,
                ROPE_OVERHEAD_EXTENSION,
                PUSH_DOWN,
            ),
        ),
        _template(
            "five-day-advanced-arm-specialization",
            "Five-Day Advanced Arm Specialization",
            "تخصصی بازو پنج‌روزه پیشرفته",
            "An advanced high-volume arm block with three to four direct movements per "
            "arm and isolated intensity techniques.",
            "دورهٔ حجمی پیشرفتهٔ بازو با سه تا چهار حرکت مستقیم برای هر بازو و "
            "تکنیک شدت روی حرکات ایزوله.",
            5,
            Level.ADVANCED,
            (Tag.BODY_PART_ROTATION, Tag.ARMS_PRIORITY, Tag.SPECIALIZATION),
            (Method.STANDARD, Method.DROP_SET),
            _day(
                "Chest",
                "سینه",
                (M.CHEST,),
                CHEST,
                INCLINE_CHEST,
                MACHINE_CHEST,
                CABLE_FLY,
                PEC_DECK,
            ),
            _day(
                "Back",
                "زیربغل",
                (M.BACK,),
                BACK_ROW,
                LAT_PULLDOWN,
                CHEST_SUPPORTED_ROW,
                SINGLE_ARM_CABLE_ROW,
                CABLE_PULLDOWN,
            ),
            _day(
                "Quadriceps + Calves",
                "چهارسر + ساق",
                (M.QUADRICEPS, M.CALVES),
                HACK_SQUAT,
                LEG_PRESS,
                SQUAT,
                LEG_EXTENSION,
                BULGARIAN_SPLIT_SQUAT,
                CALF,
            ),
            _day(
                "Hamstrings + Glutes",
                "همسترینگ + باسن",
                (M.HAMSTRINGS, M.GLUTES),
                RDL,
                LEG_CURL,
                LYING_LEG_CURL,
                HIP_THRUST,
                GLUTE_BRIDGE,
            ),
            _day(
                "Arms + Delts",
                "بازو + سرشانه",
                (M.BICEPS, M.TRICEPS, M.SHOULDERS),
                BICEPS,
                HAMMER_CURL,
                PREACHER_CURL,
                _slot(
                    "cable-curl",
                    (M.BICEPS,),
                    P.ELBOW_FLEXION,
                    reps=(12, 15),
                    rest=60,
                    method=Method.DROP_SET,
                    priority=Priority.ACCESSORY,
                ),
                TRICEPS,
                PUSH_DOWN,
                SKULL_CRUSHER,
                _slot(
                    "rope-overhead-extension",
                    (M.TRICEPS,),
                    P.ELBOW_EXTENSION,
                    placeholder_en="Rope Overhead Extension",
                    placeholder_fa="پشت بازو بالای سر طناب",
                    reps=(12, 15),
                    rest=60,
                    method=Method.DROP_SET,
                    priority=Priority.ACCESSORY,
                ),
                LATERAL_RAISE,
            ),
        ),
        _template(
            "five-day-advanced-leg-specialization",
            "Five-Day Advanced Leg Specialization",
            "تخصصی پا پنج‌روزه پیشرفته",
            "An advanced lower-body emphasis with separate quad and posterior-chain days "
            "and accessory supersets.",
            "تأکید پیشرفته بر پایین‌تنه با روزهای جدا برای چهارسر و زنجیرهٔ خلفی و سوپرست کمکی.",
            5,
            Level.ADVANCED,
            (
                Tag.BODY_PART_ROTATION,
                Tag.LOWER_PRIORITY,
                Tag.QUAD_PRIORITY,
                Tag.HAMSTRINGS_PRIORITY,
                Tag.GLUTE_PRIORITY,
            ),
            (Method.STANDARD, Method.SUPERSET, Method.DROP_SET),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                MACHINE_CHEST,
                CABLE_FLY,
                TRICEPS,
                PUSH_DOWN,
                SKULL_CRUSHER,
            ),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                CHEST_SUPPORTED_ROW,
                SINGLE_ARM_CABLE_ROW,
                CABLE_PULLDOWN,
                BICEPS,
                HAMMER_CURL,
                PREACHER_CURL,
            ),
            _day(
                "Quadriceps + Calves",
                "چهارسر + ساق",
                (M.QUADRICEPS, M.CALVES),
                HACK_SQUAT,
                LEG_PRESS,
                SQUAT,
                LEG_EXTENSION,
                _slot(
                    "bulgarian-split-squat",
                    (M.QUADRICEPS, M.GLUTES),
                    P.LUNGE,
                    placeholder_en="Bulgarian Split Squat",
                    placeholder_fa="اسپلیت اسکوات بلغاری",
                    method=Method.DROP_SET,
                    priority=Priority.ACCESSORY,
                ),
                _slot(
                    "standing-calf-raise",
                    (M.CALVES,),
                    P.CALF_RAISE,
                    reps=(10, 20),
                    rest=60,
                    method=Method.SUPERSET,
                    priority=Priority.ACCESSORY,
                    superset_group="leg-calf",
                ),
                _slot(
                    "seated-calf-raise",
                    (M.CALVES,),
                    P.CALF_RAISE,
                    placeholder_en="Seated Calf Raise",
                    placeholder_fa="ساق نشسته",
                    reps=(10, 20),
                    rest=60,
                    method=Method.SUPERSET,
                    priority=Priority.ACCESSORY,
                    superset_group="leg-calf",
                ),
            ),
            _day(
                "Hamstrings + Glutes",
                "همسترینگ + باسن",
                (M.HAMSTRINGS, M.GLUTES),
                RDL,
                LEG_CURL,
                LYING_LEG_CURL,
                HIP_THRUST,
                GLUTE_BRIDGE,
                LUNGE,
                CORE,
            ),
            _day(
                "Shoulders + Arms",
                "سرشانه + بازو",
                (M.SHOULDERS, M.BICEPS, M.TRICEPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                CABLE_LATERAL_RAISE,
                REAR_DELT,
                BICEPS,
                PREACHER_CURL,
                TRICEPS,
                PUSH_DOWN,
            ),
        ),
        _template(
            "six-day-ppl-twice",
            "Six-Day Push Pull Legs Twice",
            "پوش پول پا دوبار در هفته",
            "The conventional six-day PPL rotation with direct exposure repeated twice.",
            "چرخش متعارف شش‌روزهٔ پوش پول پا با دو مواجههٔ مستقیم برای هر الگو.",
            6,
            Level.INTERMEDIATE,
            (Tag.PUSH_PULL_LEGS, Tag.BALANCED),
            (Method.STANDARD,),
            _day(
                "Push A", "پوش A", (M.CHEST, M.SHOULDERS, M.TRICEPS), CHEST, SHOULDER_PRESS, TRICEPS
            ),
            _day("Pull A", "پول A", (M.BACK, M.BICEPS), BACK_ROW, LAT_PULLDOWN, BICEPS),
            _day("Legs A", "پا A", (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES), SQUAT, RDL, CALF),
            _day(
                "Push B",
                "پوش B",
                (M.CHEST, M.SHOULDERS, M.TRICEPS),
                INCLINE_CHEST,
                LATERAL_RAISE,
                PUSH_DOWN,
            ),
            _day("Pull B", "پول B", (M.BACK, M.BICEPS), CABLE_PULLDOWN, BACK_ROW, HAMMER_CURL),
            _day(
                "Legs B",
                "پا B",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                LEG_PRESS,
                LEG_EXTENSION,
                LEG_CURL,
                GLUTE_BRIDGE,
            ),
        ),
        _template(
            "six-day-ppl-volume",
            "Six-Day PPL Volume Rotation",
            "چرخش حجمی پوش پول پا شش روزه",
            "A higher-volume PPL rotation that spreads direct work across "
            "two push, pull, and leg days.",
            "چرخش حجمی پوش پول پا که کار مستقیم را در دو روز پوش، پول و پا پخش می‌کند.",
            6,
            Level.ADVANCED,
            (Tag.PUSH_PULL_LEGS, Tag.BALANCED),
            (Method.STANDARD,),
            _day(
                "Push Chest",
                "پوش سینه",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                CABLE_FLY,
                TRICEPS,
            ),
            _day(
                "Pull Width",
                "پول عرض پشت",
                (M.BACK, M.BICEPS),
                LAT_PULLDOWN,
                CABLE_PULLDOWN,
                BICEPS,
            ),
            _day(
                "Legs Quadriceps",
                "پا چهارسر",
                (M.QUADRICEPS, M.CALVES),
                LEG_PRESS,
                SQUAT,
                LEG_EXTENSION,
                CALF,
            ),
            _day(
                "Push Shoulders",
                "پوش سرشانه",
                (M.SHOULDERS, M.TRICEPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                REAR_DELT,
                PUSH_DOWN,
            ),
            _day(
                "Pull Thickness",
                "پول ضخامت پشت",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                HAMMER_CURL,
            ),
            _day(
                "Legs Posterior",
                "پا زنجیرهٔ خلفی",
                (M.HAMSTRINGS, M.GLUTES),
                RDL,
                LEG_CURL,
                GLUTE_BRIDGE,
                LUNGE,
            ),
        ),
        _template(
            "six-day-chest-back-legs-shoulders-arms-legs",
            "Six-Day Body-Part Rotation",
            "تفکیک عضلات شش روزه",
            "A classic body-part rotation for advanced lifters who recover well "
            "from frequent sessions.",
            "تفکیک کلاسیک عضلات برای ورزشکار پیشرفته با ریکاوری مناسب از جلسات پرتعداد.",
            6,
            Level.ADVANCED,
            (Tag.BODY_PART_ROTATION, Tag.BALANCED),
            (Method.STANDARD,),
            _day("Chest", "سینه", (M.CHEST,), CHEST, INCLINE_CHEST, CABLE_FLY),
            _day("Back", "زیربغل", (M.BACK,), BACK_ROW, LAT_PULLDOWN, CABLE_PULLDOWN),
            _day(
                "Quadriceps + Calves",
                "چهارسر + ساق",
                (M.QUADRICEPS, M.CALVES),
                LEG_PRESS,
                LEG_EXTENSION,
                CALF,
            ),
            _day(
                "Shoulders + Traps",
                "سرشانه + کول",
                (M.SHOULDERS, M.TRAPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                REAR_DELT,
                SHRUG,
            ),
            _day("Arms", "بازو", (M.BICEPS, M.TRICEPS), BICEPS, HAMMER_CURL, TRICEPS, PUSH_DOWN),
            _day(
                "Hamstrings + Glutes",
                "همسترینگ + باسن",
                (M.HAMSTRINGS, M.GLUTES),
                RDL,
                LEG_CURL,
                GLUTE_BRIDGE,
                LUNGE,
            ),
        ),
        _template(
            "six-day-chest-priority",
            "Six-Day Chest Priority",
            "تأکید سینه شش روزه",
            "A specialization block with two chest exposures and a separate "
            "calves-and-core session.",
            "دورهٔ تخصصی با دو مواجههٔ سینه و یک جلسهٔ جداگانهٔ ساق و میان‌تنه.",
            6,
            Level.ADVANCED,
            (Tag.BODY_PART_ROTATION, Tag.CHEST_PRIORITY, Tag.SPECIALIZATION),
            (Method.STANDARD,),
            _day("Chest Heavy", "سینه سنگین", (M.CHEST,), CHEST, INCLINE_CHEST, CABLE_FLY),
            _day(
                "Back + Biceps",
                "زیربغل + جلو بازو",
                (M.BACK, M.BICEPS),
                BACK_ROW,
                LAT_PULLDOWN,
                BICEPS,
            ),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                LEG_PRESS,
                RDL,
                LEG_EXTENSION,
                LEG_CURL,
            ),
            _day("Chest Volume", "سینه حجمی", (M.CHEST,), INCLINE_CHEST, CABLE_FLY, CHEST),
            _day(
                "Shoulders + Triceps",
                "سرشانه + پشت بازو",
                (M.SHOULDERS, M.TRICEPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                TRICEPS,
            ),
            _day(
                "Calves + Core",
                "ساق + میان‌تنه",
                (M.CALVES, M.ABS),
                CALF,
                SEATED_CALF_RAISE,
                CORE,
                SIDE_PLANK,
            ),
        ),
        _template(
            "six-day-back-priority",
            "Six-Day Back Priority",
            "تأکید زیربغل شش روزه",
            "A specialization block with two back exposures and a separate "
            "calves-and-core session.",
            "دورهٔ تخصصی با دو مواجههٔ زیربغل و یک جلسهٔ جداگانهٔ ساق و میان‌تنه.",
            6,
            Level.ADVANCED,
            (Tag.BODY_PART_ROTATION, Tag.BACK_PRIORITY, Tag.SPECIALIZATION),
            (Method.STANDARD,),
            _day("Back Width", "عرض زیربغل", (M.BACK,), LAT_PULLDOWN, CABLE_PULLDOWN, BACK_ROW),
            _day(
                "Chest + Triceps",
                "سینه + پشت بازو",
                (M.CHEST, M.TRICEPS),
                CHEST,
                INCLINE_CHEST,
                TRICEPS,
            ),
            _day(
                "Legs",
                "پا",
                (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                SQUAT,
                RDL,
                LEG_EXTENSION,
                LEG_CURL,
            ),
            _day(
                "Back Thickness", "ضخامت زیربغل", (M.BACK,), BACK_ROW, LAT_PULLDOWN, CABLE_PULLDOWN
            ),
            _day(
                "Shoulders + Biceps",
                "سرشانه + جلو بازو",
                (M.SHOULDERS, M.BICEPS),
                SHOULDER_PRESS,
                LATERAL_RAISE,
                BICEPS,
            ),
            _day(
                "Calves + Core",
                "ساق + میان‌تنه",
                (M.CALVES, M.ABS),
                CALF,
                SEATED_CALF_RAISE,
                CORE,
                SIDE_PLANK,
            ),
        ),
        # ── STRENGTH TEMPLATES ────────────────────────────────────────────────
        _template(
            "two-day-full-body-strength-beginner",
            "Two-Day Full Body Strength",
            "قدرت تمام‌بدن دو روزه",
            "Alternating A/B full-body sessions built around barbell compound lifts for "
            "a beginner developing foundational strength.",
            "جلسات A/B متناوب با تمرکز بر حرکات مرکب هالتری برای مبتدی که قدرت پایه را "
            "توسعه می‌دهد.",
            2,
            Level.BEGINNER,
            (Tag.FULL_BODY, Tag.COMPOUND_FOCUS, Tag.STRENGTH_BIAS),
            (Method.STANDARD,),
                _day(
                    "Full Body A",
                    "تمام‌بدن A",
                    (M.QUADRICEPS, M.CHEST, M.BACK),
                    _slot(
                        "barbell-back-squat",
                        (M.QUADRICEPS,),
                        P.SQUAT,
                        sets=3,
                        reps=(5, 8),
                        rest=180,
                    ),
                    _slot(
                        "barbell-bench-press",
                        (M.CHEST,),
                        P.HORIZONTAL_PUSH,
                        sets=3,
                        reps=(5, 8),
                        rest=180,
                    ),
                    _slot(
                        "barbell-bent-over-row",
                        (M.BACK,),
                        P.HORIZONTAL_PULL,
                        sets=3,
                        reps=(5, 8),
                        rest=150,
                    ),
                    CORE,
                ),
                _day(
                    "Full Body B",
                    "تمام‌بدن B",
                    (M.HAMSTRINGS, M.CHEST, M.BACK),
                    _slot(
                        "goblet-squat",
                        (M.QUADRICEPS,),
                        P.SQUAT,
                        sets=3,
                        reps=(6, 10),
                        rest=150,
                    ),
                    _slot(
                        "barbell-bench-press",
                        (M.CHEST,),
                        P.HORIZONTAL_PUSH,
                        sets=3,
                        reps=(5, 8),
                        rest=180,
                    ),
                    _slot(
                        "lat-pulldown",
                        (M.BACK,),
                        P.VERTICAL_PULL,
                        sets=3,
                        reps=(6, 10),
                        rest=120,
                    ),
                    _slot(
                        "romanian-deadlift",
                        (M.HAMSTRINGS, M.GLUTES),
                        P.HIP_HINGE,
                        sets=3,
                        reps=(6, 10),
                        rest=150,
                    ),
                ),
            fitness_goal=FitnessGoal.STRENGTH,
        ),
        _template(
            "three-day-full-body-strength-beginner",
            "Three-Day Full Body Strength",
            "قدرت تمام‌بدن سه روزه",
            "Three alternating full-body sessions centred on squat, press, and pull "
            "patterns for a beginner building linear strength.",
            "سه جلسهٔ متناوب تمام‌بدن بر پایهٔ الگوهای اسکوات، پرس و کشش برای مبتدی "
            "که قدرت خطی می‌سازد.",
            3,
            Level.BEGINNER,
            (Tag.FULL_BODY, Tag.COMPOUND_FOCUS, Tag.STRENGTH_BIAS),
            (Method.STANDARD,),
                _day(
                    "Full Body A",
                    "تمام‌بدن A",
                    (M.QUADRICEPS, M.CHEST, M.BACK),
                    _slot(
                        "barbell-back-squat",
                        (M.QUADRICEPS,),
                        P.SQUAT,
                        sets=3,
                        reps=(5, 8),
                        rest=180,
                    ),
                    _slot(
                        "barbell-bench-press",
                        (M.CHEST,),
                        P.HORIZONTAL_PUSH,
                        sets=3,
                        reps=(5, 8),
                        rest=180,
                    ),
                    _slot(
                        "barbell-bent-over-row",
                        (M.BACK,),
                        P.HORIZONTAL_PULL,
                        sets=3,
                        reps=(5, 8),
                        rest=150,
                    ),
                    CORE,
                ),
                _day(
                    "Full Body B",
                    "تمام‌بدن B",
                    (M.QUADRICEPS, M.SHOULDERS, M.BACK),
                    _slot(
                        "barbell-back-squat",
                        (M.QUADRICEPS,),
                        P.SQUAT,
                        sets=3,
                        reps=(5, 8),
                        rest=180,
                    ),
                    _slot(
                        "smith-machine-shoulder-press",
                        (M.SHOULDERS,),
                        P.VERTICAL_PUSH,
                        sets=3,
                        reps=(5, 8),
                        rest=180,
                    ),
                    _slot(
                        "lat-pulldown",
                        (M.BACK,),
                        P.VERTICAL_PULL,
                        sets=3,
                        reps=(6, 10),
                        rest=120,
                    ),
                    _slot(
                        "romanian-deadlift",
                        (M.HAMSTRINGS, M.GLUTES),
                        P.HIP_HINGE,
                        sets=3,
                        reps=(6, 10),
                        rest=150,
                    ),
                ),
                _day(
                    "Full Body C",
                    "تمام‌بدن C",
                    (M.QUADRICEPS, M.CHEST, M.BACK),
                    _slot(
                        "barbell-back-squat",
                        (M.QUADRICEPS,),
                        P.SQUAT,
                        sets=3,
                        reps=(5, 8),
                        rest=180,
                    ),
                    _slot(
                        "barbell-bench-press",
                        (M.CHEST,),
                        P.HORIZONTAL_PUSH,
                        sets=3,
                        reps=(5, 8),
                        rest=180,
                    ),
                    _slot(
                        "barbell-bent-over-row",
                        (M.BACK,),
                        P.HORIZONTAL_PULL,
                        sets=3,
                        reps=(5, 8),
                        rest=150,
                    ),
                    CORE,
                ),
            fitness_goal=FitnessGoal.STRENGTH,
        ),
        _template(
            "three-day-full-body-strength-intermediate",
            "Three-Day Full Body Strength",
            "قدرت تمام‌بدن سه روزه - میانی",
            "Three full-body sessions with heavy compound primaries and moderate-rep "
            "accessories for an intermediate lifter.",
            "سه جلسهٔ تمام‌بدن با حرکات مرکب سنگین اصلی و لوازم جانبی با تکرار متوسط "
            "برای ورزشکار میانی.",
            3,
            Level.INTERMEDIATE,
            (Tag.FULL_BODY, Tag.COMPOUND_FOCUS, Tag.STRENGTH_BIAS),
            (Method.STANDARD,),
                _day(
                    "Full Body A",
                    "تمام‌بدن A",
                    (M.QUADRICEPS, M.CHEST, M.BACK),
                    _slot(
                        "barbell-back-squat",
                        (M.QUADRICEPS,),
                        P.SQUAT,
                        sets=4,
                        reps=(4, 6),
                        rest=180,
                    ),
                    _slot(
                        "barbell-bench-press",
                        (M.CHEST,),
                        P.HORIZONTAL_PUSH,
                        sets=4,
                        reps=(4, 6),
                        rest=180,
                    ),
                    _slot(
                        "barbell-bent-over-row",
                        (M.BACK,),
                        P.HORIZONTAL_PULL,
                        sets=4,
                        reps=(4, 6),
                        rest=150,
                    ),
                    BICEPS,
                    CORE,
                ),
                _day(
                    "Full Body B",
                    "تمام‌بدن B",
                    (M.HAMSTRINGS, M.SHOULDERS, M.BACK),
                    _slot(
                        "romanian-deadlift",
                        (M.HAMSTRINGS, M.GLUTES),
                        P.HIP_HINGE,
                        sets=4,
                        reps=(4, 6),
                        rest=180,
                    ),
                    _slot(
                        "smith-machine-shoulder-press",
                        (M.SHOULDERS,),
                        P.VERTICAL_PUSH,
                        sets=4,
                        reps=(4, 6),
                        rest=180,
                    ),
                    _slot(
                        "lat-pulldown",
                        (M.BACK,),
                        P.VERTICAL_PULL,
                        sets=3,
                        reps=(6, 10),
                        rest=120,
                    ),
                    TRICEPS,
                    LEG_EXTENSION,
                ),
                _day(
                    "Full Body C",
                    "تمام‌بدن C",
                    (M.QUADRICEPS, M.CHEST, M.BACK),
                    _slot(
                        "barbell-back-squat",
                        (M.QUADRICEPS,),
                        P.SQUAT,
                        sets=4,
                        reps=(4, 6),
                        rest=180,
                    ),
                    _slot(
                        "incline-dumbbell-bench-press",
                        (M.CHEST,),
                        P.HORIZONTAL_PUSH,
                        sets=3,
                        reps=(6, 10),
                        rest=150,
                    ),
                    _slot(
                        "barbell-bent-over-row",
                        (M.BACK,),
                        P.HORIZONTAL_PULL,
                        sets=4,
                        reps=(4, 6),
                        rest=150,
                    ),
                    LATERAL_RAISE,
                    CORE,
                ),
            fitness_goal=FitnessGoal.STRENGTH,
        ),
        _template(
            "four-day-upper-lower-strength-intermediate",
            "Four-Day Upper/Lower Strength",
            "قدرت بالاتنه/پایین‌تنه چهار روزه",
            "Classic upper/lower split with dedicated power and strength days per body "
            "region for an intermediate lifter.",
            "تمرین کلاسیک بالاتنه/پایین‌تنه با روزهای اختصاصی قدرت برای ورزشکار میانی.",
            4,
            Level.INTERMEDIATE,
            (Tag.UPPER_LOWER, Tag.COMPOUND_FOCUS, Tag.STRENGTH_BIAS),
            (Method.STANDARD,),
                _day(
                    "Lower Power",
                    "قدرت پایین‌تنه",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                    _slot(
                        "barbell-back-squat",
                        (M.QUADRICEPS,),
                        P.SQUAT,
                        sets=4,
                        reps=(3, 6),
                        rest=180,
                    ),
                    _slot(
                        "romanian-deadlift",
                        (M.HAMSTRINGS, M.GLUTES),
                        P.HIP_HINGE,
                        sets=3,
                        reps=(5, 8),
                        rest=150,
                    ),
                    LEG_PRESS,
                    LEG_CURL,
                ),
                _day(
                    "Upper Power",
                    "قدرت بالاتنه",
                    (M.CHEST, M.BACK, M.SHOULDERS),
                    _slot(
                        "barbell-bench-press",
                        (M.CHEST,),
                        P.HORIZONTAL_PUSH,
                        sets=4,
                        reps=(3, 6),
                        rest=180,
                    ),
                    _slot(
                        "barbell-bent-over-row",
                        (M.BACK,),
                        P.HORIZONTAL_PULL,
                        sets=4,
                        reps=(3, 6),
                        rest=180,
                    ),
                    _slot(
                        "smith-machine-shoulder-press",
                        (M.SHOULDERS,),
                        P.VERTICAL_PUSH,
                        sets=3,
                        reps=(5, 8),
                        rest=150,
                    ),
                    LAT_PULLDOWN,
                ),
                _day(
                    "Lower Hypertrophy",
                    "هایپرتروفی پایین‌تنه",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                    LEG_PRESS,
                    _slot(
                        "romanian-deadlift",
                        (M.HAMSTRINGS, M.GLUTES),
                        P.HIP_HINGE,
                        sets=3,
                        reps=(8, 12),
                        rest=120,
                    ),
                    LEG_EXTENSION,
                    LEG_CURL,
                    CALF,
                ),
                _day(
                    "Upper Hypertrophy",
                    "هایپرتروفی بالاتنه",
                    (M.CHEST, M.BACK, M.SHOULDERS),
                    _slot(
                        "incline-dumbbell-bench-press",
                        (M.CHEST,),
                        P.HORIZONTAL_PUSH,
                        sets=3,
                        reps=(8, 12),
                        rest=120,
                    ),
                    LAT_PULLDOWN,
                    LATERAL_RAISE,
                    BICEPS,
                    TRICEPS,
                ),
            fitness_goal=FitnessGoal.STRENGTH,
        ),
        _template(
            "four-day-upper-lower-strength-advanced",
            "Four-Day Upper/Lower Strength — Advanced",
            "قدرت بالاتنه/پایین‌تنه چهار روزه - پیشرفته",
            "Advanced power/hypertrophy split with heavy barbell primaries and targeted "
            "accessory work.",
            "تمرین قدرت/هایپرتروفی پیشرفته با حرکات مرکب هالتری سنگین و لوازم جانبی هدفمند.",
            4,
            Level.ADVANCED,
            (Tag.UPPER_LOWER, Tag.COMPOUND_FOCUS, Tag.STRENGTH_BIAS),
            (Method.STANDARD,),
                _day(
                    "Lower Power",
                    "قدرت پایین‌تنه",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                    _slot(
                        "barbell-back-squat",
                        (M.QUADRICEPS,),
                        P.SQUAT,
                        sets=5,
                        reps=(3, 5),
                        rest=180,
                    ),
                    _slot(
                        "romanian-deadlift",
                        (M.HAMSTRINGS, M.GLUTES),
                        P.HIP_HINGE,
                        sets=4,
                        reps=(4, 6),
                        rest=180,
                    ),
                    LEG_PRESS,
                    LEG_CURL,
                    CALF,
                ),
                _day(
                    "Upper Power",
                    "قدرت بالاتنه",
                    (M.CHEST, M.BACK, M.SHOULDERS),
                    _slot(
                        "barbell-bench-press",
                        (M.CHEST,),
                        P.HORIZONTAL_PUSH,
                        sets=5,
                        reps=(3, 5),
                        rest=180,
                    ),
                    _slot(
                        "barbell-bent-over-row",
                        (M.BACK,),
                        P.HORIZONTAL_PULL,
                        sets=5,
                        reps=(3, 5),
                        rest=180,
                    ),
                    _slot(
                        "smith-machine-shoulder-press",
                        (M.SHOULDERS,),
                        P.VERTICAL_PUSH,
                        sets=3,
                        reps=(5, 8),
                        rest=150,
                    ),
                    LAT_PULLDOWN,
                ),
                _day(
                    "Lower Volume",
                    "حجم پایین‌تنه",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                    _slot(
                        "barbell-back-squat",
                        (M.QUADRICEPS,),
                        P.SQUAT,
                        sets=4,
                        reps=(6, 10),
                        rest=150,
                    ),
                    _slot(
                        "romanian-deadlift",
                        (M.HAMSTRINGS, M.GLUTES),
                        P.HIP_HINGE,
                        sets=3,
                        reps=(8, 12),
                        rest=120,
                    ),
                    LEG_EXTENSION,
                    LEG_CURL,
                ),
                _day(
                    "Upper Volume",
                    "حجم بالاتنه",
                    (M.CHEST, M.BACK, M.SHOULDERS),
                    _slot(
                        "incline-dumbbell-bench-press",
                        (M.CHEST,),
                        P.HORIZONTAL_PUSH,
                        sets=4,
                        reps=(6, 10),
                        rest=120,
                    ),
                    BACK_ROW,
                    LAT_PULLDOWN,
                    LATERAL_RAISE,
                    BICEPS,
                    TRICEPS,
                ),
            fitness_goal=FitnessGoal.STRENGTH,
        ),
        _template(
            "five-day-strength-intermediate",
            "Five-Day Strength Program",
            "برنامهٔ قدرت پنج روزه - میانی",
            "Five dedicated sessions with one primary compound per session and supporting "
            "accessory work for an intermediate strength athlete.",
            "پنج جلسهٔ اختصاصی با یک حرکت مرکب اصلی در هر جلسه و لوازم جانبی مکمل "
            "برای ورزشکار قدرتی میانی.",
            5,
            Level.INTERMEDIATE,
            (Tag.UPPER_LOWER, Tag.PUSH_PULL_LEGS, Tag.COMPOUND_FOCUS, Tag.STRENGTH_BIAS),
            (Method.STANDARD,),
                _day(
                    "Squat Day",
                    "روز اسکوات",
                    (M.QUADRICEPS, M.GLUTES),
                    _slot(
                        "barbell-back-squat",
                        (M.QUADRICEPS,),
                        P.SQUAT,
                        sets=4,
                        reps=(4, 6),
                        rest=180,
                    ),
                    LEG_PRESS,
                    LEG_EXTENSION,
                    LEG_CURL,
                    CORE,
                ),
                _day(
                    "Bench Day",
                    "روز پرس",
                    (M.CHEST, M.TRICEPS),
                    _slot(
                        "barbell-bench-press",
                        (M.CHEST,),
                        P.HORIZONTAL_PUSH,
                        sets=4,
                        reps=(4, 6),
                        rest=180,
                    ),
                    INCLINE_CHEST,
                    TRICEPS,
                    PUSH_DOWN,
                    LATERAL_RAISE,
                ),
                _day(
                    "Deadlift Day",
                    "روز ددلیفت",
                    (M.HAMSTRINGS, M.BACK, M.GLUTES),
                    _slot(
                        "romanian-deadlift",
                        (M.HAMSTRINGS, M.GLUTES),
                        P.HIP_HINGE,
                        sets=4,
                        reps=(4, 6),
                        rest=180,
                    ),
                    BACK_ROW,
                    LAT_PULLDOWN,
                    GLUTE_BRIDGE,
                ),
                _day(
                    "Overhead Press Day",
                    "روز پرس سرشانه",
                    (M.SHOULDERS, M.TRICEPS),
                    _slot(
                        "smith-machine-shoulder-press",
                        (M.SHOULDERS,),
                        P.VERTICAL_PUSH,
                        sets=4,
                        reps=(4, 6),
                        rest=180,
                    ),
                    LATERAL_RAISE,
                    REAR_DELT,
                    TRICEPS,
                    BICEPS,
                ),
                _day(
                    "Upper Accessory",
                    "لوازم جانبی بالاتنه",
                    (M.BACK, M.BICEPS, M.CHEST),
                    INCLINE_CHEST,
                    LAT_PULLDOWN,
                    CABLE_PULLDOWN,
                    BICEPS,
                    HAMMER_CURL,
                ),
            fitness_goal=FitnessGoal.STRENGTH,
        ),
        _template(
            "five-day-strength-advanced",
            "Five-Day Strength Program — Advanced",
            "برنامهٔ قدرت پنج روزه - پیشرفته",
            "Advanced five-day programme with maximal compound loading and targeted "
            "accessory blocks.",
            "برنامهٔ پنج روزهٔ پیشرفته با بارگذاری مرکب حداکثری و بلوک‌های جانبی هدفمند.",
            5,
            Level.ADVANCED,
            (Tag.UPPER_LOWER, Tag.PUSH_PULL_LEGS, Tag.COMPOUND_FOCUS, Tag.STRENGTH_BIAS),
            (Method.STANDARD,),
                _day(
                    "Squat — Heavy",
                    "اسکوات سنگین",
                    (M.QUADRICEPS, M.GLUTES),
                    _slot(
                        "barbell-back-squat",
                        (M.QUADRICEPS,),
                        P.SQUAT,
                        sets=5,
                        reps=(3, 5),
                        rest=180,
                    ),
                    LEG_PRESS,
                    LEG_EXTENSION,
                    CALF,
                ),
                _day(
                    "Bench — Heavy",
                    "پرس سنگین",
                    (M.CHEST, M.TRICEPS, M.SHOULDERS),
                    _slot(
                        "barbell-bench-press",
                        (M.CHEST,),
                        P.HORIZONTAL_PUSH,
                        sets=5,
                        reps=(3, 5),
                        rest=180,
                    ),
                    INCLINE_CHEST,
                    PUSH_DOWN,
                    LATERAL_RAISE,
                ),
                _day(
                    "Deadlift — Heavy",
                    "ددلیفت سنگین",
                    (M.HAMSTRINGS, M.BACK, M.GLUTES),
                    _slot(
                        "romanian-deadlift",
                        (M.HAMSTRINGS, M.GLUTES),
                        P.HIP_HINGE,
                        sets=5,
                        reps=(3, 5),
                        rest=180,
                    ),
                    BACK_ROW,
                    LAT_PULLDOWN,
                    CORE,
                ),
                _day(
                    "Press + Pull Accessory",
                    "لوازم پرس + کشش",
                    (M.SHOULDERS, M.BACK, M.BICEPS),
                    _slot(
                        "smith-machine-shoulder-press",
                        (M.SHOULDERS,),
                        P.VERTICAL_PUSH,
                        sets=4,
                        reps=(5, 8),
                        rest=150,
                    ),
                    LAT_PULLDOWN,
                    REAR_DELT,
                    BICEPS,
                    TRICEPS,
                ),
                _day(
                    "Leg Accessory + Core",
                    "لوازم پا + میان‌تنه",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.ABS),
                    LEG_PRESS,
                    LEG_CURL,
                    LUNGE,
                    CORE,
                    SIDE_PLANK,
                ),
            fitness_goal=FitnessGoal.STRENGTH,
        ),
        _template(
            "six-day-push-pull-legs-strength",
            "Six-Day PPL Strength",
            "قدرت پوش‌پول‌لگ شش روزه",
            "Six-day push/pull/legs rotation with weekly compound primaries for an "
            "advanced strength athlete.",
            "چرخش پوش/پول/لگ شش روزه با حرکات مرکب اصلی هفتگی برای ورزشکار قدرتی پیشرفته.",
            6,
            Level.ADVANCED,
            (Tag.PUSH_PULL_LEGS, Tag.COMPOUND_FOCUS, Tag.STRENGTH_BIAS),
            (Method.STANDARD,),
                _day(
                    "Push — Heavy",
                    "پوش سنگین",
                    (M.CHEST, M.SHOULDERS, M.TRICEPS),
                    _slot(
                        "barbell-bench-press",
                        (M.CHEST,),
                        P.HORIZONTAL_PUSH,
                        sets=5,
                        reps=(3, 5),
                        rest=180,
                    ),
                    _slot(
                        "smith-machine-shoulder-press",
                        (M.SHOULDERS,),
                        P.VERTICAL_PUSH,
                        sets=4,
                        reps=(5, 8),
                        rest=150,
                    ),
                    TRICEPS,
                    LATERAL_RAISE,
                ),
                _day(
                    "Pull — Heavy",
                    "پول سنگین",
                    (M.BACK, M.BICEPS),
                    _slot(
                        "barbell-bent-over-row",
                        (M.BACK,),
                        P.HORIZONTAL_PULL,
                        sets=5,
                        reps=(3, 5),
                        rest=180,
                    ),
                    LAT_PULLDOWN,
                    BICEPS,
                    REAR_DELT,
                ),
                _day(
                    "Legs — Heavy",
                    "پا سنگین",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                    _slot(
                        "barbell-back-squat",
                        (M.QUADRICEPS,),
                        P.SQUAT,
                        sets=5,
                        reps=(3, 5),
                        rest=180,
                    ),
                    _slot(
                        "romanian-deadlift",
                        (M.HAMSTRINGS, M.GLUTES),
                        P.HIP_HINGE,
                        sets=4,
                        reps=(4, 6),
                        rest=150,
                    ),
                    CALF,
                ),
                _day(
                    "Push — Volume",
                    "پوش حجم",
                    (M.CHEST, M.SHOULDERS, M.TRICEPS),
                    INCLINE_CHEST,
                    CABLE_FLY,
                    LATERAL_RAISE,
                    PUSH_DOWN,
                    TRICEPS,
                ),
                _day(
                    "Pull — Volume",
                    "پول حجم",
                    (M.BACK, M.BICEPS),
                    BACK_ROW,
                    CABLE_PULLDOWN,
                    HAMMER_CURL,
                    BICEPS,
                ),
                _day(
                    "Legs — Volume",
                    "پا حجم",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.ABS),
                    LEG_PRESS,
                    LEG_EXTENSION,
                    LEG_CURL,
                    CORE,
                    SIDE_PLANK,
                ),
            fitness_goal=FitnessGoal.STRENGTH,
        ),
        # ── FAT LOSS TEMPLATES ────────────────────────────────────────────────
        _template(
            "two-day-full-body-fat-loss-beginner",
            "Two-Day Full Body Fat Loss",
            "چربی‌سوزی تمام‌بدن دو روزه",
            "Two full-body resistance sessions per week to preserve muscle while in a "
            "calorie deficit for a beginner.",
            "دو جلسهٔ مقاومتی تمام‌بدن در هفته برای حفظ عضله در کمبود کالری برای مبتدی.",
            2,
            Level.BEGINNER,
            (Tag.FULL_BODY, Tag.BALANCED),
            (Method.STANDARD,),
                _day(
                    "Full Body A",
                    "تمام‌بدن A",
                    (M.CHEST, M.BACK, M.QUADRICEPS, M.GLUTES),
                    CHEST,
                    BACK_ROW,
                    SQUAT,
                    GLUTE_BRIDGE,
                    CORE,
                ),
                _day(
                    "Full Body B",
                    "تمام‌بدن B",
                    (M.CHEST, M.BACK, M.HAMSTRINGS, M.GLUTES),
                    INCLINE_CHEST,
                    LAT_PULLDOWN,
                    LUNGE,
                    RDL,
                    CORE,
                ),
            fitness_goal=FitnessGoal.FAT_LOSS,
        ),
        _template(
            "three-day-full-body-fat-loss-beginner",
            "Three-Day Full Body Fat Loss",
            "چربی‌سوزی تمام‌بدن سه روزه",
            "Three full-body sessions per week designed to maintain lean mass during a "
            "fat loss phase for a beginner.",
            "سه جلسهٔ تمام‌بدن در هفته برای حفظ توده‌ٔ عضلانی در فاز چربی‌سوزی برای مبتدی.",
            3,
            Level.BEGINNER,
            (Tag.FULL_BODY, Tag.BALANCED),
            (Method.STANDARD,),
                _day(
                    "Full Body A",
                    "تمام‌بدن A",
                    (M.CHEST, M.BACK, M.QUADRICEPS, M.GLUTES),
                    CHEST,
                    BACK_ROW,
                    SQUAT,
                    GLUTE_BRIDGE,
                    CORE,
                ),
                _day(
                    "Full Body B",
                    "تمام‌بدن B",
                    (M.CHEST, M.BACK, M.HAMSTRINGS, M.GLUTES),
                    INCLINE_CHEST,
                    LAT_PULLDOWN,
                    LUNGE,
                    RDL,
                ),
                _day(
                    "Full Body C",
                    "تمام‌بدن C",
                    (M.SHOULDERS, M.BACK, M.QUADRICEPS, M.ABS),
                    SHOULDER_PRESS,
                    BACK_ROW,
                    LEG_PRESS,
                    CORE,
                    SIDE_PLANK,
                ),
            fitness_goal=FitnessGoal.FAT_LOSS,
        ),
        _template(
            "three-day-full-body-fat-loss-intermediate",
            "Three-Day Full Body Fat Loss",
            "چربی‌سوزی تمام‌بدن سه روزه - میانی",
            "Three full-body sessions targeting major compound patterns with brief rest "
            "for an intermediate lifter in a fat loss phase.",
            "سه جلسهٔ تمام‌بدن با تمرکز بر الگوهای مرکب اصلی و استراحت کوتاه برای "
            "ورزشکار میانی در فاز چربی‌سوزی.",
            3,
            Level.INTERMEDIATE,
            (Tag.FULL_BODY, Tag.BALANCED),
            (Method.STANDARD,),
                _day(
                    "Full Body A",
                    "تمام‌بدن A",
                    (M.CHEST, M.BACK, M.QUADRICEPS, M.GLUTES),
                    CHEST,
                    BACK_ROW,
                    SQUAT,
                    GLUTE_BRIDGE,
                    CORE,
                ),
                _day(
                    "Full Body B",
                    "تمام‌بدن B",
                    (M.CHEST, M.BACK, M.HAMSTRINGS, M.GLUTES),
                    INCLINE_CHEST,
                    LAT_PULLDOWN,
                    LUNGE,
                    RDL,
                    LATERAL_RAISE,
                ),
                _day(
                    "Full Body C",
                    "تمام‌بدن C",
                    (M.SHOULDERS, M.BACK, M.QUADRICEPS, M.ABS),
                    SHOULDER_PRESS,
                    BACK_ROW,
                    LEG_PRESS,
                    LEG_EXTENSION,
                    CORE,
                ),
            fitness_goal=FitnessGoal.FAT_LOSS,
        ),
        _template(
            "four-day-upper-lower-fat-loss-intermediate",
            "Four-Day Upper/Lower Fat Loss",
            "چربی‌سوزی بالاتنه/پایین‌تنه چهار روزه",
            "Upper/lower split with higher-rep, shorter-rest training to maximise "
            "metabolic demand for an intermediate lifter in fat loss.",
            "تمرین بالاتنه/پایین‌تنه با تکرار بالا و استراحت کوتاه برای افزایش مصرف "
            "متابولیک ورزشکار میانی در فاز چربی‌سوزی.",
            4,
            Level.INTERMEDIATE,
            (Tag.UPPER_LOWER, Tag.BALANCED),
            (Method.STANDARD,),
                _day(
                    "Upper A",
                    "بالاتنه A",
                    (M.CHEST, M.BACK, M.SHOULDERS),
                    CHEST,
                    BACK_ROW,
                    SHOULDER_PRESS,
                    LATERAL_RAISE,
                    CORE,
                ),
                _day(
                    "Lower A",
                    "پایین‌تنه A",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                    SQUAT,
                    RDL,
                    LEG_EXTENSION,
                    CALF,
                ),
                _day(
                    "Upper B",
                    "بالاتنه B",
                    (M.CHEST, M.BACK, M.BICEPS, M.TRICEPS),
                    INCLINE_CHEST,
                    LAT_PULLDOWN,
                    BICEPS,
                    TRICEPS,
                ),
                _day(
                    "Lower B",
                    "پایین‌تنه B",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.ABS),
                    LEG_PRESS,
                    LUNGE,
                    LEG_CURL,
                    CORE,
                    SIDE_PLANK,
                ),
            fitness_goal=FitnessGoal.FAT_LOSS,
        ),
        _template(
            "four-day-upper-lower-fat-loss-advanced",
            "Four-Day Upper/Lower Fat Loss — Advanced",
            "چربی‌سوزی بالاتنه/پایین‌تنه چهار روزه - پیشرفته",
            "Compound-focused upper/lower split with brief rest to maximise caloric "
            "expenditure for an advanced lifter.",
            "تمرین مرکب بالاتنه/پایین‌تنه با استراحت کوتاه برای افزایش کالری سوزی "
            "ورزشکار پیشرفته در فاز چربی‌سوزی.",
            4,
            Level.ADVANCED,
            (Tag.UPPER_LOWER, Tag.BALANCED),
            (Method.STANDARD,),
                _day(
                    "Upper A",
                    "بالاتنه A",
                    (M.CHEST, M.BACK, M.SHOULDERS),
                    BARBELL_BENCH,
                    BACK_ROW,
                    SHOULDER_PRESS,
                    LAT_PULLDOWN,
                    LATERAL_RAISE,
                ),
                _day(
                    "Lower A",
                    "پایین‌تنه A",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                    SQUAT,
                    BARBELL_STRAIGHT_LEG_DEADLIFT,
                    LEG_EXTENSION,
                    LEG_CURL,
                    CALF,
                ),
                _day(
                    "Upper B",
                    "بالاتنه B",
                    (M.CHEST, M.BACK, M.BICEPS, M.TRICEPS),
                    INCLINE_CHEST,
                    LAT_PULLDOWN,
                    CABLE_FLY,
                    BICEPS,
                    TRICEPS,
                ),
                _day(
                    "Lower B",
                    "پایین‌تنه B",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.ABS),
                    LEG_PRESS,
                    RDL,
                    LUNGE,
                    CORE,
                    SIDE_PLANK,
                ),
            fitness_goal=FitnessGoal.FAT_LOSS,
        ),
        _template(
            "five-day-ppl-fat-loss-intermediate",
            "Five-Day PPL Fat Loss",
            "چربی‌سوزی پوش‌پول‌لگ پنج روزه",
            "Push/pull/legs split plus two extra upper sessions for maximum weekly "
            "frequency and metabolic stimulus.",
            "تمرین پوش/پول/لگ با دو جلسهٔ اضافی بالاتنه برای بیشترین تکرار هفتگی و محرک متابولیک.",
            5,
            Level.INTERMEDIATE,
            (Tag.PUSH_PULL_LEGS, Tag.BALANCED),
            (Method.STANDARD,),
                _day(
                    "Push",
                    "پوش",
                    (M.CHEST, M.SHOULDERS, M.TRICEPS),
                    CHEST,
                    SHOULDER_PRESS,
                    TRICEPS,
                    LATERAL_RAISE,
                ),
                _day(
                    "Pull",
                    "پول",
                    (M.BACK, M.BICEPS),
                    BACK_ROW,
                    LAT_PULLDOWN,
                    BICEPS,
                    REAR_DELT,
                ),
                _day(
                    "Legs",
                    "پا",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.ABS),
                    SQUAT,
                    RDL,
                    LEG_EXTENSION,
                    CALF,
                    CORE,
                ),
                _day(
                    "Upper A",
                    "بالاتنه A",
                    (M.CHEST, M.BACK, M.SHOULDERS),
                    INCLINE_CHEST,
                    BACK_ROW,
                    LATERAL_RAISE,
                ),
                _day(
                    "Upper B",
                    "بالاتنه B",
                    (M.BACK, M.BICEPS, M.TRICEPS),
                    LAT_PULLDOWN,
                    CABLE_FLY,
                    HAMMER_CURL,
                    PUSH_DOWN,
                ),
            fitness_goal=FitnessGoal.FAT_LOSS,
        ),
        _template(
            "five-day-ppl-fat-loss-advanced",
            "Five-Day PPL Fat Loss — Advanced",
            "چربی‌سوزی پوش‌پول‌لگ پنج روزه - پیشرفته",
            "Advanced five-day push/pull/legs with two full-body finisher sessions for "
            "maximum weekly caloric expenditure.",
            "پنج روز پوش/پول/لگ پیشرفته با دو جلسهٔ تمام‌بدن برای حداکثر کالری‌سوزی هفتگی.",
            5,
            Level.ADVANCED,
            (Tag.PUSH_PULL_LEGS, Tag.BALANCED),
            (Method.STANDARD,),
                _day(
                    "Push",
                    "پوش",
                    (M.CHEST, M.SHOULDERS, M.TRICEPS),
                    BARBELL_BENCH,
                    INCLINE_CHEST,
                    SHOULDER_PRESS,
                    PUSH_DOWN,
                    LATERAL_RAISE,
                ),
                _day(
                    "Pull",
                    "پول",
                    (M.BACK, M.BICEPS),
                    BACK_ROW,
                    LAT_PULLDOWN,
                    CABLE_PULLDOWN,
                    BICEPS,
                    REAR_DELT,
                ),
                _day(
                    "Legs",
                    "پا",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.ABS),
                    SQUAT,
                    BARBELL_STRAIGHT_LEG_DEADLIFT,
                    LEG_EXTENSION,
                    LEG_CURL,
                    CORE,
                ),
                _day(
                    "Full Body A",
                    "تمام‌بدن A",
                    (M.CHEST, M.BACK, M.QUADRICEPS),
                    INCLINE_CHEST,
                    BACK_ROW,
                    LEG_PRESS,
                    LATERAL_RAISE,
                ),
                _day(
                    "Full Body B",
                    "تمام‌بدن B",
                    (M.HAMSTRINGS, M.BACK, M.TRICEPS, M.ABS),
                    RDL,
                    LAT_PULLDOWN,
                    TRICEPS,
                    SIDE_PLANK,
                ),
            fitness_goal=FitnessGoal.FAT_LOSS,
        ),
        _template(
            "six-day-ppl-fat-loss-advanced",
            "Six-Day PPL Fat Loss — Advanced",
            "چربی‌سوزی پوش‌پول‌لگ شش روزه - پیشرفته",
            "Six-day PPL twice with brief rest to maximise weekly training volume and "
            "metabolic stimulus during a fat loss phase.",
            "پوش/پول/لگ دوبار در هفته با استراحت کوتاه برای افزایش حجم تمرین هفتگی "
            "و محرک متابولیک در فاز چربی‌سوزی.",
            6,
            Level.ADVANCED,
            (Tag.PUSH_PULL_LEGS, Tag.BALANCED),
            (Method.STANDARD,),
                _day(
                    "Push A",
                    "پوش A",
                    (M.CHEST, M.SHOULDERS, M.TRICEPS),
                    BARBELL_BENCH,
                    SHOULDER_PRESS,
                    TRICEPS,
                    LATERAL_RAISE,
                ),
                _day(
                    "Pull A",
                    "پول A",
                    (M.BACK, M.BICEPS),
                    BACK_ROW,
                    LAT_PULLDOWN,
                    BICEPS,
                    REAR_DELT,
                ),
                _day(
                    "Legs A",
                    "پا A",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.ABS),
                    SQUAT,
                    RDL,
                    LEG_EXTENSION,
                    CORE,
                ),
                _day(
                    "Push B",
                    "پوش B",
                    (M.CHEST, M.SHOULDERS, M.TRICEPS),
                    INCLINE_CHEST,
                    CABLE_FLY,
                    LATERAL_RAISE,
                    PUSH_DOWN,
                ),
                _day(
                    "Pull B",
                    "پول B",
                    (M.BACK, M.BICEPS),
                    CABLE_PULLDOWN,
                    BACK_ROW,
                    HAMMER_CURL,
                    FACE_PULL,
                ),
                _day(
                    "Legs B",
                    "پا B",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.ABS),
                    LEG_PRESS,
                    LEG_CURL,
                    LUNGE,
                    CALF,
                    SIDE_PLANK,
                ),
            fitness_goal=FitnessGoal.FAT_LOSS,
        ),
        # ── GENERAL FITNESS / IMPROVE_FITNESS TEMPLATES ──────────────────────
        _template(
            "two-day-full-body-general-fitness-beginner",
            "Two-Day Full Body General Fitness",
            "آمادگی عمومی تمام‌بدن دو روزه",
            "Two well-rounded full-body sessions per week for a beginner building "
            "foundational fitness.",
            "دو جلسهٔ جامع تمام‌بدن در هفته برای مبتدی که آمادگی جسمانی پایه را توسعه می‌دهد.",
            2,
            Level.BEGINNER,
            (Tag.FULL_BODY, Tag.BALANCED),
            (Method.STANDARD,),
                _day(
                    "Full Body A",
                    "تمام‌بدن A",
                    (M.CHEST, M.BACK, M.QUADRICEPS, M.GLUTES),
                    CHEST,
                    BACK_ROW,
                    SQUAT,
                    GLUTE_BRIDGE,
                    CORE,
                ),
                _day(
                    "Full Body B",
                    "تمام‌بدن B",
                    (M.CHEST, M.BACK, M.HAMSTRINGS, M.GLUTES),
                    INCLINE_CHEST,
                    LAT_PULLDOWN,
                    LUNGE,
                    RDL,
                    CORE,
                ),
            fitness_goal=FitnessGoal.IMPROVE_FITNESS,
        ),
        _template(
            "three-day-full-body-general-fitness-beginner",
            "Three-Day Full Body General Fitness",
            "آمادگی عمومی تمام‌بدن سه روزه",
            "Three full-body sessions per week covering all major movement patterns for "
            "a beginner building general fitness.",
            "سه جلسهٔ تمام‌بدن در هفته با پوشش همهٔ الگوهای حرکتی اصلی برای مبتدی "
            "که آمادگی عمومی می‌سازد.",
            3,
            Level.BEGINNER,
            (Tag.FULL_BODY, Tag.BALANCED),
            (Method.STANDARD,),
                _day(
                    "Full Body A",
                    "تمام‌بدن A",
                    (M.CHEST, M.BACK, M.QUADRICEPS, M.GLUTES),
                    CHEST,
                    BACK_ROW,
                    SQUAT,
                    GLUTE_BRIDGE,
                    CORE,
                ),
                _day(
                    "Full Body B",
                    "تمام‌بدن B",
                    (M.CHEST, M.BACK, M.HAMSTRINGS, M.GLUTES),
                    INCLINE_CHEST,
                    LAT_PULLDOWN,
                    LUNGE,
                    RDL,
                ),
                _day(
                    "Full Body C",
                    "تمام‌بدن C",
                    (M.SHOULDERS, M.BACK, M.QUADRICEPS, M.ABS),
                    SHOULDER_PRESS,
                    BACK_ROW,
                    LEG_PRESS,
                    CORE,
                    SIDE_PLANK,
                ),
            fitness_goal=FitnessGoal.IMPROVE_FITNESS,
        ),
        _template(
            "three-day-full-body-general-fitness-intermediate",
            "Three-Day Full Body General Fitness",
            "آمادگی عمومی تمام‌بدن سه روزه - میانی",
            "Three full-body sessions per week for an intermediate lifter maintaining "
            "or improving overall fitness.",
            "سه جلسهٔ تمام‌بدن در هفته برای ورزشکار میانی که آمادگی کلی را حفظ یا بهبود می‌دهد.",
            3,
            Level.INTERMEDIATE,
            (Tag.FULL_BODY, Tag.BALANCED),
            (Method.STANDARD,),
                _day(
                    "Full Body A",
                    "تمام‌بدن A",
                    (M.CHEST, M.BACK, M.QUADRICEPS, M.GLUTES),
                    CHEST,
                    BACK_ROW,
                    SQUAT,
                    GLUTE_BRIDGE,
                    LATERAL_RAISE,
                ),
                _day(
                    "Full Body B",
                    "تمام‌بدن B",
                    (M.CHEST, M.BACK, M.HAMSTRINGS, M.GLUTES),
                    INCLINE_CHEST,
                    LAT_PULLDOWN,
                    LUNGE,
                    RDL,
                    BICEPS,
                ),
                _day(
                    "Full Body C",
                    "تمام‌بدن C",
                    (M.SHOULDERS, M.BACK, M.QUADRICEPS, M.ABS),
                    SHOULDER_PRESS,
                    BACK_ROW,
                    LEG_PRESS,
                    TRICEPS,
                    CORE,
                ),
            fitness_goal=FitnessGoal.IMPROVE_FITNESS,
        ),
        _template(
            "four-day-upper-lower-general-fitness-intermediate",
            "Four-Day Upper/Lower General Fitness",
            "آمادگی عمومی بالاتنه/پایین‌تنه چهار روزه",
            "Upper/lower split with balanced compound and isolation work for an "
            "intermediate lifter focused on overall fitness.",
            "تمرین بالاتنه/پایین‌تنه با کار مرکب و انزوایی متعادل برای ورزشکار میانی "
            "با تمرکز بر آمادگی کلی.",
            4,
            Level.INTERMEDIATE,
            (Tag.UPPER_LOWER, Tag.BALANCED),
            (Method.STANDARD,),
                _day(
                    "Upper A",
                    "بالاتنه A",
                    (M.CHEST, M.BACK, M.SHOULDERS),
                    CHEST,
                    BACK_ROW,
                    SHOULDER_PRESS,
                    LATERAL_RAISE,
                    CORE,
                ),
                _day(
                    "Lower A",
                    "پایین‌تنه A",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES),
                    SQUAT,
                    RDL,
                    LEG_EXTENSION,
                    CALF,
                ),
                _day(
                    "Upper B",
                    "بالاتنه B",
                    (M.CHEST, M.BACK, M.BICEPS, M.TRICEPS),
                    INCLINE_CHEST,
                    LAT_PULLDOWN,
                    BICEPS,
                    TRICEPS,
                ),
                _day(
                    "Lower B",
                    "پایین‌تنه B",
                    (M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES, M.ABS),
                    LEG_PRESS,
                    LUNGE,
                    LEG_CURL,
                    CORE,
                ),
            fitness_goal=FitnessGoal.IMPROVE_FITNESS,
        ),
    )
    if template.slug not in (RETIRED_REDUNDANT_TEMPLATE_SLUGS | RETIRED_UNSUPPORTED_TEMPLATE_SLUGS)
)
