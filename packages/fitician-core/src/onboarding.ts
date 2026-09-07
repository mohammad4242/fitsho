import type {
  NutritionProfileInput,
  SafetyProfileInput,
  StructuredExerciseInput,
} from "./nutrition.js";
import type { ProductMode, ProfileInput, SharedProfileInput } from "./profile.js";

export const ONBOARDING_STATE_VERSION = 1 as const;
export const ONBOARDING_DRAFT_MAX_AGE_MILLISECONDS = 30 * 24 * 60 * 60 * 1_000;

export type OnboardingStep =
  | "product_mode"
  | "shared_profile"
  | "nutrition_safety"
  | "training_profile"
  | "exercise_context"
  | "nutrition_basics"
  | "nutrition_preferences"
  | "review"
  | "complete";

export type NutritionBasicsDraft = Pick<
  NutritionProfileInput,
  | "daily_activity_level"
  | "individual_monthly_food_budget_irr"
  | "budget_style"
  | "plan_style"
  | "allergies"
  | "intolerances"
  | "dietary_pattern"
> & {
  target_weight_change_kg_per_week?: number | null;
  weight_rate_mode?: "safe" | "user_override";
};

export type OnboardingState = {
  readonly schema_version: typeof ONBOARDING_STATE_VERSION;
  readonly mode: ProductMode | null;
  readonly step: OnboardingStep;
  readonly revision: number;
  readonly shared: SharedProfileInput | null;
  readonly training: ProfileInput | null;
  readonly safety: SafetyProfileInput | null;
  readonly structuredExercise: StructuredExerciseInput | null;
  readonly nutritionBasics: NutritionBasicsDraft | null;
  readonly nutrition: NutritionProfileInput | null;
};

export type OnboardingEvent =
  | { readonly type: "select_product_mode"; readonly mode: ProductMode }
  | { readonly type: "save_shared_profile"; readonly profile: SharedProfileInput }
  | { readonly type: "save_nutrition_safety"; readonly safety: SafetyProfileInput }
  | { readonly type: "save_training_profile"; readonly profile: ProfileInput }
  | { readonly type: "save_exercise_context"; readonly exercise: StructuredExerciseInput }
  | { readonly type: "save_nutrition_basics"; readonly basics: NutritionBasicsDraft }
  | { readonly type: "save_nutrition_profile"; readonly profile: NutritionProfileInput }
  | { readonly type: "complete" }
  | { readonly type: "back" }
  | { readonly type: "reset" };

export type OnboardingDraftLoadResult =
  | { readonly status: "missing" }
  | { readonly status: "valid"; readonly state: OnboardingState; readonly savedAt: number }
  | { readonly status: "incompatible"; readonly savedAt: number }
  | { readonly status: "stale"; readonly savedAt: number };

export interface OnboardingStateStore {
  load(): Promise<OnboardingDraftLoadResult>;
  save(state: OnboardingState): Promise<void>;
  clear(): Promise<void>;
}

export type OnboardingTransitionErrorCode =
  | "invalid_state"
  | "invalid_step"
  | "invalid_mode"
  | "no_previous_step";

export class OnboardingTransitionError extends Error {
  readonly code: OnboardingTransitionErrorCode;

  constructor(code: OnboardingTransitionErrorCode, message: string) {
    super(message);
    this.name = "OnboardingTransitionError";
    this.code = code;
  }
}

const trainingSteps: readonly OnboardingStep[] = [
  "product_mode",
  "shared_profile",
  "training_profile",
  "review",
  "complete",
];

const nutritionSteps: readonly OnboardingStep[] = [
  "product_mode",
  "shared_profile",
  "nutrition_safety",
  "exercise_context",
  "nutrition_basics",
  "nutrition_preferences",
  "review",
  "complete",
];

const combinedSteps: readonly OnboardingStep[] = [
  "product_mode",
  "shared_profile",
  "nutrition_safety",
  "training_profile",
  "nutrition_basics",
  "nutrition_preferences",
  "review",
  "complete",
];

const productModes: readonly ProductMode[] = ["training", "nutrition", "both"];

export function createInitialOnboardingState(): OnboardingState {
  return {
    schema_version: ONBOARDING_STATE_VERSION,
    mode: null,
    step: "product_mode",
    revision: 0,
    shared: null,
    training: null,
    safety: null,
    structuredExercise: null,
    nutritionBasics: null,
    nutrition: null,
  };
}

