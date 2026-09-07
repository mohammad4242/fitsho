import type {
  FoodConstraint,
  MedicalConditionCode,
  NutritionProfileInput,
  StructuredExerciseInput,
  StructuredExerciseType,
  TrainingIntensity,
} from "@fitician/core/nutrition";
import type { ProfileFormValues } from "@fitician/core/profile";
import { tomanToIrr } from "@fitician/core/formatters";

const persianDigits = "۰۱۲۳۴۵۶۷۸۹";
const arabicDigits = "٠١٢٣٤٥٦٧٨٩";
const medicalConditionCodes: readonly MedicalConditionCode[] = [
  "controlled_hypertension",
  "lipid_disorder",
  "type_2_diabetes_non_insulin",
  "stable_gastrointestinal",
  "kidney_disease",
  "dialysis",
  "liver_disease",
  "insulin_treated_diabetes",
  "other",
];

export type SafetyFormValues = {
  conditions: string;
  medications: string;
  dangerous_food_reaction_history: boolean;
  pregnant: boolean;
  breastfeeding: boolean;
  eating_disorder_diagnosed: boolean;
  eating_disorder_active_symptoms: boolean;
  emergency_or_danger_symptoms: boolean;
  complex_medication_food_interaction: boolean;
  physician_dietary_restrictions: string;
  other_relevant_condition: string;
};

export type ExerciseFormValues = {
  trains: boolean;
  exercise_type: StructuredExerciseType;
  days_per_week: string;
  minutes_per_session: string;
  intensity: TrainingIntensity;
};

export type NutritionBasicsFormValues = {
  daily_activity_level: NutritionProfileInput["daily_activity_level"];
  monthly_food_budget_toman: string;
  budget_style: NutritionProfileInput["budget_style"];
  target_weight_change_kg_per_week: string;
  weight_rate_mode: NonNullable<NutritionProfileInput["weight_rate_mode"]>;
  allergies: string;
  intolerances: string;
  dietary_pattern: NutritionProfileInput["dietary_pattern"];
};

export type NutritionPreferencesFormValues = {
  meals_per_day: string;
  snacks_per_day: string;
  preferred_plan_start_day: NutritionProfileInput["preferred_plan_start_day"];
  favourite_foods: string;
  disliked_foods: string;
  religious_cultural_exclusions: string;
  work_shift_context: string;
  daily_check_in_enabled: boolean;
  preferred_check_in_time: string;
};

export function emptySafetyFormValues(): SafetyFormValues {
  return {
    conditions: "",
    medications: "",
    dangerous_food_reaction_history: false,
    pregnant: false,
    breastfeeding: false,
    eating_disorder_diagnosed: false,
    eating_disorder_active_symptoms: false,
    emergency_or_danger_symptoms: false,
    complex_medication_food_interaction: false,
    physician_dietary_restrictions: "",
    other_relevant_condition: "",
  };
}

export function emptyExerciseFormValues(): ExerciseFormValues {
  return {
    trains: false,
    exercise_type: "mixed",
    days_per_week: "3",
    minutes_per_session: "45",
    intensity: "moderate",
  };
}

export function emptyNutritionBasicsFormValues(): NutritionBasicsFormValues {
  return {
    daily_activity_level: "moderate",
    monthly_food_budget_toman: "",
    budget_style: "strict",
    target_weight_change_kg_per_week: "",
    weight_rate_mode: "safe",
    allergies: "",
    intolerances: "",
    dietary_pattern: "omnivore",
  };
}

export function emptyNutritionPreferencesFormValues(): NutritionPreferencesFormValues {
  return {
    meals_per_day: "3",
    snacks_per_day: "1",
    preferred_plan_start_day: "saturday",
    favourite_foods: "",
    disliked_foods: "",
    religious_cultural_exclusions: "",
    work_shift_context: "",
    daily_check_in_enabled: false,
    preferred_check_in_time: "21:00",
  };
}

export function normalizeOnboardingDigits(value: string): string {
  return Array.from(value, (character) => {
    const persianIndex = persianDigits.indexOf(character);
    if (persianIndex >= 0) return String(persianIndex);
    const arabicIndex = arabicDigits.indexOf(character);
    return arabicIndex >= 0 ? String(arabicIndex) : character;
  }).join("").replaceAll("٫", ".").replaceAll("٬", "");
}

function splitValues(value: string): string[] {
  return value
    .split(/[،,\n]/u)
    .map((item) => item.trim())
    .filter((item, index, values) => item !== "" && values.indexOf(item) === index);
}

function constraintsFromText(value: string): FoodConstraint[] {
  return splitValues(value).map((name) => ({ details: null, name }));
}

function numberFromText(value: string): number {
  return Number(normalizeOnboardingDigits(value.trim()));
}

