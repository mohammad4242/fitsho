import { expect, it, vi } from "vitest";

import type {
  NutritionProfileInput,
  SafetyDecision,
  SafetyProfileInput,
  StructuredExerciseInput,
} from "@fitician/core/nutrition";
import type { ProfileInput, ProfileStatusResponse, SharedProfileInput } from "@fitician/core/profile";

import {
  NativeOnboardingController,
  type OnboardingControllerApi,
} from "./onboardingController";
import type {
  OnboardingDraftLoadResult,
  OnboardingState,
  OnboardingStateStore,
} from "@fitician/core/onboarding";

const shared: SharedProfileInput = {
  birth_date: "1992-05-12",
  current_weight_kg: 64,
  display_name: "Sara",
  fitness_goal: "build_muscle",
  height_cm: 168,
  sex: "female",
};

const training: ProfileInput = {
  ...shared,
  shoulder_circumference_cm: null,
  waist_circumference_cm: null,
  hip_circumference_cm: null,
  experience_level: "beginner",
  training_age_months: null,
  training_days_per_week: 3,
  preferred_weekdays: null,
  priority_muscles: null,
  training_location: "gym",
  home_training_setup: null,
  available_equipment: null,
  session_duration_minutes: 45,
  training_intensity: "moderate",
  training_cautions: [],
  plan_duration_weeks: 4,
};

const safety: SafetyProfileInput = {
  conditions: [],
  medications: [],
  dangerous_food_reaction_history: false,
  pregnant: false,
  breastfeeding: false,
  eating_disorder_diagnosed: false,
  eating_disorder_active_symptoms: false,
  emergency_or_danger_symptoms: false,
  complex_medication_food_interaction: false,
  physician_dietary_restrictions: null,
  other_relevant_condition: null,
};

const exercise: StructuredExerciseInput = { trains: false };

const basics = {
  daily_activity_level: "moderate" as const,
  individual_monthly_food_budget_irr: 30_000_000,
  budget_style: "strict" as const,
  allergies: [],
  intolerances: [],
  dietary_pattern: "omnivore" as const,
};

const nutrition: NutritionProfileInput = {
  daily_activity_level: "moderate",
  individual_monthly_food_budget_irr: 30_000_000,
  budget_style: "strict",
  main_meal_count_bucket: "three_main_meals",
  snack_count_bucket: "one_snack",
  meals_per_day: 3,
  snacks_per_day: 1,
  preferred_plan_start_day: "saturday",
  favourite_foods: [],
  disliked_foods: [],
  allergies: [],
  intolerances: [],
  dietary_pattern: "omnivore",
  religious_cultural_exclusions: [],
  work_shift_context: null,
  daily_check_in_enabled: false,
  preferred_check_in_time: null,
};

const safeDecision: SafetyDecision = {
  id: "decision-1",
  outcome: "standard_automatic",
  policy_version: "safety-v1",
  reason_codes: [],
  requires_physician_review: false,
  can_continue_onboarding: true,
  message: "safe",
  created_at: "2026-09-07T00:00:00Z",
};

function profileStatus(
  completion_state: ProfileStatusResponse["completion_state"],
  product_mode: ProfileStatusResponse["product_mode"] = null,
): ProfileStatusResponse {
  return { user_id: "user-1", product_mode, completion_state };
}

function fakeApi(): OnboardingControllerApi {
  return {
    createNutritionEstimate: vi.fn().mockResolvedValue({}),
    createProfile: vi.fn().mockResolvedValue({}),
    evaluateSafetyProfile: vi.fn().mockResolvedValue(safeDecision),
    getNutritionProfile: vi.fn().mockResolvedValue(null),
    getProfileStatus: vi.fn().mockResolvedValue(profileStatus("product_mode_not_selected")),
    getSafetyDecision: vi.fn().mockResolvedValue(null),
    getSharedProfile: vi.fn().mockResolvedValue(null),
    getStructuredExercise: vi.fn().mockResolvedValue(null),
    saveNutritionProfile: vi.fn().mockResolvedValue({}),
    saveSafetyProfile: vi.fn().mockResolvedValue(safeDecision),
    saveSharedProfile: vi.fn().mockResolvedValue({}),
    saveStructuredExercise: vi.fn().mockResolvedValue({}),
    selectProductMode: vi.fn().mockResolvedValue(profileStatus("shared_profile_incomplete", "training")),
  };
}

