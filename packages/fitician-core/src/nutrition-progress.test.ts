import { describe, expect, it } from "vitest";

import {
  clampNutritionProgress,
  nutritionTargetToExpenditureRatio,
  nutritionProgressTone,
} from "./nutrition-progress";

describe("nutritionTargetToExpenditureRatio", () => {
  it("calculates the daily target against estimated expenditure", () => {
    expect(nutritionTargetToExpenditureRatio(2_400, 3_000)).toBeCloseTo(0.8);
    expect(nutritionTargetToExpenditureRatio(3_000, 2_400)).toBeCloseTo(1.25);
  });

  it("rejects missing, non-positive, and non-finite inputs", () => {
    expect(nutritionTargetToExpenditureRatio(null, 2_000)).toBe(0);
    expect(nutritionTargetToExpenditureRatio(2_000, null)).toBe(0);
    expect(nutritionTargetToExpenditureRatio(500, 0)).toBe(0);
    expect(nutritionTargetToExpenditureRatio(Number.NaN, 2_000)).toBe(0);
  });
});

describe("clampNutritionProgress", () => {
  it("clamps only the visual value", () => {
    expect(clampNutritionProgress(-0.2)).toBe(0);
    expect(clampNutritionProgress(0.6)).toBe(0.6);
    expect(clampNutritionProgress(1.111)).toBe(1);
    expect(clampNutritionProgress(Number.NaN)).toBe(0);
  });
});

describe("nutritionProgressTone", () => {
  it("uses green below 60, blue from 60 to below 90, and red from 90 onward", () => {
    expect(nutritionProgressTone(0.599)).toBe("green");
    expect(nutritionProgressTone(0.6)).toBe("blue");
    expect(nutritionProgressTone(0.899)).toBe("blue");
    expect(nutritionProgressTone(0.9)).toBe("red");
    expect(nutritionProgressTone(1.2)).toBe("red");
  });
});
