from dataclasses import dataclass

from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.media_metadata import OWNER_ATTRIBUTION, OWNER_LICENSE


@dataclass(frozen=True)
class ExerciseSeed:
    slug: str
    name_en: str
    name_fa: str
    body_region: BodyRegion
    primary_muscle: MuscleGroup
    muscle_focus: MuscleFocus | None
    secondary_muscles: tuple[MuscleGroup, ...]
    equipment: tuple[Equipment, ...]
    difficulty: Difficulty
    movement_pattern: MovementPattern
    exercise_type: ExerciseType
    caution_tags: tuple[ExerciseCautionTag, ...]
    is_programmable: bool
    instructions_en: tuple[str, ...]
    instructions_fa: tuple[str, ...]
    safety_notes_en: tuple[str, ...]
    safety_notes_fa: tuple[str, ...]
    media_path: str
    media_type: MediaType
    media_source_url: str | None
    media_license: str
    media_attribution: str


@dataclass(frozen=True)
class AlternativeSeed:
    exercise_slug: str
    alternative_slug: str
    reason_en: str
    reason_fa: str


_OWNER_MEDIA: dict[str, tuple[str, MediaType]] = {
    "dumbbell-bench-press": (
        "/exercises/upper-body/chest/dumbbell-bench-press.gif",
        MediaType.GIF,
    ),
    "barbell-bent-over-row": (
        "/exercises/upper-body/back/barbell-bent-over-row.gif",
        MediaType.GIF,
    ),
    "dumbbell-lateral-raise": (
        "/exercises/upper-body/shoulders/dumbbell-lateral-raise.gif",
        MediaType.GIF,
    ),
    "smith-machine-shoulder-press": (
        "/exercises/upper-body/shoulders/smith-machine-shoulder-press.gif",
        MediaType.GIF,
    ),
    "rear-delt-fly": (
        "/exercises/upper-body/shoulders/rear-delt-fly.gif",
        MediaType.GIF,
    ),
    "dumbbell-curl": (
        "/exercises/upper-body/biceps/dumbbell-curl.gif",
        MediaType.GIF,
    ),
    "hammer-curl": (
        "/exercises/upper-body/biceps/hammer-curl.gif",
        MediaType.GIF,
    ),
    "cable-curl": (
        "/exercises/upper-body/biceps/cable-curl.gif",
        MediaType.GIF,
    ),
    "barbell-curl": (
        "/exercises/upper-body/biceps/barbell-curl.gif",
        MediaType.GIF,
    ),
    "overhead-dumbbell-extension": (
        "/exercises/upper-body/triceps/overhead-dumbbell-extension.gif",
        MediaType.GIF,
    ),
    "glute-bridge": (
        "/exercises/lower-body/glutes/glute-bridge.gif",
        MediaType.GIF,
    ),
    "goblet-squat": (
        "/exercises/lower-body/quadriceps/goblet-squat.gif",
        MediaType.GIF,
    ),
    "leg-press": (
        "/exercises/lower-body/quadriceps/leg-press.gif",
        MediaType.GIF,
    ),
    "leg-extension": (
        "/exercises/lower-body/quadriceps/leg-extension.gif",
        MediaType.GIF,
    ),
    "dumbbell-lunge": (
        "/exercises/lower-body/quadriceps/dumbbell-lunge.gif",
        MediaType.GIF,
    ),
    "romanian-deadlift": (
        "/exercises/lower-body/hamstrings/romanian-deadlift.gif",
        MediaType.GIF,
    ),
    "standing-calf-raise": (
        "/exercises/lower-body/calves/standing-calf-raise.gif",
        MediaType.GIF,
    ),
}


