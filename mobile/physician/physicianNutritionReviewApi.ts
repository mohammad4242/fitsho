import type { components, TransportRequest } from "@fitician/core";

export type PhysicianReviewQueueItem = components["schemas"]["PhysicianReviewQueueItemResponse"];
export type PhysicianReviewQueueView = "pending" | "claimed" | "approved";
export type PhysicianNutritionPlan = components["schemas"]["WeeklyPlanResponse"];
export type PhysicianPlanAction = "start_review" | "approve" | "request_changes" | "reject";
export type PhysicianMedicalContextResponse = components["schemas"]["PhysicianMedicalContextResponse"];
export type PhysicianCatalogueFood = components["schemas"]["CatalogueFoodResponse"];

export type AuthenticatedPhysicianRequest = <TResponse>(
  request: TransportRequest,
) => Promise<TResponse>;

export interface PhysicianNutritionReviewApi {
  action(
    planId: string,
    expectedPlanRevisionId: string,
    action: PhysicianPlanAction,
    notes: string | null,
    internalNotes?: string | null,
  ): Promise<PhysicianNutritionPlan>;
  adjustFoodQuantity(
    planId: string,
    expectedPlanRevisionId: string,
    mealId: string,
    foodId: string,
    grams: number,
  ): Promise<PhysicianNutritionPlan>;
  claim(reviewId: string): Promise<components["schemas"]["NutritionReviewClaimResponse"]>;
  getAccess(): Promise<{ authorized: true }>;
  getLabs(planId: string): Promise<components["schemas"]["NutritionLabDocumentResponse"][]>;
  getMedicalContext(planId: string): Promise<PhysicianMedicalContextResponse>;
  getPlan(planId: string): Promise<PhysicianNutritionPlan>;
  listFoods(): Promise<PhysicianCatalogueFood[]>;
  list(view: PhysicianReviewQueueView): Promise<PhysicianReviewQueueItem[]>;
  removeMeal(
    planId: string,
    expectedPlanRevisionId: string,
    mealId: string,
  ): Promise<PhysicianNutritionPlan>;
  replaceFood(
    planId: string,
    expectedPlanRevisionId: string,
    mealId: string,
    foodId: string,
    replacementFoodId: string,
  ): Promise<PhysicianNutritionPlan>;
}

const nutritionPath = "/api/v1/nutrition";

function jsonBody(value: object): TransportRequest["body"] {
  return value as TransportRequest["body"];
}

function planPath(planId: string): string {
  return `${nutritionPath}/physician/plans/${encodeURIComponent(planId)}`;
}

function reviewPath(reviewId: string): string {
  return `${nutritionPath}/physician/reviews/${encodeURIComponent(reviewId)}`;
}

export function createPhysicianNutritionReviewApi(
  request: AuthenticatedPhysicianRequest,
): PhysicianNutritionReviewApi {
  return {
    action: (planId, expectedPlanRevisionId, action, notes, internalNotes = null) => request<PhysicianNutritionPlan>({
      body: jsonBody({
        expected_plan_revision_id: expectedPlanRevisionId,
        action,
        notes,
        internal_notes: internalNotes,
      }),
      method: "POST",
      path: `${planPath(planId)}/action`,
    }),
    adjustFoodQuantity: (planId, expectedPlanRevisionId, mealId, foodId, grams) => request<PhysicianNutritionPlan>({
      body: jsonBody({
        expected_plan_revision_id: expectedPlanRevisionId,
        meal_id: mealId,
        food_id: foodId,
        grams,
      }),
      method: "POST",
      path: `${planPath(planId)}/edits/food-quantity`,
    }),
    claim: (reviewId) => request<components["schemas"]["NutritionReviewClaimResponse"]>({
      method: "POST",
      path: `${reviewPath(reviewId)}/claim`,
    }),
    getAccess: () => request<{ authorized: true }>({
      method: "GET",
      path: `${nutritionPath}/physician/access`,
    }),
    getLabs: (planId) => request<components["schemas"]["NutritionLabDocumentResponse"][]>({
      method: "GET",
      path: `${planPath(planId)}/labs`,
    }),
    getMedicalContext: (planId) => request<PhysicianMedicalContextResponse>({
      method: "GET",
      path: `${planPath(planId)}/medical-context`,
    }),
    getPlan: (planId) => request<PhysicianNutritionPlan>({
      method: "GET",
      path: planPath(planId),
    }),
    listFoods: () => request<PhysicianCatalogueFood[]>({
      method: "GET",
      path: `${nutritionPath}/foods`,
    }),
    list: (view) => request<PhysicianReviewQueueItem[]>({
      method: "GET",
      path: `${nutritionPath}/physician/reviews?view=${encodeURIComponent(view)}`,
    }),
    removeMeal: (planId, expectedPlanRevisionId, mealId) => request<PhysicianNutritionPlan>({
      body: jsonBody({ expected_plan_revision_id: expectedPlanRevisionId, meal_id: mealId }),
      method: "POST",
      path: `${planPath(planId)}/edits/remove-meal`,
    }),
    replaceFood: (planId, expectedPlanRevisionId, mealId, foodId, replacementFoodId) => request<PhysicianNutritionPlan>({
      body: jsonBody({
        expected_plan_revision_id: expectedPlanRevisionId,
        meal_id: mealId,
        food_id: foodId,
        replacement_food_id: replacementFoodId,
      }),
      method: "POST",
      path: `${planPath(planId)}/edits/replace-food`,
    }),
  } satisfies PhysicianNutritionReviewApi;
}
