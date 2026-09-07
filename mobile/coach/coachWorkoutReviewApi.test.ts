import { expect, it } from "vitest";

import type { TransportRequest } from "@fitician/core";

import { createCoachWorkoutReviewApi } from "./coachWorkoutReviewApi";

it("uses the authenticated coach review contract for queue, claim, draft, and decisions", async () => {
  const requests: TransportRequest[] = [];
  const api = createCoachWorkoutReviewApi(async <TResponse>(request: TransportRequest) => {
    requests.push(request);
    return {} as TResponse;
  });
  const draft = {
    expected_revision: 2,
    coach_note: "توضیح بررسی",
    days: [],
  };

  await api.getAccess();
  await api.list("pending");
  await api.get("review-1");
  await api.claim("review-1");
  await api.renew("review-1");
  await api.saveDraft("review-1", draft);
  await api.approve("review-1", 3);
  await api.reject("review-1", 3, "نیاز به اصلاح دارد");

  expect(requests).toEqual([
    { method: "GET", path: "/api/v1/coach/workout-reviews/access" },
    { method: "GET", path: "/api/v1/coach/workout-reviews?view=pending" },
    { method: "GET", path: "/api/v1/coach/workout-reviews/review-1" },
    { method: "POST", path: "/api/v1/coach/workout-reviews/review-1/claim" },
    { method: "POST", path: "/api/v1/coach/workout-reviews/review-1/renew" },
    {
      body: draft,
      method: "PUT",
      path: "/api/v1/coach/workout-reviews/review-1/draft",
    },
    {
      body: { expected_revision: 3 },
      method: "POST",
      path: "/api/v1/coach/workout-reviews/review-1/approve",
    },
    {
      body: { expected_revision: 3, explanation: "نیاز به اصلاح دارد" },
      method: "POST",
      path: "/api/v1/coach/workout-reviews/review-1/reject",
    },
  ]);
});