function fakeStore(
  loadResult: OnboardingDraftLoadResult = { status: "missing" },
): OnboardingStateStore {
  return {
    clear: vi.fn().mockResolvedValue(undefined),
    load: vi.fn().mockResolvedValue(loadResult),
    save: vi.fn().mockResolvedValue(undefined),
  };
}

async function initialized(
  api: OnboardingControllerApi,
  store: OnboardingStateStore,
): Promise<NativeOnboardingController> {
  const controller = new NativeOnboardingController(api, store);
  await controller.initialize();
  return controller;
}

it("completes the training onboarding flow through the backend and local draft store", async () => {
  const api = fakeApi();
  const store = fakeStore();
  const controller = await initialized(api, store);

  await controller.selectProductMode("training");
  await controller.saveSharedProfile(shared);
  await controller.saveTrainingProfile(training);
  await controller.complete();

  expect(controller.getState().step).toBe("complete");
  expect(api.createProfile).toHaveBeenCalledWith(training);
  expect(store.clear).toHaveBeenCalledOnce();
});

it("keeps a blocked nutrition safety path at the safety step", async () => {
  const api = fakeApi();
  vi.mocked(api.selectProductMode).mockResolvedValue(
    profileStatus("shared_profile_incomplete", "nutrition"),
  );
  const blocked: SafetyDecision = {
    ...safeDecision,
    can_continue_onboarding: false,
    outcome: "physician_manual_plan_required",
  };
  vi.mocked(api.saveSafetyProfile).mockResolvedValue(blocked);
  const controller = await initialized(api, fakeStore());

  await controller.selectProductMode("nutrition");
  await controller.saveSharedProfile(shared);
  const result = await controller.saveNutritionSafety(safety);

  expect(result).toEqual({ blocked: true, decision: blocked, state: controller.getState() });
  expect(controller.getState().step).toBe("nutrition_safety");
});

it("saves nutrition profile, structured exercise, and estimate in the authoritative order", async () => {
  const api = fakeApi();
  vi.mocked(api.selectProductMode).mockResolvedValue(
    profileStatus("shared_profile_incomplete", "nutrition"),
  );
  const store = fakeStore();
  const controller = await initialized(api, store);

  await controller.selectProductMode("nutrition");
  await controller.saveSharedProfile(shared);
  await controller.saveNutritionSafety(safety);
  await controller.saveExerciseContext(exercise);
  await controller.saveNutritionBasics(basics);
  await controller.saveNutritionProfile(nutrition);

  const saveNutritionProfile = vi.mocked(api.saveNutritionProfile);
  const saveStructuredExercise = vi.mocked(api.saveStructuredExercise);
  const createNutritionEstimate = vi.mocked(api.createNutritionEstimate);
  expect(api.saveNutritionProfile).toHaveBeenCalledWith(nutrition);
  expect(api.saveStructuredExercise).toHaveBeenCalledWith(exercise);
  expect(api.createNutritionEstimate).toHaveBeenCalledOnce();
  expect(saveNutritionProfile.mock.invocationCallOrder[0]).toBeLessThan(
    saveStructuredExercise.mock.invocationCallOrder[0],
  );
  expect(saveStructuredExercise.mock.invocationCallOrder[0]).toBeLessThan(
    createNutritionEstimate.mock.invocationCallOrder[0],
  );
  expect(controller.getState().step).toBe("review");
});

it("uses a compatible persisted draft before rebuilding from remote profile status", async () => {
  const api = fakeApi();
  const storedState = {
    schema_version: 1,
    mode: "both",
    step: "training_profile",
    revision: 3,
    shared,
    training: null,
    safety,
    structuredExercise: null,
    nutritionBasics: null,
    nutrition: null,
  } satisfies OnboardingState;
  const store = fakeStore({ status: "valid", savedAt: 1_000, state: storedState });
  vi.mocked(api.getProfileStatus).mockResolvedValue(profileStatus("training_onboarding_incomplete", "both"));

  const controller = await initialized(api, store);

  expect(controller.getState()).toEqual(storedState);
  expect(api.getSharedProfile).not.toHaveBeenCalled();
});
