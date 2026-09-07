import {
  irrToToman,
} from "@fitician/core";
import {
  toProfilePatch,
  validateStep,
  type ProfileValidationErrors,
} from "@fitician/core/profile-validation";
import type { NutritionProfile, NutritionProfileInput } from "@fitician/core/nutrition";
import type {
  Profile,
  ProfileFormValues,
  ProfilePatch,
  SharedProfileInput,
} from "@fitician/core/profile";

import {
  emptyNutritionBasicsFormValues,
  emptyNutritionPreferencesFormValues,
  normalizeOnboardingDigits,
  nutritionInputFromForms,
  type NutritionBasicsFormValues,
  type NutritionPreferencesFormValues,
} from "../onboarding/onboardingModel";
import {
  emptyProfileFormValues,
  profileFormValuesForSharedProfile,
} from "../onboarding/onboardingForms";

export type ProfileEditSection = "personal" | "training";

const personalFields: ReadonlySet<keyof ProfilePatch> = new Set([
  "birth_date",
  "current_weight_kg",
  "display_name",
  "fitness_goal",
  "height_cm",
  "hip_circumference_cm",
  "sex",
  "shoulder_circumference_cm",
  "waist_circumference_cm",
]);

const trainingFields: ReadonlySet<keyof ProfilePatch> = new Set([
  "available_equipment",
  "experience_level",
  "home_training_setup",
  "plan_duration_weeks",
  "preferred_weekdays",
  "priority_muscles",
  "session_duration_minutes",
  "training_cautions",
  "training_days_per_week",
  "workout_generation_method",
  "training_intensity",
  "training_location",
  "training_age_months",
]);

export function profileFormValuesForProfile(profile: Profile): ProfileFormValues {
  return {
    ...profileFormValuesForSharedProfile(profile),
    available_equipment: [...(profile.available_equipment ?? [])],
    experience_level: profile.experience_level,
    hip_circumference_cm: profile.hip_circumference_cm === null ? "" : String(profile.hip_circumference_cm),
    home_training_setup: profile.home_training_setup ?? "",
    plan_duration_weeks: String(profile.plan_duration_weeks),
    preferred_weekdays: [...(profile.preferred_weekdays ?? [])],
    priority_muscle: profile.priority_muscles?.length === 1 ? profile.priority_muscles[0] : "",
    session_duration_minutes: String(profile.session_duration_minutes),
    shoulder_circumference_cm: profile.shoulder_circumference_cm === null ? "" : String(profile.shoulder_circumference_cm),
    training_age_months: profile.training_age_months === null ? "" : String(profile.training_age_months),
    training_cautions: [...profile.training_cautions],
    training_days_per_week: String(profile.training_days_per_week),
    training_intensity: profile.training_intensity ?? "",
    training_location: profile.training_location,
    waist_circumference_cm: profile.waist_circumference_cm === null ? "" : String(profile.waist_circumference_cm),
  };
}

export function profileFormValuesForSharedProfileInput(
  input: SharedProfileInput,
): ProfileFormValues {
  return {
    ...emptyProfileFormValues(),
    ...profileFormValuesForSharedProfile(input),
  };
}

export function sharedProfileInputForEdit(values: ProfileFormValues): SharedProfileInput {
  return {
    birth_date: values.birth_date.trim(),
    current_weight_kg: Number(values.current_weight_kg.trim()),
    display_name: values.display_name.trim(),
    fitness_goal: values.fitness_goal as SharedProfileInput["fitness_goal"],
    height_cm: Number(values.height_cm.trim()),
    sex: values.sex as SharedProfileInput["sex"],
  };
}

export function validateProfileSection(
  values: ProfileFormValues,
  section: "personal" | "training",
  today: Date,
): ProfileValidationErrors {
  return section === "personal"
    ? { ...validateStep(values, 1, today), ...validateStep(values, 2, today) }
    : validateStep(values, 3, today);
}

export function profilePatchForSection(
  values: ProfileFormValues,
  currentProfile: Profile,
  section: ProfileEditSection,
): ProfilePatch {
  const patch = toProfilePatch(values, currentProfile);
  const allowed = section === "personal" ? personalFields : trainingFields;
  return Object.fromEntries(
    Object.entries(patch).filter(([field]) => allowed.has(field as keyof ProfilePatch)),
  ) as ProfilePatch;
}

export type NutritionEditForms = {
  readonly basics: NutritionBasicsFormValues;
  readonly preferences: NutritionPreferencesFormValues;
};

