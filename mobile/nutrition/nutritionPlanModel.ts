import { irrToRoundedToman } from "@fitician/core";

import type { WeeklyPlan, WeeklyPlanFood } from "./nutritionPlanApi";

export type NutritionPlanSelection = {
  readonly isLatest: boolean;
  readonly plan: WeeklyPlan | null;
};

export type NutritionPlanStatus =
  | "active"
  | "archived"
  | "changes_requested"
  | "generated"
  | "historical"
  | "physician_approved"
  | "physician_review"
  | "pending_review"
  | "rejected";

export type NutritionGenerationStatus =
  | "failed"
  | "infeasible"
  | "price_unavailable"
  | "safety_blocked"
  | "success";

export type PreparedRecipePresentation = {
  readonly costIrrPer100g: number | null;
  readonly nutrients: readonly { readonly code: string; readonly value: number }[];
  readonly status: "estimated" | "verified";
};

const publicPreparedRecipeNutrients = [
  "energy_kcal",
  "protein_g",
  "carbohydrate_g",
  "total_fat_g",
  "fibre_g",
] as const;

export function getNutritionPlanStatus(
  plan: WeeklyPlan,
  historical = false,
): NutritionPlanStatus {
  if (historical) return "historical";
  switch (plan.lifecycle_status) {
    case "active":
      return "active";
    case "archived":
      return "archived";
    case "changes_requested":
      return "changes_requested";
    case "physician_approved":
      return "physician_approved";
    case "pending_physician_review":
      return "pending_review";
    case "physician_review_in_progress":
    case "awaiting_lab_information":
      return "physician_review";
    case "rejected":
      return "rejected";
    default:
      return "generated";
  }
}

export function isNutritionPlanExecutable(plan: WeeklyPlan, historical = false): boolean {
  return !historical
    && plan.is_user_visible
    && plan.lifecycle_status === "active"
    && plan.physician_approved
    && plan.review_status === "approved";
}

export function selectNutritionPlan(
  active: WeeklyPlan | null,
  latest: WeeklyPlan | null,
): NutritionPlanSelection {
  if (latest !== null) return { isLatest: true, plan: latest };
  return { isLatest: false, plan: active };
}

export function preparedRecipePresentation(food: WeeklyPlanFood): PreparedRecipePresentation | null {
  if (food.item_kind !== "prepared_recipe") return null;
  const summary = food.prepared_recipe;
  return {
    costIrrPer100g: summary?.cost_irr_per_100g ?? null,
    nutrients: summary === undefined || summary === null
      ? []
      : publicPreparedRecipeNutrients.flatMap((code) => {
        const value = summary.nutrients_per_100g[code];
        return value === undefined ? [] : [{ code, value }];
      }),
    status: summary?.status ?? "estimated",
  };
}

export function classifyNutritionGenerationOutcome(outcome: string): NutritionGenerationStatus {
  switch (outcome) {
    case "success":
      return "success";
    case "safety_blocked":
      return "safety_blocked";
    case "infeasible":
    case "target_infeasible":
      return "infeasible";
    case "live_price_unavailable":
      return "price_unavailable";
    default:
      return "failed";
  }
}

export function formatNutritionPlanMoney(valueIrr: number): string {
  return `${new Intl.NumberFormat("fa-IR").format(irrToRoundedToman(valueIrr))} تومان`;
}

export function nutritionPlanPdfFilename(planId: string): string {
  const safeId = planId.replace(/[^A-Za-z0-9_-]/gu, "-").replace(/-+/gu, "-");
  return `fitician-nutrition-plan-${safeId || "plan"}.pdf`;
}
