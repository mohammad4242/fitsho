import { expect, it } from "vitest";

import type {
  BinaryDownload,
  BinaryDownloadRequest,
  TransportRequest,
} from "@fitician/core";

import {
  createNutritionTrackingApi,
  type NutritionTrackingApi,
} from "./nutritionTrackingApi";

function binaryDownload(): BinaryDownload {
  return {
    bytes: Uint8Array.from([1, 2, 3]),
    contentType: "application/octet-stream",
    filename: "private.bin",
  };
}

function createApi(
  requests: TransportRequest[],
  downloads: BinaryDownloadRequest[] = [],
): NutritionTrackingApi {
  return createNutritionTrackingApi(
    async <TResponse>(request: TransportRequest): Promise<TResponse> => {
      requests.push(request);
      return {} as TResponse;
    },
    async (request: BinaryDownloadRequest): Promise<BinaryDownload> => {
      downloads.push(request);
      return binaryDownload();
    },
  );
}

it("uses authenticated member tracking and adherence endpoints with backend bodies", async () => {
  const requests: TransportRequest[] = [];
  const api = createApi(requests);

  await api.getDailyTracking("2026-09-07");
  await api.getTrackingHistory("2026-09-01", "2026-09-07");
  await api.getRecentFoods(12);
  await api.saveDailyCheckIn({
    entry_date: "2026-09-07",
    note: "ثبت شد",
    status: "mostly_on_plan",
  });
  await api.addCatalogueFood({
    entry_date: "2026-09-07",
    food_id: "food/1",
    grams: 125.5,
    note: null,
  });
  await api.addQuickApproximation({
    calories: 420,
    display_name: "ساندویچ",
    entry_date: "2026-09-07",
    protein_g: 18,
  });
  await api.editEntry("entry/1", { grams: 130, note: "ویرایش" });
  await api.removeEntry("entry/1");
  await api.adjustPlannedMeal("meal/1", {
    entry_date: "2026-09-07",
    portion_ratio: 0.5,
    status: "adjusted",
  });
  await api.saveFreeMeal("meal/2", {
    calories: 700,
    carbohydrate_g: 80,
    entry_date: "2026-09-07",
    fat_g: 22,
    protein_g: 30,
  });
  await api.getAdherence("2026-09-01", "2026-09-07");
  await api.getAdaptivePreferences();
  await api.confirmTarget({ requested_goal: "fat_loss", confirmed: true });

  expect(requests).toEqual([
    {
      method: "GET",
      path: "/api/v1/nutrition/tracking/days/2026-09-07",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/tracking/history?start=2026-09-01&end=2026-09-07",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/tracking/recent-foods?limit=12",
    },
    {
      body: {
        entry_date: "2026-09-07",
        note: "ثبت شد",
        status: "mostly_on_plan",
      },
      method: "PUT",
      path: "/api/v1/nutrition/tracking/check-in",
    },
    {
      body: {
        entry_date: "2026-09-07",
        food_id: "food/1",
        grams: 125.5,
        note: null,
      },
      method: "POST",
      path: "/api/v1/nutrition/tracking/entries/catalogue",
    },
    {
      body: {
        calories: 420,
        display_name: "ساندویچ",
        entry_date: "2026-09-07",
        protein_g: 18,
      },
      method: "POST",
      path: "/api/v1/nutrition/tracking/entries/quick",
    },
    {
      body: { grams: 130, note: "ویرایش" },
      method: "PUT",
      path: "/api/v1/nutrition/tracking/entries/entry%2F1",
    },
    {
      method: "DELETE",
      path: "/api/v1/nutrition/tracking/entries/entry%2F1",
    },
    {
      body: {
        entry_date: "2026-09-07",
        portion_ratio: 0.5,
        status: "adjusted",
      },
      method: "PUT",
      path: "/api/v1/nutrition/tracking/planned-meals/meal%2F1",
    },
    {
      body: {
        calories: 700,
        carbohydrate_g: 80,
        entry_date: "2026-09-07",
        fat_g: 22,
        protein_g: 30,
      },
      method: "PUT",
      path: "/api/v1/nutrition/tracking/free-meals/meal%2F2",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/adherence?start=2026-09-01&end=2026-09-07",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/adaptive-preferences",
    },
    {
      body: { confirmed: true, requested_goal: "fat_loss" },
      method: "POST",
      path: "/api/v1/nutrition/targets/confirm-update",
    },
  ]);
  expect(requests.every((request) => !request.path.includes("/admin/") && !request.path.includes("/physician/"))).toBe(true);
});

it("keeps private photo and laboratory operations token-bound", async () => {
  const requests: TransportRequest[] = [];
  const downloads: BinaryDownloadRequest[] = [];
  const api = createApi(requests, downloads);

  await api.correctPhotoItem("estimate/1", "item/1", {
    estimated_amount: 180,
    food_id: "food/1",
    remove: false,
  });
  await api.confirmPhoto("estimate/1", { entry_date: "2026-09-07" });
  await api.confirmFreeMealPhotoPreview("estimate/1");
  await api.deletePhotoEstimate("estimate/1");
  await api.grantPhotoAccess("estimate/1");
  await api.downloadPhoto("estimate/1", "token with/slash");
  await api.getLabRequests();
  await api.getLabDocuments();
  await api.deleteLabDocument("lab/1");
  await api.grantLabAccess("lab/1");
  await api.downloadLabDocument("lab/1", "lab-token");
  await api.getSupplementCatalogue();
  await api.getSupplementOrders();
  await api.acknowledgeSupplementOrder("order/1", { adherence_note: "طبق برنامه" });

  expect(requests).toEqual([
    {
      body: {
        estimated_amount: 180,
        food_id: "food/1",
        remove: false,
      },
      method: "PATCH",
      path: "/api/v1/nutrition/tracking/photo-estimates/estimate%2F1/items/item%2F1",
    },
    {
      body: { entry_date: "2026-09-07" },
      method: "POST",
      path: "/api/v1/nutrition/tracking/photo-estimates/estimate%2F1/confirm",
    },
    {
      method: "POST",
      path: "/api/v1/nutrition/tracking/photo-estimates/estimate%2F1/free-meal-preview",
    },
    {
      method: "DELETE",
      path: "/api/v1/nutrition/tracking/photo-estimates/estimate%2F1",
    },
    {
      method: "POST",
      path: "/api/v1/nutrition/tracking/photo-estimates/estimate%2F1/access-grant",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/lab-requests",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/labs",
    },
    {
      method: "DELETE",
      path: "/api/v1/nutrition/labs/lab%2F1",
    },
    {
      method: "POST",
      path: "/api/v1/nutrition/labs/lab%2F1/access-grant",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/supplements/catalogue",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/supplement-orders",
    },
    {
      body: { adherence_note: "طبق برنامه" },
      method: "POST",
      path: "/api/v1/nutrition/supplement-orders/order%2F1/acknowledge",
    },
  ]);
  expect(downloads).toEqual([
    {
      method: "GET",
      path: "/api/v1/nutrition/tracking/photo-estimates/estimate%2F1/file?token=token%20with%2Fslash",
      responseType: "binary",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/labs/lab%2F1/file?token=lab-token",
      responseType: "binary",
    },
  ]);
});
