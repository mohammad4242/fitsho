import * as nutritionApi from "../nutrition/api";
import type { NutritionProfileInput, SafetyProfileInput } from "../nutrition/types";
import * as profileApi from "../profile/api";
import type { ProductMode, ProfileInput, SharedProfileInput } from "../profile/types";

export const ONBOARDING_DRAFT_KEY = "fitsho:onboarding-draft:v1";
export const PENDING_NUTRITION_BASICS_KEY = "fitsho:pending-nutrition-basics:v1";

export type PreAccountNutritionBasics = Pick<
  NutritionProfileInput,
  "individual_monthly_food_budget_irr" | "budget_style" | "plan_style" | "allergies" | "intolerances" | "dietary_pattern"
>;

export type OnboardingDraft = {
  mode: ProductMode;
  shared?: SharedProfileInput;
  safety?: SafetyProfileInput;
  training?: ProfileInput;
  nutrition?: NutritionProfileInput;
  nutritionBasics?: PreAccountNutritionBasics;
  readyForAuth?: boolean;
};

export function saveOnboardingDraft(draft: OnboardingDraft): void {
  sessionStorage.setItem(ONBOARDING_DRAFT_KEY, JSON.stringify(draft));
}

export function loadOnboardingDraft(): OnboardingDraft | null {
  const stored = sessionStorage.getItem(ONBOARDING_DRAFT_KEY);
  if (stored === null) return null;
  try {
    const draft = JSON.parse(stored) as Partial<OnboardingDraft>;
    if (draft.mode !== "training" && draft.mode !== "nutrition" && draft.mode !== "both") {
      clearOnboardingDraft();
      return null;
    }
    return draft as OnboardingDraft;
  } catch {
    clearOnboardingDraft();
    return null;
  }
}

export function clearOnboardingDraft(): void {
  sessionStorage.removeItem(ONBOARDING_DRAFT_KEY);
}

export function loadPendingNutritionBasics(): PreAccountNutritionBasics | null {
  const stored = sessionStorage.getItem(PENDING_NUTRITION_BASICS_KEY);
  if (stored === null) return null;
  try { return JSON.parse(stored) as PreAccountNutritionBasics; } catch { sessionStorage.removeItem(PENDING_NUTRITION_BASICS_KEY); return null; }
}

export function clearPendingNutritionBasics(): void {
  sessionStorage.removeItem(PENDING_NUTRITION_BASICS_KEY);
}

function sharedFromTraining(training: ProfileInput): SharedProfileInput {
  return {
    display_name: training.display_name,
    birth_date: training.birth_date,
    sex: training.sex,
    height_cm: training.height_cm,
    current_weight_kg: training.current_weight_kg,
    fitness_goal: training.fitness_goal,
  };
}

export async function hydrateOnboardingDraft(draft: OnboardingDraft): Promise<void> {
  await profileApi.selectProductMode(draft.mode);
  if (draft.mode === "training") {
    if (draft.training === undefined) throw new Error("Training draft is incomplete");
    await profileApi.createProfile(draft.training);
    clearOnboardingDraft();
    return;
  }

  const shared = draft.shared ?? (draft.training === undefined ? undefined : sharedFromTraining(draft.training));
  if (shared === undefined || draft.safety === undefined || draft.nutritionBasics === undefined) throw new Error("Nutrition draft is incomplete");
  await profileApi.saveSharedProfile(shared);

  if (draft.mode === "both" && draft.training !== undefined) {
    await profileApi.createProfile(draft.training);
  }
  await nutritionApi.saveSafetyProfile(draft.safety);
  sessionStorage.setItem(PENDING_NUTRITION_BASICS_KEY, JSON.stringify(draft.nutritionBasics));
  clearOnboardingDraft();
}
