import { afterEach, expect, it, vi } from "vitest";

import { getSafetyDecision, saveNutritionProfile, saveSafetyProfile } from "./api";
import type { NutritionProfileInput, SafetyProfileInput } from "./types";

const safetyInput: SafetyProfileInput = {
  conditions: [], medications: [], dangerous_food_reaction_history: false,
  pregnant: false, breastfeeding: false, eating_disorder_diagnosed: false,
  eating_disorder_active_symptoms: false, emergency_or_danger_symptoms: false,
  complex_medication_food_interaction: false, physician_dietary_restrictions: null,
  other_relevant_condition: null,
};

const nutritionInput = {
  individual_monthly_food_budget_irr: 13_000_000, budget_style: "strict",
  meals_per_day: 3, snacks_per_day: 1, preferred_plan_start_day: "saturday",
  plan_style: "balanced", cooking_skill: "basic", maximum_cooking_time_minutes: 45,
  cooking_frequency_per_week: 4, meal_preparation_preference: "mixed",
  refrigerator_access: true, freezer_access: true, cooking_equipment: ["stove"],
  supplied_meals_per_week: 0, supplied_meal_source: null, foods_available_at_home: [],
  favourite_foods: [], disliked_foods: [], never_suggest_foods: [], refused_foods: [],
  allergies: [], intolerances: [], dietary_pattern: "omnivore", religious_cultural_exclusions: [],
  preferred_variety: "medium", maximum_meal_repetition_per_week: 2,
  accepts_leftovers: true, accepts_batch_cooking: true, work_shift_context: null,
  daily_check_in_enabled: false, preferred_check_in_time: null,
} satisfies NutritionProfileInput;

afterEach(() => vi.restoreAllMocks());

it("uses the dedicated safety and nutrition endpoints", async () => {
  const decision = { id: "1", outcome: "standard_automatic" };
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json(decision))
    .mockResolvedValueOnce(Response.json(decision))
    .mockResolvedValueOnce(Response.json({ ...nutritionInput, currency: "IRR" }));

  await saveSafetyProfile(safetyInput);
  await getSafetyDecision();
  await saveNutritionProfile(nutritionInput);

  expect(fetch).toHaveBeenNthCalledWith(1, "/api/v1/nutrition/safety", expect.objectContaining({ method: "PUT" }));
  expect(fetch).toHaveBeenNthCalledWith(2, "/api/v1/nutrition/safety", expect.objectContaining({ credentials: "include" }));
  expect(fetch).toHaveBeenNthCalledWith(3, "/api/v1/nutrition/profile", expect.objectContaining({ method: "PUT" }));
});
