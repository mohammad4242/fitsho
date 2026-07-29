import { request } from "../../shared/apiClient";
import type {
  AdminExercise,
  AdminExerciseCreate,
  AdminExerciseFilters,
  AdminExerciseMediaFiles,
  PaginatedAdminExercises,
} from "./types";

const adminExercisesPath = "/api/v1/admin/exercises";

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
  mediaAssets: AdminExerciseMediaFiles = {},
): Promise<AdminExercise> {
  const body = new FormData();
  body.set("payload", JSON.stringify(input));
  if (media !== null) {
    body.set("media", media);
  }
  for (const [key, file] of Object.entries(mediaAssets)) {
    if (file !== undefined) body.set(`media_${key}`, file);
  }
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
  mediaAssets: AdminExerciseMediaFiles = {},
): Promise<AdminExercise> {
  const body = new FormData();
  body.set("payload", JSON.stringify(input));
  if (media !== null) {
    body.set("media", media);
  }
  for (const [key, file] of Object.entries(mediaAssets)) {
    if (file !== undefined) body.set(`media_${key}`, file);
  }
  return request<AdminExercise>(`${adminExercisesPath}/${exerciseId}`, {
    method: "PATCH",
    body,
  });
}
