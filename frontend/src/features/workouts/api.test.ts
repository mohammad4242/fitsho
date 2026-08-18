import { afterEach, expect, it, vi } from "vitest";

import {
  downloadWorkoutPlanPdf,
  generateWorkoutPlan,
  getActiveWorkoutPlan,
  getCurrentWorkoutCycle,
  getWorkoutPlan,
  getWorkoutPlanHistory,
  getCurrentWeeklyCheckIn,
  recordExerciseReplacement,
  saveCurrentWeeklyCheckIn,
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
    status: "active" as const,
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

it("records a replacement through the current workout cycle API", async () => {
  const replacement = { id: "replacement-1", week_number: 1 };
  vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(replacement));

  await expect(recordExerciseReplacement({
    workout_plan_exercise_id: "018f0000-0000-7000-8000-000000000011",
    replacement_exercise_id: "018f0000-0000-7000-8000-000000000003",
    reason: "equipment_unavailable",
    scope: "this_time",
  })).resolves.toEqual(replacement);

  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/workout-cycles/current/replacements",
    expect.objectContaining({
      credentials: "include",
      method: "POST",
      body: JSON.stringify({
        workout_plan_exercise_id: "018f0000-0000-7000-8000-000000000011",
        replacement_exercise_id: "018f0000-0000-7000-8000-000000000003",
        reason: "equipment_unavailable",
        scope: "this_time",
      }),
    }),
  );
});

it("treats a missing current-week check-in as empty", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(errorResponse(404, "No weekly check-in for current week"));

  await expect(getCurrentWeeklyCheckIn()).resolves.toBeNull();
  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/workout-cycles/current/weekly-check-in",
    expect.objectContaining({ credentials: "include" }),
  );
});

it("reads the current active cycle and server-derived week", async () => {
  const cycle = {
    cycle_id: "cycle-1",
    workout_plan_id: plan.id,
    started_at: "2026-08-01T10:00:00Z",
    duration_weeks: 4,
    status: "active",
    current_week: 2,
  } as const;
  vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(cycle));

  await expect(getCurrentWorkoutCycle()).resolves.toEqual(cycle);
  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/workout-cycles/current",
    expect.objectContaining({ credentials: "include" }),
  );
});

it("saves the member-entered weekly check-in through the current cycle API", async () => {
  const checkIn = { id: "check-in-1", week_number: 1 };
  vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(checkIn));
  const input = {
    sessions_completed: 2,
    perceived_difficulty: "appropriate" as const,
    recovery_rating: "good" as const,
    has_pain_or_limitation: false,
    pain_follow_up: null,
    note_optional: null,
  };

  await expect(saveCurrentWeeklyCheckIn(input)).resolves.toEqual(checkIn);
  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/workout-cycles/current/weekly-check-in",
    expect.objectContaining({ credentials: "include", method: "PUT", body: JSON.stringify(input) }),
  );
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

function errorResponse(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), { status, headers: { "Content-Type": "application/json" } });
}
