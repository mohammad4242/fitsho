import { expect, it } from "vitest";

import {
  canGenerateNutritionEstimate,
  formatNutritionNumber,
  nutritionSafetyPresentation,
  nutritionTargetRows,
} from "./nutritionModel";

const activeDecision = {
  can_continue_onboarding: true,
  created_at: "2026-09-07T00:00:00Z",
  id: "safety-1",
  message: "مسیر ایمن است.",
  outcome: "standard_automatic" as const,
  policy_version: "v1",
  reason_codes: [],
  requires_physician_review: false,
};

it("keeps backend safety authority explicit for estimate availability", () => {
  expect(nutritionSafetyPresentation(null)).toMatchObject({ blocked: true, variant: "warning" });
  expect(nutritionSafetyPresentation(activeDecision)).toMatchObject({
    blocked: false,
    variant: "success",
  });
  expect(canGenerateNutritionEstimate(activeDecision)).toBe(true);
  expect(canGenerateNutritionEstimate(null)).toBe(false);
  expect(canGenerateNutritionEstimate({
    ...activeDecision,
    can_continue_onboarding: false,
    outcome: "physician_manual_plan_required",
  })).toBe(false);
});

it("orders estimate targets and preserves stored precision for display", () => {
  expect(nutritionTargetRows({
    confidence: "high",
    confidence_reasons: [],
    created_at: "2026-09-07T00:00:00Z",
    formula_version: "f1",
    id: "estimate-1",
    is_stale: false,
    micronutrients: {},
    policy_version: "p1",
    revision: 1,
    status: "active",
    targets: {
      fat: {
        confidence: "high",
        explanation_codes: [],
        maximum: null,
        minimum: null,
        preferred: 63.75,
        preferred_maximum: 70.125,
        source_ids: [],
        unit: "g",
      },
      protein: {
        confidence: "high",
        explanation_codes: [],
        maximum: null,
        minimum: 105,
        preferred: 120.5,
        preferred_maximum: 135,
        source_ids: [],
        unit: "g",
      },
      energy: {
        confidence: "high",
        explanation_codes: [],
        maximum: 2_100,
        minimum: 1_800,
        preferred: 1_950,
        preferred_maximum: null,
        source_ids: [],
        unit: "kcal",
      },
    },
  })[0]?.code).toBe("energy");
  expect(formatNutritionNumber(120.5)).toBe("۱۲۰٫۵");
});
