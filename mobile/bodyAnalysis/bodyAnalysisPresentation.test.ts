import { expect, it } from "vitest";

import type { BodyAnalysisExperienceV4 } from "@fitician/core/body-photos";

import {
  bodyBmiLabel,
  bodyMetricProgress,
  buildBodyProgressLandingSummary,
  buildBodyIndicatorSummary,
} from "./bodyAnalysisPresentation";

const experience = {
  indicators: {
    body_shape: { score_percent: 52, status: "available" },
    muscle_balance: { score_percent: 88, status: "balanced" },
    upper_lower_balance: { score_percent: 64, status: "needs_improvement" },
    visible_symmetry: { score_percent: 91, status: "no_clear_difference" },
  },
} as unknown as BodyAnalysisExperienceV4;

it("keeps the website indicator order and normalizes display scores", () => {
  const indicators = buildBodyIndicatorSummary(experience);

  expect(indicators.map((item) => item.id)).toEqual([
    "muscle_balance",
    "visible_symmetry",
    "upper_lower_balance",
  ]);
  expect(indicators.map((item) => item.score)).toEqual([88, 91, 64]);
  expect(indicators[2]?.caption).toBe("نیازمند توجه بیشتر");
});

it("uses the body shape fallback and keeps missing scores unset", () => {
  const indicators = buildBodyIndicatorSummary({
    ...experience,
    indicators: {
      ...experience.indicators,
      body_shape: { score_percent: 112, status: "available" },
      muscle_balance: undefined,
      visible_symmetry: { score_percent: null, status: "unknown" },
    },
  } as unknown as BodyAnalysisExperienceV4);

  expect(indicators[0]?.score).toBe(100);
  expect(indicators[1]?.score).toBeNull();
});

it("provides display-only metric scales and BMI labels", () => {
  expect(bodyMetricProgress(22.5, 15, 35)).toBeCloseTo(0.375);
  expect(bodyMetricProgress(100, 15, 35)).toBe(1);
  expect(bodyMetricProgress(null, 15, 35)).toBe(0);
  expect(bodyBmiLabel(22)).toBe("محدوده نرمال");
  expect(bodyBmiLabel(null)).toBe("ثبت نشده");
});

it("keeps incomplete uploads separate and preserves the web newest-first analysis order", () => {
  const incomplete = { session: { submitted_at: null } } as never;
  const latest = { session: { submitted_at: "2026-09-09T10:00:00Z" } } as never;
  const previous = { session: { submitted_at: "2026-09-01T10:00:00Z" } } as never;

  const summary = buildBodyProgressLandingSummary([incomplete, latest, previous]);

  expect(summary.incomplete).toEqual([incomplete]);
  expect(summary.submitted).toEqual([latest, previous]);
  expect(summary.latestAnalysis).toBe(latest);
});
