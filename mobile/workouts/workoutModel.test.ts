import { expect, it } from "vitest";

import type { components } from "@fitician/core";

import {
  findPendingWorkoutPlanId,
  getWorkoutPlanSummaryStatus,
  isWorkoutPlanExecutable,
  workoutPlanAverageDuration,
  workoutPlanPdfFilename,
} from "./workoutModel";

type WorkoutPlan = components["schemas"]["WorkoutPlanResponse"];
type WorkoutPlanVersion = components["schemas"]["WorkoutPlanVersionSummaryResponse"];

function plan(overrides: Partial<WorkoutPlan> = {}): WorkoutPlan {
  return {
    activated_at: null,
    created_at: "2026-09-07T00:00:00Z",
    days: [],
    engine_version: "test",
    id: "plan-1",
    is_stale: false,
    plan_duration_weeks: 4,
    primary_goal: "general_fitness",
    ruleset_version: "test",
    safety_status: "clear",
    seed: 1,
    status: "active",
    training_status: "novice",
    ...overrides,
  };
}

function version(overrides: Partial<WorkoutPlanVersion> = {}): WorkoutPlanVersion {
  return {
    activated_at: null,
    coach_review: { state: "none" },
    created_at: "2026-09-07T00:00:00Z",
    id: "plan-1",
    is_active: false,
    status: "superseded",
    ...overrides,
  };
}

it("distinguishes active, coach-pending, and historical plan summaries", () => {
  expect(getWorkoutPlanSummaryStatus(plan())).toBe("active");
  expect(getWorkoutPlanSummaryStatus(plan({ status: "pending_review" }))).toBe("pending");
  expect(
    getWorkoutPlanSummaryStatus(plan({ coach_review: { state: "pending_coach_review" } })),
  ).toBe("pending");
  expect(getWorkoutPlanSummaryStatus(plan(), true)).toBe("inactive");
});

it("never exposes pending or historical plans as executable", () => {
  expect(isWorkoutPlanExecutable(plan())).toBe(true);
  expect(isWorkoutPlanExecutable(plan({ status: "pending_review" }))).toBe(false);
  expect(isWorkoutPlanExecutable(plan({ coach_review: { state: "pending_coach_review" } }))).toBe(false);
  expect(isWorkoutPlanExecutable(plan(), true)).toBe(false);
});

it("selects only the pending-review version for the pending plan slot", () => {
  expect(findPendingWorkoutPlanId([
    version(),
    version({ id: "pending-1", status: "pending_review" }),
  ])).toBe("pending-1");
  expect(findPendingWorkoutPlanId([version({ status: "active" })])).toBeNull();
});

it("calculates average session duration and safe PDF filenames", () => {
  expect(workoutPlanAverageDuration(plan({
    days: [
      { day_number: 1, estimated_duration_minutes: 41, exercises: [], focus: "push", title_en: "Push", title_fa: "پوش", total_exercise_count: 0, main_exercise_count: 0, supplemental_exercise_count: 0 },
      { day_number: 2, estimated_duration_minutes: 50, exercises: [], focus: "pull", title_en: "Pull", title_fa: "پول", total_exercise_count: 0, main_exercise_count: 0, supplemental_exercise_count: 0 },
    ],
  }))).toBe(46);
  expect(workoutPlanAverageDuration(plan())).toBeNull();
  expect(workoutPlanPdfFilename("plan/id")).toBe("fitician-workout-plan-plan-id.pdf");
});
