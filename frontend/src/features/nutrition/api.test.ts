import { afterEach, expect, it, vi } from "vitest";

import {
  createNutritionEstimate,
  createWeeklyNutritionPlan,
  deleteCatalogueFood,
  getCurrentNutritionEstimate,
  getLatestWeeklyNutritionPlan,
  getMealCatalogue,
  getSafetyDecision,
  getStructuredExercise,
  saveNutritionProfile,
  saveSafetyProfile,
  saveStructuredExercise,
  uploadCatalogueFoodImage,
} from "./api";
import type { NutritionProfileInput, SafetyProfileInput } from "./types";

const safetyInput: SafetyProfileInput = {
  conditions: [], medications: [], dangerous_food_reaction_history: false,
  pregnant: false, breastfeeding: false, eating_disorder_diagnosed: false,
  eating_disorder_active_symptoms: false, emergency_or_danger_symptoms: false,
  complex_medication_food_interaction: false, physician_dietary_restrictions: null,
  other_relevant_condition: null,
};

const nutritionInput = {
  daily_activity_level: "moderate",
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
    .mockResolvedValueOnce(Response.json({ ...nutritionInput, currency: "IRR" }))
    .mockResolvedValueOnce(Response.json({ trains: false, source: "user_reported" }))
    .mockResolvedValueOnce(Response.json({ trains: false, source: "user_reported" }))
    .mockResolvedValueOnce(Response.json({ id: "estimate-1" }, { status: 201 }))
    .mockResolvedValueOnce(Response.json({ id: "estimate-1" }))
    .mockResolvedValueOnce(Response.json({ outcome: "success", plan: { id: "plan-1" } }))
    .mockResolvedValueOnce(Response.json({ id: "plan-1" }));

  await saveSafetyProfile(safetyInput);
  await getSafetyDecision();
  await saveNutritionProfile(nutritionInput);
  await saveStructuredExercise({ trains: false });
  await getStructuredExercise();
  await createNutritionEstimate();
  await getCurrentNutritionEstimate();
  await createWeeklyNutritionPlan();
  await getLatestWeeklyNutritionPlan();

  expect(fetch).toHaveBeenNthCalledWith(1, "/api/v1/nutrition/safety", expect.objectContaining({ method: "PUT" }));
  expect(fetch).toHaveBeenNthCalledWith(2, "/api/v1/nutrition/safety", expect.objectContaining({ credentials: "include" }));
  expect(fetch).toHaveBeenNthCalledWith(3, "/api/v1/nutrition/profile", expect.objectContaining({ method: "PUT" }));
  expect(fetch).toHaveBeenNthCalledWith(4, "/api/v1/nutrition/structured-exercise", expect.objectContaining({ method: "PUT" }));
  expect(fetch).toHaveBeenNthCalledWith(5, "/api/v1/nutrition/structured-exercise", expect.objectContaining({ credentials: "include" }));
  expect(fetch).toHaveBeenNthCalledWith(6, "/api/v1/nutrition/estimates", expect.objectContaining({ method: "POST" }));
  expect(fetch).toHaveBeenNthCalledWith(7, "/api/v1/nutrition/estimates/current", expect.objectContaining({ credentials: "include" }));
  expect(fetch).toHaveBeenNthCalledWith(8, "/api/v1/nutrition/plans", expect.objectContaining({ method: "POST" }));
  expect(fetch).toHaveBeenNthCalledWith(9, "/api/v1/nutrition/plans/latest", expect.objectContaining({ credentials: "include" }));
});

it("uploads a catalogue food image as multipart form data", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    Response.json({ image_url: "/media/food-catalogue/chicken.png" }),
  );
  const file = new File(["image"], "chicken.png", { type: "image/png" });

  await uploadCatalogueFoodImage("chicken-breast", file);

  const requestInit = vi.mocked(fetch).mock.calls[0]?.[1];
  expect(requestInit).toBeDefined();
  if (!requestInit) throw new Error("Expected upload request options");
  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/nutrition/admin/foods/chicken-breast/image",
    expect.objectContaining({ method: "POST", credentials: "include" }),
  );
  expect(requestInit.body).toBeInstanceOf(FormData);
  expect((requestInit.body as FormData).get("file")).toBe(file);
  expect(new Headers(requestInit.headers).has("Content-Type")).toBe(false);
});

it("deletes a catalogue food through the admin endpoint", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(null, { status: 204 }));

  await deleteCatalogueFood("chicken-breast");

  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/nutrition/admin/foods/chicken-breast",
    expect.objectContaining({ method: "DELETE", credentials: "include" }),
  );
  const requestInit = vi.mocked(fetch).mock.calls[0]?.[1];
  expect(requestInit?.body).toBeUndefined();
});

it("fetches the member meal catalogue without category filter", async () => {
  const fakeResponse = { items: [], categories: ["breakfast", "lunch"] };
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json(fakeResponse));

  const result = await getMealCatalogue();

  expect(result).toEqual(fakeResponse);
  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/nutrition/meal-catalogue",
    expect.objectContaining({ credentials: "include" }),
  );
});

it("fetches the member meal catalogue with category query parameter", async () => {
  const fakeResponse = { items: [], categories: ["breakfast", "lunch"] };
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json(fakeResponse));

  const result = await getMealCatalogue("breakfast");

  expect(result).toEqual(fakeResponse);
  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/nutrition/meal-catalogue?category=breakfast",
    expect.objectContaining({ credentials: "include" }),
  );
});
