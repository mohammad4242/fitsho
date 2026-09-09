import { describe, expect, it } from "vitest";

import { calculateRingGeometry, clampProgress } from "./visualMetrics";

describe("clampProgress", () => {
  it("keeps progress inside the visible unit interval", () => {
    expect(clampProgress(-0.2)).toBe(0);
    expect(clampProgress(0.375)).toBe(0.375);
    expect(clampProgress(1.4)).toBe(1);
    expect(clampProgress(Number.NaN)).toBe(0);
  });
});

describe("calculateRingGeometry", () => {
  it("derives a value-driven stroke offset from size and progress", () => {
    const geometry = calculateRingGeometry(100, 10, 0.25);

    expect(geometry.radius).toBe(45);
    expect(geometry.circumference).toBeCloseTo(282.743, 3);
    expect(geometry.dashOffset).toBeCloseTo(212.058, 3);
  });
});
