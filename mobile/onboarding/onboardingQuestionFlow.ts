import { getOnboardingSteps, type OnboardingStep } from "@fitician/core/onboarding";
import type { ProductMode } from "@fitician/core/profile";

export interface QuestionProgress {
  readonly current: number;
  readonly progress: number;
  readonly total: number;
}

export interface OnboardingStageProgress {
  readonly completed: number;
  readonly progress: number;
  readonly total: number;
}

export function nextQuestionIndex(current: number, total: number): number {
  return Math.min(Math.max(0, total - 1), current + 1);
}

export function previousQuestionIndex(current: number): number {
  return Math.max(0, current - 1);
}

export function getQuestionProgress(current: number, total: number): QuestionProgress {
  const safeTotal = Math.max(1, total);
  const safeCurrent = Math.min(Math.max(0, current), safeTotal - 1);
  return {
    current: safeCurrent + 1,
    progress: (safeCurrent + 1) / safeTotal,
    total: safeTotal,
  };
}

/** Progress for persisted stages; the active stage is not counted early. */
export function getOnboardingStageProgress(
  mode: ProductMode | null,
  step: OnboardingStep,
): OnboardingStageProgress {
  if (mode === null) return { completed: 0, progress: 0, total: 0 };

  const steps = getOnboardingSteps(mode);
  const reviewIndex = steps.indexOf("review");
  const questionSteps = steps.slice(1, reviewIndex);
  const currentIndex = questionSteps.indexOf(step);
  const completed = step === "review" || step === "complete"
    ? questionSteps.length
    : Math.max(0, currentIndex);

  return {
    completed,
    progress: questionSteps.length === 0 ? 0 : completed / questionSteps.length,
    total: questionSteps.length,
  };
}
