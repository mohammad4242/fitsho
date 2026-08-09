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
  DailyTrackingSummary,
  NutritionAdherence,
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

export function getDailyTracking(entryDate: string): Promise<DailyTrackingSummary> {
  return request<DailyTrackingSummary>(`${nutritionPath}/tracking/days/${entryDate}`);
}

export function saveDailyCheckIn(
  entryDate: string,
  status: DailyTrackingSummary["check_in_status"],
): Promise<DailyTrackingSummary> {
  return request<DailyTrackingSummary>(`${nutritionPath}/tracking/check-in`, {
    method: "PUT",
    body: JSON.stringify({ entry_date: entryDate, status }),
  });
}

export function addQuickApproximation(input: {
  entry_date: string;
  display_name: string;
  calories: number;
  protein_g: number | null;
}): Promise<unknown> {
  return request(`${nutritionPath}/tracking/entries/quick`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function estimateFoodPhoto(file: File): Promise<{
  id: string;
  items: Array<{ name_guess: string; estimated_amount: number; unit: string; mapping_status: string }>;
  overall_confidence: number;
  needs_user_confirmation: true;
}> {
  const body = new FormData();
  body.append("file", file);
  return request(`${nutritionPath}/tracking/photo-estimates`, {
    method: "POST",
    headers: { "X-Fitsho-Food-Photo-Consent": "true" },
    body,
  });
}

export function confirmFoodPhoto(estimateId: string, entryDate: string): Promise<unknown> {
  return request(`${nutritionPath}/tracking/photo-estimates/${estimateId}/confirm`, {
    method: "POST",
    body: JSON.stringify({ entry_date: entryDate }),
  });
}

export function getNutritionAdherence(start: string, end: string): Promise<NutritionAdherence> {
  const query = new URLSearchParams({ start, end });
  return request<NutritionAdherence>(`${nutritionPath}/adherence?${query}`);
}

export function listLabDocuments(): Promise<Array<{ id: string; original_filename: string; review_status: string; uploaded_at: string }>> {
  return request(`${nutritionPath}/labs`);
}

export function uploadLabDocument(file: File): Promise<unknown> {
  const body = new FormData();
  body.append("file", file);
  return request(`${nutritionPath}/labs`, { method: "POST", body });
}

export function listPhysicianReviews(): Promise<Array<{ review_id: string; plan_id: string; status: string; priority: number; overdue: boolean }>> {
  return request(`${nutritionPath}/physician/reviews`);
}

export function claimPhysicianReview(reviewId: string): Promise<unknown> {
  return request(`${nutritionPath}/physician/reviews/${reviewId}/claim`, { method: "POST" });
}

export type SupplementOrder = { id: string; plan_id: string; name: string; dose_amount: number; dose_unit: string; frequency: string; duration_days: number; instructions: string; rationale: string | null; status: string; acknowledged_at: string | null };
export type SupplementCatalogueItem = { id: string; slug: string; name_fa: string; name_en: string };

export function listSupplementOrders(): Promise<SupplementOrder[]> { return request(`${nutritionPath}/supplement-orders`); }
export function acknowledgeSupplementOrder(orderId: string): Promise<SupplementOrder> { return request(`${nutritionPath}/supplement-orders/${orderId}/acknowledge`, { method: "POST", body: JSON.stringify({ adherence_note: null }) }); }
export function listSupplementCatalogue(): Promise<SupplementCatalogueItem[]> { return request(`${nutritionPath}/supplements/catalogue`); }
export function createPhysicianSupplementOrder(planId: string, supplementId: string): Promise<SupplementOrder> {
  return request(`${nutritionPath}/physician/plans/${planId}/supplement-orders`, { method: "POST", body: JSON.stringify({ supplement_id: supplementId, dose_amount: 1, dose_unit: "unit", daily_units: 1, frequency: "once_daily", duration_days: 30, instructions: "Follow physician instructions", rationale: "Physician-reviewed indication", rationale_user_visible: true, linked_gap_codes: [], linked_lab_document_ids: [] }) });
}
export function saveSupplementCatalogue(input: Record<string, unknown>): Promise<unknown> { return request(`${nutritionPath}/admin/supplements/catalogue`, { method: "PUT", body: JSON.stringify(input) }); }
