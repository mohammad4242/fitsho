import type { OnboardingState } from "@fitician/core/onboarding";

import { NativeOnboardingController } from "./onboardingController";

export async function hydratePublicOnboardingState(
  controller: NativeOnboardingController,
  draft: OnboardingState,
): Promise<OnboardingState> {
  const current = controller.getState();
  if (current.step === "complete" || current.step !== "product_mode") {
    return current;
  }

  if (draft.step !== "review" || draft.mode === null || draft.shared === null) {
    throw new Error("Public onboarding draft is incomplete");
  }

  await controller.selectProductMode(draft.mode);
  await controller.saveSharedProfile(draft.shared);

  if (draft.mode === "training") {
    if (draft.training === null) throw new Error("Public onboarding draft is incomplete");
    await controller.saveTrainingProfile(draft.training);
  } else {
    if (draft.safety === null || draft.nutritionBasics === null || draft.nutrition === null) {
      throw new Error("Public onboarding draft is incomplete");
    }
    const safety = await controller.saveNutritionSafety(draft.safety);
    if (safety.blocked) throw new Error("Nutrition onboarding requires a specialist review");

    if (draft.mode === "both") {
      if (draft.training === null) throw new Error("Public onboarding draft is incomplete");
      await controller.saveTrainingProfile(draft.training);
    } else {
      if (draft.structuredExercise === null) throw new Error("Public onboarding draft is incomplete");
      await controller.saveExerciseContext(draft.structuredExercise);
    }
    await controller.saveNutritionBasics(draft.nutritionBasics);
    await controller.saveNutritionProfile(draft.nutrition);
  }

  return controller.complete();
}
