import type { NutritionEstimate } from "./nutritionApi";

export type NutritionSummaryMetric = {
  readonly actual: number | null;
  readonly code: "carbohydrate" | "fat" | "protein";
  readonly color: string;
  readonly label: string;
  readonly progress: number | null;
  readonly target: number | null;
  readonly unit: string;
};

export type NutritionSummary = {
  readonly calories: {
    readonly actual: number | null;
    readonly progress: number | null;
    readonly target: number | null;
  };
  readonly macros: readonly NutritionSummaryMetric[];
};

export function buildNutritionSummary(
  estimate: NutritionEstimate,
  actualTotals: Readonly<Record<string, number>> | null,
): NutritionSummary {
  const calories = metricValue(
    estimate.targets,
    ["goal_calories", "energy"],
    actualTotals,
    ["energy_kcal", "calories"],
  );
  return {
    calories,
    macros: [
      macroMetric(estimate.targets, "protein", "پروتئین", "#50dfce", ["protein", "protein_g"], actualTotals, ["protein_g", "protein"]),
      macroMetric(estimate.targets, "carbohydrate", "کربوهیدرات", "#8ec5ff", ["carbohydrate", "carbohydrates", "carbohydrate_g"], actualTotals, ["carbohydrate_g", "carbohydrates"]),
      macroMetric(estimate.targets, "fat", "چربی", "#f2b85b", ["total_fat", "fat", "total_fat_g"], actualTotals, ["total_fat_g", "fat_g", "fat"]),
    ],
  };
}

function macroMetric(
  targets: NutritionEstimate["targets"],
  code: NutritionSummaryMetric["code"],
  label: string,
  color: string,
  targetKeys: readonly string[],
  actualTotals: Readonly<Record<string, number>> | null,
  actualKeys: readonly string[],
): NutritionSummaryMetric {
  const value = metricValue(targets, targetKeys, actualTotals, actualKeys);
  return { ...value, code, color, label, unit: "گرم" };
}

function metricValue(
  targets: NutritionEstimate["targets"],
  targetKeys: readonly string[],
  actualTotals: Readonly<Record<string, number>> | null,
  actualKeys: readonly string[],
): { readonly actual: number | null; readonly progress: number | null; readonly target: number | null } {
  const target = firstTarget(targets, targetKeys);
  const actual = firstNumber(actualTotals, actualKeys);
  return {
    actual,
    progress: target === null || actual === null || target <= 0 ? null : Math.min(1, Math.max(0, actual / target)),
    target,
  };
}

function firstTarget(
  targets: NutritionEstimate["targets"],
  keys: readonly string[],
): number | null {
  for (const key of keys) {
    const target = targets[key];
    if (target === undefined) continue;
    const value = target.preferred ?? target.minimum ?? target.preferred_maximum ?? target.maximum;
    if (value !== null && value !== undefined) return value;
  }
  return null;
}

function firstNumber(
  values: Readonly<Record<string, number>> | null,
  keys: readonly string[],
): number | null {
  if (values === null) return null;
  for (const key of keys) {
    const value = values[key];
    if (value !== undefined && Number.isFinite(value)) return value;
  }
  return null;
}
