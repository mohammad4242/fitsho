import { expect, it, vi } from "vitest";

import { createInitialOnboardingState, transitionOnboardingState, type OnboardingState } from "@fitician/core/onboarding";
import type { ProfileInput, ProfileStatusResponse, SharedProfileInput } from "@fitician/core/profile";
import type { SafetyDecision, SafetyProfileInput } from "@fitician/core/nutrition";
import type { NutritionBasicsDraft } from "@fitician/core/onboarding";

import { NativeOnboardingController, type OnboardingControllerApi } from "./onboardingController";
import { hydratePublicOnboardingState } from "./publicOnboardingHandoff";
import type { OnboardingStateStore } from "@fitician/core/onboarding";

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
  experience_level: "beginner" as const,
  training_age_months: null,
  training_days_per_week: 3,
  preferred_weekdays: null,
  priority_muscles: null,
  training_location: "gym" as const,
  home_training_setup: null,
  available_equipment: null,
  session_duration_minutes: 45,
  training_intensity: "moderate" as const,
  training_cautions: [],
  plan_duration_weeks: 4,
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

const nutritionBasics: NutritionBasicsDraft = {
  daily_activity_level: "moderate",
  individual_monthly_food_budget_irr: 50_000_000,
  budget_style: "strict",
  plan_style: "balanced",
  allergies: [],
  intolerances: [],
  dietary_pattern: "omnivore",
};

function status(completion_state: ProfileStatusResponse["completion_state"], product_mode: ProfileStatusResponse["product_mode"] = null): ProfileStatusResponse {
  return { user_id: "user-1", product_mode, completion_state };
}

function store(): OnboardingStateStore {
  return {
    clear: vi.fn().mockResolvedValue(undefined),
    load: vi.fn().mockResolvedValue({ status: "missing" }),
    save: vi.fn().mockResolvedValue(undefined),
  };
}

function api(): OnboardingControllerApi {
  return {
    createNutritionEstimate: vi.fn().mockResolvedValue({}),
    createProfile: vi.fn().mockResolvedValue({}),
    evaluateSafetyProfile: vi.fn().mockResolvedValue(safeDecision),
    getNutritionProfile: vi.fn().mockResolvedValue(null),
    getProfileStatus: vi.fn().mockResolvedValue(status("product_mode_not_selected")),
    getSafetyDecision: vi.fn().mockResolvedValue(null),
    getSharedProfile: vi.fn().mockResolvedValue(null),
    getStructuredExercise: vi.fn().mockResolvedValue(null),
    saveNutritionProfile: vi.fn().mockResolvedValue({}),
    saveSafetyProfile: vi.fn().mockResolvedValue(safeDecision),
    saveSharedProfile: vi.fn().mockResolvedValue({}),
    saveStructuredExercise: vi.fn().mockResolvedValue({}),
    selectProductMode: vi.fn().mockImplementation(async (mode: "training" | "nutrition" | "both") => status("shared_profile_incomplete", mode)),
  };
}

async function initialized(activeApi: OnboardingControllerApi): Promise<NativeOnboardingController> {
  const controller = new NativeOnboardingController(activeApi, store());
  await controller.initialize();
  return controller;
}

function trainingReviewState(): OnboardingState {
  let state = createInitialOnboardingState();
  state = transitionOnboardingState(state, { mode: "training", type: "select_product_mode" });
  state = transitionOnboardingState(state, { profile: shared, type: "save_shared_profile" });
  return transitionOnboardingState(state, { profile: training, type: "save_training_profile" });
}

function nutritionPreferencesState(): OnboardingState {
  let state = createInitialOnboardingState();
  state = transitionOnboardingState(state, { mode: "nutrition", type: "select_product_mode" });
  state = transitionOnboardingState(state, { profile: shared, type: "save_shared_profile" });
  state = transitionOnboardingState(state, { safety: safeDecisionInput(), type: "save_nutrition_safety" });
  state = transitionOnboardingState(state, { exercise: { trains: false }, type: "save_exercise_context" });
  return transitionOnboardingState(state, { basics: nutritionBasics, type: "save_nutrition_basics" });
}

function safeDecisionInput(): SafetyProfileInput {
  return {
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
}

it("hydrates a public training draft through the same controller order", async () => {
  const activeApi = api();
  const controller = await initialized(activeApi);

  const result = await hydratePublicOnboardingState(controller, trainingReviewState());

  expect(result.step).toBe("complete");
  expect(activeApi.selectProductMode).toHaveBeenCalledWith("training");
  expect(activeApi.saveSharedProfile).toHaveBeenCalledWith(shared);
  expect(activeApi.createProfile).toHaveBeenCalledWith(training);
  expect(vi.mocked(activeApi.selectProductMode).mock.invocationCallOrder[0]).toBeLessThan(
    vi.mocked(activeApi.saveSharedProfile).mock.invocationCallOrder[0],
  );
  expect(vi.mocked(activeApi.saveSharedProfile).mock.invocationCallOrder[0]).toBeLessThan(
    vi.mocked(activeApi.createProfile).mock.invocationCallOrder[0],
  );
});

it("does not overwrite a completed member when a public draft remains on the device", async () => {
  const activeApi = api();
  vi.mocked(activeApi.getProfileStatus).mockResolvedValue(status("training_ready", "training"));
  const controller = await initialized(activeApi);

  const result = await hydratePublicOnboardingState(controller, trainingReviewState());

  expect(result.step).toBe("complete");
  expect(activeApi.selectProductMode).not.toHaveBeenCalled();
  expect(activeApi.createProfile).not.toHaveBeenCalled();
});

it("hydrates a public nutrition draft to authenticated nutrition preferences", async () => {
  const activeApi = api();
  const controller = await initialized(activeApi);

  const result = await hydratePublicOnboardingState(controller, nutritionPreferencesState());

  expect(result.step).toBe("nutrition_preferences");
  expect(activeApi.selectProductMode).toHaveBeenCalledWith("nutrition");
  expect(activeApi.saveSharedProfile).toHaveBeenCalledWith(shared);
  expect(activeApi.saveSafetyProfile).toHaveBeenCalledWith(safeDecisionInput());
  expect(activeApi.saveNutritionProfile).not.toHaveBeenCalled();
  expect(activeApi.createNutritionEstimate).not.toHaveBeenCalled();
});

it("rejects a public handoff before all required answers are present", async () => {
  const controller = await initialized(api());
  const incomplete = transitionOnboardingState(createInitialOnboardingState(), {
    mode: "training",
    type: "select_product_mode",
  });

  await expect(hydratePublicOnboardingState(controller, incomplete)).rejects.toThrow(
    "Public onboarding draft is incomplete",
  );
});
