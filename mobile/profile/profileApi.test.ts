import { expect, it, vi } from "vitest";

import { ApiError } from "@fitician/core";

import { createProfileApi } from "./profileApi";

it("uses the shared profile endpoints for native reads and writes", async () => {
  const request = vi.fn().mockResolvedValue({});
  const api = createProfileApi(request);

  await api.getProfile();
  await api.getSharedProfile();
  await api.updateProfile({ display_name: "Sara" });
  await api.saveSharedProfile({
    birth_date: "1992-05-12",
    current_weight_kg: 64,
    display_name: "Sara",
    fitness_goal: "build_muscle",
    height_cm: 168,
    sex: "female",
  });

  expect(request).toHaveBeenNthCalledWith(1, { method: "GET", path: "/api/v1/profile" });
  expect(request).toHaveBeenNthCalledWith(2, { method: "GET", path: "/api/v1/profile/shared" });
  expect(request).toHaveBeenNthCalledWith(3, {
    body: { display_name: "Sara" },
    method: "PATCH",
    path: "/api/v1/profile",
  });
  expect(request).toHaveBeenNthCalledWith(4, {
    body: {
      birth_date: "1992-05-12",
      current_weight_kg: 64,
      display_name: "Sara",
      fitness_goal: "build_muscle",
      height_cm: 168,
      sex: "female",
    },
    method: "PUT",
    path: "/api/v1/profile/shared",
  });
});

it("treats only 404 profile reads as absent", async () => {
  const request = vi.fn().mockRejectedValue(new ApiError(404, "Not found"));
  const api = createProfileApi(request);

  await expect(api.getProfile()).resolves.toBeNull();
  await expect(api.getSharedProfile()).resolves.toBeNull();
  await expect(api.getNutritionProfile()).resolves.toBeNull();
});

it("preserves non-404 failures for profile startup", async () => {
  const request = vi.fn().mockRejectedValue(new ApiError(503, "Unavailable"));
  const api = createProfileApi(request);

  await expect(api.getProfile()).rejects.toMatchObject({ status: 503 });
});
