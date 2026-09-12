import { expect, it } from "vitest";

import type { NutritionProfile } from "@fitician/core/nutrition";
import type { Equipment, HomeTrainingSetup, Profile } from "@fitician/core/profile";

import {
  nutritionFormsForProfile,
  nutritionInputForEdit,
  profileFormValuesForProfile,
  profilePatchForSection,
  validateNutritionEdit,
  validateProfileSection,
} from "./profileModel";

const profile = {
  available_equipment: ["bodyweight", "dumbbell", "pull_up_bar"],
  birth_date: "1992-05-12",
  circumferences_measured_at: "2026-08-01T10:00:00Z",
  created_at: "2026-08-01T10:00:00Z",
  current_weight_kg: 64,
  display_name: "Sara",
  experience_level: "beginner",
  fitness_goal: "build_muscle",
  height_cm: 168,
  hip_circumference_cm: 96,
  home_training_setup: "dumbbells_available",
  plan_duration_weeks: 4,
  preferred_weekdays: [0, 2, 4],
  priority_muscles: ["glutes"],
  profile_photo_url: null,
  session_duration_minutes: 45,
  sex: "female",
  shoulder_circumference_cm: 92,
  training_age_months: 8,
  training_cautions: [],
  training_days_per_week: 3,
  training_intensity: "moderate",
  training_location: "home",
  updated_at: "2026-08-01T10:00:00Z",
  user_id: "user-1",
  waist_circumference_cm: 72,
  weight_measured_at: "2026-08-01T10:00:00Z",
  physical_limitations: null,
} as Profile;

const nutrition = {
  accepts_batch_cooking: true,
  accepts_leftovers: true,
  allergies: [{ details: null, name: "بادام" }],
  budget_style: "flexible",
  cooking_equipment: [],
  cooking_frequency_per_week: 0,
  cooking_skill: "none",
  currency: "IRR",
  created_at: "2026-08-01T10:00:00Z",
  daily_activity_level: "moderate",
  daily_check_in_enabled: true,
  dietary_pattern: "omnivore",
  disliked_foods: ["کرفس"],
  favourite_foods: ["برنج"],
  foods_available_at_home: ["تخم‌مرغ"],
  individual_monthly_food_budget_irr: 123_450,
  intolerances: [],
  main_meal_count_bucket: "three_main_meals",
  maximum_meal_repetition_per_week: 3,
  maximum_cooking_time_minutes: 0,
  meals_per_day: 3,
  meal_preparation_preference: "no_cooking",
  metabolic_basis: null,
  snacks_per_day: 1,
  never_suggest_foods: ["سیر"],
  onboarding_status: "completed",
  plan_style: "balanced",
  physician_review_required: false,
  preferred_check_in_time: "21:00:00",
  preferred_plan_start_day: "saturday",
  preferred_variety: "medium",
  refrigerator_access: true,
  religious_cultural_exclusions: ["گوشت خوک"],
  snack_count_bucket: "one_snack",
  supplied_meal_source: null,
  supplied_meals_per_week: 0,
  refused_foods: [],
  target_weight_change_kg_per_week: null,
  updated_at: "2026-08-01T10:00:00Z",
  user_id: "user-1",
  weekly_budget_irr: 30_000,
  weight_rate_mode: "safe",
  work_shift_context: "شیفت شب",
  freezer_access: true,
} as NutritionProfile;

it("filters personal and training edits into backend PATCH fields", () => {
  const values = profileFormValuesForProfile(profile);
  values.current_weight_kg = "65";
  values.training_days_per_week = "4";

  expect(profilePatchForSection(values, profile, "personal")).toEqual({
    current_weight_kg: 65,
  });
  expect(profilePatchForSection(values, profile, "training")).toEqual({
    training_days_per_week: 4,
  });
});

it("shares the existing core validation rules for native sections", () => {
  const values = profileFormValuesForProfile(profile);
  values.current_weight_kg = "301";
  expect(validateProfileSection(values, "personal", new Date("2026-09-07T00:00:00Z"))).toMatchObject({
    current_weight_kg: "weightRange",
  });

  values.current_weight_kg = "64";
  values.training_days_per_week = "1";
  expect(validateProfileSection(values, "training", new Date("2026-09-07T00:00:00Z"))).toMatchObject({
    training_days_per_week: "trainingDaysRange",
  });
});

