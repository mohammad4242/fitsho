import { request } from "../../shared/apiClient";
import {
  getAdminFoodCatalogue as readAdminFoodCatalogue,
  type AdminFoodCatalogueResponse,
  type FoodCatalogueQuery,
} from "../nutrition/api";
import type {
  AdminAiModel,
  AdminAiModelCheck,
  AdminAiModelCreate,
  AdminAiGenerationFailure,
  AdminAiModelTestRun,
  AdminAiModelsResponse,
  AdminAiModelSync,
  AdminAiModelUpdate,
  AdminAiRoutingSettings,
  AdminAiRoutingUpdate,
  AdminAiCatalogRefresh,
  AdminAiCatalogResponse,
  AdminAiProviderTest,
  AdminAiTaskConfig,
  AdminAiTaskConfigUpdate,
  AdminAiTaskType,
  AdminExercise,
  AdminExerciseCreate,
  AdminExerciseFilters,
  AdminExerciseMediaFiles,
  AdminMealCatalogueItem,
  AdminMealCatalogueResponse,
  AdminMealWrite,
  AdminNutritionProgram,
  AdminNutritionProgramPage,
  AdminNutritionProgramWrite,
  MealCategory,
  NutritionDietStyle,
  NutritionProgramLifecycle,
  AdminTrainingProgramStructuresResponse,
  AdminTrainingProgramStructure,
  AdminTrainingProgramStructureWrite,
  AdminTrainingProgramTemplatesResponse,
  AdminTrainingProgramTemplate,
  AdminTrainingProgramTemplateWrite,
  AdminTrainingTemplateSlotWrite,
  PaginatedAdminExercises,
  AdminPreparedRecipeWrite,
  PreparedRecipePreview,
  StructureFamily,
} from "./types";
import type { ExperienceLevel } from "../profile/types";

const adminExercisesPath = "/api/v1/admin/exercises";
const adminAiModelsPath = "/api/v1/admin/ai-models";
const adminTrainingProgramTemplatesPath = "/api/v1/admin/training-program-templates";
const adminMealCataloguePath = "/api/v1/nutrition/admin/meals";
const adminNutritionProgramsPath = "/api/v1/nutrition/admin/programs";

export function getAdminNutritionPrograms(input: {
  dietStyle?: NutritionDietStyle | "all";
  lifecycle?: NutritionProgramLifecycle;
} = {}): Promise<AdminNutritionProgramPage> {
  const query = new URLSearchParams();
  if (input.dietStyle && input.dietStyle !== "all") query.set("diet_style", input.dietStyle);
  if (input.lifecycle) query.set("lifecycle", input.lifecycle);
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return request<AdminNutritionProgramPage>(`${adminNutritionProgramsPath}${suffix}`);
}

export function getAdminNutritionProgram(programId: string): Promise<AdminNutritionProgram> {
  return request<AdminNutritionProgram>(`${adminNutritionProgramsPath}/${programId}`);
}

