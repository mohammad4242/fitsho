import { expect, it } from "vitest";

import {
  exerciseInputFromForm,
  nutritionInputFromForms,
  safetyInputFromForm,
  type ExerciseFormValues,
  type NutritionBasicsFormValues,
  type NutritionPreferencesFormValues,
  type SafetyFormValues,
} from "./onboardingModel";

it("normalizes safety text fields and preserves every safety flag", () => {
  const values: SafetyFormValues = {
    conditions: "دیابت، other",
    medications: "Metformin, Vitamin D",
    dangerous_food_reaction_history: true,
    pregnant: false,
    breastfeeding: false,
    eating_disorder_diagnosed: false,
    eating_disorder_active_symptoms: false,
    emergency_or_danger_symptoms: false,
    complex_medication_food_interaction: true,
    physician_dietary_restrictions: "  no raw grapefruit  ",
    other_relevant_condition: "",
  };

  expect(safetyInputFromForm(values)).toEqual({
    conditions: [
      { code: "other", details: null },
    ],
    medications: [
      { name: "Metformin", dosage: null, notes: null },
      { name: "Vitamin D", dosage: null, notes: null },
    ],
    dangerous_food_reaction_history: true,
    pregnant: false,
    breastfeeding: false,
    eating_disorder_diagnosed: false,
    eating_disorder_active_symptoms: false,
    emergency_or_danger_symptoms: false,
    complex_medication_food_interaction: true,
    physician_dietary_restrictions: "no raw grapefruit",
    other_relevant_condition: null,
  });
});

it("does not submit exercise details when the user does not train", () => {
  const values: ExerciseFormValues = {
    trains: false,
    exercise_type: "mixed",
    days_per_week: "4",
    minutes_per_session: "60",
    intensity: "vigorous",
  };

  expect(exerciseInputFromForm(values)).toEqual({ trains: false });
});

it("maps nutrition basics and preferences into the backend nutrition contract", () => {
  const basics: NutritionBasicsFormValues = {
    daily_activity_level: "moderate",
    monthly_food_budget_toman: "۳۰۰۰۰۰۰",
    budget_style: "strict",
    target_weight_change_kg_per_week: "۰٫۵",
    weight_rate_mode: "safe",
    allergies: "peanut، shrimp",
    intolerances: "lactose",
    dietary_pattern: "omnivore",
  };
  const preferences: NutritionPreferencesFormValues = {
    meals_per_day: "3",
    snacks_per_day: "1",
    preferred_plan_start_day: "saturday",
    favourite_foods: "rice, chicken",
    disliked_foods: "coriander",
    religious_cultural_exclusions: "",
    work_shift_context: "",
    daily_check_in_enabled: false,
    preferred_check_in_time: "21:00",
  };

  expect(nutritionInputFromForms(basics, preferences)).toEqual(expect.objectContaining({
    daily_activity_level: "moderate",
    individual_monthly_food_budget_irr: 30_000_000,
    target_weight_change_kg_per_week: 0.5,
    weight_rate_mode: "safe",
    main_meal_count_bucket: "three_main_meals",
    snack_count_bucket: "one_snack",
    meals_per_day: 3,
    snacks_per_day: 1,
    allergies: [{ name: "peanut", details: null }, { name: "shrimp", details: null }],
    intolerances: [{ name: "lactose", details: null }],
    favourite_foods: ["rice", "chicken"],
    preferred_check_in_time: null,
  }));
});
