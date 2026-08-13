import { afterEach, expect, it, vi } from "vitest";

import {
  getBodyPhotoAnalysis,
  retryBodyPhotoAnalysis,
  startBodyPhotoAnalysis,
  uploadBodyPhoto,
} from "./api";
import type { ProcessedBodyPhoto } from "./processor";

afterEach(() => vi.restoreAllMocks());

it("uploads only the standardized file without crop-evidence headers", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ id: "session-1", state: "uploading", photos: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  const processed: ProcessedBodyPhoto = {
    file: new File(["cropped"], "front.jpg", { type: "image/jpeg" }),
    previewUrl: "blob:preview",
    validation: {
      isValid: true,
      expectedView: "front",
      viewAssessment: "ambiguous",
      quality: {
        brightnessScore: 0.8,
        sharpnessScore: 0.9,
        minimumLandmarkVisibility: 0.9,
      },
      visibleLandmarks: ["shoulders", "arms", "hips", "knees", "ankles", "feet"],
    },
  };

  await uploadBodyPhoto("session-1", "front", processed);

  const [, init] = vi.mocked(fetch).mock.calls[0];
  const headers = new Headers(init?.headers);
  expect(Array.from(headers.keys()).some((key) => key.toLowerCase().includes("crop"))).toBe(false);
  expect(init?.body).toBeInstanceOf(FormData);
});

it("uses the owner-scoped analysis endpoints", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response("null", { status: 200, headers: { "Content-Type": "application/json" } }),
  );

  await getBodyPhotoAnalysis("session-1");
  fetchMock.mockImplementation(async () => new Response(JSON.stringify({ status: "queued" }), {
    status: 202,
    headers: { "Content-Type": "application/json" },
  }));
  await startBodyPhotoAnalysis("session-1");
  await retryBodyPhotoAnalysis("session-1");

  expect(fetchMock.mock.calls.map(([path, init]) => [path, init?.method ?? "GET"])).toEqual([
    ["/api/v1/body-photo-sessions/session-1/analysis", "GET"],
    ["/api/v1/body-photo-sessions/session-1/analysis", "POST"],
    ["/api/v1/body-photo-sessions/session-1/analysis/retry", "POST"],
  ]);
});
