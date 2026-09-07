import type { components, TransportRequest } from "@fitician/core";

export type CoachWorkoutReviewQueueItem = components["schemas"]["WorkoutReviewQueueItemResponse"];
export type CoachWorkoutReviewDetail = components["schemas"]["WorkoutReviewDetailResponse"];
export type CoachWorkoutReviewDraft = components["schemas"]["WorkoutReviewDraftUpdate"];
export type CoachWorkoutReviewView = components["schemas"]["WorkoutReviewQueueView"];

export type AuthenticatedCoachRequest = <TResponse>(
  request: TransportRequest,
) => Promise<TResponse>;

export interface CoachWorkoutReviewApi {
  approve(reviewId: string, expectedRevision: number): Promise<CoachWorkoutReviewDetail>;
  claim(reviewId: string): Promise<CoachWorkoutReviewDetail>;
  get(reviewId: string): Promise<CoachWorkoutReviewDetail>;
  getAccess(): Promise<components["schemas"]["WorkoutReviewAccessResponse"]>;
  list(view: CoachWorkoutReviewView): Promise<CoachWorkoutReviewQueueItem[]>;
  reject(reviewId: string, expectedRevision: number, explanation: string): Promise<CoachWorkoutReviewDetail>;
  renew(reviewId: string): Promise<CoachWorkoutReviewDetail>;
  saveDraft(reviewId: string, draft: CoachWorkoutReviewDraft): Promise<CoachWorkoutReviewDetail>;
}

const reviewPath = "/api/v1/coach/workout-reviews";

function jsonBody(value: object): TransportRequest["body"] {
  return value as TransportRequest["body"];
}

function detailPath(reviewId: string): string {
  return `${reviewPath}/${encodeURIComponent(reviewId)}`;
}

export function createCoachWorkoutReviewApi(
  request: AuthenticatedCoachRequest,
): CoachWorkoutReviewApi {
  return {
    approve: (reviewId, expectedRevision) => request<CoachWorkoutReviewDetail>({
      body: jsonBody({ expected_revision: expectedRevision }),
      method: "POST",
      path: `${detailPath(reviewId)}/approve`,
    }),
    claim: (reviewId) => request<CoachWorkoutReviewDetail>({
      method: "POST",
      path: `${detailPath(reviewId)}/claim`,
    }),
    get: (reviewId) => request<CoachWorkoutReviewDetail>({
      method: "GET",
      path: detailPath(reviewId),
    }),
    getAccess: () => request<components["schemas"]["WorkoutReviewAccessResponse"]>({
      method: "GET",
      path: `${reviewPath}/access`,
    }),
    list: (view) => request<CoachWorkoutReviewQueueItem[]>({
      method: "GET",
      path: `${reviewPath}?view=${encodeURIComponent(view)}`,
    }),
    reject: (reviewId, expectedRevision, explanation) => request<CoachWorkoutReviewDetail>({
      body: jsonBody({ expected_revision: expectedRevision, explanation }),
      method: "POST",
      path: `${detailPath(reviewId)}/reject`,
    }),
    renew: (reviewId) => request<CoachWorkoutReviewDetail>({
      method: "POST",
      path: `${detailPath(reviewId)}/renew`,
    }),
    saveDraft: (reviewId, draft) => request<CoachWorkoutReviewDetail>({
      body: jsonBody(draft),
      method: "PUT",
      path: `${detailPath(reviewId)}/draft`,
    }),
  };
}
