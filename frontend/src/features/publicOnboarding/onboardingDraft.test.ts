import { beforeEach, expect, it, vi } from "vitest";

import * as profileApi from "../profile/api";
import { clearOnboardingDraft, hydrateOnboardingDraft, loadOnboardingDraft, saveOnboardingDraft } from "./onboardingDraft";

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
  expect(loadOnboardingDraft()).toBeNull();
});

it("preserves the draft when server hydration fails", async () => {
  const draft = { mode: "training" as const, training: trainingInput };
  saveOnboardingDraft(draft);
  vi.mocked(profileApi.createProfile).mockRejectedValue(new Error("offline"));

  await expect(hydrateOnboardingDraft(draft)).rejects.toThrow("offline");

  expect(loadOnboardingDraft()).toEqual(draft);
});