export function safetyInputFromForm(values: SafetyFormValues) {
  const conditions = splitValues(values.conditions).filter(
    (code): code is MedicalConditionCode => medicalConditionCodes.includes(code as MedicalConditionCode),
  );
  return {
    conditions: conditions.map((code) => ({ code, details: null })),
    medications: splitValues(values.medications).map((name) => ({ name, dosage: null, notes: null })),
    dangerous_food_reaction_history: values.dangerous_food_reaction_history,
    pregnant: values.pregnant,
    breastfeeding: values.breastfeeding,
    eating_disorder_diagnosed: values.eating_disorder_diagnosed,
    eating_disorder_active_symptoms: values.eating_disorder_active_symptoms,
    emergency_or_danger_symptoms: values.emergency_or_danger_symptoms,
    complex_medication_food_interaction: values.complex_medication_food_interaction,
    physician_dietary_restrictions: values.physician_dietary_restrictions.trim() || null,
    other_relevant_condition: values.other_relevant_condition.trim() || null,
  };
}

export function exerciseInputFromForm(values: ExerciseFormValues): StructuredExerciseInput {
  if (!values.trains) return { trains: false };
  return {
    trains: true,
    exercise_type: values.exercise_type,
    days_per_week: numberFromText(values.days_per_week),
    minutes_per_session: numberFromText(values.minutes_per_session),
    intensity: values.intensity,
  };
}

export function nutritionBasicsFromForm(values: NutritionBasicsFormValues) {
  const targetRate = values.target_weight_change_kg_per_week.trim();
  return {
    daily_activity_level: values.daily_activity_level,
    individual_monthly_food_budget_irr: tomanToIrr(values.monthly_food_budget_toman),
    budget_style: values.budget_style,
    ...(targetRate === "" ? {} : {
      target_weight_change_kg_per_week: numberFromText(targetRate),
    }),
    weight_rate_mode: values.weight_rate_mode,
    allergies: constraintsFromText(values.allergies),
    intolerances: constraintsFromText(values.intolerances),
    dietary_pattern: values.dietary_pattern,
  };
}

export function nutritionInputFromForms(
  basics: NutritionBasicsFormValues,
  preferences: NutritionPreferencesFormValues,
): NutritionProfileInput {
  const meals = numberFromText(preferences.meals_per_day);
  const snacks = numberFromText(preferences.snacks_per_day);
  const basicsInput = nutritionBasicsFromForm(basics);
  return {
    ...basicsInput,
    main_meal_count_bucket: meals === 2
      ? "two_main_meals"
      : meals === 3
        ? "three_main_meals"
        : "four_or_more_main_meals",
    snack_count_bucket: snacks === 0
      ? "zero_snacks"
      : snacks === 1
        ? "one_snack"
        : snacks === 2
          ? "two_snacks"
          : "three_or_more_snacks",
    meals_per_day: meals,
    snacks_per_day: snacks,
    preferred_plan_start_day: preferences.preferred_plan_start_day,
    favourite_foods: splitValues(preferences.favourite_foods),
    disliked_foods: splitValues(preferences.disliked_foods),
    religious_cultural_exclusions: splitValues(preferences.religious_cultural_exclusions),
    work_shift_context: preferences.work_shift_context.trim() || null,
    daily_check_in_enabled: preferences.daily_check_in_enabled,
    preferred_check_in_time: preferences.daily_check_in_enabled
      ? `${preferences.preferred_check_in_time}:00`
      : null,
  };
}

export function profileValidationMessage(code: string): string {
  const messages: Record<string, string> = {
    required: "این مورد را وارد کنید.",
    displayNameLength: "نام نمایشی باید بین ۲ تا ۸۰ نویسه باشد.",
    birthDateInvalid: "تاریخ تولد معتبر نیست.",
    ageRange: "سن باید بین ۱۸ تا ۱۰۰ سال باشد.",
    heightRange: "قد باید بین ۱۲۰ تا ۲۳۰ سانتی‌متر باشد.",
    weightRange: "وزن باید بین ۳۵ تا ۳۰۰ کیلوگرم باشد.",
    weightPrecision: "وزن را با حداکثر دو رقم اعشار وارد کنید.",
    circumferenceRange: "اندازه باید بین ۴۰ تا ۲۵۰ سانتی‌متر باشد.",
    circumferencePrecision: "اندازه را با حداکثر دو رقم اعشار وارد کنید.",
    trainingDaysRange: "تعداد روزهای تمرین باید بین ۲ تا ۶ باشد.",
    trainingAgeRange: "سابقه تمرین باید حداکثر ۹۰۰ ماه باشد.",
    preferredWeekdaysInvalid: "تعداد روزهای انتخابی بیشتر از روزهای تمرین است.",
    sessionDurationInvalid: "زمان جلسه را از گزینه‌های موجود انتخاب کنید.",
    planDurationInvalid: "مدت برنامه را از گزینه‌های موجود انتخاب کنید.",
  };
  return messages[code] ?? "پاسخ‌ها را بررسی کنید.";
}

export type ProfileValues = ProfileFormValues;
