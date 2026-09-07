import { expect, it } from "vitest";

import {
  ApiError,
  type BinaryDownload,
  type BinaryDownloadRequest,
  type TransportRequest,
} from "@fitician/core";

import { createWorkoutPlanApi, type ProgramGenerationOverrides } from "./workoutApi";

function binaryDownload(): BinaryDownload {
  return {
    bytes: Uint8Array.from([37, 80, 68, 70]),
    contentType: "application/pdf",
    filename: "workout-plan.pdf",
  };
}

it("uses the authenticated workout plan endpoints and preserves plan ids", async () => {
  const requests: TransportRequest[] = [];
  const downloads: BinaryDownloadRequest[] = [];
  const api = createWorkoutPlanApi(
    async <TResponse>(request: TransportRequest): Promise<TResponse> => {
      requests.push(request);
      return (request.path.endsWith("/history") ? [] : {}) as TResponse;
    },
    async (request: BinaryDownloadRequest): Promise<BinaryDownload> => {
      downloads.push(request);
      return binaryDownload();
    },
  );

  await api.getActive();
  await api.generate();
  await api.getHistory();
  await api.get("plan/id");
  await api.downloadPdf("plan/id");

  expect(requests).toEqual([
    { method: "GET", path: "/api/v1/workout-plans/active" },
    { method: "POST", path: "/api/v1/workout-plans/generate" },
    { method: "GET", path: "/api/v1/workout-plans/history" },
    { method: "GET", path: "/api/v1/workout-plans/plan%2Fid" },
  ]);
  expect(downloads).toEqual([
    {
      method: "GET",
      path: "/api/v1/workout-plans/plan%2Fid/pdf",
      responseType: "binary",
    },
  ]);
});

it("serializes generation overrides only when supplied", async () => {
  const requests: TransportRequest[] = [];
  const api = createWorkoutPlanApi(
    async <TResponse>(request: TransportRequest): Promise<TResponse> => {
      requests.push(request);
      return { plan: {}, reused: false } as TResponse;
    },
    async () => binaryDownload(),
  );

  await api.generate({
    allowed_range_of_motion: [],
    blocked_caution_tags: [],
    blocked_exercises: [],
    blocked_movement_patterns: [],
    current_pain_or_red_flags: [],
    disliked_exercises: [],
    injuries_and_limitations: [],
    preferred_exercises: [],
    pregnancy_or_postpartum: false,
    priority_muscles: [],
    reports_uncontrolled_medical_condition: false,
  } as ProgramGenerationOverrides);

  expect(requests).toEqual([
    {
      body: {
        allowed_range_of_motion: [],
        blocked_caution_tags: [],
        blocked_exercises: [],
        blocked_movement_patterns: [],
        current_pain_or_red_flags: [],
        disliked_exercises: [],
        injuries_and_limitations: [],
        preferred_exercises: [],
        pregnancy_or_postpartum: false,
        priority_muscles: [],
        reports_uncontrolled_medical_condition: false,
      },
      method: "POST",
      path: "/api/v1/workout-plans/generate",
    },
  ]);
});

it("treats only an active-plan 404 as an empty active plan", async () => {
  const api = createWorkoutPlanApi(
    async <TResponse>(request: TransportRequest): Promise<TResponse> => {
      throw new ApiError(404, request.path);
    },
    async () => binaryDownload(),
  );

  await expect(api.getActive()).resolves.toBeNull();
  await expect(api.get("missing")).rejects.toMatchObject({ status: 404 });
});
