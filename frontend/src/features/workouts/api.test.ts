import { afterEach, expect, it, vi } from "vitest";

import { generateWorkoutPlan, getActiveWorkoutPlan } from "./api";
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

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

function errorResponse(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), { status, headers: { "Content-Type": "application/json" } });
}
