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
  await api.requestLabs("plan/1", "plan/1", ["CBC"], "برای بررسی ایمن‌تر برنامه");
  await api.reviewLab("lab/1", "reviewed", "بررسی شد");
  await api.listSupplementCatalogue();
  await api.listSupplementOrders("plan/1");

  expect(request.mock.calls.map(([input]) => input.path)).toEqual([
    "/api/v1/nutrition/physician/access",
    "/api/v1/nutrition/physician/reviews?view=claimed",
    "/api/v1/nutrition/physician/reviews/review%2F1/claim",
    "/api/v1/nutrition/physician/plans/plan%2F1",
    "/api/v1/nutrition/physician/plans/plan%2F1/labs",
    "/api/v1/nutrition/physician/plans/plan%2F1/medical-context",
    "/api/v1/nutrition/foods",
    "/api/v1/nutrition/physician/plans/plan%2F1/request-labs",
    "/api/v1/nutrition/physician/labs/lab%2F1/review",
    "/api/v1/nutrition/supplements/catalogue",
    "/api/v1/nutrition/physician/plans/plan%2F1/supplement-orders",
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
  const supplementInput = {
    daily_units: 1,
    dose_amount: 1000,
    dose_unit: "mg",
    duration_days: 30,
    frequency: "روزانه",
    instructions: "بعد از غذا",
    rationale: "جبران کمبود ثبت‌شده",
    rationale_user_visible: true,
    supplement_id: "supplement-1",
  } satisfies import("@fitician/core").components["schemas"]["PhysicianSupplementOrderInput"];
  await api.createSupplementOrder("plan-1", supplementInput);
  await api.updateSupplementOrder("order/1", supplementInput);
  await api.transitionSupplementOrder("order/1", "prescribed");

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
    supplementInput,
    supplementInput,
    { status: "prescribed" },
  ] satisfies Array<TransportRequest["body"]>);

  expect(request.mock.calls.map(([input]) => input.path).slice(-3)).toEqual([
    "/api/v1/nutrition/physician/plans/plan-1/supplement-orders",
    "/api/v1/nutrition/physician/supplement-orders/order%2F1",
    "/api/v1/nutrition/physician/supplement-orders/order%2F1/transition",
  ]);
});
