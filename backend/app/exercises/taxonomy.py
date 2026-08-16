from dataclasses import dataclass

from app.exercises.enums import BodyRegion, MuscleFocus, MuscleGroup

MUSCLES_BY_REGION: dict[BodyRegion, frozenset[MuscleGroup]] = {
    BodyRegion.UPPER_BODY: frozenset(
        {
            MuscleGroup.CHEST,
            MuscleGroup.BACK,
            MuscleGroup.SHOULDERS,
            MuscleGroup.BICEPS,
            MuscleGroup.TRICEPS,
            MuscleGroup.TRAPS,
            MuscleGroup.FOREARMS,
            MuscleGroup.NECK,
            MuscleGroup.LOWER_BACK,
        }
    ),
    BodyRegion.LOWER_BODY: frozenset(
        {
            MuscleGroup.GLUTES,
            MuscleGroup.QUADRICEPS,
            MuscleGroup.HAMSTRINGS,
            MuscleGroup.ADDUCTORS,
            MuscleGroup.ABDUCTORS,
            MuscleGroup.LEGS,
            MuscleGroup.CALVES,
        }
    ),
    BodyRegion.CORE: frozenset(
        {
            MuscleGroup.ABS,
            MuscleGroup.OBLIQUES,
        }
    ),
}

FOCUSES_BY_MUSCLE: dict[MuscleGroup, tuple[MuscleFocus, ...]] = {
    MuscleGroup.CHEST: (
        MuscleFocus.GENERAL_CHEST,
        MuscleFocus.UPPER_CHEST,
        MuscleFocus.MID_CHEST,
        MuscleFocus.LOWER_CHEST,
    ),
    MuscleGroup.BACK: (
        MuscleFocus.GENERAL_BACK,
        MuscleFocus.LATS,
        MuscleFocus.MID_BACK_RHOMBOIDS,
        MuscleFocus.UPPER_BACK,
    ),
    MuscleGroup.SHOULDERS: (
        MuscleFocus.GENERAL_SHOULDERS,
        MuscleFocus.FRONT_DELT,
        MuscleFocus.LATERAL_DELT,
        MuscleFocus.REAR_DELT,
    ),
    MuscleGroup.BICEPS: (
        MuscleFocus.GENERAL_BICEPS,
        MuscleFocus.BICEPS_BRACHII,
        MuscleFocus.BRACHIALIS_BRACHIORADIALIS,
    ),
    MuscleGroup.TRICEPS: (
        MuscleFocus.GENERAL_TRICEPS,
        MuscleFocus.TRICEPS_LONG_HEAD,
        MuscleFocus.TRICEPS_LATERAL_MEDIAL_HEADS,
    ),
    MuscleGroup.TRAPS: (MuscleFocus.UPPER_TRAPS, MuscleFocus.MID_LOWER_TRAPS),
    MuscleGroup.FOREARMS: (
        MuscleFocus.GENERAL_FOREARMS,
        MuscleFocus.FOREARM_FLEXORS,
        MuscleFocus.FOREARM_EXTENSORS,
    ),
    MuscleGroup.NECK: (MuscleFocus.NECK_FLEXION, MuscleFocus.NECK_LATERAL_EXTENSION),
    MuscleGroup.GLUTES: (MuscleFocus.GLUTE_MAX, MuscleFocus.GLUTE_MEDIUS_MINIMUS),
    MuscleGroup.QUADRICEPS: (),
    MuscleGroup.HAMSTRINGS: (
        MuscleFocus.HAMSTRINGS_HIP_EXTENSION,
        MuscleFocus.HAMSTRINGS_KNEE_FLEXION,
    ),
    MuscleGroup.ADDUCTORS: (),
    MuscleGroup.ABDUCTORS: (),
    MuscleGroup.LEGS: (),
    MuscleGroup.CALVES: (
        MuscleFocus.GENERAL_CALVES,
        MuscleFocus.GASTROCNEMIUS,
        MuscleFocus.SOLEUS,
    ),
    MuscleGroup.ABS: (
        MuscleFocus.TRUNK_FLEXION,
        MuscleFocus.HIP_FLEXION_POSTERIOR_TILT,
        MuscleFocus.ANTI_EXTENSION,
    ),
    MuscleGroup.OBLIQUES: (
        MuscleFocus.TRUNK_ROTATION,
        MuscleFocus.LATERAL_FLEXION,
        MuscleFocus.ANTI_ROTATION,
    ),
    MuscleGroup.LOWER_BACK: (
        MuscleFocus.LUMBAR_ERECTORS,
        MuscleFocus.THORACIC_MOBILITY,
    ),
}


@dataclass(frozen=True)
class MuscleFocusCategory:
    value: MuscleFocus
    name_en: str
    name_fa: str


