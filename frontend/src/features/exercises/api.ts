import { ApiError, request } from "../../shared/apiClient";
import type {
  ExerciseCategories,
  ExerciseDetail,
  ExerciseFilters,
  PaginatedExercises,
} from "./types";

const exercisesPath = "/api/v1/exercises";

export function getExerciseCategories(): Promise<ExerciseCategories> {
  return request<ExerciseCategories>("/api/v1/exercise-categories");
}

export function getExercises(filters: ExerciseFilters = {}): Promise<PaginatedExercises> {
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
  return request<PaginatedExercises>(query ? `${exercisesPath}?${query}` : exercisesPath);
}

export async function getExercise(slug: string): Promise<ExerciseDetail | null> {
  try {
    return await request<ExerciseDetail>(`${exercisesPath}/${encodeURIComponent(slug)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}
