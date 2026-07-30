import { request } from "../../shared/apiClient";
import type {
  AdminAiModel,
  AdminAiModelCheck,
  AdminAiModelCreate,
  AdminAiGenerationFailure,
  AdminAiModelsResponse,
  AdminAiModelSync,
  AdminAiModelUpdate,
  AdminAiRoutingSettings,
  AdminAiRoutingUpdate,
  AdminExercise,
  AdminExerciseCreate,
  AdminExerciseFilters,
  AdminExerciseMediaFiles,
  PaginatedAdminExercises,
} from "./types";

const adminExercisesPath = "/api/v1/admin/exercises";
const adminAiModelsPath = "/api/v1/admin/ai-models";

export function getAdminAiModels(): Promise<AdminAiModelsResponse> {
  return request<AdminAiModelsResponse>(adminAiModelsPath);
}

export function getAdminAiGenerationFailures(
  limit = 20,
): Promise<AdminAiGenerationFailure[]> {
  return request<AdminAiGenerationFailure[]>(
    `/api/v1/admin/ai-generation-failures?limit=${limit}`,
  );
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

export function getAdminExercises(
  filters: AdminExerciseFilters = {},
): Promise<PaginatedAdminExercises> {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
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
