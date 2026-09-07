import { expect, it } from "vitest";

import {
  createInitialOnboardingState,
  deserializeOnboardingState,
  getOnboardingSteps,
  serializeOnboardingState,
  transitionOnboardingState,
} from "@fitician/core/onboarding";
import type { SafetyProfileInput } from "@fitician/core/nutrition";
import type { SharedProfileInput } from "@fitician/core/profile";

const shared: SharedProfileInput = {
  display_name: "Sara",
  birth_date: "1992-05-12",
  sex: "female",
  height_cm: 168,
  current_weight_kg: 64,
  fitness_goal: "build_muscle",
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

it("starts at mode selection and exposes the exact steps for each product mode", () => {
  const initial = createInitialOnboardingState();

  expect(initial).toMatchObject({ mode: null, step: "product_mode", revision: 0 });
  expect(getOnboardingSteps("training")).toEqual([
    "product_mode",
    "shared_profile",
    "training_profile",
    "review",
    "complete",
  ]);
  expect(getOnboardingSteps("nutrition")).toEqual([
    "product_mode",
    "shared_profile",
    "nutrition_safety",
    "exercise_context",
    "nutrition_basics",
    "nutrition_preferences",
    "review",
    "complete",
  ]);
  expect(getOnboardingSteps("both")).toEqual([
    "product_mode",
    "shared_profile",
    "nutrition_safety",
    "training_profile",
    "nutrition_basics",
    "nutrition_preferences",
    "review",
    "complete",
  ]);
});

it("moves through the combined flow and preserves a resumable immutable state", () => {
  const selected = transitionOnboardingState(createInitialOnboardingState(), {
    type: "select_product_mode",
    mode: "both",
  });
  const sharedSaved = transitionOnboardingState(selected, {
    type: "save_shared_profile",
    profile: shared,
  });
  const safetySaved = transitionOnboardingState(sharedSaved, {
    type: "save_nutrition_safety",
    safety,
  });

  expect(selected).toMatchObject({ mode: "both", step: "shared_profile", revision: 1 });
  expect(sharedSaved).toMatchObject({
    mode: "both",
    step: "nutrition_safety",
    shared,
    revision: 2,
  });
  expect(safetySaved).toMatchObject({
    mode: "both",
    step: "training_profile",
    shared,
    safety,
    revision: 3,
  });
  expect(sharedSaved).not.toBe(safetySaved);
});

it("supports wizard back navigation without changing saved answers", () => {
  const selected = transitionOnboardingState(createInitialOnboardingState(), {
    type: "select_product_mode",
    mode: "nutrition",
  });
  const sharedSaved = transitionOnboardingState(selected, {
    type: "save_shared_profile",
    profile: shared,
  });
  const safetySaved = transitionOnboardingState(sharedSaved, {
    type: "save_nutrition_safety",
    safety,
  });
  const returnedToSafety = transitionOnboardingState(safetySaved, { type: "back" });
  const returned = transitionOnboardingState(returnedToSafety, { type: "back" });

  expect(returned).toMatchObject({
    mode: "nutrition",
    step: "shared_profile",
    shared,
    safety,
  });
  expect(returned.revision).toBe(safetySaved.revision + 2);
});

it("rejects events that do not match the current mode or step", () => {
  const state = transitionOnboardingState(createInitialOnboardingState(), {
    type: "select_product_mode",
    mode: "training",
  });

  expect(() => transitionOnboardingState(state, { type: "complete" })).toThrow(
    "Onboarding event is not valid for the current step",
  );
  expect(() => transitionOnboardingState(state, { type: "save_nutrition_safety", safety })).toThrow(
    "Onboarding event is not valid for the selected product mode",
  );
  expect(() => transitionOnboardingState(createInitialOnboardingState(), { type: "back" })).toThrow(
    "Onboarding step has no previous step",
  );
});

it("round-trips only compatible versioned states and rejects incompatible drafts", () => {
  const state = transitionOnboardingState(createInitialOnboardingState(), {
    type: "select_product_mode",
    mode: "training",
  });
  const serialized = serializeOnboardingState(state);

  expect(deserializeOnboardingState(serialized)).toEqual(state);
  expect(deserializeOnboardingState("not-json")).toBeNull();
  expect(deserializeOnboardingState(JSON.stringify({ ...state, schema_version: 99 }))).toBeNull();
  expect(
    deserializeOnboardingState(JSON.stringify({ ...state, mode: "nutrition", step: "training_profile" })),
  ).toBeNull();
});
