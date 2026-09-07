import { expect, it } from "vitest";

import type { components } from "@fitician/core";

import {
  labReviewStatusLabel,
  supplementSafetyPresentation,
  supplementStatusLabel,
} from "./nutritionClinicalModel";

it("localizes lab review statuses and supplement order statuses", () => {
  expect(labReviewStatusLabel("pending_review")).toBe("در انتظار بررسی پزشک");
  expect(labReviewStatusLabel("reviewed")).toBe("بررسی‌شده");
  expect(supplementStatusLabel("active")).toBe("فعال");
});

it("surfaces supplement hard blocks before member acknowledgement", () => {
  const exposure: components["schemas"]["NutritionSupplementExposureResponse"] = {
    combined_exposure: { vitamin_d: "above_upper_bound" },
    food_contribution: {},
    hard_blocks: [{ code: "UPPER_BOUND_EXCEEDED" }],
    supplement_contribution: {},
  };

  expect(supplementSafetyPresentation(exposure)).toEqual({
    blocked: true,
    message: "این مکمل به‌دلیل هشدار ایمنی فعلاً قابل تأیید نیست.",
    title: "نیازمند بررسی ایمنی",
  });
  expect(supplementSafetyPresentation({ ...exposure, hard_blocks: [] })).toMatchObject({
    blocked: false,
    title: "بررسی ایمنی انجام شده است",
  });
});
