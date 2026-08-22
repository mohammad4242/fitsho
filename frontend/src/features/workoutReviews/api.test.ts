import { afterEach, expect, it, vi } from "vitest";

import {
  claimWorkoutReview,
  listWorkoutReviews,
  saveWorkoutReviewDraft,
  verifyCoachAccess,
} from "./api";
import type { WorkoutReviewDetail, WorkoutReviewDraftUpdate } from "./types";

const detail: WorkoutReviewDetail = {
  id: "review-1",
  source_plan_id: "plan-1",
  user_id: "member-1",
  member_display_name: "Member",
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  status: "claimed",
  claimed_by_user_id: "coach-1",
  lease_expires_at: "2026-08-09T10:00:00Z",
  draft_revision: 2,
  created_at: "2026-08-09T08:00:00Z",
  approved_at: null,
  coach_note: null,
  draft: { days: [] },
  source_plan: {
    id: "plan-1",
    status: "active",
    created_at: "2026-08-09T08:00:00Z",
    activated_at: "2026-08-09T08:00:00Z",
    plan_duration_weeks: 4,
    is_stale: false,
    days: [],
    coach_review: {
      state: "pending_coach_review",
      coach_display_name: null,
      coach_note: null,
      approved_at: null,
    },
  },
  exercise_options: [],
  template_selection: null,
};

afterEach(() => vi.restoreAllMocks());

it("verifies coach access and lists the requested queue", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(jsonResponse({ authorized: true }))
    .mockResolvedValueOnce(jsonResponse([detail]));

  await expect(verifyCoachAccess()).resolves.toEqual({ authorized: true });
  await expect(listWorkoutReviews("mine")).resolves.toEqual([detail]);

  expect(fetch).toHaveBeenNthCalledWith(
    2,
    "/api/v1/coach/workout-reviews?view=mine",
    expect.objectContaining({ credentials: "include" }),
  );
});

it("claims and saves a typed review draft", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(jsonResponse(detail))
    .mockResolvedValueOnce(jsonResponse(detail));
  const payload: WorkoutReviewDraftUpdate = {
    expected_revision: 1,
    coach_note: "Keep control.",
    days: [],
  };

  await claimWorkoutReview("review-1");
  await saveWorkoutReviewDraft("review-1", payload);

  expect(fetch).toHaveBeenNthCalledWith(
    2,
    "/api/v1/coach/workout-reviews/review-1/draft",
    expect.objectContaining({
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  );
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