export function createAdminNutritionProgram(
  input: AdminNutritionProgramWrite,
): Promise<AdminNutritionProgram> {
  return request<AdminNutritionProgram>(adminNutritionProgramsPath, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateAdminNutritionProgram(
  programId: string,
  input: AdminNutritionProgramWrite,
): Promise<AdminNutritionProgram> {
  return request<AdminNutritionProgram>(`${adminNutritionProgramsPath}/${programId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function archiveAdminNutritionProgram(programId: string): Promise<void> {
  return request<void>(`${adminNutritionProgramsPath}/${programId}`, { method: "DELETE" });
}

export function restoreAdminNutritionProgram(programId: string): Promise<AdminNutritionProgram> {
  return request<AdminNutritionProgram>(`${adminNutritionProgramsPath}/${programId}/restore`, {
    method: "POST",
  });
}

export function getAdminMealCatalogue(
  category: MealCategory,
): Promise<AdminMealCatalogueResponse> {
  return request<AdminMealCatalogueResponse>(`${adminMealCataloguePath}?category=${category}`);
}

export function getAdminMeal(mealId: string): Promise<AdminMealCatalogueItem> {
  return request<AdminMealCatalogueItem>(`${adminMealCataloguePath}/${mealId}`);
}

export function createAdminMeal(input: AdminMealWrite): Promise<AdminMealCatalogueItem> {
  return request<AdminMealCatalogueItem>(adminMealCataloguePath, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateAdminMeal(
  mealId: string,
  input: AdminMealWrite,
): Promise<AdminMealCatalogueItem> {
  return request<AdminMealCatalogueItem>(`${adminMealCataloguePath}/${mealId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function previewAdminPreparedRecipe(
  input: AdminPreparedRecipeWrite,
): Promise<PreparedRecipePreview> {
  return request(`${adminMealCataloguePath}/prepared-recipe/preview`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function uploadAdminMealImage(
  mealId: string,
  file: File,
): Promise<{ image_url: string }> {
  const body = new FormData();
  body.append("file", file);
  return request(`${adminMealCataloguePath}/${mealId}/image`, {
    method: "POST",
    body,
  });
}

export function getAdminFoodCatalogue(
  input: FoodCatalogueQuery = {},
): Promise<AdminFoodCatalogueResponse> {
  return readAdminFoodCatalogue(input);
}

export function getAdminAiModels(): Promise<AdminAiModelsResponse> {
  return request<AdminAiModelsResponse>(adminAiModelsPath);
}

export function getAdminTrainingProgramTemplates(
  daysPerWeek: number,
  trainingLevel: ExperienceLevel | "all" = "all",
  structureId?: string,
  family?: StructureFamily,
): Promise<AdminTrainingProgramTemplatesResponse> {
  const query = new URLSearchParams({ days_per_week: String(daysPerWeek) });
  if (trainingLevel !== "all") query.set("training_level", trainingLevel);
  if (family) query.set("family", family);
  if (structureId) query.set("structure_id", structureId);
  return request<AdminTrainingProgramTemplatesResponse>(
    `${adminTrainingProgramTemplatesPath}?${query.toString()}`,
  );
}

export function getAdminTrainingProgramStructures(
  daysPerWeek?: number,
  includeInactive?: boolean,
): Promise<AdminTrainingProgramStructuresResponse>;
export function getAdminTrainingProgramStructures(
  daysPerWeek?: number,
  family?: StructureFamily,
  includeInactive?: boolean,
): Promise<AdminTrainingProgramStructuresResponse>;
export function getAdminTrainingProgramStructures(
  daysPerWeek?: number,
  familyOrIncludeInactive?: StructureFamily | boolean,
  includeInactive: boolean = false,
): Promise<AdminTrainingProgramStructuresResponse> {
  const family = typeof familyOrIncludeInactive === "string" ? familyOrIncludeInactive : undefined;
  const shouldIncludeInactive = typeof familyOrIncludeInactive === "boolean"
    ? familyOrIncludeInactive
    : includeInactive;
  const query = new URLSearchParams();
  if (daysPerWeek) query.set("days_per_week", String(daysPerWeek));
  if (family) query.set("family", family);
  if (shouldIncludeInactive) query.set("include_inactive", "true");
  return request<AdminTrainingProgramStructuresResponse>(
    `/api/v1/admin/training-program-structures?${query.toString()}`,
  );
}

const adminTrainingProgramStructuresPath = "/api/v1/admin/training-program-structures";

export function getAdminTrainingProgramStructure(
  structureId: string,
): Promise<AdminTrainingProgramStructure> {
  return request<AdminTrainingProgramStructure>(`${adminTrainingProgramStructuresPath}/${structureId}`);
}

export function createAdminTrainingProgramStructure(
  input: AdminTrainingProgramStructureWrite,
): Promise<AdminTrainingProgramStructure> {
  return request<AdminTrainingProgramStructure>(adminTrainingProgramStructuresPath, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateAdminTrainingProgramStructure(
  structureId: string,
  input: AdminTrainingProgramStructureWrite,
): Promise<AdminTrainingProgramStructure> {
  return request<AdminTrainingProgramStructure>(`${adminTrainingProgramStructuresPath}/${structureId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function activateAdminTrainingProgramStructure(
  structureId: string,
): Promise<AdminTrainingProgramStructure> {
  return request<AdminTrainingProgramStructure>(
    `${adminTrainingProgramStructuresPath}/${structureId}/activate`,
    { method: "PATCH" },
  );
}

export function deactivateAdminTrainingProgramStructure(
  structureId: string,
): Promise<AdminTrainingProgramStructure> {
  return request<AdminTrainingProgramStructure>(
    `${adminTrainingProgramStructuresPath}/${structureId}/deactivate`,
    { method: "PATCH" },
  );
}


export function getAdminTrainingProgramTemplate(
  templateId: string,
): Promise<AdminTrainingProgramTemplate> {
  return request<AdminTrainingProgramTemplate>(`${adminTrainingProgramTemplatesPath}/${templateId}`);
}

export function createAdminTrainingProgramTemplate(
  input: AdminTrainingProgramTemplateWrite,
): Promise<AdminTrainingProgramTemplate> {
  return request<AdminTrainingProgramTemplate>(adminTrainingProgramTemplatesPath, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateAdminTrainingProgramTemplate(
  templateId: string,
  input: AdminTrainingProgramTemplateWrite,
): Promise<AdminTrainingProgramTemplate> {
  return request<AdminTrainingProgramTemplate>(`${adminTrainingProgramTemplatesPath}/${templateId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function updateAdminTrainingTemplateSlot(
  templateId: string,
  dayId: string,
  slotId: string,
  input: AdminTrainingTemplateSlotWrite,
): Promise<AdminTrainingProgramTemplate> {
  return request<AdminTrainingProgramTemplate>(
    `${adminTrainingProgramTemplatesPath}/${templateId}/days/${dayId}/slots/${slotId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
}

export function deleteAdminTrainingTemplateSlot(
  templateId: string,
  dayId: string,
  slotId: string,
): Promise<AdminTrainingProgramTemplate> {
  return request<AdminTrainingProgramTemplate>(
    `${adminTrainingProgramTemplatesPath}/${templateId}/days/${dayId}/slots/${slotId}`,
    { method: "DELETE" },
  );
}

export function deleteAdminTrainingProgramTemplate(templateId: string): Promise<void> {
  return request<void>(`${adminTrainingProgramTemplatesPath}/${templateId}`, {
    method: "DELETE",
  });
}

export function getAdminAiGenerationFailures(
  limit = 20,
): Promise<AdminAiGenerationFailure[]> {
  return request<AdminAiGenerationFailure[]>(
    `/api/v1/admin/ai-generation-failures?limit=${limit}`,
  );
}

export function getAdminAiModelTestRuns(limit = 20): Promise<AdminAiModelTestRun[]> {
  return request<AdminAiModelTestRun[]>(`/api/v1/admin/ai-model-test-runs?limit=${limit}`);
}

export function updateAdminAiRouting(
  input: AdminAiRoutingUpdate,
): Promise<AdminAiRoutingSettings> {
  return request<AdminAiRoutingSettings>("/api/v1/admin/ai-routing", {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function updateAdminAiModel(
  modelId: string,
  input: AdminAiModelUpdate,
): Promise<AdminAiModel> {
  return request<AdminAiModel>(`${adminAiModelsPath}/${modelId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function createAdminAiModel(input: AdminAiModelCreate): Promise<AdminAiModel> {
  return request<AdminAiModel>(adminAiModelsPath, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function syncAdminAiModels(): Promise<AdminAiModelSync> {
  return request<AdminAiModelSync>(`${adminAiModelsPath}/sync`, { method: "POST" });
}

export function testAdminAiModel(modelId: string): Promise<AdminAiModelCheck> {
  return request<AdminAiModelCheck>(`${adminAiModelsPath}/${modelId}/test`, {
    method: "POST",
  });
}

export function getAdminAiTaskConfigs(): Promise<AdminAiTaskConfig[]> {
  return request<AdminAiTaskConfig[]>("/api/v1/admin/ai/task-configs");
}

export function getAdminAiTaskModels(
  taskType: AdminAiTaskType,
  search = "",
): Promise<AdminAiCatalogResponse> {
  const query = new URLSearchParams({ task_type: taskType });
  if (search.trim()) query.set("search", search.trim());
  return request<AdminAiCatalogResponse>(`/api/v1/admin/ai/models?${query.toString()}`);
}

export function saveAdminAiTaskConfig(
  taskType: AdminAiTaskType,
  input: AdminAiTaskConfigUpdate,
): Promise<AdminAiTaskConfig> {
  return request<AdminAiTaskConfig>(`/api/v1/admin/ai/task-configs/${taskType}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function testAdminAiProvider(apiKey?: string): Promise<AdminAiProviderTest> {
  return request<AdminAiProviderTest>("/api/v1/admin/ai/providers/test", {
    method: "POST",
    body: JSON.stringify({ provider: "openrouter", ...(apiKey ? { api_key: apiKey } : {}) }),
  });
}

export function refreshAdminAiModels(): Promise<AdminAiCatalogRefresh> {
  return request<AdminAiCatalogRefresh>("/api/v1/admin/ai/models/refresh", {
    method: "POST",
  });
}

export function getAdminExercises(
  filters: AdminExerciseFilters = {},
): Promise<PaginatedAdminExercises> {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (Array.isArray(value)) {
      value.forEach((item) => searchParams.append(key, item));
      continue;
    }
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  }
  const query = searchParams.toString();
  return request<PaginatedAdminExercises>(
    query ? `${adminExercisesPath}?${query}` : adminExercisesPath,
  );
}

export function createAdminExercise(
  input: AdminExerciseCreate,
  media: File | null = null,
  mediaAssets: AdminExerciseMediaFiles = [],
): Promise<AdminExercise> {
  const body = new FormData();
  body.set("payload", JSON.stringify(input));
  if (media !== null) {
    body.set("media", media);
  }
  mediaAssets.forEach((file) => body.append("media_files", file));
  return request<AdminExercise>(adminExercisesPath, {
    method: "POST",
    body,
  });
}

export function getAdminExercise(exerciseId: string): Promise<AdminExercise> {
  return request<AdminExercise>(`${adminExercisesPath}/${exerciseId}`);
}

export function updateAdminExercise(
  exerciseId: string,
  input: AdminExerciseCreate,
  media: File | null = null,
  mediaAssets: AdminExerciseMediaFiles = [],
): Promise<AdminExercise> {
  const body = new FormData();
  body.set("payload", JSON.stringify(input));
  if (media !== null) {
    body.set("media", media);
  }
  mediaAssets.forEach((file) => body.append("media_files", file));
  return request<AdminExercise>(`${adminExercisesPath}/${exerciseId}`, {
    method: "PATCH",
    body,
  });
}

export function deleteAdminExercise(exerciseId: string): Promise<void> {
  return request<void>(`${adminExercisesPath}/${exerciseId}`, { method: "DELETE" });
}
