import { describe, expect, it } from "vitest";

import {
  cinematicMotion,
  easedProgressBetween,
  processStepMotion,
  sectionProgress,
} from "./landingScrollMotion";

describe("native landing scroll motion", () => {
  it("clamps section progress and eases the middle of a reveal", () => {
    expect(sectionProgress(-20, 0, 800, 400)).toBe(0);
    expect(sectionProgress(200, 0, 800, 400)).toBe(0.5);
    expect(sectionProgress(900, 0, 800, 400)).toBe(1);
    expect(easedProgressBetween(0.5, 0, 1)).toBe(0.5);
  });

  it("hands cinematic emphasis from one scene to the next", () => {
    expect(cinematicMotion(0.08).hero).toBeGreaterThan(0.5);
    expect(cinematicMotion(0.18).training).toBeGreaterThan(0);
    expect(cinematicMotion(0.4).training).toBeLessThan(0.5);
    expect(cinematicMotion(0.42).nutrition).toBeGreaterThan(0);
    expect(cinematicMotion(0.68).meal).toBeGreaterThan(0);
  });

  it("reveals each process step as ring, copy, connector", () => {
    expect(processStepMotion(0.08, 0)).toMatchObject({ copy: 0, connector: 0 });
    expect(processStepMotion(0.16, 0).ring).toBe(1);
    expect(processStepMotion(0.16, 0).copy).toBeGreaterThan(0);
    expect(processStepMotion(0.2, 0).connector).toBeGreaterThan(0);
    expect(processStepMotion(0.2, 1)).toEqual({ connector: 0, copy: 0, ring: 0 });
  });
});
