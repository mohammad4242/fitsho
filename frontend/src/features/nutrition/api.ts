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
  ShoppingList,
  WeeklyPlanHistoryItem,
} from "./types";

const nutritionPath = "/api/v1/nutrition";

export type FoodCatalogueNutrient = {
  nutrient_code: string;
  value_per_100g: number;
  unit: string;
  unit_form: string;
  source_name: string;
  source_reference: string;
  confidence: "low" | "medium" | "high";
};

export type FoodCatalogueItem = {
  id: string;
  slug: string;
  name_fa: string;
  name_en: string;
  image_url: string | null;
  category: string;
  measurement_basis: "raw" | "dry" | "as_purchased";
  nutrient_basis: { quantity: string; unit: string };
  portions: FoodCataloguePortion[];
  macros: Record<"energy_kcal" | "protein_g" | "carbohydrate_g" | "total_fat_g" | "fibre_g", string | null>;
  nutrients: FoodCatalogueNutrient[];
  source: {
    name: string;
    reference: string;
    source_food_id: string | null;
    data_version: string;
    access_date: string | null;
  };
};

export type FoodCataloguePortion = {
  code: "piece" | "palm" | "cup" | "tablespoon" | "teaspoon";
  quantity: string;
  label_fa: string;
  label_en: string;
  grams: string;
  is_default: boolean;
  source_name: string;
  source_reference: string;
};

export type AdminFoodCatalogueItem = FoodCatalogueItem & {
  price: {
    status: "accepted" | "not_found";
    reference_price_irr?: string;
    reference_unit?: "IRR_PER_KG" | "IRR_PER_LITER" | "IRR_PER_UNIT";
    observed_at?: string;
    /** Deprecated compatibility fields; member UI displays IRR. */
    reference_price_toman?: string;
    canonical_unit?: string;
    accepted_at?: string;
    source?: "automatic" | "manual_override";
  };
};

export type FoodCatalogueResponse = {
  items: FoodCatalogueItem[];
  page: number;
  page_size: number;
  total: number;
  categories: string[];
};

export type FoodCatalogueQuery = {
  query?: string;
  category?: string;
  page?: number;
  pageSize?: number;
};

export type AdminFoodCatalogueResponse = Omit<FoodCatalogueResponse, "items"> & {
  items: AdminFoodCatalogueItem[];
};

export function getFoodCatalogue(input: FoodCatalogueQuery = {}): Promise<FoodCatalogueResponse> {
  return getCatalogueAtPath<FoodCatalogueResponse>("food-catalogue", input);
}

export function getAdminFoodCatalogue(input: FoodCatalogueQuery = {}): Promise<AdminFoodCatalogueResponse> {
  return getCatalogueAtPath<AdminFoodCatalogueResponse>("admin/food-catalogue", input);
}

function getCatalogueAtPath<T>(path: string, input: FoodCatalogueQuery): Promise<T> {
  const parameters = new URLSearchParams();
  if (input.query) parameters.set("q", input.query);
  if (input.category) parameters.set("category", input.category);
  parameters.set("page", String(input.page ?? 1));
  parameters.set("page_size", String(input.pageSize ?? 24));
  return request<T>(`${nutritionPath}/${path}?${parameters}`);
}

