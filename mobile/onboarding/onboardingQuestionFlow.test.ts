import { describe, expect, it } from "vitest";

import {
  getQuestionProgress,
  nextQuestionIndex,
  previousQuestionIndex,
} from "./onboardingQuestionFlow";

describe("onboarding question flow", () => {
  it("moves only inside the available question range", () => {
    expect(nextQuestionIndex(0, 3)).toBe(1);
    expect(nextQuestionIndex(2, 3)).toBe(2);
    expect(previousQuestionIndex(2)).toBe(1);
    expect(previousQuestionIndex(0)).toBe(0);
  });

  it("returns stable progress for a single or multi-question stage", () => {
    expect(getQuestionProgress(0, 1)).toEqual({ current: 1, progress: 1, total: 1 });
    expect(getQuestionProgress(1, 3)).toEqual({ current: 2, progress: 2 / 3, total: 3 });
  });
});
