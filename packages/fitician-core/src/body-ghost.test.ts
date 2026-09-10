import { describe, expect, it } from "vitest";

import {
  ghostPrivacyCutRatioForView,
  ghostPrivacyLineGeometry,
} from "./body-ghost";

describe("body Ghost neck privacy geometry", () => {
  it.each([
    ["male", "front", 0.08],
    ["male", "side", 0.08],
    ["male", "back", 0.08],
    ["female", "front", 0.045],
    ["female", "side", 0.06],
    ["female", "back", 0.055],
  ] as const)("uses the %s %s neck anchor", (variant, view, expectedRatio) => {
    expect(ghostPrivacyCutRatioForView(view, variant)).toBeCloseTo(expectedRatio);
    expect(ghostPrivacyLineGeometry(view, 1, false, variant).anchor.y).toBeCloseTo(expectedRatio);
  });

  it("keeps the neck line horizontal when the side Ghost is mirrored", () => {
    const right = ghostPrivacyLineGeometry("side", 1, false, "female");
    const left = ghostPrivacyLineGeometry("side", 1, true, "female");

    expect(left.anchor.y).toBe(right.anchor.y);
    expect(left.start.y).toBe(right.start.y);
    expect(left.end.y).toBe(right.end.y);
    expect(left.start.x).toBe(1 - right.end.x);
    expect(left.end.x).toBe(1 - right.start.x);
  });
});
