import { expect, it, vi } from "vitest";

import { ApiError } from "@fitician/core";
import type { SharedProfileInput } from "@fitician/core/profile";

import { createOnboardingApi } from "./onboardingApi";

const shared: SharedProfileInput = {
  display_name: "Sara",
  birth_date: "1992-05-12",
  sex: "female",
  height_cm: 168,
  current_weight_kg: 64,
  fitness_goal: "build_muscle",
};

it("routes authenticated onboarding writes through the injected request boundary", async () => {
  const request = vi.fn().mockResolvedValue({});
  const api = createOnboardingApi(request);

  await api.selectProductMode("both");
  await api.saveSharedProfile(shared);

  expect(request).toHaveBeenNthCalledWith(1, {
    method: "POST",
    path: "/api/v1/profile/mode",
    body: { product_mode: "both" },
  });
  expect(request).toHaveBeenNthCalledWith(2, {
    method: "PUT",
    path: "/api/v1/profile/shared",
    body: shared,
  });
});

it("preserves backend 404 semantics for optional resume data", async () => {
  const request = vi.fn().mockRejectedValue(new ApiError(404, "Not found"));
  const api = createOnboardingApi(request);

  await expect(api.getSharedProfile()).resolves.toBeNull();
  await expect(api.getNutritionProfile()).resolves.toBeNull();
  await expect(api.getStructuredExercise()).resolves.toBeNull();
});

it("does not hide non-404 failures while loading onboarding state", async () => {
  const request = vi.fn().mockRejectedValue(new ApiError(503, "Unavailable"));
  const api = createOnboardingApi(request);

  await expect(api.getSharedProfile()).rejects.toMatchObject({ status: 503 });
});
