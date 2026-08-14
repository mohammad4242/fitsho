import { afterEach, expect, it, vi } from "vitest";

import {
  downloadWorkoutPlanPdf,
  generateWorkoutPlan,
  getActiveWorkoutPlan,
  getWorkoutPlan,
  getWorkoutPlanHistory,
} from "./api";
import type { WorkoutPlan } from "./types";

const plan: WorkoutPlan = {
  id: "018f0000-0000-7000-8000-000000000001",
  status: "active",
  created_at: "2026-07-28T10:00:00Z",
  activated_at: "2026-07-28T10:00:00Z",
  plan_duration_weeks: 4,
  is_stale: false,
  days: [],
};

afterEach(() => vi.restoreAllMocks());

it("reads the active plan through the Fitsho backend", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(plan));

  await expect(getActiveWorkoutPlan()).resolves.toEqual(plan);

  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/workout-plans/active",
    expect.objectContaining({ credentials: "include" }),
  );
});

it("treats only an absent active plan as empty", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(errorResponse(404, "No active workout plan"));

  await expect(getActiveWorkoutPlan()).resolves.toBeNull();
});

it("requests generation from Fitsho instead of an AI provider", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ plan, reused: false }));

  await expect(generateWorkoutPlan()).resolves.toEqual({ plan, reused: false });

  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/workout-plans/generate",
    expect.objectContaining({ credentials: "include", method: "POST" }),
  );
});

it("reads member plan history and a selected immutable version", async () => {
  const history = [{
    id: plan.id,
    created_at: plan.created_at,
    activated_at: plan.activated_at,
    is_active: true,
    coach_review: { state: "coach_approved", coach_display_name: "Coach", coach_note: null, approved_at: plan.activated_at },
  }];
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(jsonResponse(history))
    .mockResolvedValueOnce(jsonResponse(plan));

  await expect(getWorkoutPlanHistory()).resolves.toEqual(history);
  await expect(getWorkoutPlan(plan.id)).resolves.toEqual(plan);

  expect(fetch).toHaveBeenNthCalledWith(
    1,
    "/api/v1/workout-plans/history",
    expect.objectContaining({ credentials: "include" }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    2,
    `/api/v1/workout-plans/${plan.id}`,
    expect.objectContaining({ credentials: "include" }),
  );
});

it("downloads a workout plan PDF through Fitsho", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response("%PDF-test", { headers: { "Content-Type": "application/pdf" } }),
  );

  const response = await downloadWorkoutPlanPdf(plan.id);

  expect(await response.text()).toBe("%PDF-test");
  expect(fetch).toHaveBeenCalledWith(
    `/api/v1/workout-plans/${plan.id}/pdf`,
    expect.objectContaining({ credentials: "include" }),
  );
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

function errorResponse(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), { status, headers: { "Content-Type": "application/json" } });
}
