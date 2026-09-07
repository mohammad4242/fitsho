import { expect, it, vi } from "vitest";

import { createBodyPhotoApi } from "./bodyPhotoApi";

const file = vi.hoisted(() => ({
  arrayBuffer: vi.fn().mockResolvedValue(Uint8Array.from([1, 2, 3]).buffer),
  exists: true,
}));

vi.mock("expo-file-system", () => ({
  File: function MockFile() {
    return file;
  },
}));

it("uses the shared body-photo session endpoints", async () => {
  const request = vi.fn().mockResolvedValue({ id: "session-1" });
  const api = createBodyPhotoApi(request);

  await api.createSession("initial_plan");
  await api.getSession("session-1");

  expect(request).toHaveBeenNthCalledWith(1, {
    body: { purpose: "initial_plan" },
    method: "POST",
    path: "/api/v1/body-photo-sessions",
  });
  expect(request).toHaveBeenNthCalledWith(2, {
    method: "GET",
    path: "/api/v1/body-photo-sessions/session-1",
  });
});

it("rejects an empty session id before making a request", async () => {
  const request = vi.fn();
  const api = createBodyPhotoApi(request);

  await expect(api.getSession(" ")).rejects.toThrow("session id");
  expect(request).not.toHaveBeenCalled();
});

it("uploads only the validated privacy-cropped JPEG bytes", async () => {
  const request = vi.fn().mockResolvedValue({ id: "session-1" });
  const upload = vi.fn().mockResolvedValue({ id: "session-1" });
  const api = createBodyPhotoApi(request, upload);

  await api.uploadPhoto("session-1", "front", {
    height: 2016,
    mimeType: "image/jpeg",
    privacyCropApplied: true,
    source: "camera",
    uri: "file:///cache/body-front-cropped.jpg",
    width: 1600,
  });

  expect(upload).toHaveBeenCalledWith({
    method: "PUT",
    parts: [{
      bytes: Uint8Array.from([1, 2, 3]),
      contentType: "image/jpeg",
      filename: "body-front.jpg",
      name: "file",
    }],
    path: "/api/v1/body-photo-sessions/session-1/photos/front",
  });
});

it("rejects uploads that do not carry the privacy-crop marker", async () => {
  const upload = vi.fn();
  const api = createBodyPhotoApi(vi.fn(), upload);

  await expect(api.uploadPhoto("session-1", "front", {
    height: 2400,
    mimeType: "image/jpeg",
    privacyCropApplied: false,
    source: "library",
    uri: "file:///photos/body-raw.jpg",
    width: 1600,
  } as never)).rejects.toThrow("privacy-cropped");
  expect(upload).not.toHaveBeenCalled();
});

it("builds submission, analysis, history, comparison, and delete requests", async () => {
  const request = vi.fn().mockResolvedValue({});
  const download = vi.fn().mockResolvedValue({ bytes: Uint8Array.from([1]) });
  const api = createBodyPhotoApi(request, undefined, download);

  await api.listSessions();
  await api.submitSession("session-1", true, false);
  await api.startAnalysis("session-1");
  await api.retryAnalysis("session-1", false);
  await api.getAnalysis("session-1");
  await api.getComparison("session-1");
  await api.getTimeline();
  await api.downloadPhoto("session-1", "front");
  await api.deleteSession("session-1");

  expect(request).toHaveBeenNthCalledWith(1, {
    method: "GET",
    path: "/api/v1/body-photo-sessions",
  });
  expect(request).toHaveBeenNthCalledWith(2, {
    body: {
      model_training: { granted: false, version: "body-photo-model-training-v1" },
      operational_processing: { granted: true, version: "body-photo-processing-v1" },
    },
    method: "POST",
    path: "/api/v1/body-photo-sessions/session-1/submit",
  });
  expect(request).toHaveBeenNthCalledWith(3, {
    body: { confirm_measurements_current: true },
    method: "POST",
    path: "/api/v1/body-photo-sessions/session-1/analysis",
  });
  expect(request).toHaveBeenNthCalledWith(4, {
    body: { confirm_measurements_current: false },
    method: "POST",
    path: "/api/v1/body-photo-sessions/session-1/analysis/retry",
  });
  expect(download).toHaveBeenCalledWith({
    headers: { "Cache-Control": "no-store", Pragma: "no-cache" },
    method: "GET",
    path: "/api/v1/body-photo-sessions/session-1/photos/front/content",
    responseType: "binary",
  });
  expect(request).toHaveBeenLastCalledWith({
    method: "DELETE",
    path: "/api/v1/body-photo-sessions/session-1",
  });
});
