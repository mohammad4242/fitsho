import { expect, it } from "vitest";

import type { NutritionEstimate } from "./nutritionApi";
import { buildNutritionSummary } from "./nutritionSummaryModel";

const estimate = {
  targets: {
    goal_calories: { maximum: null, minimum: 2_000, preferred: 2_200, preferred_maximum: null, unit: "kcal/day" },
    protein: { maximum: null, minimum: 120, preferred: 150, preferred_maximum: null, unit: "g/day" },
    carbohydrate: { maximum: null, minimum: 180, preferred: 240, preferred_maximum: null, unit: "g/day" },
    total_fat: { maximum: null, minimum: 50, preferred: 70, preferred_maximum: null, unit: "g/day" },
  },
} as unknown as NutritionEstimate;

it("maps estimate targets and tracked totals into the daily summary", () => {
  const summary = buildNutritionSummary(estimate, {
    carbohydrate_g: 120,
    energy_kcal: 1_100,
    protein_g: 75,
    total_fat_g: 35,
  });

  expect(summary.calories).toMatchObject({ actual: 1_100, target: 2_200, progress: 0.5 });
  expect(summary.macros.map((metric) => metric.actual)).toEqual([75, 120, 35]);
  expect(summary.macros.map((metric) => metric.target)).toEqual([150, 240, 70]);
});

it("keeps missing targets and missing tracking visibly unset", () => {
  const summary = buildNutritionSummary({ targets: {} } as NutritionEstimate, null);

  expect(summary.calories).toMatchObject({ actual: null, progress: null, target: null });
  expect(summary.macros.every((metric) => metric.actual === null && metric.progress === null)).toBe(true);
});

it("clamps progress when a tracked total exceeds its target", () => {
  const summary = buildNutritionSummary(estimate, { energy_kcal: 2_500 });

  expect(summary.calories.progress).toBe(1);
});
