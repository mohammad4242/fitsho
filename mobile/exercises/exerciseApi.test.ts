import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@fitician/core";

import {
  createExerciseApi,
  type AuthenticatedExerciseRequest,
  type ExerciseDetail,
  type ExerciseFilters,
} from "./exerciseApi";

const detail = { slug: "press/advanced" } as ExerciseDetail;

describe("native exercise API", () => {
  it("uses the protected catalogue endpoints and serializes filters deterministically", async () => {
    const request = vi.fn().mockResolvedValue({});
    const api = createExerciseApi(request as unknown as AuthenticatedExerciseRequest);
    const filters: ExerciseFilters = {
      body_region: "upper_body",
      content_type: "guide",
      difficulty: "intermediate",
      equipment: "dumbbell",
      exercise_type: "compound",
      labels: ["cardio", "full_body"],
      muscle_focus: "upper_chest",
      page: 2,
      page_size: 20,
      primary_muscle: "chest",
      search: "incline press",
    };

    await api.getCategories();
    await api.list(filters);

    expect(request).toHaveBeenNthCalledWith(1, {
      method: "GET",
      path: "/api/v1/exercise-categories",
    });
    expect(request).toHaveBeenNthCalledWith(2, {
      method: "GET",
      path: "/api/v1/exercises?content_type=guide&body_region=upper_body&primary_muscle=chest&muscle_focus=upper_chest&equipment=dumbbell&difficulty=intermediate&exercise_type=compound&labels=cardio&labels=full_body&search=incline+press&page=2&page_size=20",
    });
  });

  it("encodes exercise slugs and forwards selected media presentation", async () => {
    const request = vi.fn().mockResolvedValue(detail);
    const api = createExerciseApi(request as unknown as AuthenticatedExerciseRequest);

    await expect(api.get("press/advanced", "female")).resolves.toBe(detail);

    expect(request).toHaveBeenCalledWith({
      method: "GET",
      path: "/api/v1/exercises/press%2Fadvanced?presentation=female",
    });
  });

  it("can request the complete media inventory for gender availability", async () => {
    const request = vi.fn().mockResolvedValue(detail);
    const api = createExerciseApi(request as unknown as AuthenticatedExerciseRequest);

    await expect(api.get("press/advanced", "unspecified")).resolves.toBe(detail);

    expect(request).toHaveBeenCalledWith({
      method: "GET",
      path: "/api/v1/exercises/press%2Fadvanced?presentation=unspecified",
    });
  });

  it("returns null only for an unknown exercise", async () => {
    const request = vi.fn()
      .mockRejectedValueOnce(new ApiError(404, "Exercise not found"))
      .mockRejectedValueOnce(new ApiError(503, "Service unavailable"));
    const api = createExerciseApi(request as unknown as AuthenticatedExerciseRequest);

    await expect(api.get("missing")).resolves.toBeNull();
    await expect(api.get("unavailable")).rejects.toMatchObject({ status: 503 });
  });
});
