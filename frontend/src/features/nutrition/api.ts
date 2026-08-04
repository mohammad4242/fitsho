import { ApiError, request } from "../../shared/apiClient";
import type {
  NutritionProfile,
  NutritionProfileInput,
  SafetyDecision,
  SafetyEvaluation,
  SafetyProfileInput,
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
