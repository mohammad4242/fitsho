import { describe, expect, it } from "vitest";

import {
  ghostAssetCalibrationForView,
  ghostAssetVisibleTopRatioForView,
  ghostPrivacyCutRatioForView,
  ghostPrivacyLineGeometry,
} from "./body-ghost";

describe("body Ghost upper-edge privacy geometry", () => {
  it.each([
    ["male", "front", 156 / 1280, 0.10003125],
    ["male", "side", 156 / 1280, 0.10425],
    ["male", "back", 104 / 1280, 0.0159375],
    ["female", "front", 44 / 1280, 0.1098125],
    ["female", "side", 77 / 1280, 0.1099296875],
    ["female", "back", 140 / 1280, 0.0228125],
  ] as const)("uses the visible upper edge of the %s %s asset", (
    variant,
    view,
    expectedAssetTop,
    expectedRatio,
  ) => {
    expect(ghostAssetVisibleTopRatioForView(view, variant)).toBeCloseTo(expectedAssetTop);
    expect(ghostPrivacyCutRatioForView(view, variant)).toBeCloseTo(expectedRatio);
    expect(ghostPrivacyLineGeometry(view, 1, false, variant).anchor.y).toBeCloseTo(expectedRatio);
  });

  it("keeps the asset calibration in the shared geometry contract", () => {
    expect(ghostAssetCalibrationForView("front", "female")).toEqual({
      scale: 0.78,
      translateYRatio: -0.027,
    });
    expect(ghostAssetCalibrationForView("back", "neutral")).toEqual({
      scale: 0.91,
      translateYRatio: -0.103,
    });
  });

  it("keeps the upper-edge line horizontal when the side Ghost is mirrored", () => {
    const right = ghostPrivacyLineGeometry("side", 1, false, "female");
    const left = ghostPrivacyLineGeometry("side", 1, true, "female");

    expect(left.anchor.y).toBe(right.anchor.y);
    expect(left.start.y).toBe(right.start.y);
    expect(left.end.y).toBe(right.end.y);
    expect(left.start.x).toBe(1 - right.end.x);
    expect(left.end.x).toBe(1 - right.start.x);
  });
});