def _exercise(
    slug: str,
    name_en: str,
    name_fa: str,
    body_region: BodyRegion,
    primary_muscle: MuscleGroup,
    secondary_muscles: tuple[MuscleGroup, ...],
    equipment: tuple[Equipment, ...],
    difficulty: Difficulty,
    instructions_en: tuple[str, str, str],
    instructions_fa: tuple[str, str, str],
    safety_en: str,
    safety_fa: str,
) -> ExerciseSeed:
    movement_pattern, exercise_type, caution_tags = PROGRAMMING_METADATA[slug]
    media_path, media_type = _OWNER_MEDIA[slug]
    return ExerciseSeed(
        slug=slug,
        name_en=name_en,
        name_fa=name_fa,
        body_region=body_region,
        primary_muscle=primary_muscle,
        muscle_focus=SEED_MUSCLE_FOCUS[slug],
        secondary_muscles=secondary_muscles,
        equipment=equipment,
        movement_pattern=movement_pattern,
        exercise_type=exercise_type,
        caution_tags=caution_tags,
        is_programmable=True,
        difficulty=difficulty,
        instructions_en=instructions_en,
        instructions_fa=instructions_fa,
        safety_notes_en=(safety_en,),
        safety_notes_fa=(safety_fa,),
        media_path=media_path,
        media_type=media_type,
        media_source_url=None,
        media_license=OWNER_LICENSE,
        media_attribution=OWNER_ATTRIBUTION,
    )


B = BodyRegion
D = Difficulty
E = Equipment
M = MuscleGroup
P = MovementPattern
T = ExerciseType
C = ExerciseCautionTag
F = MuscleFocus

SEED_MUSCLE_FOCUS: dict[str, MuscleFocus | None] = {
    "dumbbell-bench-press": F.MID_CHEST,
    "barbell-bent-over-row": F.GENERAL_BACK,
    "dumbbell-lateral-raise": F.LATERAL_DELT,
    "smith-machine-shoulder-press": F.FRONT_DELT,
    "rear-delt-fly": F.REAR_DELT,
    "dumbbell-curl": F.BICEPS_BRACHII,
    "hammer-curl": F.BRACHIALIS_BRACHIORADIALIS,
    "cable-curl": F.BICEPS_BRACHII,
    "barbell-curl": F.BICEPS_BRACHII,
    "overhead-dumbbell-extension": F.TRICEPS_LONG_HEAD,
    "glute-bridge": F.GLUTE_MAX,
    "goblet-squat": None,
    "leg-press": None,
    "leg-extension": None,
    "dumbbell-lunge": None,
    "romanian-deadlift": F.HAMSTRINGS_HIP_EXTENSION,
    "standing-calf-raise": F.GASTROCNEMIUS,
}

PROGRAMMING_METADATA: dict[
    str, tuple[MovementPattern, ExerciseType, tuple[ExerciseCautionTag, ...]]
] = {
    "dumbbell-bench-press": (P.HORIZONTAL_PUSH, T.COMPOUND, (C.SHOULDER_INTERNAL_ROTATION,)),
    "barbell-bent-over-row": (P.HORIZONTAL_PULL, T.COMPOUND, (C.LOWER_BACK_LOADING,)),
    "dumbbell-lateral-raise": (P.SHOULDER_ABDUCTION, T.ISOLATION, ()),
    "smith-machine-shoulder-press": (P.VERTICAL_PUSH, T.COMPOUND, (C.OVERHEAD_POSITION,)),
    "rear-delt-fly": (P.HORIZONTAL_PULL, T.ISOLATION, (C.LOWER_BACK_LOADING,)),
    "dumbbell-curl": (P.ELBOW_FLEXION, T.ISOLATION, ()),
    "hammer-curl": (P.ELBOW_FLEXION, T.ISOLATION, ()),
    "cable-curl": (P.ELBOW_FLEXION, T.ISOLATION, ()),
    "barbell-curl": (P.ELBOW_FLEXION, T.ISOLATION, (C.WRIST_LOADING,)),
    "overhead-dumbbell-extension": (P.ELBOW_EXTENSION, T.ISOLATION, (C.OVERHEAD_POSITION,)),
    "glute-bridge": (P.HIP_EXTENSION, T.COMPOUND, ()),
    "goblet-squat": (P.SQUAT, T.COMPOUND, (C.DEEP_KNEE_FLEXION, C.WRIST_LOADING)),
    "leg-press": (P.SQUAT, T.COMPOUND, (C.DEEP_KNEE_FLEXION,)),
    "leg-extension": (P.KNEE_EXTENSION, T.ISOLATION, ()),
    "dumbbell-lunge": (P.LUNGE, T.COMPOUND, (C.DEEP_KNEE_FLEXION, C.BALANCE_DEMAND)),
    "romanian-deadlift": (P.HIP_HINGE, T.COMPOUND, (C.LOWER_BACK_LOADING,)),
    "standing-calf-raise": (P.CALF_RAISE, T.ISOLATION, (C.BALANCE_DEMAND,)),
}


