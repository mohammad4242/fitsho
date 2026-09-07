import {
  createInitialOnboardingState,
  getOnboardingSteps,
  transitionOnboardingState,
  type OnboardingState,
} from "@fitician/core";
import type { NutritionBasicsDraft } from "@fitician/core/onboarding";
import type {
  SafetyDecision,
  SafetyProfileInput,
  StructuredExerciseInput,
} from "@fitician/core/nutrition";
import type { ProfileCompletionState, ProductMode, ProfileInput, SharedProfileInput } from "@fitician/core/profile";
import type { NutritionProfileInput } from "@fitician/core/nutrition";

import type { OnboardingApi } from "./onboardingApi";
import type { OnboardingStateStore } from "@fitician/core/onboarding";

export type OnboardingControllerApi = OnboardingApi;

export type NutritionSafetyResult = {
  readonly blocked: boolean;
  readonly decision: SafetyDecision;
  readonly state: OnboardingState;
};

function stepForRemoteStatus(
  mode: ProductMode,
  completionState: ProfileCompletionState,
): OnboardingState["step"] {
  if (completionState === "training_onboarding_incomplete") {
    return mode === "nutrition" ? "exercise_context" : "training_profile";
  }
  if (completionState === "medical_review_information_incomplete") return "nutrition_safety";
  if (
    completionState === "nutrition_onboarding_incomplete"
    || completionState === "nutrition_draft_ready"
  ) {
    return "nutrition_preferences";
  }
  if (
    completionState === "training_ready"
    || completionState === "nutrition_pending_review"
    || completionState === "nutrition_ready"
    || completionState === "both_ready"
  ) {
    return "complete";
  }
  return "shared_profile";
}

export function onboardingStateForRemoteStatus(
  productMode: ProductMode | null,
  completionState: ProfileCompletionState,
): OnboardingState {
  if (productMode === null || completionState === "product_mode_not_selected") {
    return createInitialOnboardingState();
  }
  const selected = transitionOnboardingState(createInitialOnboardingState(), {
    type: "select_product_mode",
    mode: productMode,
  });
  const step = stepForRemoteStatus(productMode, completionState);
  return {
    ...selected,
    step: getOnboardingSteps(productMode).includes(step) ? step : "shared_profile",
  };
}

function sharedInputFromResponse(
  shared: Awaited<ReturnType<OnboardingApi["getSharedProfile"]>>,
): SharedProfileInput | null {
  if (shared === null) return null;
  return {
    birth_date: shared.birth_date,
    current_weight_kg: shared.current_weight_kg,
    display_name: shared.display_name,
    fitness_goal: shared.fitness_goal,
    height_cm: shared.height_cm,
    sex: shared.sex,
  };
}

export class NativeOnboardingController {
  private state: OnboardingState = createInitialOnboardingState();

  constructor(
    private readonly api: OnboardingControllerApi,
    private readonly store: OnboardingStateStore,
  ) {}

  getState(): OnboardingState {
    return this.state;
  }

  async initialize(): Promise<OnboardingState> {
    const stored = await this.store.load();
    let remoteState: OnboardingState | null = null;
    try {
      const status = await this.api.getProfileStatus();
      remoteState = onboardingStateForRemoteStatus(status.product_mode, status.completion_state);
    } catch (error) {
      if (stored.status === "valid") {
        this.state = stored.state;
        return this.state;
      }
      throw error;
    }

    if (
      stored.status === "valid"
      && stored.state.mode === remoteState.mode
      && remoteState.step !== "complete"
    ) {
      this.state = stored.state;
      return this.state;
    }

    if (stored.status === "valid" && stored.state.mode !== remoteState.mode) {
      await this.store.clear();
    }

    this.state = remoteState;
    if (this.state.mode !== null && this.state.shared === null) {
      const shared = sharedInputFromResponse(await this.api.getSharedProfile());
      if (shared !== null) {
        this.state = { ...this.state, revision: this.state.revision + 1, shared };
      }
    }
    await this.store.save(this.state);
    return this.state;
  }

  async selectProductMode(mode: ProductMode): Promise<OnboardingState> {
    const response = await this.api.selectProductMode(mode);
    if (response.product_mode !== mode) {
      throw new Error("Backend returned a different product mode");
    }
    return this.commit({ type: "select_product_mode", mode });
  }

  async saveSharedProfile(profile: SharedProfileInput): Promise<OnboardingState> {
    await this.api.saveSharedProfile(profile);
    return this.commit({ type: "save_shared_profile", profile });
  }

  async saveNutritionSafety(safety: SafetyProfileInput): Promise<NutritionSafetyResult> {
    const decision = await this.api.saveSafetyProfile(safety);
    if (!decision.can_continue_onboarding) {
      return { blocked: true, decision, state: this.state };
    }
    const state = await this.commit({ type: "save_nutrition_safety", safety });
    return { blocked: false, decision, state };
  }

  async saveTrainingProfile(profile: ProfileInput): Promise<OnboardingState> {
    await this.api.createProfile(profile);
    return this.commit({ type: "save_training_profile", profile });
  }

  async saveExerciseContext(
    exercise: StructuredExerciseInput,
  ): Promise<OnboardingState> {
    return this.commit({ type: "save_exercise_context", exercise });
  }

  async saveNutritionBasics(
    basics: NutritionBasicsDraft,
  ): Promise<OnboardingState> {
    return this.commit({ type: "save_nutrition_basics", basics });
  }

  async saveNutritionProfile(
    profile: NutritionProfileInput,
  ): Promise<OnboardingState> {
    if (this.state.mode === "nutrition" && this.state.structuredExercise === null) {
      throw new Error("Structured exercise is required before saving nutrition");
    }
    await this.api.saveNutritionProfile(profile);
    if (this.state.mode === "nutrition") {
      const exercise = this.state.structuredExercise;
      if (exercise === null) {
        throw new Error("Structured exercise is required before saving nutrition");
      }
      await this.api.saveStructuredExercise(exercise);
    }
    await this.api.createNutritionEstimate();
    return this.commit({ type: "save_nutrition_profile", profile });
  }

  async complete(): Promise<OnboardingState> {
    const next = transitionOnboardingState(this.state, { type: "complete" });
    await this.store.clear();
    this.state = next;
    return this.state;
  }

  async goBack(): Promise<OnboardingState> {
    return this.commit({ type: "back" });
  }

  private async commit(event: Parameters<typeof transitionOnboardingState>[1]): Promise<OnboardingState> {
    const next = transitionOnboardingState(this.state, event);
    await this.store.save(next);
    this.state = next;
    return this.state;
  }
}
