import { describe, expect, it } from "vitest";

import {
  clampNutritionProgress,
  nutritionProgressRatio,
  nutritionProgressTone,
} from "./nutrition-progress";

describe("nutritionProgressRatio", () => {
  it("uses the same target-relative calculation for gain and loss targets", () => {
    expect(nutritionProgressRatio(1_800, 3_000)).toBeCloseTo(0.6);
    expect(nutritionProgressRatio(1_800, 1_800)).toBe(1);
  });

  it("preserves a ratio above the target and rejects invalid targets", () => {
    expect(nutritionProgressRatio(2_000, 1_800)).toBeCloseTo(1.111111);
    expect(nutritionProgressRatio(null, 2_000)).toBe(0);
    expect(nutritionProgressRatio(500, 0)).toBe(0);
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
