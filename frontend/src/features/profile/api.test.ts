import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../shared/apiClient";
import {
  createProfile,
  getSharedProfile,
  getProfile,
  getProfileStatus,
  selectProductMode,
  saveSharedProfile,
  updateProfile,
} from "./api";
import type { Profile, ProfileInput } from "./types";

const profileInput: ProfileInput = {
  display_name: "Mohammad",
  birth_date: "2000-05-14",
  sex: "male",
  height_cm: 178,
  current_weight_kg: 76.5,
  shoulder_circumference_cm: null,
  waist_circumference_cm: null,
  hip_circumference_cm: null,
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  training_days_per_week: 3,
  training_location: "gym",
  home_training_setup: null,
  session_duration_minutes: 60,
  physical_limitations: null,
  training_cautions: [],
  plan_duration_weeks: 4,
};

const profile: Profile = {
  user_id: "018f0000-0000-7000-8000-000000000001",
  ...profileInput,
  weight_measured_at: "2026-07-27T12:00:00Z",
  circumferences_measured_at: null,
  created_at: "2026-07-27T12:00:00Z",
  updated_at: "2026-07-27T12:00:00Z",
};

afterEach(() => vi.restoreAllMocks());

describe("profile api", () => {
  it("reads profile status and explicitly selects product mode", async () => {
    const missing = {
      user_id: profile.user_id,
      product_mode: null,
      completion_state: "product_mode_not_selected",
    } as const;
    const selected = {
      user_id: profile.user_id,
      product_mode: "both",
      completion_state: "shared_profile_incomplete",
    } as const;
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json(missing))
      .mockResolvedValueOnce(Response.json(selected, { status: 201 }));

    await expect(getProfileStatus()).resolves.toEqual(missing);
    await expect(selectProductMode("both")).resolves.toEqual(selected);
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      "/api/v1/profile/mode",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ product_mode: "both" }),
      }),
    );
  });

  it("catches a changed profile endpoint or HTTP method", async () => {
    const updated = { ...profile, current_weight_kg: 75.25 };
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 404 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify(profile), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(updated), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    await expect(getProfile()).resolves.toBeNull();
    await expect(createProfile(profileInput)).resolves.toEqual(profile);
    await expect(updateProfile({ current_weight_kg: 75.25 })).resolves.toEqual(updated);

    expect(fetch).toHaveBeenNthCalledWith(
      1,
      "/api/v1/profile",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      "/api/v1/profile",
      expect.objectContaining({ method: "POST", body: JSON.stringify(profileInput) }),
    );
    expect(fetch).toHaveBeenNthCalledWith(
      3,
      "/api/v1/profile",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ current_weight_kg: 75.25 }),
      }),
    );
  });

  it("reads and updates the shared profile without duplicating training fields", async () => {
    const shared = {
      user_id: profile.user_id,
      product_mode: "nutrition" as const,
      display_name: "Sara",
      birth_date: "2000-05-14",
      sex: "female" as const,
      height_cm: 165,
      current_weight_kg: 62.5,
      fitness_goal: "maintain_weight" as const,
      weight_measured_at: "2026-08-05T12:00:00Z",
    };
    const input = {
      display_name: shared.display_name,
      birth_date: shared.birth_date,
      sex: shared.sex,
      height_cm: shared.height_cm,
      current_weight_kg: shared.current_weight_kg,
      fitness_goal: shared.fitness_goal,
    };
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json(shared))
      .mockResolvedValueOnce(Response.json(shared));

    await expect(getSharedProfile()).resolves.toEqual(shared);
    await expect(saveSharedProfile(input)).resolves.toEqual(shared);
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      "/api/v1/profile/shared",
      expect.objectContaining({ method: "PUT", body: JSON.stringify(input) }),
    );
  });

  it("catches treating non-404 profile errors as an absent profile", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Service temporarily unavailable" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getProfile()).rejects.toEqual(
      new ApiError(503, "Service temporarily unavailable"),
    );
  });
});
