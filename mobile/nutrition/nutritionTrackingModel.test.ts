import { expect, it } from "vitest";

import type { components } from "@fitician/core";

import {
  adherencePercentLabel,
  checkInStatusLabel,
  photoEstimatePresentation,
  trackingDataStatusLabel,
  trackingSourceLabel,
} from "./nutritionTrackingModel";

it("localizes tracking statuses and sources for members", () => {
  expect(checkInStatusLabel("mostly_on_plan")).toBe("بیشتر مطابق برنامه");
  expect(trackingDataStatusLabel("insufficient_data")).toBe("داده کافی نیست");
  expect(trackingSourceLabel("photo_estimated_confirmed")).toBe("عکس تأییدشده");
  expect(trackingSourceLabel("quick_approximation")).toBe("برآورد سریع");
});

it("rounds adherence only for display", () => {
  expect(adherencePercentLabel(87.6)).toBe("۸۸٪");
  expect(adherencePercentLabel(null)).toBe("—");
});

it("keeps photo estimates visibly estimated until the member confirms them", () => {
  const estimate: components["schemas"]["NutritionFoodPhotoEstimateResponse"] = {
    created_at: "2026-09-07T00:00:00Z",
    error_code: null,
    error_message: null,
    expires_at: "2026-09-08T00:00:00Z",
    id: "estimate-1",
    items: [],
    macro_totals: { calories: 450 },
    macro_totals_complete: false,
    model_id: "model-1",
    needs_user_confirmation: true,
    overall_confidence: 0.78,
    status: "estimated",
  };

  expect(photoEstimatePresentation(estimate)).toEqual({
    canConfirm: true,
    message: "این نتیجه تخمینی است و قبل از ثبت باید آن را بررسی کنی.",
    title: "برآورد عکس؛ نیازمند بررسی",
  });
});

it("does not offer confirmation for deleted or already confirmed estimates", () => {
  const base: components["schemas"]["NutritionFoodPhotoEstimateResponse"] = {
    created_at: "2026-09-07T00:00:00Z",
    error_code: null,
    error_message: null,
    expires_at: "2026-09-08T00:00:00Z",
    id: "estimate-1",
    items: [],
    macro_totals: {},
    macro_totals_complete: true,
    model_id: "model-1",
    needs_user_confirmation: false,
    overall_confidence: null,
    status: "confirmed",
  };
  expect(photoEstimatePresentation(base).canConfirm).toBe(false);
  expect(photoEstimatePresentation({ ...base, status: "deleted" })).toMatchObject({
    canConfirm: false,
    title: "برآورد حذف شده است",
  });
});

it("keeps every estimated photo confirmable after review, even at high confidence", () => {
  const estimate: components["schemas"]["NutritionFoodPhotoEstimateResponse"] = {
    created_at: "2026-09-07T00:00:00Z",
    error_code: null,
    error_message: null,
    expires_at: "2026-09-08T00:00:00Z",
    id: "estimate-1",
    items: [],
    macro_totals: { calories: 450 },
    macro_totals_complete: true,
    model_id: "model-1",
    needs_user_confirmation: false,
    overall_confidence: 0.99,
    status: "estimated",
  };

  expect(photoEstimatePresentation(estimate).canConfirm).toBe(true);
});

it("keeps queued and failed photo jobs outside the confirmation flow", () => {
  const base: components["schemas"]["NutritionFoodPhotoEstimateResponse"] = {
    created_at: "2026-09-07T00:00:00Z",
    error_code: null,
    error_message: null,
    expires_at: "2026-09-08T00:00:00Z",
    id: "estimate-1",
    items: [],
    macro_totals: {},
    macro_totals_complete: false,
    model_id: null,
    needs_user_confirmation: true,
    overall_confidence: null,
    status: "queued",
  };

  expect(photoEstimatePresentation(base)).toMatchObject({
    canConfirm: false,
    title: "تحلیل عکس در صف است",
  });
  expect(photoEstimatePresentation({ ...base, status: "analyzing" })).toMatchObject({
    canConfirm: false,
    title: "عکس در حال تحلیل است",
  });
  expect(photoEstimatePresentation({ ...base, status: "failed", error_code: "provider_timeout" })).toMatchObject({
    canConfirm: false,
    title: "تحلیل عکس ناموفق بود",
  });
});
