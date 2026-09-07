import { ApiError, type TransportRequest } from "@fitician/core";
import type { components } from "@fitician/core";

export type WorkoutCycleCurrent = components["schemas"]["WorkoutCycleCurrentResponse"];
export type WorkoutCycleWeeklyCheckIn = components["schemas"]["WorkoutCycleWeeklyCheckInResponse"];
export type WorkoutCycleWeeklyCheckInInput = components["schemas"]["WorkoutCycleWeeklyCheckInUpsertRequest"];
export type WorkoutExerciseReplacementInput = components["schemas"]["WorkoutExerciseReplacementCreateRequest"];
export type WorkoutExerciseReplacement = components["schemas"]["WorkoutExerciseReplacementResponse"];
export type WorkoutCycleCompletionFeedback = components["schemas"]["WorkoutCycleCompletionFeedbackResponse"];
export type WorkoutCycleCompletionFeedbackInput = components["schemas"]["CompletionFeedbackInput"];

export type AuthenticatedWorkoutCycleRequest = <TResponse>(
  request: TransportRequest,
) => Promise<TResponse>;

export interface WorkoutCycleApi {
  getCompletionFeedback(): Promise<WorkoutCycleCompletionFeedback | null>;
  getCurrent(): Promise<WorkoutCycleCurrent | null>;
  getWeeklyCheckIn(): Promise<WorkoutCycleWeeklyCheckIn | null>;
  recordReplacement(input: WorkoutExerciseReplacementInput): Promise<WorkoutExerciseReplacement>;
  saveCompletionFeedback(input: WorkoutCycleCompletionFeedbackInput): Promise<WorkoutCycleCompletionFeedback>;
  saveWeeklyCheckIn(input: WorkoutCycleWeeklyCheckInInput): Promise<WorkoutCycleWeeklyCheckIn>;
}

const currentCyclePath = "/api/v1/workout-cycles/current";

function jsonBody(value: object): TransportRequest["body"] {
  return value as TransportRequest["body"];
}

async function optional<TResponse>(
  request: AuthenticatedWorkoutCycleRequest,
  path: string,
): Promise<TResponse | null> {
  try {
    return await request<TResponse>({ method: "GET", path });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function createWorkoutCycleApi(request: AuthenticatedWorkoutCycleRequest): WorkoutCycleApi {
  return {
    getCompletionFeedback: () => optional<WorkoutCycleCompletionFeedback>(
      request,
      `${currentCyclePath}/completion-feedback`,
    ),
    getCurrent: () => optional<WorkoutCycleCurrent>(request, currentCyclePath),
    getWeeklyCheckIn: () => optional<WorkoutCycleWeeklyCheckIn>(
      request,
      `${currentCyclePath}/weekly-check-in`,
    ),
    recordReplacement: (input) => request<WorkoutExerciseReplacement>({
      body: jsonBody(input),
      method: "POST",
      path: `${currentCyclePath}/replacements`,
    }),
    saveCompletionFeedback: (input) => request<WorkoutCycleCompletionFeedback>({
      body: jsonBody(input),
      method: "PUT",
      path: `${currentCyclePath}/completion-feedback`,
    }),
    saveWeeklyCheckIn: (input) => request<WorkoutCycleWeeklyCheckIn>({
      body: jsonBody(input),
      method: "PUT",
      path: `${currentCyclePath}/weekly-check-in`,
    }),
  };
}
