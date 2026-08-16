import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../shared/apiClient";
import { getExercise, getExerciseCategories, getExercises } from "./api";
import type {
  ExerciseCategories,
  ExerciseDetail,
  PaginatedExercises,
} from "./types";
import { muscleGroups } from "./types";

const categories: ExerciseCategories = {
  body_regions: [
    { value: "upper_body", name_en: "Upper Body", name_fa: "بالاتنه" },
    { value: "lower_body", name_en: "Lower Body", name_fa: "پایین‌تنه" },
    { value: "core", name_en: "Core", name_fa: "میان‌تنه" },
  ],
  upper_body: [{ value: "chest", name_en: "Chest", name_fa: "سینه" }],
  lower_body: [
    { value: "quadriceps", name_en: "Quadriceps", name_fa: "جلو پا" },
  ],
  core: [{ value: "lower_back", name_en: "Lower Back", name_fa: "فیله" }],
  muscle_focuses: Object.fromEntries(
    muscleGroups.map((muscle) => [muscle, []]),
  ) as unknown as ExerciseCategories["muscle_focuses"],
};

const page: PaginatedExercises = {
  items: [],
  page: 2,
  page_size: 12,
  total: 0,
  total_pages: 0,
};

const detail: ExerciseDetail = {
  id: "018f0000-0000-7000-8000-000000000001",
  slug: "dumbbell-bench-press",
  name_en: "Dumbbell Bench Press",
  name_fa: "پرس سینه دمبل",
  content_type: "exercise",
  body_region: "upper_body",
  primary_muscle: "chest",
  muscle_focus: "mid_chest",
  labels: [],
  secondary_muscles: ["triceps", "shoulders"],
  equipment: ["dumbbell", "bench"],
  difficulty: "intermediate",
  instructions_en: ["Lie on the bench."],
  instructions_fa: ["روی نیمکت دراز بکشید."],
  safety_notes_en: ["Keep both feet planted."],
  safety_notes_fa: ["هر دو پا را روی زمین نگه دارید."],
  media_path: "/exercises/upper-body/chest/dumbbell-bench-press.gif",
  media_type: "gif",
  media_source_url: null,
  media_license: "Project owner supplied and authorized",
  media_attribution: "Provided by Fitsho project owner",
};

afterEach(() => vi.restoreAllMocks());

describe("exercise api", () => {
  it("uses the protected categories endpoint through the shared client", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(categories));

    await expect(getExerciseCategories()).resolves.toEqual(categories);

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/exercise-categories",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("encodes selected filters and omits empty values", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(page));

    await expect(
      getExercises({
        body_region: "upper_body",
        primary_muscle: "chest",
        content_type: "guide",
        muscle_focus: "upper_chest",
        equipment: "",
        difficulty: undefined,
        search: "incline press",
        page: 2,
      }),
    ).resolves.toEqual(page);

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/exercises?body_region=upper_body&primary_muscle=chest&content_type=guide&muscle_focus=upper_chest&search=incline+press&page=2",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("encodes a detail slug before building the path", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(detail));

    await expect(getExercise("press/advanced")).resolves.toEqual(detail);

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/exercises/press%2Fadvanced",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("returns null only for an unknown exercise", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(errorResponse(404, "Exercise not found"))
      .mockResolvedValueOnce(errorResponse(503, "Service unavailable"));

    await expect(getExercise("unknown-exercise")).resolves.toBeNull();
    await expect(getExercise("known-exercise")).rejects.toEqual(
      new ApiError(503, "Service unavailable"),
    );
  });
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function errorResponse(status: number, detailMessage: string): Response {
  return new Response(JSON.stringify({ detail: detailMessage }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