export function getOnboardingSteps(mode: ProductMode): readonly OnboardingStep[] {
  if (mode === "training") return trainingSteps;
  if (mode === "nutrition") return nutritionSteps;
  return combinedSteps;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isProductMode(value: unknown): value is ProductMode {
  return typeof value === "string" && productModes.includes(value as ProductMode);
}

function isStep(value: unknown): value is OnboardingStep {
  return (
    value === "product_mode"
    || value === "shared_profile"
    || value === "nutrition_safety"
    || value === "training_profile"
    || value === "exercise_context"
    || value === "nutrition_basics"
    || value === "nutrition_preferences"
    || value === "review"
    || value === "complete"
  );
}

function isNullableRecord(value: unknown): boolean {
  return value === null || isRecord(value);
}

export function isOnboardingState(value: unknown): value is OnboardingState {
  if (!isRecord(value)) return false;
  if (value.schema_version !== ONBOARDING_STATE_VERSION) return false;
  if (!isStep(value.step)) return false;
  if (!Number.isInteger(value.revision) || (value.revision as number) < 0) return false;
  if (
    !isNullableRecord(value.shared)
    || !isNullableRecord(value.training)
    || !isNullableRecord(value.safety)
    || !isNullableRecord(value.structuredExercise)
    || !isNullableRecord(value.nutritionBasics)
    || !isNullableRecord(value.nutrition)
  ) {
    return false;
  }

  if (value.mode === null) {
    return (
      value.step === "product_mode"
      && value.shared === null
      && value.training === null
      && value.safety === null
      && value.structuredExercise === null
      && value.nutritionBasics === null
      && value.nutrition === null
    );
  }
  return isProductMode(value.mode) && getOnboardingSteps(value.mode).includes(value.step);
}

export function serializeOnboardingState(state: OnboardingState): string {
  if (!isOnboardingState(state)) {
    throw new OnboardingTransitionError("invalid_state", "Onboarding state is not compatible");
  }
  return JSON.stringify(state);
}

export function deserializeOnboardingState(serialized: string): OnboardingState | null {
  try {
    const parsed: unknown = JSON.parse(serialized);
    return isOnboardingState(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function nextRevision(state: OnboardingState, changes: Partial<OnboardingState>): OnboardingState {
  return { ...state, ...changes, revision: state.revision + 1 };
}

function requireMode(state: OnboardingState): ProductMode {
  if (state.mode === null) {
    throw new OnboardingTransitionError("invalid_mode", "Select a product mode before continuing");
  }
  return state.mode;
}

function requireStep(state: OnboardingState, step: OnboardingStep): void {
  if (state.step !== step) {
    throw new OnboardingTransitionError(
      "invalid_step",
      "Onboarding event is not valid for the current step",
    );
  }
}

function requireModeStep(state: OnboardingState, modes: readonly ProductMode[], step: OnboardingStep): ProductMode {
  const mode = requireMode(state);
  if (!modes.includes(mode)) {
    throw new OnboardingTransitionError(
      "invalid_mode",
      "Onboarding event is not valid for the selected product mode",
    );
  }
  requireStep(state, step);
  return mode;
}

function previousStep(state: OnboardingState): OnboardingStep {
  if (state.step === "product_mode") {
    throw new OnboardingTransitionError("no_previous_step", "Onboarding step has no previous step");
  }
  const mode = requireMode(state);
  if (state.step === "shared_profile") return "product_mode";
  if (state.step === "training_profile") {
    return mode === "training" ? "shared_profile" : "nutrition_safety";
  }
  if (state.step === "nutrition_safety") return "shared_profile";
  if (state.step === "exercise_context") return "nutrition_safety";
  if (state.step === "nutrition_basics") {
    return mode === "nutrition" ? "exercise_context" : "training_profile";
  }
  if (state.step === "nutrition_preferences") return "nutrition_basics";
  if (state.step === "review") {
    return mode === "training" ? "training_profile" : "nutrition_preferences";
  }
  throw new OnboardingTransitionError("no_previous_step", "Onboarding step has no previous step");
}

export function transitionOnboardingState(
  state: OnboardingState,
  event: OnboardingEvent,
): OnboardingState {
  if (!isOnboardingState(state)) {
    throw new OnboardingTransitionError("invalid_state", "Onboarding state is not compatible");
  }

  if (event.type === "reset") return createInitialOnboardingState();

  if (event.type === "select_product_mode") {
    requireStep(state, "product_mode");
    return nextRevision(state, {
      mode: event.mode,
      step: "shared_profile",
      shared: null,
      training: null,
      safety: null,
      structuredExercise: null,
      nutritionBasics: null,
      nutrition: null,
    });
  }

  if (event.type === "save_shared_profile") {
    const mode = requireMode(state);
    requireStep(state, "shared_profile");
    return nextRevision(state, {
      shared: event.profile,
      step: mode === "training" ? "training_profile" : "nutrition_safety",
    });
  }

  if (event.type === "save_nutrition_safety") {
    const mode = requireModeStep(state, ["nutrition", "both"], "nutrition_safety");
    return nextRevision(state, {
      safety: event.safety,
      step: mode === "nutrition" ? "exercise_context" : "training_profile",
    });
  }

  if (event.type === "save_training_profile") {
    const mode = requireModeStep(state, ["training", "both"], "training_profile");
    return nextRevision(state, {
      training: event.profile,
      step: mode === "training" ? "review" : "nutrition_basics",
    });
  }

  if (event.type === "save_exercise_context") {
    requireModeStep(state, ["nutrition"], "exercise_context");
    return nextRevision(state, {
      structuredExercise: event.exercise,
      step: "nutrition_basics",
    });
  }

  if (event.type === "save_nutrition_basics") {
    requireModeStep(state, ["nutrition", "both"], "nutrition_basics");
    return nextRevision(state, {
      nutritionBasics: event.basics,
      step: "nutrition_preferences",
    });
  }

  if (event.type === "save_nutrition_profile") {
    requireModeStep(state, ["nutrition", "both"], "nutrition_preferences");
    return nextRevision(state, {
      nutrition: event.profile,
      step: "review",
    });
  }

  if (event.type === "complete") {
    requireStep(state, "review");
    return nextRevision(state, { step: "complete" });
  }

  const step = previousStep(state);
  return nextRevision(state, { step });
}

export function canTransitionOnboardingState(
  state: OnboardingState,
  event: OnboardingEvent,
): boolean {
  try {
    transitionOnboardingState(state, event);
    return true;
  } catch {
    return false;
  }
}
