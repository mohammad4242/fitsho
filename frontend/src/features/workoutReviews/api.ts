import { request } from "../../shared/apiClient";

import type {
  WorkoutReviewDetail,
  WorkoutReviewDraftUpdate,
  WorkoutReviewQueueItem,
  WorkoutReviewQueueView,
} from "./types";

const basePath = "/api/v1/coach/workout-reviews";

export function verifyCoachAccess(): Promise<{ authorized: true }> {
  return request(`${basePath}/access`);
}

export function listWorkoutReviews(
  view: WorkoutReviewQueueView,
): Promise<WorkoutReviewQueueItem[]> {
  return request(`${basePath}?view=${view}`);
}

export function getWorkoutReview(reviewId: string): Promise<WorkoutReviewDetail> {
  return request(`${basePath}/${reviewId}`);
}

export function claimWorkoutReview(reviewId: string): Promise<WorkoutReviewDetail> {
  return request(`${basePath}/${reviewId}/claim`, { method: "POST" });
}

export function renewWorkoutReview(reviewId: string): Promise<WorkoutReviewDetail> {
  return request(`${basePath}/${reviewId}/renew`, { method: "POST" });
}

export function saveWorkoutReviewDraft(
  reviewId: string,
  payload: WorkoutReviewDraftUpdate,
): Promise<WorkoutReviewDetail> {
  return request(`${basePath}/${reviewId}/draft`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function approveWorkoutReview(
  reviewId: string,
  expectedRevision: number,
): Promise<WorkoutReviewDetail> {
  return request(`${basePath}/${reviewId}/approve`, {
    method: "POST",
    body: JSON.stringify({ expected_revision: expectedRevision }),
  });
}
