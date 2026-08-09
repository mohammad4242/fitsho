import { ApiError, request } from "../../shared/apiClient";

import type { WorkoutPlan, WorkoutPlanGeneration, WorkoutPlanVersionSummary } from "./types";

const workoutPlansPath = "/api/v1/workout-plans";

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
