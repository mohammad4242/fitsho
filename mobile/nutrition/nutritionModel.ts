import type { NutritionEstimate, SafetyDecision } from "./nutritionApi";

export type NutritionSafetyPresentation = {
  readonly blocked: boolean;
  readonly message: string;
  readonly title: string;
  readonly variant: "danger" | "success" | "warning";
};

export type NutritionTargetRow = {
  readonly code: string;
  readonly label: string;
  readonly maximum: number | null;
  readonly minimum: number | null;
  readonly preferred: number | null;
  readonly preferredMaximum: number | null;
  readonly unit: string;
};

const targetLabels: Readonly<Record<string, string>> = {
  carbohydrate: "کربوهیدرات",
  carbohydrates: "کربوهیدرات",
  energy: "انرژی",
  fat: "چربی",
  fibre: "فیبر",
  fiber: "فیبر",
  protein: "پروتئین",
};

export function nutritionSafetyPresentation(
  decision: SafetyDecision | null,
): NutritionSafetyPresentation {
  if (decision === null) {
    return {
      blocked: true,
      message: "برای استفاده از برآوردها و برنامه غذایی، ارزیابی ایمنی را کامل کن.",
      title: "ارزیابی ایمنی ثبت نشده است",
      variant: "warning",
    };
  }
  if (decision.can_continue_onboarding) {
    return decision.requires_physician_review
      ? {
        blocked: false,
        message: decision.message,
        title: "ادامه با بررسی پزشک",
        variant: "warning",
      }
      : {
        blocked: false,
        message: decision.message,
        title: "مسیر تغذیه ایمن است",
        variant: "success",
      };
  }
  return {
    blocked: true,
    message: decision.message,
    title: "ادامه مسیر تغذیه فعلاً مسدود است",
    variant: decision.outcome === "unsupported_or_hard_blocked" ? "danger" : "warning",
  };
}

export function canGenerateNutritionEstimate(decision: SafetyDecision | null): boolean {
  return decision !== null && decision.can_continue_onboarding;
}

export function nutritionTargetRows(estimate: NutritionEstimate): NutritionTargetRow[] {
  return Object.entries(estimate.targets)
    .sort(([left], [right]) => targetSortIndex(left) - targetSortIndex(right) || left.localeCompare(right))
    .map(([code, target]) => ({
      code,
      label: targetLabels[code] ?? code,
      maximum: target.maximum,
      minimum: target.minimum,
      preferred: target.preferred,
      preferredMaximum: target.preferred_maximum,
      unit: target.unit,
    }));
}

export function formatNutritionNumber(value: number): string {
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 2 }).format(value);
}

function targetSortIndex(code: string): number {
  const order = ["energy", "protein", "carbohydrate", "carbohydrates", "fat", "fibre", "fiber"];
  const index = order.indexOf(code);
  return index === -1 ? order.length : index;
}
