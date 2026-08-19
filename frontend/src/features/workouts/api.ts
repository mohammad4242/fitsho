import { ApiError, request, requestBlob } from "../../shared/apiClient";

import type {
  WorkoutExerciseReplacement,
  WorkoutExerciseReplacementReason,
  WorkoutExerciseReplacementScope,
  WorkoutCycleWeeklyCheckIn,
  WorkoutCycleWeeklyCheckInInput,
  WorkoutCycleCurrent,
  WorkoutCycleCompletionFeedbackContext,
  WorkoutCycleCompletionFeedbackInput,
  WorkoutPlan,
  WorkoutPlanGeneration,
  WorkoutPlanVersionSummary,
} from "./types";

const workoutPlansPath = "/api/v1/workout-plans";
const workoutCyclesPath = "/api/v1/workout-cycles";

export async function getCurrentWorkoutCycle(): Promise<WorkoutCycleCurrent | null> {
  try {
    return await request<WorkoutCycleCurrent>(`${workoutCyclesPath}/current`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function getActiveWorkoutPlan(): Promise<WorkoutPlan | null> {
  try {
    return await request<WorkoutPlan>(`${workoutPlansPath}/active`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export function generateWorkoutPlan(): Promise<WorkoutPlanGeneration> {
  return request<WorkoutPlanGeneration>(`${workoutPlansPath}/generate`, { method: "POST" });
}

export function getWorkoutPlanHistory(): Promise<WorkoutPlanVersionSummary[]> {
  return request<WorkoutPlanVersionSummary[]>(`${workoutPlansPath}/history`);
}

export function getWorkoutPlan(planId: string): Promise<WorkoutPlan> {
  return request<WorkoutPlan>(`${workoutPlansPath}/${planId}`);
}

export function downloadWorkoutPlanPdf(planId: string): Promise<Blob> {
  return requestBlob(`${workoutPlansPath}/${planId}/pdf`);
}

export function recordExerciseReplacement(input: {
  workout_plan_exercise_id: string;
  replacement_exercise_id: string;
  reason: WorkoutExerciseReplacementReason;
  scope: WorkoutExerciseReplacementScope;
}): Promise<WorkoutExerciseReplacement> {
  return request<WorkoutExerciseReplacement>("/api/v1/workout-cycles/current/replacements", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function getCurrentWeeklyCheckIn(): Promise<WorkoutCycleWeeklyCheckIn | null> {
  try {
    return await request<WorkoutCycleWeeklyCheckIn>(`${workoutCyclesPath}/current/weekly-check-in`);
  } catch (error) {
    if (
      error instanceof ApiError
      && error.status === 404
      && error.message === "No weekly check-in for current week"
    ) {
      return null;
    }
    throw error;
  }
}

export function saveCurrentWeeklyCheckIn(
  input: WorkoutCycleWeeklyCheckInInput,
): Promise<WorkoutCycleWeeklyCheckIn> {
  return request<WorkoutCycleWeeklyCheckIn>(`${workoutCyclesPath}/current/weekly-check-in`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function getCurrentCompletionFeedback(): Promise<WorkoutCycleCompletionFeedbackContext | null> {
  try {
    return await request<WorkoutCycleCompletionFeedbackContext>(`${workoutCyclesPath}/current/completion-feedback`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function saveCurrentCompletionFeedback(
  input: WorkoutCycleCompletionFeedbackInput,
): Promise<WorkoutCycleCompletionFeedbackContext> {
  return request<WorkoutCycleCompletionFeedbackContext>(`${workoutCyclesPath}/current/completion-feedback`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}
