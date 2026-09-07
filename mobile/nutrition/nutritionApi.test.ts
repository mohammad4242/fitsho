import { expect, it, vi } from "vitest";

import { ApiError, type TransportRequest } from "@fitician/core";

import { createNutritionApi, type NutritionProfileInput } from "./nutritionApi";

it("uses the member nutrition profile, safety, exercise, and estimate endpoints", async () => {
  const requests: TransportRequest[] = [];
  const api = createNutritionApi(async <TResponse>(request: TransportRequest) => {
    requests.push(request);
    return {} as TResponse;
  });
  const safety = {
    breastfeeding: false,
    complex_medication_food_interaction: false,
    conditions: [],
    dangerous_food_reaction_history: false,
    eating_disorder_active_symptoms: false,
    eating_disorder_diagnosed: false,
    emergency_or_danger_symptoms: false,
    medications: [],
    pregnant: false,
  };
  const structuredExercise = { trains: false };
  const nutritionProfile: NutritionProfileInput = {
    accepts_batch_cooking: false,
    accepts_leftovers: true,
    budget_style: "flexible",
    cooking_frequency_per_week: 0,
    cooking_skill: "none",
    daily_activity_level: "sedentary",
    daily_check_in_enabled: false,
    dietary_pattern: "omnivore",
    freezer_access: true,
    individual_monthly_food_budget_irr: 1_000_000,
    maximum_cooking_time_minutes: 0,
    maximum_meal_repetition_per_week: 3,
    meal_preparation_preference: "no_cooking",
    plan_style: "balanced",
    preferred_plan_start_day: "saturday",
    preferred_variety: "medium",
    refrigerator_access: true,
    supplied_meals_per_week: 0,
    weight_rate_mode: "safe",
    favourite_foods: [],
    disliked_foods: [],
    allergies: [],
    intolerances: [],
    religious_cultural_exclusions: [],
    work_shift_context: null,
    meals_per_day: 3,
    snacks_per_day: 0,
    preferred_check_in_time: null,
  };

  await api.evaluateSafety(safety);
  await api.getSafety();
  await api.saveSafety(safety);
  await api.getNutritionProfile();
  await api.saveNutritionProfile(nutritionProfile);
  await api.getStructuredExercise();
  await api.saveStructuredExercise(structuredExercise);
  await api.getCurrentEstimate();
  await api.generateEstimate();
  await api.getReviewRequirement();

  expect(requests).toEqual([
    {
      body: safety,
      method: "POST",
      path: "/api/v1/nutrition/safety/evaluate",
    },
    { method: "GET", path: "/api/v1/nutrition/safety" },
    {
      body: safety,
      method: "PUT",
      path: "/api/v1/nutrition/safety",
    },
    { method: "GET", path: "/api/v1/nutrition/profile" },
    {
      body: nutritionProfile,
      method: "PUT",
      path: "/api/v1/nutrition/profile",
    },
    { method: "GET", path: "/api/v1/nutrition/structured-exercise" },
    {
      body: structuredExercise,
      method: "PUT",
      path: "/api/v1/nutrition/structured-exercise",
    },
    { method: "GET", path: "/api/v1/nutrition/estimates/current" },
    { method: "POST", path: "/api/v1/nutrition/estimates" },
    { method: "GET", path: "/api/v1/nutrition/review-requirement" },
  ]);
});

it("treats only missing optional nutrition resources as absent", async () => {
  const request = vi.fn().mockRejectedValue(new ApiError(404, "Not found"));
  const api = createNutritionApi(request);

  await expect(api.getNutritionProfile()).resolves.toBeNull();
  await expect(api.getSafety()).resolves.toBeNull();
  await expect(api.getStructuredExercise()).resolves.toBeNull();
  await expect(api.getCurrentEstimate()).resolves.toBeNull();
  await expect(api.getReviewRequirement()).resolves.toBeNull();
});

it("preserves non-404 nutrition failures", async () => {
  const request = vi.fn().mockRejectedValue(new ApiError(503, "Unavailable"));
  const api = createNutritionApi(request);

  await expect(api.getSafety()).rejects.toMatchObject({ status: 503 });
});
