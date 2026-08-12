import { beforeEach, expect, it, vi } from "vitest";

import * as nutritionApi from "../nutrition/api";
import * as profileApi from "../profile/api";
import { clearOnboardingDraft, HYDRATED_ACCOUNT_KEY, hydrateOnboardingDraft, loadOnboardingDraft, loadPendingNutritionSetup, saveOnboardingDraft } from "./onboardingDraft";

vi.mock("../nutrition/api");
vi.mock("../profile/api");

const trainingInput = {
  display_name: "محمد",
  birth_date: "2000-05-14",
  sex: "male" as const,
  height_cm: 178,
  current_weight_kg: 76,
  shoulder_circumference_cm: null,
  waist_circumference_cm: null,
  hip_circumference_cm: null,
  fitness_goal: "build_muscle" as const,
  experience_level: "beginner" as const,
  training_days_per_week: 3,
  training_location: "gym" as const,
  home_training_setup: null,
  session_duration_minutes: 60 as const,
  physical_limitations: null,
  training_cautions: [],
  plan_duration_weeks: 4 as const,
};

beforeEach(() => {
  sessionStorage.clear();
  vi.clearAllMocks();
  vi.mocked(profileApi.selectProductMode).mockResolvedValue({
    user_id: "u1", product_mode: "training", completion_state: "training_onboarding_incomplete",
  });
  vi.mocked(profileApi.createProfile).mockResolvedValue({
    ...trainingInput,
    user_id: "u1", weight_measured_at: "now", circumferences_measured_at: null,
    created_at: "now", updated_at: "now",
  });
  vi.mocked(nutritionApi.saveSafetyProfile).mockResolvedValue({} as never);
  vi.mocked(nutritionApi.saveNutritionProfile).mockResolvedValue({} as never);
  vi.mocked(nutritionApi.saveStructuredExercise).mockResolvedValue({} as never);
  vi.mocked(nutritionApi.createNutritionEstimate).mockResolvedValue({} as never);
});

it("keeps a pre-auth draft only in the current browser session", () => {
  saveOnboardingDraft({ mode: "training", training: trainingInput });
  expect(loadOnboardingDraft()).toEqual({ mode: "training", training: trainingInput });
  clearOnboardingDraft();
  expect(loadOnboardingDraft()).toBeNull();
});

it("hydrates the selected mode before its profile and clears only after success", async () => {
  const draft = { mode: "training" as const, training: trainingInput };
  saveOnboardingDraft(draft);

  await hydrateOnboardingDraft(draft);

  expect(profileApi.selectProductMode).toHaveBeenCalledWith("training");
  expect(profileApi.createProfile).toHaveBeenCalledWith(trainingInput);
  expect(nutritionApi.saveSafetyProfile).not.toHaveBeenCalled();
  expect(nutritionApi.saveNutritionProfile).not.toHaveBeenCalled();
  expect(sessionStorage.getItem(HYDRATED_ACCOUNT_KEY)).toBe("true");
  expect(loadOnboardingDraft()).toBeNull();
});

it("preserves the draft when server hydration fails", async () => {
  const draft = { mode: "training" as const, training: trainingInput };
  saveOnboardingDraft(draft);
  vi.mocked(profileApi.createProfile).mockRejectedValue(new Error("offline"));

  await expect(hydrateOnboardingDraft(draft)).rejects.toThrow("offline");

  expect(loadOnboardingDraft()).toEqual(draft);
});

it("keeps nutrition safety and basics pending for post-registration completion", async () => {
  const draft = {
    mode: "nutrition" as const,
    shared: {
      display_name: "سارا", birth_date: "2000-05-14", sex: "female" as const,
      height_cm: 165, current_weight_kg: 62.5, fitness_goal: "fat_loss" as const,
    },
    safety: {
      conditions: [], medications: [], dangerous_food_reaction_history: false, pregnant: false,
      breastfeeding: false, eating_disorder_diagnosed: false, eating_disorder_active_symptoms: false,
      emergency_or_danger_symptoms: false, complex_medication_food_interaction: false,
      physician_dietary_restrictions: null, other_relevant_condition: null,
    },
    nutritionBasics: {
      daily_activity_level: "moderate" as const,
      individual_monthly_food_budget_irr: 13_000_000, budget_style: "strict" as const,
      plan_style: "balanced" as const, allergies: [], intolerances: [], dietary_pattern: "omnivore" as const,
    },
    structuredExercise: { trains: false as const },
  };

  await hydrateOnboardingDraft(draft);

  expect(nutritionApi.saveSafetyProfile).not.toHaveBeenCalled();
  expect(nutritionApi.saveNutritionProfile).not.toHaveBeenCalled();
  expect(nutritionApi.saveStructuredExercise).not.toHaveBeenCalled();
  expect(nutritionApi.createNutritionEstimate).not.toHaveBeenCalled();
  expect(loadPendingNutritionSetup()).toEqual({
    safety: draft.safety,
    nutritionBasics: draft.nutritionBasics,
    structuredExercise: draft.structuredExercise,
  });
});