EXERCISE_SEEDS: tuple[ExerciseSeed, ...] = (
    _exercise(
        "dumbbell-bench-press",
        "Dumbbell Bench Press",
        "پرس سینه دمبل",
        B.UPPER_BODY,
        M.CHEST,
        (M.TRICEPS, M.SHOULDERS),
        (E.DUMBBELL, E.BENCH),
        D.INTERMEDIATE,
        (
            "Lie on the bench with feet planted and dumbbells beside the chest.",
            "Press the dumbbells upward while keeping wrists stacked over elbows.",
            "Lower with control until the upper arms approach the bench line.",
        ),
        (
            "روی نیمکت دراز بکش، پاها را ثابت کن و دمبل‌ها را کنار سینه نگه دار.",
            "دمبل‌ها را بالا ببر و مچ‌ها را روی آرنج‌ها نگه دار.",
            "با کنترل پایین بیاور تا بازوها به نزدیکی خط نیمکت برسند.",
        ),
        "Choose a load you can control and avoid forcing an excessive shoulder stretch.",
        "وزنه‌ای انتخاب کن که کنترل شود و کشش بیش‌ازحد شانه ایجاد نکن.",
    ),
    _exercise(
        "barbell-bent-over-row",
        "Barbell Bent-Over Row",
        "زیربغل هالتر خم",
        B.UPPER_BODY,
        M.BACK,
        (M.BICEPS, M.TRAPS, M.LOWER_BACK),
        (E.BARBELL,),
        D.INTERMEDIATE,
        (
            "Hinge at the hips with knees softly bent and hold a neutral spine.",
            "Pull the bar toward the lower ribs while keeping it close to the body.",
            "Lower the bar under control without changing the torso angle.",
        ),
        (
            "از لگن خم شو، زانوها را کمی خم و ستون فقرات را خنثی نگه دار.",
            "هالتر را نزدیک بدن به سمت دنده‌های پایینی بکش.",
            "بدون تغییر زاویه تنه، هالتر را با کنترل پایین ببر.",
        ),
        "Stop the set if the lower back rounds or the torso begins to jerk.",
        "اگر کمر گرد شد یا تنه شروع به تکان خوردن کرد، ست را متوقف کن.",
    ),
    _exercise(
        "dumbbell-lateral-raise",
        "Dumbbell Lateral Raise",
        "نشر جانب دمبل",
        B.UPPER_BODY,
        M.SHOULDERS,
        (),
        (E.DUMBBELL,),
        D.BEGINNER,
        (
            "Stand tall with light dumbbells at your sides and elbows softly bent.",
            "Raise the arms out to the sides to about shoulder height.",
            "Lower slowly without shrugging or swinging.",
        ),
        (
            "صاف بایست و دمبل‌های سبک را با آرنج کمی خم کنار بدن نگه دار.",
            "بازوها را از طرفین تا حدود ارتفاع شانه بالا ببر.",
            "بدون بالا انداختن شانه یا تاب دادن، آهسته پایین بیاور.",
        ),
        "Use a light load and keep the movement within a comfortable shoulder range.",
        "وزنه سبک استفاده کن و حرکت را در دامنه راحت شانه انجام بده.",
    ),
    _exercise(
        "smith-machine-shoulder-press",
        "Smith Machine Shoulder Press",
        "پرس سرشانه اسمیت",
        B.UPPER_BODY,
        M.SHOULDERS,
        (M.TRICEPS,),
        (E.MACHINE, E.BENCH),
        D.BEGINNER,
        (
            "Set the bench so the bar starts slightly in front of shoulder level.",
            "Unrack and press the bar upward without overextending the lower back.",
            "Lower under control, then secure the bar fully on the hooks.",
        ),
        (
            "نیمکت را طوری تنظیم کن که میله کمی جلوی شانه‌ها شروع شود.",
            "میله را آزاد و بدون گود کردن زیاد کمر به بالا فشار بده.",
            "با کنترل پایین بیاور و در پایان میله را کامل روی قلاب‌ها قفل کن.",
        ),
        "Confirm the safety stops and hook position before beginning the set.",
        "پیش از شروع ست، محل قلاب‌ها و محدودکننده‌های ایمنی را بررسی کن.",
    ),
    _exercise(
        "rear-delt-fly",
        "Rear Delt Fly",
        "نشر خم دمبل",
        B.UPPER_BODY,
        M.SHOULDERS,
        (M.TRAPS, M.BACK),
        (E.DUMBBELL,),
        D.BEGINNER,
        (
            "Hinge forward with a neutral back and let the dumbbells hang below you.",
            "Open the arms outward with elbows softly bent.",
            "Lower slowly while keeping the neck relaxed.",
        ),
        (
            "با کمر خنثی از لگن خم شو و دمبل‌ها را زیر بدن آویزان نگه دار.",
            "با آرنج کمی خم، بازوها را به طرفین باز کن.",
            "با حفظ آرامش گردن، دمبل‌ها را آهسته پایین بیاور.",
        ),
        "Avoid lifting beyond a controlled range or pulling the shoulders toward the ears.",
        "بیش از دامنه کنترل‌شده بالا نبر و شانه‌ها را به سمت گوش نکش.",
    ),
    _exercise(
        "dumbbell-curl",
        "Dumbbell Curl",
        "جلو بازو دمبل",
        B.UPPER_BODY,
        M.BICEPS,
        (),
        (E.DUMBBELL,),
        D.BEGINNER,
        (
            "Stand tall with dumbbells at your sides and palms facing forward.",
            "Curl the weights while keeping the elbows close to the torso.",
            "Lower fully with control without moving the upper arms.",
        ),
        (
            "صاف بایست و دمبل‌ها را با کف دست رو به جلو کنار بدن نگه دار.",
            "با ثابت ماندن آرنج‌ها کنار تنه، دمبل‌ها را بالا بیاور.",
            "بدون حرکت دادن بازوها، دمبل‌ها را کامل و کنترل‌شده پایین ببر.",
        ),
        "Reduce the load if you need to lean back or swing the dumbbells.",
        "اگر مجبور به عقب رفتن یا تاب دادن دمبل‌ها هستی، وزنه را کم کن.",
    ),
    _exercise(
        "hammer-curl",
        "Hammer Curl",
        "جلو بازو چکشی",
        B.UPPER_BODY,
        M.BICEPS,
        (),
        (E.DUMBBELL,),
        D.BEGINNER,
        (
            "Hold the dumbbells at your sides with palms facing each other.",
            "Curl toward the shoulders while keeping the wrists neutral.",
            "Lower slowly until the elbows are straight but not forcefully locked.",
        ),
        (
            "دمبل‌ها را با کف دست‌ها رو به هم کنار بدن نگه دار.",
            "با مچ خنثی، دمبل‌ها را به سمت شانه‌ها بالا بیاور.",
            "آهسته پایین ببر تا آرنج‌ها صاف شوند، بدون قفل کردن شدید.",
        ),
        "Keep the elbows still and avoid using body momentum.",
        "آرنج‌ها را ثابت نگه دار و از شتاب بدن استفاده نکن.",
    ),
    _exercise(
        "cable-curl",
        "Cable Curl",
        "جلو بازو سیم‌کش",
        B.UPPER_BODY,
        M.BICEPS,
        (),
        (E.CABLE,),
        D.BEGINNER,
        (
            "Face the low pulley and hold the bar with elbows close to your sides.",
            "Curl the bar upward without letting the shoulders roll forward.",
            "Return slowly until the arms are long and the cable stays taut.",
        ),
        (
            "روبه‌روی قرقره پایین بایست و میله را با آرنج‌های نزدیک بدن بگیر.",
            "بدون جلو آمدن شانه‌ها، میله را بالا بیاور.",
            "آهسته دست‌ها را باز کن و کشش کابل را حفظ کن.",
        ),
        "Stand far enough from the stack that the cable remains controlled.",
        "به اندازه‌ای از دستگاه فاصله بگیر که کابل در تمام حرکت کنترل‌شده باشد.",
    ),
    _exercise(
        "barbell-curl",
        "Barbell Curl",
        "جلو بازو هالتر",
        B.UPPER_BODY,
        M.BICEPS,
        (),
        (E.BARBELL,),
        D.INTERMEDIATE,
        (
            "Stand tall and hold the bar around shoulder width with palms forward.",
            "Curl the bar while keeping elbows close and wrists straight.",
            "Lower under control to the starting position.",
        ),
        (
            "صاف بایست و هالتر را به عرض شانه با کف دست رو به جلو بگیر.",
            "با آرنج‌های نزدیک بدن و مچ صاف، هالتر را بالا بیاور.",
            "هالتر را با کنترل به وضعیت شروع پایین ببر.",
        ),
        "Use a comfortable grip and stop if the straight bar irritates the wrists or elbows.",
        "گیرش راحت انتخاب کن و اگر میله صاف مچ یا آرنج را آزار داد، حرکت را متوقف کن.",
    ),
    _exercise(
        "overhead-dumbbell-extension",
        "Overhead Dumbbell Triceps Extension",
        "پشت بازو دمبل بالای سر",
        B.UPPER_BODY,
        M.TRICEPS,
        (),
        (E.DUMBBELL, E.BENCH),
        D.INTERMEDIATE,
        (
            "Sit tall and hold one dumbbell securely above the head.",
            "Bend the elbows to lower the dumbbell behind the head.",
            "Extend the elbows and return overhead without flaring the ribs.",
        ),
        (
            "صاف بنشین و یک دمبل را محکم بالای سر نگه دار.",
            "آرنج‌ها را خم کن و دمبل را پشت سر پایین ببر.",
            "بدون باز شدن دنده‌ها، آرنج‌ها را صاف و دمبل را بالا ببر.",
        ),
        "Use a load you can grip securely and keep the range comfortable for the shoulders.",
        "وزنه‌ای انتخاب کن که محکم نگه داشته شود و دامنه برای شانه‌ها راحت باشد.",
    ),
    _exercise(
        "glute-bridge",
        "Glute Bridge",
        "پل باسن",
        B.LOWER_BODY,
        M.GLUTES,
        (M.HAMSTRINGS, M.LOWER_BACK),
        (E.BODYWEIGHT,),
        D.BEGINNER,
        (
            "Lie on your back with knees bent and feet flat near the hips.",
            "Brace gently and press through the feet to lift the hips.",
            "Pause when shoulders, hips, and knees align, then lower slowly.",
        ),
        (
            "به پشت دراز بکش، زانوها را خم و کف پاها را نزدیک لگن بگذار.",
            "میان‌تنه را ملایم منقبض کن و با فشار پاها لگن را بالا ببر.",
            "وقتی شانه، لگن و زانو هم‌راستا شدند مکث کن و آهسته پایین بیاور.",
        ),
        "Keep the movement at the hips and avoid pushing into lower-back extension.",
        "حرکت را از لگن انجام بده و کمر را به گودی بیشتر هل نده.",
    ),
    _exercise(
        "goblet-squat",
        "Goblet Squat",
        "گابلت اسکوات",
        B.LOWER_BODY,
        M.QUADRICEPS,
        (M.GLUTES, M.HAMSTRINGS, M.LOWER_BACK),
        (E.DUMBBELL,),
        D.BEGINNER,
        (
            "Hold one dumbbell close to the chest and set the feet around shoulder width.",
            "Squat between the hips while keeping the chest tall and knees tracking over toes.",
            "Drive through the feet to return to standing.",
        ),
        (
            "یک دمبل را نزدیک سینه بگیر و پاها را حدود عرض شانه قرار بده.",
            "با سینه بالا میان لگن بنشین و زانوها را هم‌راستای پنجه‌ها نگه دار.",
            "با فشار کف پاها به حالت ایستاده برگرد.",
        ),
        "Keep the dumbbell secure and stop the descent before posture or balance is lost.",
        "دمبل را محکم نگه دار و پیش از به‌هم خوردن فرم یا تعادل، پایین رفتن را متوقف کن.",
    ),
    _exercise(
        "leg-press",
        "Leg Press",
        "پرس پا دستگاه",
        B.LOWER_BODY,
        M.QUADRICEPS,
        (M.GLUTES, M.HAMSTRINGS),
        (E.MACHINE,),
        D.BEGINNER,
        (
            "Place the feet about shoulder width on the platform and keep the hips "
            "against the pad.",
            "Lower the platform until the knees reach a comfortable bend.",
            "Press through the feet to return without forcefully locking the knees.",
        ),
        (
            "پاها را به عرض شانه روی صفحه بگذار و لگن را به پشتی بچسبان.",
            "صفحه را تا خم شدن راحت زانوها پایین بیاور.",
            "با فشار پاها برگرد و زانوها را با شدت قفل نکن.",
        ),
        "Set the safety stops and do not lower so far that the pelvis curls off the pad.",
        "قفل ایمنی را تنظیم کن و آن‌قدر پایین نیاور که لگن از پشتی جدا شود.",
    ),
    _exercise(
        "leg-extension",
        "Leg Extension",
        "جلو پا دستگاه",
        B.LOWER_BODY,
        M.QUADRICEPS,
        (),
        (E.MACHINE,),
        D.BEGINNER,
        (
            "Adjust the seat and roller so the machine pivot aligns with the knee.",
            "Extend the knees smoothly until the legs are nearly straight.",
            "Lower the pad slowly to the starting position.",
        ),
        (
            "صندلی و پد را طوری تنظیم کن که محور دستگاه با زانو هم‌راستا باشد.",
            "زانوها را نرم باز کن تا پاها تقریباً صاف شوند.",
            "پد را آهسته به وضعیت شروع پایین بیاور.",
        ),
        "Avoid kicking the pad or using a range that causes knee discomfort.",
        "به پد ضربه نزن و در دامنه‌ای که زانو را آزار می‌دهد حرکت نکن.",
    ),
    _exercise(
        "dumbbell-lunge",
        "Dumbbell Lunge",
        "لانج دمبل",
        B.LOWER_BODY,
        M.QUADRICEPS,
        (M.GLUTES, M.HAMSTRINGS, M.CALVES),
        (E.DUMBBELL,),
        D.INTERMEDIATE,
        (
            "Stand tall with dumbbells at your sides and take a controlled step forward.",
            "Lower both knees while the front knee tracks over the foot.",
            "Push through the front foot to return, then repeat on the other side.",
        ),
        (
            "صاف بایست، دمبل‌ها را کنار بدن بگیر و یک قدم کنترل‌شده جلو برو.",
            "هر دو زانو را خم کن و زانوی جلو را در راستای پا نگه دار.",
            "با فشار پای جلو برگرد و سپس سمت دیگر را انجام بده.",
        ),
        "Shorten the step or range if you cannot keep balance and knee alignment.",
        "اگر تعادل و راستای زانو حفظ نمی‌شود، طول قدم یا دامنه را کمتر کن.",
    ),
    _exercise(
        "romanian-deadlift",
        "Romanian Deadlift",
        "ددلیفت رومانیایی",
        B.LOWER_BODY,
        M.HAMSTRINGS,
        (M.GLUTES, M.BACK, M.LOWER_BACK),
        (E.BARBELL,),
        D.INTERMEDIATE,
        (
            "Stand with the bar close to the thighs and knees softly bent.",
            "Push the hips backward while sliding the bar close to the legs.",
            "Stop at a controlled hamstring stretch, then drive the hips forward to stand.",
        ),
        (
            "با هالتر نزدیک ران‌ها و زانوهای کمی خم بایست.",
            "لگن را عقب ببر و هالتر را نزدیک پاها پایین بده.",
            "در کشش کنترل‌شده پشت پا توقف کن و با جلو آوردن لگن بایست.",
        ),
        "Keep the spine neutral and end the descent before the back rounds.",
        "ستون فقرات را خنثی نگه دار و پیش از گرد شدن کمر، پایین رفتن را تمام کن.",
    ),
    _exercise(
        "standing-calf-raise",
        "Standing Calf Raise",
        "ساق پا ایستاده",
        B.LOWER_BODY,
        M.CALVES,
        (),
        (E.BODYWEIGHT,),
        D.BEGINNER,
        (
            "Stand tall with the balls of the feet supported and hold a stable surface.",
            "Raise the heels as high as you can without rolling the ankles.",
            "Pause briefly, then lower the heels slowly.",
        ),
        (
            "صاف بایست، پنجه‌ها را ثابت کن و یک سطح محکم را برای تعادل بگیر.",
            "بدون چرخیدن مچ‌ها، پاشنه‌ها را تا حد کنترل‌شده بالا ببر.",
            "کمی مکث کن و پاشنه‌ها را آهسته پایین بیاور.",
        ),
        "Keep pressure even across the forefoot and avoid bouncing at the bottom.",
        "فشار را روی جلوی پا یکنواخت نگه دار و در پایین حرکت جهش نکن.",
    ),
)


ALTERNATIVE_SEEDS: tuple[AlternativeSeed, ...] = (
    AlternativeSeed(
        "leg-press",
        "goblet-squat",
        "A curated squat-pattern option when a leg-press machine is unavailable.",
        "گزینه الگوی اسکوات برای زمانی که دستگاه پرس پا در دسترس نیست.",
    ),
)