export function saveCatalogueFood(input: Record<string, unknown>): Promise<unknown> {
  return request(`${nutritionPath}/admin/foods`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function uploadCatalogueFoodImage(
  slug: string,
  file: File,
): Promise<{ image_url: string }> {
  const body = new FormData();
  body.append("file", file);
  return request(`${nutritionPath}/admin/foods/${slug}/image`, {
    method: "POST",
    body,
  });
}

export function saveFoodPriceOverride(
  slug: string,
  input: { reference_price_toman: string; canonical_unit: string; reason: string },
): Promise<{ id: string; source: "manual_override" }> {
  return request(`${nutritionPath}/admin/foods/${slug}/price-override`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

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

export function getWeeklyNutritionPlan(planId: string): Promise<WeeklyPlan> {
  return request(`${nutritionPath}/plans/${planId}`);
}

export function listWeeklyNutritionPlans(): Promise<WeeklyPlanHistoryItem[]> {
  return request(`${nutritionPath}/plans/history`);
}

export function getShoppingList(planId: string): Promise<ShoppingList> {
  return request(`${nutritionPath}/plans/${planId}/shopping-list`);
}

export function setMealLock(planId: string, mealId: string, isLocked: boolean): Promise<{ is_locked: boolean }> {
  return request(`${nutritionPath}/plans/${planId}/meals/${mealId}/lock`, {
    method: "PUT",
    body: JSON.stringify({ is_locked: isLocked }),
  });
}

export function saveMealFeedback(planId: string, mealId: string, feedbackType: "liked" | "disliked" | "do_not_suggest_again" | "prefer_more_often" | "too_large" | "too_small"): Promise<unknown> {
  return request(`${nutritionPath}/plans/${planId}/meals/${mealId}/feedback`, {
    method: "PUT",
    body: JSON.stringify({ feedback_type: feedbackType, notes: null }),
  });
}

export function previewMealRemoval(planId: string, mealId: string): Promise<{ expected_plan_revision_id: string; meal_id: string; daily_delta: Record<string, number>; weekly_cost_delta_irr: number; new_warning_codes: string[] }> {
  return request(`${nutritionPath}/plans/${planId}/edits/remove-meal/preview?meal_id=${mealId}`, { method: "POST" });
}

export function confirmMealRemoval(planId: string, mealId: string, expectedPlanRevisionId: string): Promise<WeeklyPlan> {
  return request(`${nutritionPath}/plans/${planId}/edits/remove-meal/confirm`, {
    method: "POST",
    body: JSON.stringify({ meal_id: mealId, expected_plan_revision_id: expectedPlanRevisionId }),
  });
}

export type PlanEditPreview = { expected_plan_revision_id: string; meal_id: string; weekly_cost_delta_irr?: number; cost_delta_irr?: number };
export function previewMealReplacement(planId: string, mealId: string, replacementMealId: string): Promise<PlanEditPreview> { return request(`${nutritionPath}/plans/${planId}/edits/replace-meal/preview`, { method: "POST", body: JSON.stringify({ expected_plan_revision_id: planId, meal_id: mealId, replacement_meal_id: replacementMealId }) }); }
export function confirmMealReplacement(planId: string, mealId: string, replacementMealId: string): Promise<WeeklyPlan> { return request(`${nutritionPath}/plans/${planId}/edits/replace-meal/confirm`, { method: "POST", body: JSON.stringify({ expected_plan_revision_id: planId, meal_id: mealId, replacement_meal_id: replacementMealId }) }); }
export function previewFoodReplacement(planId: string, mealId: string, foodId: string, replacementFoodId: string): Promise<PlanEditPreview> { return request(`${nutritionPath}/plans/${planId}/edits/replace-food/preview`, { method: "POST", body: JSON.stringify({ expected_plan_revision_id: planId, meal_id: mealId, food_id: foodId, replacement_food_id: replacementFoodId }) }); }
export function confirmFoodReplacement(planId: string, mealId: string, foodId: string, replacementFoodId: string): Promise<WeeklyPlan> { return request(`${nutritionPath}/plans/${planId}/edits/replace-food/confirm`, { method: "POST", body: JSON.stringify({ expected_plan_revision_id: planId, meal_id: mealId, food_id: foodId, replacement_food_id: replacementFoodId }) }); }
export function partialRegeneratePlan(planId: string, dayIndexes: number[]): Promise<WeeklyPlan> { return request(`${nutritionPath}/plans/${planId}/edits/partial-regenerate`, { method: "POST", body: JSON.stringify({ expected_plan_revision_id: planId, day_indexes: dayIndexes }) }); }

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

export type CatalogueFood = { id: string; slug: string; name_fa: string; name_en: string; canonical_unit: string };
export function listCatalogueFoods(): Promise<CatalogueFood[]> { return request(`${nutritionPath}/foods`); }
export function addCatalogueFoodEntry(input: { entry_date: string; food_id: string; grams: number; note: string | null }): Promise<unknown> { return request(`${nutritionPath}/tracking/entries/catalogue`, { method: "POST", body: JSON.stringify(input) }); }
export function deleteTrackingEntry(entryId: string): Promise<void> { return request(`${nutritionPath}/tracking/entries/${entryId}`, { method: "DELETE" }); }
export function editTrackingEntry(entryId: string, input: { grams?: number; display_name?: string; calories?: number; protein_g?: number | null; note?: string | null }): Promise<DailyTrackingSummary["entries"][number]> { return request(`${nutritionPath}/tracking/entries/${entryId}`, { method: "PUT", body: JSON.stringify(input) }); }
export function listRecentFoods(): Promise<Array<{ food_id: string; display_name: string; last_quantity_grams: number | null; last_entry_date: string }>> { return request(`${nutritionPath}/tracking/recent-foods`); }
export function getTrackingHistory(start: string, end: string): Promise<DailyTrackingSummary[]> { return request(`${nutritionPath}/tracking/history?${new URLSearchParams({ start, end })}`); }
export function adjustPlannedMeal(mealId: string, input: { entry_date: string; status: "consumed" | "adjusted" | "skipped"; portion_ratio: number | null }): Promise<DailyTrackingSummary> { return request(`${nutritionPath}/tracking/planned-meals/${mealId}`, { method: "PUT", body: JSON.stringify(input) }); }

export function estimateFoodPhoto(file: File): Promise<{
  id: string;
  items: Array<{ item_id: string; food_id: string | null; name_guess: string; estimated_amount: number; unit: string; mapping_status: string }>;
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

export function correctFoodPhotoItem(estimateId: string, itemId: string, input: { food_id?: string; estimated_amount?: number; remove?: boolean }): ReturnType<typeof estimateFoodPhoto> {
  return request(`${nutritionPath}/tracking/photo-estimates/${estimateId}/items/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function confirmFoodPhoto(estimateId: string, entryDate: string): Promise<unknown> {
  return request(`${nutritionPath}/tracking/photo-estimates/${estimateId}/confirm`, {
    method: "POST",
    body: JSON.stringify({ entry_date: entryDate }),
  });
}

export type FreeMealMacros = { calories: number; protein_g: number; carbohydrate_g: number; fat_g: number };
export function confirmFreeMealPhotoPreview(estimateId: string): Promise<FreeMealMacros> {
  return request(`${nutritionPath}/tracking/photo-estimates/${estimateId}/free-meal-preview`, { method: "POST" });
}
export function saveFreeMeal(mealId: string, input: FreeMealMacros & { entry_date: string }): Promise<DailyTrackingSummary> {
  return request(`${nutritionPath}/tracking/free-meals/${mealId}`, { method: "PUT", body: JSON.stringify(input) });
}

export function getNutritionAdherence(start: string, end: string): Promise<NutritionAdherence> {
  const query = new URLSearchParams({ start, end });
  return request<NutritionAdherence>(`${nutritionPath}/adherence?${query}`);
}

export type LabDocument = { id: string; original_filename: string; content_type: string; byte_size: number; test_date: string | null; laboratory_name: string | null; user_note: string | null; category: string | null; review_status: string; review_notes: string | null; uploaded_at: string };
export function listLabDocuments(): Promise<LabDocument[]> {
  return request(`${nutritionPath}/labs`);
}

export function uploadLabDocument(file: File, input: { requestId?: string; testDate?: string; laboratoryName?: string; userNote?: string; category?: string } = {}): Promise<unknown> {
  const body = new FormData();
  body.append("file", file);
  if (input.requestId) body.append("request_id", input.requestId);
  if (input.testDate) body.append("test_date", input.testDate);
  if (input.laboratoryName) body.append("laboratory_name", input.laboratoryName);
  if (input.userNote) body.append("user_note", input.userNote);
  if (input.category) body.append("category", input.category);
  return request(`${nutritionPath}/labs`, { method: "POST", body });
}
export function deleteLabDocument(documentId: string): Promise<void> { return request(`${nutritionPath}/labs/${documentId}`, { method: "DELETE" }); }
export function grantLabDocumentAccess(documentId: string): Promise<{ access_url: string; expires_in_seconds: number }> {
  return request(`${nutritionPath}/labs/${documentId}/access-grant`, { method: "POST" });
}

export function listLabRequests(): Promise<Array<{ id: string; plan_id: string; status: string; requested_tests: string[]; user_visible_reason: string | null; created_at: string }>> {
  return request(`${nutritionPath}/lab-requests`);
}

export type PhysicianQueueView = "pending" | "claimed" | "approved";
export type PhysicianReviewQueueItem = {
  review_id: string;
  plan_id: string;
  user_id: string;
  member_display_name: string | null;
  status: string;
  priority: number;
  physician_user_id: string | null;
  requested_at: string;
  target_review_by: string | null;
  reviewed_at: string | null;
  overdue: boolean;
};

export function listPhysicianReviews(view: PhysicianQueueView = "pending"): Promise<PhysicianReviewQueueItem[]> {
  return request(`${nutritionPath}/physician/reviews?view=${view}`);
}
export function verifyPhysicianAccess(): Promise<{ authorized: true }> { return request(`${nutritionPath}/physician/access`); }

export function claimPhysicianReview(reviewId: string): Promise<unknown> {
  return request(`${nutritionPath}/physician/reviews/${reviewId}/claim`, { method: "POST" });
}

export function getPhysicianPlan(planId: string): Promise<WeeklyPlan> { return request(`${nutritionPath}/physician/plans/${planId}`); }
export function actOnPhysicianPlan(planId: string, action: "start_review" | "approve" | "request_changes" | "reject", notes: string | null, internalNotes: string | null = null): Promise<WeeklyPlan> { return request(`${nutritionPath}/physician/plans/${planId}/action`, { method: "POST", body: JSON.stringify({ expected_plan_revision_id: planId, action, notes, internal_notes: internalNotes }) }); }
export function requestPhysicianLabs(planId: string, requestedTests: string[], reason: string): Promise<unknown> { return request(`${nutritionPath}/physician/plans/${planId}/request-labs`, { method: "POST", body: JSON.stringify({ expected_plan_revision_id: planId, requested_tests: requestedTests, user_visible_reason: reason }) }); }
export function listPhysicianLabs(planId: string): Promise<LabDocument[]> { return request(`${nutritionPath}/physician/plans/${planId}/labs`); }
export function reviewPhysicianLab(documentId: string, reviewStatus: "reviewed" | "requires_follow_up", notes: string | null): Promise<LabDocument> { return request(`${nutritionPath}/physician/labs/${documentId}/review`, { method: "PUT", body: JSON.stringify({ review_status: reviewStatus, notes }) }); }
export function adjustPhysicianFoodQuantity(planId: string, mealId: string, foodId: string, grams: number): Promise<WeeklyPlan> { return request(`${nutritionPath}/physician/plans/${planId}/edits/food-quantity`, { method: "POST", body: JSON.stringify({ expected_plan_revision_id: planId, meal_id: mealId, food_id: foodId, grams }) }); }
export function replacePhysicianFood(planId: string, mealId: string, foodId: string, replacementFoodId: string): Promise<WeeklyPlan> { return request(`${nutritionPath}/physician/plans/${planId}/edits/replace-food`, { method: "POST", body: JSON.stringify({ expected_plan_revision_id: planId, meal_id: mealId, food_id: foodId, replacement_food_id: replacementFoodId }) }); }

export type SupplementOrder = { id: string; plan_id: string; supplement_id: string; name: string; dose_amount: number; dose_unit: string; daily_units: number; frequency: string; duration_days: number; instructions: string; rationale: string | null; status: string; acknowledged_at: string | null; supplement_nutrient_contribution: Record<string, string>; combined_exposure_safety: { food_contribution?: Record<string, string>; supplement_contribution?: Record<string, string>; combined_exposure?: Record<string, string>; hard_blocks?: string[] } };
export type SupplementCatalogueItem = { id: string; slug: string; name_fa: string; name_en: string };
export type PhysicianSupplementOrderInput = { supplement_id: string; dose_amount: number; dose_unit: string; daily_units: number; frequency: string; duration_days: number; instructions: string; rationale: string; rationale_user_visible: boolean; linked_gap_codes: string[]; linked_lab_document_ids: string[] };

export function listSupplementOrders(): Promise<SupplementOrder[]> { return request(`${nutritionPath}/supplement-orders`); }
export function acknowledgeSupplementOrder(orderId: string): Promise<SupplementOrder> { return request(`${nutritionPath}/supplement-orders/${orderId}/acknowledge`, { method: "POST", body: JSON.stringify({ adherence_note: null }) }); }
export function listSupplementCatalogue(): Promise<SupplementCatalogueItem[]> { return request(`${nutritionPath}/supplements/catalogue`); }
export function listPhysicianSupplementOrders(planId: string): Promise<SupplementOrder[]> { return request(`${nutritionPath}/physician/plans/${planId}/supplement-orders`); }
export function createPhysicianSupplementOrder(planId: string, input: PhysicianSupplementOrderInput): Promise<SupplementOrder> { return request(`${nutritionPath}/physician/plans/${planId}/supplement-orders`, { method: "POST", body: JSON.stringify(input) }); }
export function updatePhysicianSupplementOrder(orderId: string, input: PhysicianSupplementOrderInput): Promise<SupplementOrder> { return request(`${nutritionPath}/physician/supplement-orders/${orderId}`, { method: "PUT", body: JSON.stringify(input) }); }
export function transitionPhysicianSupplementOrder(orderId: string, status: "active" | "completed" | "discontinued" | "cancelled"): Promise<SupplementOrder> { return request(`${nutritionPath}/physician/supplement-orders/${orderId}/transition`, { method: "POST", body: JSON.stringify({ status }) }); }
export function saveSupplementCatalogue(input: Record<string, unknown>): Promise<unknown> { return request(`${nutritionPath}/admin/supplements/catalogue`, { method: "PUT", body: JSON.stringify(input) }); }

export type NutritionMonitoring = {
  counts: { foods: number; meals: number; accepted_price_references: number; price_reviews: number; supplements: number };
  recent_price_runs: Array<{ id: string; status: string; trigger_kind: string; started_at: string; finished_at: string | null; foods_attempted: number; foods_updated: number; foods_needing_review: number; provider_failures: number; failure_codes: string[] }>;
  provider_health: Array<{ code: string; enabled: boolean; last_success_at: string | null; last_error: string | null; parser_version: string | null }>;
  coverage_warning: string | null;
  price_reviews: Array<{ id: string; food_slug: string; reason_codes: string[]; candidate_reference_price_toman: string | null; created_at: string }>;
  broken_mappings: Array<{ id: string; food_slug: string; provider_code: string; provider_product_id: string; broken_at: string | null }>;
};
export function getNutritionMonitoring(): Promise<NutritionMonitoring> { return request(`${nutritionPath}/admin/monitoring`); }
export function triggerNutritionPriceRefresh(): Promise<{ status: string }> { return request(`${nutritionPath}/admin/prices/refresh`, { method: "POST" }); }