_FOCUS_LABELS: dict[MuscleFocus, tuple[str, str]] = {
    MuscleFocus.GENERAL_CHEST: ("General Chest", "کل سینه"),
    MuscleFocus.UPPER_CHEST: ("Upper Chest", "بالاسینه"),
    MuscleFocus.MID_CHEST: ("Mid Chest", "میان‌سینه"),
    MuscleFocus.LOWER_CHEST: ("Lower Chest", "زیرسینه"),
    MuscleFocus.GENERAL_BACK: ("General Back", "کل پشت"),
    MuscleFocus.LATS: ("Lats", "زیر بغل"),
    MuscleFocus.MID_BACK_RHOMBOIDS: ("Mid Back / Rhomboids", "میانه پشت / رومبوئید"),
    MuscleFocus.UPPER_BACK: ("Upper Back", "بالای پشت"),
    MuscleFocus.GENERAL_SHOULDERS: ("General Shoulders", "کل سرشانه"),
    MuscleFocus.FRONT_DELT: ("Front Delt", "سرشانه جلویی"),
    MuscleFocus.LATERAL_DELT: ("Lateral Delt", "سرشانه میانی"),
    MuscleFocus.REAR_DELT: ("Rear Delt", "سرشانه پشتی"),
    MuscleFocus.GENERAL_BICEPS: ("General Biceps", "کل جلو بازو"),
    MuscleFocus.BICEPS_BRACHII: ("Biceps Brachii", "دوسر بازویی"),
    MuscleFocus.BRACHIALIS_BRACHIORADIALIS: (
        "Brachialis / Brachioradialis",
        "بازویی / بازویی‌زندزبرین",
    ),
    MuscleFocus.GENERAL_TRICEPS: ("General Triceps", "کل پشت بازو"),
    MuscleFocus.TRICEPS_LONG_HEAD: ("Long Head", "سر بلند"),
    MuscleFocus.TRICEPS_LATERAL_MEDIAL_HEADS: ("Lateral / Medial Heads", "سر خارجی / داخلی"),
    MuscleFocus.UPPER_TRAPS: ("Upper Traps", "کول بالایی"),
    MuscleFocus.MID_LOWER_TRAPS: ("Mid / Lower Traps", "کول میانی / پایینی"),
    MuscleFocus.GENERAL_FOREARMS: ("General Forearms", "کل ساعد"),
    MuscleFocus.FOREARM_FLEXORS: ("Forearm Flexors", "خم‌کننده‌های ساعد"),
    MuscleFocus.FOREARM_EXTENSORS: ("Forearm Extensors", "بازکننده‌های ساعد"),
    MuscleFocus.NECK_FLEXION: ("Neck Flexion", "خم‌کردن گردن"),
    MuscleFocus.NECK_LATERAL_EXTENSION: ("Lateral / Extension", "جانبی / بازکردن گردن"),
    MuscleFocus.GLUTE_MAX: ("Glute Max", "سرینی بزرگ"),
    MuscleFocus.GLUTE_MEDIUS_MINIMUS: ("Glute Medius / Minimus", "سرینی میانی / کوچک"),
    MuscleFocus.GENERAL_QUADRICEPS: ("General Quadriceps", "کل چهارسر"),
    MuscleFocus.RECTUS_FEMORIS: ("Rectus Femoris", "راست‌رانی"),
    MuscleFocus.VASTI: ("Vasti", "عضلات پهن چهارسر"),
    MuscleFocus.HAMSTRINGS_HIP_EXTENSION: ("Hip Extension", "بازکردن مفصل ران"),
    MuscleFocus.HAMSTRINGS_KNEE_FLEXION: ("Knee Flexion", "خم‌کردن زانو"),
    MuscleFocus.HIP_ADDUCTION: ("Hip Adduction", "نزدیک‌کردن ران"),
    MuscleFocus.ADDUCTOR_MOBILITY: ("Adductor Mobility", "تحرک داخل ران"),
    MuscleFocus.GENERAL_CALVES: ("General Calves", "کل ساق"),
    MuscleFocus.GASTROCNEMIUS: ("Gastrocnemius", "دوقلو"),
    MuscleFocus.SOLEUS: ("Soleus", "نعلی"),
    MuscleFocus.TRUNK_FLEXION: ("Trunk Flexion", "خم‌کردن تنه"),
    MuscleFocus.HIP_FLEXION_POSTERIOR_TILT: (
        "Hip Flexion / Posterior Tilt",
        "خم‌کردن ران / چرخش لگن",
    ),
    MuscleFocus.ANTI_EXTENSION: ("Anti-Extension", "ضد بازشدن کمر"),
    MuscleFocus.TRUNK_ROTATION: ("Trunk Rotation", "چرخش تنه"),
    MuscleFocus.LATERAL_FLEXION: ("Lateral Flexion", "خم‌شدن جانبی"),
    MuscleFocus.ANTI_ROTATION: ("Anti-Rotation", "ضد چرخش"),
    MuscleFocus.LUMBAR_ERECTORS: ("Lumbar Erectors", "راست‌کننده‌های کمری"),
    MuscleFocus.THORACIC_MOBILITY: ("Thoracic Mobility", "تحرک ستون پشتی"),
}

MUSCLE_FOCUS_CATEGORIES: dict[MuscleGroup, tuple[MuscleFocusCategory, ...]] = {
    muscle: tuple(
        MuscleFocusCategory(focus, *_FOCUS_LABELS[focus]) for focus in focuses
    )
    for muscle, focuses in FOCUSES_BY_MUSCLE.items()
}


def is_compatible_muscle_focus(
    primary_muscle: MuscleGroup | None,
    muscle_focus: MuscleFocus | None,
) -> bool:
    if primary_muscle is None:
        return muscle_focus is None
    focuses = FOCUSES_BY_MUSCLE[primary_muscle]
    if not focuses:
        return muscle_focus is None
    if muscle_focus is None:
        return False
    return muscle_focus in focuses
