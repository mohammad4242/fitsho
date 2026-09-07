import { ApiError, type TransportRequest } from "@fitician/core";
import type { components } from "@fitician/core";
import type { ExerciseFilters } from "@fitician/core/exercises";

export type {
  ExerciseFilters,
} from "@fitician/core/exercises";

export type ExerciseCategories = components["schemas"]["ExerciseCategories"];
export type ExerciseDetail = components["schemas"]["ExerciseDetail"];
export type ExerciseSummary = components["schemas"]["ExerciseSummary"];
export type PaginatedExercises = components["schemas"]["PaginatedExercises"];

export type AuthenticatedExerciseRequest = <TResponse>(
  request: TransportRequest,
) => Promise<TResponse>;

export interface ExerciseApi {
  getCategories(): Promise<ExerciseCategories>;
  get(slug: string, presentation?: "male" | "female"): Promise<ExerciseDetail | null>;
  list(filters?: ExerciseFilters): Promise<PaginatedExercises>;
}

const categoriesPath = "/api/v1/exercise-categories";
const exercisesPath = "/api/v1/exercises";

const filterKeys: readonly (keyof ExerciseFilters)[] = [
  "content_type",
  "body_region",
  "primary_muscle",
  "muscle_focus",
  "equipment",
  "difficulty",
  "exercise_type",
  "labels",
  "search",
  "page",
  "page_size",
];

export function serializeExerciseFilters(filters: ExerciseFilters = {}): string {
  const searchParams = new URLSearchParams();
  for (const key of filterKeys) {
    const value = filters[key];
    if (Array.isArray(value)) {
      for (const item of value) {
        searchParams.append(key, item);
      }
    } else if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  }
  return searchParams.toString();
}

async function optionalDetail(
  request: AuthenticatedExerciseRequest,
  path: string,
): Promise<ExerciseDetail | null> {
  try {
    return await request<ExerciseDetail>({ method: "GET", path });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export function createExerciseApi(request: AuthenticatedExerciseRequest): ExerciseApi {
  return {
    get: (slug, presentation) => {
      const query = presentation === undefined ? "" : `?presentation=${presentation}`;
      return optionalDetail(
        request,
        `${exercisesPath}/${encodeURIComponent(slug)}${query}`,
      );
    },
    getCategories: () => request<ExerciseCategories>({ method: "GET", path: categoriesPath }),
    list: (filters = {}) => {
      const query = serializeExerciseFilters(filters);
      return request<PaginatedExercises>({
        method: "GET",
        path: query ? `${exercisesPath}?${query}` : exercisesPath,
      });
    },
  };
}
