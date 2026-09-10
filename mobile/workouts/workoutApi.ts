import {
  ApiError,
  type BinaryDownload,
  type BinaryDownloadRequest,
  type TransportRequest,
} from "@fitician/core";
import type { components } from "@fitician/core";

export type WorkoutPlan = components["schemas"]["WorkoutPlanResponse"];
export type WorkoutPlanExercise = components["schemas"]["WorkoutPlanExerciseResponse"];
export type WorkoutDay = components["schemas"]["WorkoutDayResponse"];
export type WorkoutPlanGeneration = components["schemas"]["WorkoutPlanGenerateResponse"];
export type WorkoutPlanVersionSummary = components["schemas"]["WorkoutPlanVersionSummaryResponse"];
export type ProgramGenerationOverrides = components["schemas"]["ProgramGenerationOverrides"];

export type AuthenticatedWorkoutRequest = <TResponse>(
  request: TransportRequest,
) => Promise<TResponse>;

export type AuthenticatedWorkoutDownload = (
  request: BinaryDownloadRequest,
) => Promise<BinaryDownload>;

export interface WorkoutPlanApi {
  deletePlan(planId: string): Promise<void>;
  downloadPdf(planId: string): Promise<BinaryDownload>;
  generate(overrides?: ProgramGenerationOverrides | null): Promise<WorkoutPlanGeneration>;
  get(planId: string): Promise<WorkoutPlan>;
  getActive(): Promise<WorkoutPlan | null>;
  getHistory(): Promise<WorkoutPlanVersionSummary[]>;
}

const workoutPlansPath = "/api/v1/workout-plans";

function jsonBody(value: object | null): TransportRequest["body"] {
  return value as TransportRequest["body"];
}

export function createWorkoutPlanApi(
  request: AuthenticatedWorkoutRequest,
  download: AuthenticatedWorkoutDownload,
): WorkoutPlanApi {
  return {
    deletePlan(planId) {
      return request<void>({
        method: "DELETE",
        path: `${workoutPlansPath}/${encodeURIComponent(planId)}`,
      });
    },

    async downloadPdf(planId) {
      return download({
        method: "GET",
        path: `${workoutPlansPath}/${encodeURIComponent(planId)}/pdf`,
        responseType: "binary",
      });
    },

    generate(overrides) {
      const input: TransportRequest = overrides === undefined
        ? {
          method: "POST",
          path: `${workoutPlansPath}/generate`,
        }
        : {
          body: jsonBody(overrides),
          method: "POST",
          path: `${workoutPlansPath}/generate`,
        };
      return request<WorkoutPlanGeneration>(input);
    },

    get: (planId) => request<WorkoutPlan>({
      method: "GET",
      path: `${workoutPlansPath}/${encodeURIComponent(planId)}`,
    }),

    async getActive() {
      try {
        return await request<WorkoutPlan>({
          method: "GET",
          path: `${workoutPlansPath}/active`,
        });
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          return null;
        }
        throw error;
      }
    },

    getHistory: () => request<WorkoutPlanVersionSummary[]>({
      method: "GET",
      path: `${workoutPlansPath}/history`,
    }),
  };
}
