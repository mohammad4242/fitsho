import { expect, it } from "vitest";

import {
  bodyAnalysisKeys,
  exerciseKeys,
  featureQueryKeys,
  nutritionKeys,
  profileKeys,
  workoutKeys,
} from "./queryKeys";

it("creates hierarchical feature keys for list and detail invalidation", () => {
  const filters = { page: 2, query: "squat" };

  expect(profileKeys.all).toEqual(["profile"]);
  expect(profileKeys.current()).toEqual(["profile", "current"]);
  expect(exerciseKeys.categories()).toEqual(["exercises", "categories"]);
  expect(exerciseKeys.list(filters)).toEqual(["exercises", "list", filters]);
  expect(exerciseKeys.detail("exercise-1")).toEqual(["exercises", "detail", "exercise-1"]);
  expect(workoutKeys.list({ status: "active" })).toEqual([
    "workouts",
    "list",
    { status: "active" },
  ]);
  expect(workoutKeys.currentCycle()).toEqual(["workouts", "current-cycle"]);
  expect(workoutKeys.weeklyCheckIn("cycle-1")).toEqual([
    "workouts",
    "weekly-check-in",
    "cycle-1",
  ]);
  expect(workoutKeys.completionFeedback("cycle-1")).toEqual([
    "workouts",
    "completion-feedback",
    "cycle-1",
  ]);
  expect(nutritionKeys.detail("plan-1")).toEqual(["nutrition", "detail", "plan-1"]);
  expect(bodyAnalysisKeys.session("session-1")).toEqual([
    "body-analysis",
    "detail",
    "session-1",
  ]);
});

it("exposes the same factories through the feature registry", () => {
  expect(featureQueryKeys.profile).toBe(profileKeys);
  expect(featureQueryKeys.exercises).toBe(exerciseKeys);
  expect(featureQueryKeys.workouts).toBe(workoutKeys);
  expect(featureQueryKeys.nutrition).toBe(nutritionKeys);
  expect(featureQueryKeys.bodyAnalysis).toBe(bodyAnalysisKeys);
});
