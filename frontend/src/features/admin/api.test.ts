import { afterEach, expect, it, vi } from "vitest";

import {
  createAdminMeal,
  createAdminNutritionProgram,
  createAdminExercise,
  getAdminAiGenerationFailures,
  getAdminAiModelTestRuns,
  getAdminAiModels,
  getAdminExercises,
  getAdminMealCatalogue,
  getAdminNutritionPrograms,
  archiveAdminNutritionProgram,
  restoreAdminNutritionProgram,
  updateAdminAiRouting,
} from "./api";
import type {
  AdminAiModelsResponse,
  AdminExercise,
  AdminExerciseCreate,
  PaginatedAdminExercises,
} from "./types";

const created: AdminExercise = {
  id: "018f0000-0000-7000-8000-000000000001",
  slug: "incline-push-up",
  name_en: "Incline Push Up",
  name_fa: "شنا سوئدی شیب‌دار",
  body_region: "upper_body",
  primary_muscle: "chest",
  secondary_muscles: ["shoulders"],
  equipment: ["bench", "bodyweight"],
  difficulty: "beginner",
  movement_pattern: "horizontal_push",
  exercise_type: "compound",
  caution_tags: [],
  labels: [],
  needs_review: false,
  is_programmable: true,
  instructions_en: ["Brace", "Lower", "Press"],
  instructions_fa: ["منقبض", "پایین", "بالا"],
  safety_notes_en: ["Keep aligned"],
  safety_notes_fa: ["هم‌راستا بمانید"],
  media_path: "/exercises/exercise-placeholder.svg",
  media_type: "placeholder",
  media_source_url: null,
  media_license: null,
  media_attribution: null,
  is_active: true,
  created_at: "2026-07-27T12:00:00Z",
  updated_at: "2026-07-27T12:00:00Z",
};

const input: AdminExerciseCreate = {
  slug: created.slug,
  name_en: created.name_en,
  name_fa: created.name_fa,
  body_region: created.body_region,
  primary_muscle: created.primary_muscle,
  secondary_muscles: created.secondary_muscles,
  equipment: created.equipment,
  difficulty: created.difficulty,
  movement_pattern: created.movement_pattern,
  exercise_type: created.exercise_type,
  caution_tags: created.caution_tags,
  labels: created.labels,
  needs_review: created.needs_review,
  is_programmable: created.is_programmable,
  instructions_en: created.instructions_en,
  instructions_fa: created.instructions_fa,
  safety_notes_en: created.safety_notes_en,
  safety_notes_fa: created.safety_notes_fa,
  media_source_url: null,
  media_license: null,
  media_attribution: null,
  is_active: true,
};

afterEach(() => vi.restoreAllMocks());

it("reads models and updates the global AI routing setting", async () => {
  const models: AdminAiModelsResponse = {
    routing: { mode: "automatic", manual_model_id: null },
    models: [],
  };
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(jsonResponse(models))
    .mockResolvedValueOnce(jsonResponse(models.routing));

  await expect(getAdminAiModels()).resolves.toEqual(models);
  await expect(updateAdminAiRouting({ mode: "automatic" })).resolves.toEqual(models.routing);

  expect(fetch).toHaveBeenNthCalledWith(
    1,
    "/api/v1/admin/ai-models",
    expect.objectContaining({ credentials: "include" }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    2,
    "/api/v1/admin/ai-routing",
    expect.objectContaining({ method: "PATCH", body: JSON.stringify({ mode: "automatic" }) }),
  );
});

it("reads recent AI generation failures", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([]));

  await expect(getAdminAiGenerationFailures()).resolves.toEqual([]);

  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/admin/ai-generation-failures?limit=20",
    expect.objectContaining({ credentials: "include" }),
  );
});

it("reads recent AI model test runs", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([]));

  await expect(getAdminAiModelTestRuns()).resolves.toEqual([]);

  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/admin/ai-model-test-runs?limit=20",
    expect.objectContaining({ credentials: "include" }),
  );
});