it("hydrates every home preset with its canonical inventory", () => {
  const expected: Record<HomeTrainingSetup, readonly Equipment[]> = {
    bodyweight_only: ["bodyweight", "pull_up_bar"],
    dumbbells_available: ["bodyweight", "dumbbell", "pull_up_bar"],
    resistance_bands_available: ["bodyweight", "resistance_band", "pull_up_bar"],
    dumbbells_and_resistance_bands_available: ["bodyweight", "dumbbell", "resistance_band", "pull_up_bar"],
  };

  for (const [setup, equipment] of Object.entries(expected) as [HomeTrainingSetup, readonly Equipment[]][]) {
    const values = profileFormValuesForProfile({
      ...profile,
      available_equipment: ["bodyweight"],
      home_training_setup: setup,
    });
    expect(values.home_training_setup).toBe(setup);
    expect(values.available_equipment).toEqual(equipment);
  }

  const legacyValues = profileFormValuesForProfile({
    ...profile,
    available_equipment: ["bodyweight"],
    home_training_setup: null,
  });
  expect(legacyValues.home_training_setup).toBe("bodyweight_only");
  expect(legacyValues.available_equipment).toEqual(["bodyweight", "pull_up_bar"]);
});

it("patches both home fields when the selected preset changes", () => {
  const values = profileFormValuesForProfile(profile);
  values.home_training_setup = "resistance_bands_available";
  values.available_equipment = ["bodyweight", "resistance_band", "pull_up_bar"];

  expect(profilePatchForSection(values, profile, "training")).toEqual({
    available_equipment: ["bodyweight", "resistance_band", "pull_up_bar"],
    home_training_setup: "resistance_bands_available",
  });
});

it("requires a supported native sex choice for legacy persisted values", () => {
  for (const sex of ["other", "prefer_not_to_say"] as const) {
    const values = profileFormValuesForProfile(profile);
    values.sex = sex;

    expect(validateProfileSection(values, "personal", new Date("2026-09-07T00:00:00Z"))).toMatchObject({
      sex: "required",
    });
    expect(values.sex).toBe(sex);
  }
});

it("round-trips editable nutrition preferences without dropping backend fields", () => {
  const forms = nutritionFormsForProfile(nutrition);
  expect(forms.basics.monthly_food_budget_toman).toBe("12,345");
  expect(forms.preferences.preferred_check_in_time).toBe("21:00");

  forms.basics.monthly_food_budget_toman = "20,000";
  forms.preferences.favourite_foods = "ماست، برنج";
  forms.preferences.daily_check_in_enabled = false;

  const input = nutritionInputForEdit(nutrition, forms.basics, forms.preferences);
  expect(input.individual_monthly_food_budget_irr).toBe(200_000);
  expect(input.favourite_foods).toEqual(["ماست", "برنج"]);
  expect(input.preferred_check_in_time).toBeNull();
  expect(input.foods_available_at_home).toEqual(["تخم‌مرغ"]);
  expect(input.never_suggest_foods).toEqual(["سیر"]);
  expect(input.work_shift_context).toBe("شیفت شب");
  expect(input).not.toHaveProperty("user_id");
  expect(input).not.toHaveProperty("onboarding_status");
});

it("validates native nutrition preference fields before the full PUT", () => {
  const forms = nutritionFormsForProfile(nutrition);
  forms.basics.monthly_food_budget_toman = "abc";
  forms.preferences.meals_per_day = "5";
  forms.preferences.daily_check_in_enabled = true;
  forms.preferences.preferred_check_in_time = "noon";

  expect(validateNutritionEdit(forms.basics, forms.preferences)).toMatchObject({
    meals_per_day: "تعداد وعده اصلی معتبر نیست.",
    monthly_food_budget_toman: "بودجه ماهانه را وارد کن.",
    preferred_check_in_time: "زمان یادآوری معتبر نیست.",
  });
});
