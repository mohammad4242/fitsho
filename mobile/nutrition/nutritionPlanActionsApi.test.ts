import { expect, it } from "vitest";

import type { TransportRequest } from "@fitician/core";

import {
  createNutritionPlanActionsApi,
  type MealFeedbackInput,
  type ReplaceFoodInput,
  type ReplaceMealInput,
  type RemoveMealConfirmationInput,
} from "./nutritionPlanActionsApi";

it("uses authenticated member plan control and replacement endpoints", async () => {
  const requests: TransportRequest[] = [];
  const api = createNutritionPlanActionsApi(async <TResponse>(request: TransportRequest) => {
    requests.push(request);
    return {} as TResponse;
  });

  await api.getFeedback("plan/id");
  await api.setMealLock("plan/id", "meal/id", true);
  await api.setMealFeedback("plan/id", "meal/id", {
    feedback_type: "liked",
    notes: "خوب بود",
  });
  await api.getMealReplacementOptions("plan/id", "meal/id");
  await api.getFoodReplacementOptions("plan/id", "meal/id", "food/id");
  await api.previewRemoveMeal("plan/id", "meal/id");
  await api.confirmRemoveMeal("plan/id", {
    expected_plan_revision_id: "revision/id",
    meal_id: "meal/id",
  });
  await api.previewReplaceMeal("plan/id", {
    expected_plan_revision_id: "revision/id",
    meal_id: "meal/id",
    replacement_meal_id: "replacement/id",
  });
  await api.confirmReplaceMeal("plan/id", {
    expected_plan_revision_id: "revision/id",
    meal_id: "meal/id",
    replacement_meal_id: "replacement/id",
  });
  await api.previewReplaceFood("plan/id", {
    expected_plan_revision_id: "revision/id",
    food_id: "food/id",
    meal_id: "meal/id",
    replacement_food_id: "replacement-food/id",
  });
  await api.confirmReplaceFood("plan/id", {
    expected_plan_revision_id: "revision/id",
    food_id: "food/id",
    meal_id: "meal/id",
    replacement_food_id: "replacement-food/id",
  });

  expect(requests).toEqual([
    { method: "GET", path: "/api/v1/nutrition/plans/plan%2Fid/feedback" },
    {
      body: { is_locked: true },
      method: "PUT",
      path: "/api/v1/nutrition/plans/plan%2Fid/meals/meal%2Fid/lock",
    },
    {
      body: { feedback_type: "liked", notes: "خوب بود" },
      method: "PUT",
      path: "/api/v1/nutrition/plans/plan%2Fid/meals/meal%2Fid/feedback",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/plans/plan%2Fid/meal-replacement-options?meal_id=meal%2Fid",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/plans/plan%2Fid/food-replacement-options?meal_id=meal%2Fid&food_id=food%2Fid",
    },
    {
      method: "POST",
      path: "/api/v1/nutrition/plans/plan%2Fid/edits/remove-meal/preview?meal_id=meal%2Fid",
    },
    {
      body: { expected_plan_revision_id: "revision/id", meal_id: "meal/id" },
      method: "POST",
      path: "/api/v1/nutrition/plans/plan%2Fid/edits/remove-meal/confirm",
    },
    {
      body: {
        expected_plan_revision_id: "revision/id",
        meal_id: "meal/id",
        replacement_meal_id: "replacement/id",
      },
      method: "POST",
      path: "/api/v1/nutrition/plans/plan%2Fid/edits/replace-meal/preview",
    },
    {
      body: {
        expected_plan_revision_id: "revision/id",
        meal_id: "meal/id",
        replacement_meal_id: "replacement/id",
      },
      method: "POST",
      path: "/api/v1/nutrition/plans/plan%2Fid/edits/replace-meal/confirm",
    },
    {
      body: {
        expected_plan_revision_id: "revision/id",
        food_id: "food/id",
        meal_id: "meal/id",
        replacement_food_id: "replacement-food/id",
      },
      method: "POST",
      path: "/api/v1/nutrition/plans/plan%2Fid/edits/replace-food/preview",
    },
    {
      body: {
        expected_plan_revision_id: "revision/id",
        food_id: "food/id",
        meal_id: "meal/id",
        replacement_food_id: "replacement-food/id",
      },
      method: "POST",
      path: "/api/v1/nutrition/plans/plan%2Fid/edits/replace-food/confirm",
    },
  ]);
});

it("keeps action payloads typed and unmodified", async () => {
  const requests: TransportRequest[] = [];
  const api = createNutritionPlanActionsApi(async <TResponse>(request: TransportRequest) => {
    requests.push(request);
    return {} as TResponse;
  });
  const feedback: MealFeedbackInput = { feedback_type: "too_small", notes: null };
  const remove: RemoveMealConfirmationInput = {
    expected_plan_revision_id: "revision-1",
    meal_id: "meal-1",
  };
  const food: ReplaceFoodInput = {
    expected_plan_revision_id: "revision-1",
    food_id: "food-1",
    meal_id: "meal-1",
    replacement_food_id: "food-2",
  };
  const meal: ReplaceMealInput = {
    expected_plan_revision_id: "revision-1",
    meal_id: "meal-1",
    replacement_meal_id: "meal-2",
  };

  await api.setMealFeedback("plan-1", "meal-1", feedback);
  await api.confirmRemoveMeal("plan-1", remove);
  await api.confirmReplaceFood("plan-1", food);
  await api.confirmReplaceMeal("plan-1", meal);

  expect(requests[0]?.body).toBe(feedback);
  expect(requests[1]?.body).toBe(remove);
  expect(requests[2]?.body).toBe(food);
  expect(requests[3]?.body).toBe(meal);
});
