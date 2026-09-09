import type { NutritionDailyTracking } from "../nutrition/nutritionTrackingApi";
import type { NutritionEstimate } from "../nutrition/nutritionApi";
import type { WeeklyPlan } from "../nutrition/nutritionPlanApi";
import type { WorkoutDay, WorkoutPlan } from "../workouts/workoutApi";

export type HomeNutritionStatus = "empty" | "pending" | "ready" | "on_plan" | "off_plan";

export type HomeNutritionSummary = {
  readonly carbohydrate: number | null;
  readonly consumedCalories: number | null;
  readonly fat: number | null;
  readonly protein: number | null;
  readonly progress: number;
  readonly status: HomeNutritionStatus;
  readonly targetCalories: number | null;
};

export function currentWorkoutDay(plan: Pick<WorkoutPlan, "days"> | null | undefined): WorkoutDay | null {
  return plan?.days[0] ?? null;
}

export function nutritionSummary(
  plan: Pick<WeeklyPlan, "days" | "physician_approved"> | null | undefined,
  estimate: Pick<NutritionEstimate, "targets"> | null | undefined,
  tracking: Pick<NutritionDailyTracking, "actual_totals" | "check_in_status" | "data_status" | "entries"> | null | undefined,
  date: string,
): HomeNutritionSummary {
  const day = plan?.days.find((item) => item.plan_date === date) ?? plan?.days[0];
  const planned = day?.nutrient_totals ?? {};
  const targets = estimate?.targets ?? {};
  const targetCalories = numberValue(planned.energy_kcal) ?? targetValue(targets.energy_kcal);
  const targetProtein = numberValue(planned.protein_g) ?? targetValue(targets.protein_g);
  const targetCarbohydrate = numberValue(planned.carbohydrate_g) ?? targetValue(targets.carbohydrate_g);
  const targetFat = numberValue(planned.total_fat_g) ?? targetValue(targets.total_fat_g);
  const hasActual = tracking != null && (
    tracking.data_status === "sufficient"
    || tracking.entries.length > 0
    || Object.values(tracking.actual_totals).some((value) => value > 0)
  );
  const actual = hasActual ? tracking?.actual_totals : null;
  const consumedCalories = numberValue(actual?.energy_kcal);
  const status = plan !== null && plan !== undefined && !plan.physician_approved
    ? "pending"
    : targetCalories === null
      ? "empty"
      : tracking?.check_in_status === "on_plan"
        ? "on_plan"
        : tracking?.check_in_status === "off_plan"
          ? "off_plan"
          : "ready";

  return {
    carbohydrate: numberValue(actual?.carbohydrate_g) ?? targetCarbohydrate,
    consumedCalories,
    fat: numberValue(actual?.total_fat_g) ?? targetFat,
    protein: numberValue(actual?.protein_g) ?? targetProtein,
    progress: targetCalories !== null && targetCalories > 0 && consumedCalories !== null
      ? Math.min(1, Math.max(0, consumedCalories / targetCalories))
      : 0,
    status,
    targetCalories,
  };
}

function targetValue(target: { readonly preferred: number | null; readonly minimum: number | null } | undefined): number | null {
  return target?.preferred ?? target?.minimum ?? null;
}

function numberValue(value: number | undefined | null): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
