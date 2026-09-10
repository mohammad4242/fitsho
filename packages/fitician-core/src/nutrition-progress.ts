export type NutritionProgressTone = "green" | "blue" | "red";

export function nutritionTargetToExpenditureRatio(
  targetCalories: number | null | undefined,
  estimatedDailyExpenditureCalories: number | null | undefined,
): number {
  if (
    typeof targetCalories !== "number"
    || !Number.isFinite(targetCalories)
    || targetCalories <= 0
    || typeof estimatedDailyExpenditureCalories !== "number"
    || !Number.isFinite(estimatedDailyExpenditureCalories)
    || estimatedDailyExpenditureCalories <= 0
  ) {
    return 0;
  }
  return targetCalories / estimatedDailyExpenditureCalories;
}

export function clampNutritionProgress(progress: number): number {
  if (!Number.isFinite(progress)) return 0;
  return Math.min(1, Math.max(0, progress));
}

export function nutritionProgressTone(progress: number): NutritionProgressTone {
  const normalized = Number.isFinite(progress) ? Math.max(0, progress) : 0;
  if (normalized < 0.6) return "green";
  if (normalized < 0.9) return "blue";
  return "red";
}