export function nutritionFormsForProfile(profile: NutritionProfile): NutritionEditForms {
  const basics = emptyNutritionBasicsFormValues();
  basics.daily_activity_level = profile.daily_activity_level;
  basics.monthly_food_budget_toman = irrToToman(profile.individual_monthly_food_budget_irr);
  basics.budget_style = profile.budget_style;
  basics.target_weight_change_kg_per_week = profile.target_weight_change_kg_per_week === null
    || profile.target_weight_change_kg_per_week === undefined
    ? ""
    : String(profile.target_weight_change_kg_per_week);
  basics.weight_rate_mode = profile.weight_rate_mode ?? "safe";
  basics.allergies = profile.allergies.map((item) => item.name).join("، ");
  basics.intolerances = profile.intolerances.map((item) => item.name).join("، ");
  basics.dietary_pattern = profile.dietary_pattern;

  const preferences = emptyNutritionPreferencesFormValues();
  preferences.meals_per_day = String(profile.effective_main_meal_slots ?? profile.meals_per_day);
  preferences.snacks_per_day = String(profile.effective_snack_slots ?? profile.snacks_per_day);
  preferences.preferred_plan_start_day = profile.preferred_plan_start_day;
  preferences.favourite_foods = profile.favourite_foods.join("، ");
  preferences.disliked_foods = profile.disliked_foods.join("، ");
  preferences.religious_cultural_exclusions = profile.religious_cultural_exclusions.join("، ");
  preferences.work_shift_context = profile.work_shift_context ?? "";
  preferences.daily_check_in_enabled = profile.daily_check_in_enabled;
  preferences.preferred_check_in_time = profile.preferred_check_in_time?.slice(0, 5) ?? "21:00";
  return { basics, preferences };
}

export function nutritionInputForEdit(
  profile: NutritionProfile,
  basics: NutritionBasicsFormValues,
  preferences: NutritionPreferencesFormValues,
): NutritionProfileInput {
  const edited = nutritionInputFromForms(basics, preferences);
  return {
    accepts_batch_cooking: profile.accepts_batch_cooking,
    accepts_leftovers: profile.accepts_leftovers,
    allergies: edited.allergies,
    budget_style: edited.budget_style,
    cooking_equipment: profile.cooking_equipment,
    cooking_frequency_per_week: profile.cooking_frequency_per_week,
    cooking_skill: profile.cooking_skill,
    daily_activity_level: edited.daily_activity_level,
    daily_check_in_enabled: edited.daily_check_in_enabled,
    dietary_pattern: edited.dietary_pattern,
    disliked_foods: edited.disliked_foods,
    favourite_foods: edited.favourite_foods,
    foods_available_at_home: profile.foods_available_at_home,
    individual_monthly_food_budget_irr: edited.individual_monthly_food_budget_irr,
    intolerances: edited.intolerances,
    main_meal_count_bucket: edited.main_meal_count_bucket,
    maximum_cooking_time_minutes: profile.maximum_cooking_time_minutes,
    maximum_meal_repetition_per_week: profile.maximum_meal_repetition_per_week,
    meal_preparation_preference: profile.meal_preparation_preference,
    meals_per_day: edited.meals_per_day,
    metabolic_basis: profile.metabolic_basis ?? null,
    never_suggest_foods: profile.never_suggest_foods,
    plan_style: profile.plan_style,
    preferred_check_in_time: edited.preferred_check_in_time,
    preferred_plan_start_day: edited.preferred_plan_start_day,
    preferred_variety: profile.preferred_variety,
    refrigerator_access: profile.refrigerator_access,
    religious_cultural_exclusions: edited.religious_cultural_exclusions,
    refused_foods: profile.refused_foods,
    snack_count_bucket: edited.snack_count_bucket,
    snacks_per_day: edited.snacks_per_day,
    supplied_meal_source: profile.supplied_meal_source,
    supplied_meals_per_week: profile.supplied_meals_per_week,
    target_weight_change_kg_per_week: basics.target_weight_change_kg_per_week.trim() === ""
      ? null
      : edited.target_weight_change_kg_per_week ?? null,
    weight_rate_mode: edited.weight_rate_mode,
    work_shift_context: edited.work_shift_context,
    freezer_access: profile.freezer_access,
  };
}

export type NutritionValidationErrors = Partial<
  Record<keyof NutritionBasicsFormValues | keyof NutritionPreferencesFormValues, string>
>;

export function validateNutritionEdit(
  basics: NutritionBasicsFormValues,
  preferences: NutritionPreferencesFormValues,
): NutritionValidationErrors {
  const errors: NutritionValidationErrors = {};
  const budget = normalizeOnboardingDigits(basics.monthly_food_budget_toman)
    .replaceAll(",", "")
    .trim();
  if (budget === "" || !/^\d+$/.test(budget)) {
    errors.monthly_food_budget_toman = "بودجه ماهانه را وارد کن.";
  }

  const targetRate = normalizeOnboardingDigits(basics.target_weight_change_kg_per_week.trim());
  if (
    targetRate !== ""
    && (!/^\d+(?:\.\d+)?$/.test(targetRate)
      || Number(targetRate) < 0.3
      || Number(targetRate) > 2
    )
  ) {
    errors.target_weight_change_kg_per_week = "نرخ هفتگی باید بین ۰٫۳ تا ۲ کیلوگرم باشد.";
  }

  if (!(["2", "3", "4"] as const).includes(preferences.meals_per_day as "2" | "3" | "4")) {
    errors.meals_per_day = "تعداد وعده اصلی معتبر نیست.";
  }
  if (!(["0", "1", "2", "3"] as const).includes(preferences.snacks_per_day as "0" | "1" | "2" | "3")) {
    errors.snacks_per_day = "تعداد میان‌وعده معتبر نیست.";
  }
  if (
    preferences.daily_check_in_enabled
    && !/^\d{2}:\d{2}$/.test(preferences.preferred_check_in_time)
  ) {
    errors.preferred_check_in_time = "زمان یادآوری معتبر نیست.";
  }
  return errors;
}
