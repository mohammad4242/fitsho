import type { components, TransportRequest } from "@fitician/core";

export type PhysicianReviewQueueItem = components["schemas"]["PhysicianReviewQueueItemResponse"];
export type PhysicianReviewQueueView = "pending" | "claimed" | "approved";
export type PhysicianNutritionPlan = components["schemas"]["WeeklyPlanResponse"];
export type PhysicianPlanAction = "start_review" | "approve" | "request_changes" | "reject";
export type PhysicianMedicalContextResponse = components["schemas"]["PhysicianMedicalContextResponse"];
export type PhysicianCatalogueFood = components["schemas"]["CatalogueFoodResponse"];
export type PhysicianLabDocument = components["schemas"]["NutritionLabDocumentResponse"];
export type PhysicianLabRequest = components["schemas"]["NutritionLabRequestResponse"];
export type PhysicianSupplementCatalogue = components["schemas"]["NutritionSupplementCatalogueResponse"];
export type PhysicianSupplementOrder = components["schemas"]["NutritionSupplementOrderResponse"];
export type PhysicianSupplementOrderInput = components["schemas"]["PhysicianSupplementOrderInput"];
export type PhysicianSupplementOrderStatus = components["schemas"]["NutritionSupplementOrderStatus"];

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
  getLabs(planId: string): Promise<PhysicianLabDocument[]>;
  getMedicalContext(planId: string): Promise<PhysicianMedicalContextResponse>;
  getPlan(planId: string): Promise<PhysicianNutritionPlan>;
  listFoods(): Promise<PhysicianCatalogueFood[]>;
  list(view: PhysicianReviewQueueView): Promise<PhysicianReviewQueueItem[]>;
  listSupplementCatalogue(): Promise<PhysicianSupplementCatalogue[]>;
  listSupplementOrders(planId: string): Promise<PhysicianSupplementOrder[]>;
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
  requestLabs(
    planId: string,
    expectedPlanRevisionId: string,
    requestedTests: string[],
    userVisibleReason: string,
  ): Promise<components["schemas"]["NutritionLabRequestCreatedResponse"]>;
  reviewLab(
    documentId: string,
    reviewStatus: string,
    notes: string | null,
  ): Promise<PhysicianLabDocument>;
  createSupplementOrder(
    planId: string,
    input: PhysicianSupplementOrderInput,
  ): Promise<PhysicianSupplementOrder>;
  updateSupplementOrder(
    orderId: string,
    input: PhysicianSupplementOrderInput,
  ): Promise<PhysicianSupplementOrder>;
  transitionSupplementOrder(
    orderId: string,
    status: PhysicianSupplementOrderStatus,
  ): Promise<PhysicianSupplementOrder>;
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
    getLabs: (planId) => request<PhysicianLabDocument[]>({
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
    listSupplementCatalogue: () => request<PhysicianSupplementCatalogue[]>({
      method: "GET",
      path: `${nutritionPath}/supplements/catalogue`,
    }),
    listSupplementOrders: (planId) => request<PhysicianSupplementOrder[]>({
      method: "GET",
      path: `${planPath(planId)}/supplement-orders`,
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
    requestLabs: (planId, expectedPlanRevisionId, requestedTests, userVisibleReason) => request<components["schemas"]["NutritionLabRequestCreatedResponse"]>({
      body: jsonBody({
        expected_plan_revision_id: expectedPlanRevisionId,
        requested_tests: requestedTests,
        user_visible_reason: userVisibleReason,
      }),
      method: "POST",
      path: `${planPath(planId)}/request-labs`,
    }),
    reviewLab: (documentId, reviewStatus, notes) => request<PhysicianLabDocument>({
      body: jsonBody({ notes, review_status: reviewStatus }),
      method: "PUT",
      path: `${nutritionPath}/physician/labs/${encodeURIComponent(documentId)}/review`,
    }),
    createSupplementOrder: (planId, input) => request<PhysicianSupplementOrder>({
      body: jsonBody(input),
      method: "POST",
      path: `${planPath(planId)}/supplement-orders`,
    }),
    updateSupplementOrder: (orderId, input) => request<PhysicianSupplementOrder>({
      body: jsonBody(input),
      method: "PUT",
      path: `${nutritionPath}/physician/supplement-orders/${encodeURIComponent(orderId)}`,
    }),
    transitionSupplementOrder: (orderId, status) => request<PhysicianSupplementOrder>({
      body: jsonBody({ status }),
      method: "POST",
      path: `${nutritionPath}/physician/supplement-orders/${encodeURIComponent(orderId)}/transition`,
    }),
  } satisfies PhysicianNutritionReviewApi;
}
