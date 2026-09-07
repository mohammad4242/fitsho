import { afterEach, expect, it, vi } from "vitest";

import type { TransportRequest } from "@fitician/core";

import {
  createPhysicianNutritionReviewApi,
  type AuthenticatedPhysicianRequest,
} from "./physicianNutritionReviewApi";

afterEach(() => vi.restoreAllMocks());

it("uses the role-scoped physician queue and access endpoints", async () => {
  const request = vi.fn<AuthenticatedPhysicianRequest>(
    async <TResponse>(_input: TransportRequest): Promise<TResponse> => [] as unknown as TResponse,
  );
  const api = createPhysicianNutritionReviewApi(request as unknown as AuthenticatedPhysicianRequest);

  await api.getAccess();
  await api.list("claimed");
  await api.claim("review/1");
  await api.getPlan("plan/1");
  await api.getLabs("plan/1");
  await api.getMedicalContext("plan/1");
  await api.listFoods();

  expect(request.mock.calls.map(([input]) => input.path)).toEqual([
    "/api/v1/nutrition/physician/access",
    "/api/v1/nutrition/physician/reviews?view=claimed",
    "/api/v1/nutrition/physician/reviews/review%2F1/claim",
    "/api/v1/nutrition/physician/plans/plan%2F1",
    "/api/v1/nutrition/physician/plans/plan%2F1/labs",
    "/api/v1/nutrition/physician/plans/plan%2F1/medical-context",
    "/api/v1/nutrition/foods",
  ]);
});

it("sends the current plan revision for edits and decisions", async () => {
  const request = vi.fn<AuthenticatedPhysicianRequest>(
    async <TResponse>(_input: TransportRequest): Promise<TResponse> => ({}) as TResponse,
  );
  const api = createPhysicianNutritionReviewApi(request as unknown as AuthenticatedPhysicianRequest);

  await api.action("plan-1", "plan-1", "request_changes", "Adjust the portions.", "Internal note");
  await api.adjustFoodQuantity("plan-1", "plan-1", "meal-1", "food-1", 150);
  await api.replaceFood("plan-1", "plan-1", "meal-1", "food-1", "food-2");
  await api.removeMeal("plan-1", "plan-1", "meal-1");

  expect(request.mock.calls.map(([input]) => input.body)).toEqual([
    {
      expected_plan_revision_id: "plan-1",
      action: "request_changes",
      notes: "Adjust the portions.",
      internal_notes: "Internal note",
    },
    {
      expected_plan_revision_id: "plan-1",
      meal_id: "meal-1",
      food_id: "food-1",
      grams: 150,
    },
    {
      expected_plan_revision_id: "plan-1",
      meal_id: "meal-1",
      food_id: "food-1",
      replacement_food_id: "food-2",
    },
    {
      expected_plan_revision_id: "plan-1",
      meal_id: "meal-1",
    },
  ] satisfies Array<TransportRequest["body"]>);
});
