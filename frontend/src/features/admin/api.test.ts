import { afterEach, expect, it, vi } from "vitest";

import {
  createAdminMeal,
  createAdminNutritionProgram,
  createAdminExercise,
  deleteAdminTrainingProgramTemplate,
  getAdminAiGenerationFailures,
  getAdminAiModelTestRuns,
  getAdminAiModels,
  getAdminAiAgentAuthSession,
  getAdminExercises,
  getAdminTrainingProgramTemplates,
  getAdminMealCatalogue,
  getAdminNutritionPrograms,
  archiveAdminNutritionProgram,
  restoreAdminNutritionProgram,
  startAdminAiAgentAuth,
  submitAdminAiAgentAuthInput,
  cancelAdminAiAgentAuthActive,
  cancelAdminAiAgentAuthSession,
  uploadAdminMealImage,
  updateAdminAiRouting,
  createAdminTrainingProgramStructure,
  deactivateAdminTrainingProgramStructure,
  getAdminTrainingProgramStructures,
  updateAdminTrainingProgramStructure,
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
  content_type: "exercise",
  body_region: "upper_body",
  primary_muscle: "chest",
  muscle_focus: "mid_chest",
  secondary_muscles: ["shoulders"],
  equipment: ["bench", "bodyweight"],
  difficulty: "beginner",
  movement_pattern: "horizontal_push",
  exercise_type: "compound",
  caution_tags: [],
  labels: [],
  needs_review: false,
  is_programmable: true,
  body_position: "supported",
  stability_demand: "high",
  skill_demand: "moderate",
  impact_level: "low",
  axial_loading_level: "none",
  fatigue_cost: 4,
  setup_cost: 2,
  laterality: "unilateral",
  substitution_group: "horizontal_push",
  range_of_motion_profile: ["supported", "shortened"],
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
  content_type: created.content_type,
  body_region: created.body_region,
  primary_muscle: created.primary_muscle,
  muscle_focus: created.muscle_focus,
  secondary_muscles: created.secondary_muscles,
  equipment: created.equipment,
  difficulty: created.difficulty,
  movement_pattern: created.movement_pattern,
  exercise_type: created.exercise_type,
  caution_tags: created.caution_tags,
  labels: created.labels,
  needs_review: created.needs_review,
  is_programmable: created.is_programmable,
  body_position: created.body_position,
  stability_demand: created.stability_demand,
  skill_demand: created.skill_demand,
  impact_level: created.impact_level,
  axial_loading_level: created.axial_loading_level,
  fatigue_cost: created.fatigue_cost,
  setup_cost: created.setup_cost,
  laterality: created.laterality,
  substitution_group: created.substitution_group,
  range_of_motion_profile: created.range_of_motion_profile,
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

it("routes agent authentication through the backend with bounded payloads", async () => {
  const session = {
    session_id: "session-1",
    agent: "codex" as const,
    status: "waiting_for_user" as const,
    verification_url: "https://auth.openai.com/device",
    user_code: "ABCD-EFGH",
    input_label: null,
    expires_at: "2026-08-31T12:10:00Z",
    safe_error_message: null,
  };
  const fetchMock = vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(jsonResponse(session))
    .mockResolvedValueOnce(jsonResponse(session))
    .mockResolvedValueOnce(jsonResponse({ ...session, status: "waiting_for_input", user_code: null, input_label: "Authorization code" }))
    .mockResolvedValueOnce(new Response(null, { status: 204 }));

  await expect(startAdminAiAgentAuth("codex")).resolves.toEqual(session);
  await expect(getAdminAiAgentAuthSession("session-1")).resolves.toEqual(session);
  await expect(submitAdminAiAgentAuthInput("session-1", "AUTH-CODE")).resolves.toMatchObject({ status: "waiting_for_input" });
  await expect(cancelAdminAiAgentAuthSession("session-1")).resolves.toBeUndefined();

  expect(fetch).toHaveBeenNthCalledWith(
    1,
    "/api/v1/admin/ai/agent-service/auth/start",
    expect.objectContaining({ method: "POST", body: JSON.stringify({ agent: "codex" }) }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    2,
    "/api/v1/admin/ai/agent-service/auth/session-1",
    expect.objectContaining({ credentials: "include" }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    3,
    "/api/v1/admin/ai/agent-service/auth/session-1/input",
    expect.objectContaining({ method: "POST", body: JSON.stringify({ value: "AUTH-CODE" }) }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    4,
    "/api/v1/admin/ai/agent-service/auth/session-1",
    expect.objectContaining({ method: "DELETE" }),
  );
  expect(fetchMock.mock.calls.flat().join(" ")).not.toContain("9001");
});

it("cancels the active agent authentication through the backend", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch")
    .mockResolvedValue(jsonResponse({ agent: "codex", canceled: true }));

  await expect(cancelAdminAiAgentAuthActive("codex")).resolves.toEqual({
    agent: "codex",
    canceled: true,
  });

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/admin/ai/agent-service/auth/cancel-active",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ agent: "codex" }),
      credentials: "include",
    }),
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

it("lists admin exercises with focus and inactive filter support", async () => {
  const page: PaginatedAdminExercises = {
    items: [created],
    page: 1,
    page_size: 20,
    total: 1,
    total_pages: 1,
  };
  vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(page));

  await expect(getAdminExercises({
    primary_muscle: "chest",
    muscle_focus: "mid_chest",
    is_active: false,
    search: "push up",
  })).resolves.toEqual(page);
  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/admin/exercises?primary_muscle=chest&muscle_focus=mid_chest&is_active=false&search=push+up",
    expect.objectContaining({ credentials: "include" }),
  );
});

it("filters shared training templates by level and deletes by canonical id", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(jsonResponse({ items: [] }))
    .mockResolvedValueOnce(new Response(null, { status: 204 }));

  await expect(getAdminTrainingProgramTemplates(2, "intermediate")).resolves.toEqual({
    items: [],
  });
  await expect(deleteAdminTrainingProgramTemplate("template-17")).resolves.toBeUndefined();

  expect(fetch).toHaveBeenNthCalledWith(
    1,
    "/api/v1/admin/training-program-templates?days_per_week=2&training_level=intermediate",
    expect.objectContaining({ credentials: "include" }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    2,
    "/api/v1/admin/training-program-templates/template-17",
    expect.objectContaining({ method: "DELETE" }),
  );
});

it("filters structures by family and manages structure lifecycle", async () => {
  const structure = {
    slug: "5d-body-part-b",
    name_en: "5-Day Body-Part Split B",
    name_fa: "تقسیم عضله‌ای پنج‌روزه ب",
    days_per_week: 5,
    family: "split" as const,
    split_type: "body_part" as const,
    description_en: null,
    description_fa: null,
    days: [
      { day_number: 1, label_en: "Chest + Triceps", label_fa: "سینه + پشت بازو", day_type: null },
      { day_number: 2, label_en: "Back + Biceps", label_fa: "پشت + جلو بازو", day_type: null },
      { day_number: 3, label_en: "Quads", label_fa: "چهارسر", day_type: null },
      { day_number: 4, label_en: "Shoulders + Traps", label_fa: "سرشانه + کول", day_type: null },
      { day_number: 5, label_en: "Hamstrings", label_fa: "همسترینگ", day_type: null },
    ],
  };
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(jsonResponse({ items: [] }))
    .mockResolvedValueOnce(jsonResponse({ id: "structure-1", ...structure }))
    .mockResolvedValueOnce(jsonResponse({ id: "structure-1", ...structure }))
    .mockResolvedValueOnce(jsonResponse({ id: "structure-1", ...structure, is_active: false }));

  await expect(getAdminTrainingProgramStructures(5, "split", true)).resolves.toEqual({ items: [] });
  await expect(createAdminTrainingProgramStructure(structure)).resolves.toMatchObject({ id: "structure-1" });
  await expect(updateAdminTrainingProgramStructure("structure-1", structure)).resolves.toMatchObject({ id: "structure-1" });
  await expect(deactivateAdminTrainingProgramStructure("structure-1")).resolves.toMatchObject({ is_active: false });

  expect(fetch).toHaveBeenNthCalledWith(
    1,
    "/api/v1/admin/training-program-structures?days_per_week=5&family=split&include_inactive=true",
    expect.objectContaining({ credentials: "include" }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    2,
    "/api/v1/admin/training-program-structures",
    expect.objectContaining({ method: "POST", body: JSON.stringify(structure) }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    3,
    "/api/v1/admin/training-program-structures/structure-1",
    expect.objectContaining({ method: "PUT", body: JSON.stringify(structure) }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    4,
    "/api/v1/admin/training-program-structures/structure-1/deactivate",
    expect.objectContaining({ method: "PATCH" }),
  );
});

it("passes family through the training template library query", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ items: [] }));

  await expect(getAdminTrainingProgramTemplates(5, "advanced", undefined, "split")).resolves.toEqual({ items: [] });

  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/admin/training-program-templates?days_per_week=5&training_level=advanced&family=split",
    expect.objectContaining({ credentials: "include" }),
  );
});

it("lists and creates nutrition meal catalogue templates", async () => {
  const page = { items: [], categories: ["breakfast", "lunch", "post_workout", "snack", "dinner"] };
  const input = {
    code: "SN99",
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

it("uploads a meal catalogue image as multipart data", async () => {
  const file = new File(["image"], "meal.png", { type: "image/png" });
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    jsonResponse({ image_url: "/media/meal-catalogue/meal.png" }),
  );

  await expect(uploadAdminMealImage("meal-1", file)).resolves.toEqual({
    image_url: "/media/meal-catalogue/meal.png",
  });

  const [path, init] = vi.mocked(fetch).mock.calls[0];
  expect(path).toBe("/api/v1/nutrition/admin/meals/meal-1/image");
  expect(init).toEqual(expect.objectContaining({ method: "POST" }));
  const body = init?.body;
  expect(body).toBeInstanceOf(FormData);
  expect((body as FormData).get("file")).toBe(file);
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
