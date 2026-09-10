export type NutritionProgressTone = "green" | "blue" | "red";

export function nutritionProgressRatio(
  consumedCalories: number | null | undefined,
  targetCalories: number | null | undefined,
): number {
  if (
    typeof consumedCalories !== "number"
    || !Number.isFinite(consumedCalories)
    || consumedCalories < 0
    || typeof targetCalories !== "number"
    || !Number.isFinite(targetCalories)
    || targetCalories <= 0
  ) {
    return 0;
  }
  return consumedCalories / targetCalories;
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
