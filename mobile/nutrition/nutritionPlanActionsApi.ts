import type { TransportRequest } from "@fitician/core";
import type { components } from "@fitician/core";

import type { AuthenticatedNutritionRequest } from "./nutritionApi";
import type { WeeklyPlan } from "./nutritionPlanApi";

export type MealFeedbackInput = components["schemas"]["MealFeedbackInput"];
export type MealFeedbackUpdateResponse = components["schemas"]["MealFeedbackUpdateResponse"];
export type MealLockResponse = components["schemas"]["MealLockResponse"];
export type WeeklyPlanFeedback = components["schemas"]["WeeklyPlanFeedbackResponse"];
export type MealReplacementOptions = components["schemas"]["MealReplacementOptionsResponse"];
export type FoodReplacementOptions = components["schemas"]["FoodReplacementOptionsResponse"];
export type MealRemovalPreview = components["schemas"]["MealRemovalPreviewResponse"];
export type MealReplacementPreview = components["schemas"]["MealReplacementPreviewResponse"];
export type FoodReplacementPreview = components["schemas"]["FoodReplacementPreviewResponse"];
export type RemoveMealConfirmationInput = components["schemas"]["RemoveMealConfirmationInput"];
export type ReplaceMealInput = components["schemas"]["ReplaceMealInput"];
export type ReplaceFoodInput = components["schemas"]["ReplaceFoodInput"];

export interface NutritionPlanActionsApi {
  confirmRemoveMeal(planId: string, input: RemoveMealConfirmationInput): Promise<WeeklyPlan>;
  confirmReplaceFood(planId: string, input: ReplaceFoodInput): Promise<WeeklyPlan>;
  confirmReplaceMeal(planId: string, input: ReplaceMealInput): Promise<WeeklyPlan>;
  getFeedback(planId: string): Promise<WeeklyPlanFeedback>;
  getFoodReplacementOptions(planId: string, mealId: string, foodId: string): Promise<FoodReplacementOptions>;
  getMealReplacementOptions(planId: string, mealId: string): Promise<MealReplacementOptions>;
  previewRemoveMeal(planId: string, mealId: string): Promise<MealRemovalPreview>;
  previewReplaceFood(planId: string, input: ReplaceFoodInput): Promise<FoodReplacementPreview>;
  previewReplaceMeal(planId: string, input: ReplaceMealInput): Promise<MealReplacementPreview>;
  setMealFeedback(planId: string, mealId: string, input: MealFeedbackInput): Promise<MealFeedbackUpdateResponse>;
  setMealLock(planId: string, mealId: string, isLocked: boolean): Promise<MealLockResponse>;
}

const plansPath = "/api/v1/nutrition/plans";

function jsonBody(value: object): TransportRequest["body"] {
  return value as TransportRequest["body"];
}

function planPath(planId: string): string {
  return `${plansPath}/${encodeURIComponent(planId)}`;
}

export function createNutritionPlanActionsApi(
  request: AuthenticatedNutritionRequest,
): NutritionPlanActionsApi {
  return {
    confirmRemoveMeal: (planId, input) => request<WeeklyPlan>({
      body: jsonBody(input),
      method: "POST",
      path: `${planPath(planId)}/edits/remove-meal/confirm`,
    }),
    confirmReplaceFood: (planId, input) => request<WeeklyPlan>({
      body: jsonBody(input),
      method: "POST",
      path: `${planPath(planId)}/edits/replace-food/confirm`,
    }),
    confirmReplaceMeal: (planId, input) => request<WeeklyPlan>({
      body: jsonBody(input),
      method: "POST",
      path: `${planPath(planId)}/edits/replace-meal/confirm`,
    }),
    getFeedback: (planId) => request<WeeklyPlanFeedback>({
      method: "GET",
      path: `${planPath(planId)}/feedback`,
    }),
    getFoodReplacementOptions: (planId, mealId, foodId) => request<FoodReplacementOptions>({
      method: "GET",
      path: `${planPath(planId)}/food-replacement-options?${query({ meal_id: mealId, food_id: foodId })}`,
    }),
    getMealReplacementOptions: (planId, mealId) => request<MealReplacementOptions>({
      method: "GET",
      path: `${planPath(planId)}/meal-replacement-options?${query({ meal_id: mealId })}`,
    }),
    previewRemoveMeal: (planId, mealId) => request<MealRemovalPreview>({
      method: "POST",
      path: `${planPath(planId)}/edits/remove-meal/preview?${query({ meal_id: mealId })}`,
    }),
    previewReplaceFood: (planId, input) => request<FoodReplacementPreview>({
      body: jsonBody(input),
      method: "POST",
      path: `${planPath(planId)}/edits/replace-food/preview`,
    }),
    previewReplaceMeal: (planId, input) => request<MealReplacementPreview>({
      body: jsonBody(input),
      method: "POST",
      path: `${planPath(planId)}/edits/replace-meal/preview`,
    }),
    setMealFeedback: (planId, mealId, input) => request<MealFeedbackUpdateResponse>({
      body: jsonBody(input),
      method: "PUT",
      path: `${planPath(planId)}/meals/${encodeURIComponent(mealId)}/feedback`,
    }),
    setMealLock: (planId, mealId, isLocked) => request<MealLockResponse>({
      body: jsonBody({ is_locked: isLocked }),
      method: "PUT",
      path: `${planPath(planId)}/meals/${encodeURIComponent(mealId)}/lock`,
    }),
  };
}

function query(values: Record<string, string>): string {
  return new URLSearchParams(values).toString();
}
