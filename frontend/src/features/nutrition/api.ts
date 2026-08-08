import { ApiError, request } from "../../shared/apiClient";
import type {
  NutritionProfile,
  NutritionProfileInput,
  NutritionEstimate,
  SafetyDecision,
  SafetyEvaluation,
  SafetyProfileInput,
  StructuredExercise,
  StructuredExerciseInput,
  WeeklyPlan,
  WeeklyPlanGeneration,
} from "./types";

const nutritionPath = "/api/v1/nutrition";

export function evaluateSafetyProfile(input: SafetyProfileInput): Promise<SafetyEvaluation> {
  return request<SafetyEvaluation>(`${nutritionPath}/safety/evaluate`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function saveSafetyProfile(input: SafetyProfileInput): Promise<SafetyDecision> {
  return request<SafetyDecision>(`${nutritionPath}/safety`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function getSafetyDecision(): Promise<SafetyDecision | null> {
  try {
    return await request<SafetyDecision>(`${nutritionPath}/safety`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function saveNutritionProfile(input: NutritionProfileInput): Promise<NutritionProfile> {
  return request<NutritionProfile>(`${nutritionPath}/profile`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function getNutritionProfile(): Promise<NutritionProfile | null> {
  try {
    return await request<NutritionProfile>(`${nutritionPath}/profile`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function saveStructuredExercise(
  input: StructuredExerciseInput,
): Promise<StructuredExercise> {
  return request<StructuredExercise>(`${nutritionPath}/structured-exercise`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function getStructuredExercise(): Promise<StructuredExercise | null> {
  try {
    return await request<StructuredExercise>(`${nutritionPath}/structured-exercise`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function createNutritionEstimate(): Promise<NutritionEstimate> {
  return request<NutritionEstimate>(`${nutritionPath}/estimates`, { method: "POST" });
}

export async function getCurrentNutritionEstimate(): Promise<NutritionEstimate | null> {
  try {
    return await request<NutritionEstimate>(`${nutritionPath}/estimates/current`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function createWeeklyNutritionPlan(): Promise<WeeklyPlanGeneration> {
  return request<WeeklyPlanGeneration>(`${nutritionPath}/plans`, { method: "POST" });
}

export async function getLatestWeeklyNutritionPlan(): Promise<WeeklyPlan | null> {
  try {
    return await request<WeeklyPlan>(`${nutritionPath}/plans/latest`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}