it("lists admin exercises with inactive filter support", async () => {
  const page: PaginatedAdminExercises = {
    items: [created],
    page: 1,
    page_size: 20,
    total: 1,
    total_pages: 1,
  };
  vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(page));

  await expect(getAdminExercises({ is_active: false, search: "push up" })).resolves.toEqual(
    page,
  );
  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/admin/exercises?is_active=false&search=push+up",
    expect.objectContaining({ credentials: "include" }),
  );
});

it("lists and creates nutrition meal catalogue templates", async () => {
  const page = { items: [], categories: ["breakfast", "lunch", "post_workout", "snack", "dinner"] };
  const input = {
    name_fa: "میان‌وعده",
    name_en: "Snack",
    category: "snack" as const,
    verification_status: "draft" as const,
    items: [{ food_id: "food-1", reference_grams: 50, min_grams: 20, max_grams: 80, is_required: true, functional_role: "fat" as const }],
  };
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(jsonResponse(page))
    .mockResolvedValueOnce(jsonResponse({ id: "meal-1", ...input, totals: {} }));

  await expect(getAdminMealCatalogue("snack")).resolves.toEqual(page);
  await createAdminMeal(input);

  expect(fetch).toHaveBeenNthCalledWith(
    1,
    "/api/v1/nutrition/admin/meals?category=snack",
    expect.objectContaining({ credentials: "include" }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    2,
    "/api/v1/nutrition/admin/meals",
    expect.objectContaining({ method: "POST", body: JSON.stringify(input) }),
  );
});

it("filters, creates, archives, and restores nutrition programs", async () => {
  const page = { items: [], diet_styles: ["economy"] };
  const input = {
    name_fa: "برنامه اقتصادی",
    name_en: "Economy program",
    description_fa: "ساختار هفت روزه",
    description_en: "Seven-day structure",
    diet_style: "economy" as const,
    post_workout_enabled: false,
    days: [],
  };
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(jsonResponse(page))
    .mockResolvedValueOnce(jsonResponse({ id: "program-1", ...input }))
    .mockResolvedValueOnce(new Response(null, { status: 204 }))
    .mockResolvedValueOnce(jsonResponse({ id: "program-1", ...input, is_active: true }));

  await expect(getAdminNutritionPrograms({ dietStyle: "economy", lifecycle: "archived" })).resolves.toEqual(page);
  await createAdminNutritionProgram(input);
  await archiveAdminNutritionProgram("program-1");
  await restoreAdminNutritionProgram("program-1");

  expect(fetch).toHaveBeenNthCalledWith(
    1,
    "/api/v1/nutrition/admin/programs?diet_style=economy&lifecycle=archived",
    expect.objectContaining({ credentials: "include" }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    2,
    "/api/v1/nutrition/admin/programs",
    expect.objectContaining({ method: "POST", body: JSON.stringify(input) }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    3,
    "/api/v1/nutrition/admin/programs/program-1",
    expect.objectContaining({ method: "DELETE" }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    4,
    "/api/v1/nutrition/admin/programs/program-1/restore",
    expect.objectContaining({ method: "POST" }),
  );
});

it("creates an exercise as multipart metadata with an optional media file", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(created), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    }),
  );
  const media = new File(["GIF89a"], "demo.gif", { type: "image/gif" });

  await expect(createAdminExercise(input, media)).resolves.toEqual(created);

  const [path, init] = vi.mocked(fetch).mock.calls[0];
  expect(path).toBe("/api/v1/admin/exercises");
  expect(init?.method).toBe("POST");
  expect(init?.body).toBeInstanceOf(FormData);
  const body = init?.body as FormData;
  expect(JSON.parse(String(body.get("payload")))).toEqual(input);
  expect(body.get("media")).toBe(media);
  expect(new Headers(init?.headers).has("Content-Type")).toBe(false);
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
