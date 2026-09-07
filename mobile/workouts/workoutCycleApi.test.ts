import { expect, it } from "vitest";

import { ApiError, type TransportRequest } from "@fitician/core";

import { createWorkoutCycleApi } from "./workoutCycleApi";

it("uses the current-cycle endpoints with authenticated request bodies", async () => {
  const requests: TransportRequest[] = [];
  const api = createWorkoutCycleApi(async <TResponse>(request: TransportRequest) => {
    requests.push(request);
    return {} as TResponse;
  });
  const weeklyInput = {
    has_pain_or_limitation: false,
    pain_follow_up: null,
    perceived_difficulty: "appropriate" as const,
    recovery_rating: "good" as const,
    sessions_completed: 2,
  };
  const replacementInput = {
    reason: "equipment_unavailable" as const,
    replacement_exercise_id: "exercise-2",
    scope: "this_time" as const,
    workout_plan_exercise_id: "plan-exercise-1",
  };
  const completionInput = {
    overall_difficulty: "appropriate" as const,
    overall_recovery: "good" as const,
    overall_satisfaction: "satisfied" as const,
    strength_progress: "improved" as const,
  };

  await api.getCurrent();
  await api.getWeeklyCheckIn();
  await api.saveWeeklyCheckIn(weeklyInput);
  await api.recordReplacement(replacementInput);
  await api.getCompletionFeedback();
  await api.saveCompletionFeedback(completionInput);

  expect(requests).toEqual([
    { method: "GET", path: "/api/v1/workout-cycles/current" },
    { method: "GET", path: "/api/v1/workout-cycles/current/weekly-check-in" },
    {
      body: weeklyInput,
      method: "PUT",
      path: "/api/v1/workout-cycles/current/weekly-check-in",
    },
    {
      body: replacementInput,
      method: "POST",
      path: "/api/v1/workout-cycles/current/replacements",
    },
    { method: "GET", path: "/api/v1/workout-cycles/current/completion-feedback" },
    {
      body: completionInput,
      method: "PUT",
      path: "/api/v1/workout-cycles/current/completion-feedback",
    },
  ]);
});

it("maps missing current-cycle resources to empty states", async () => {
  const api = createWorkoutCycleApi(async (request: TransportRequest) => {
    throw new ApiError(404, request.path);
  });

  await expect(api.getCurrent()).resolves.toBeNull();
  await expect(api.getWeeklyCheckIn()).resolves.toBeNull();
  await expect(api.getCompletionFeedback()).resolves.toBeNull();
});
