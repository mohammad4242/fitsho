import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createMediaPipeLivePoseLandmarkerLoader,
  MediaPipeLivePoseGuide,
} from "./livePoseGuide";

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
});

afterEach(() => {
  vi.restoreAllMocks();
});

function pose(shape: "front" | "side" = "front") {
  const points = Array.from({ length: 33 }, (_, index) => ({
    x: index % 2 === 0 ? 0.58 : 0.42,
    y: 0.2 + (index / 45),
    z: 0,
    visibility: 0.95,
  }));
  if (shape === "side") {
    points[11] = { x: 0.47, y: 0.20, z: 0, visibility: 0.95 };
    points[12] = { x: 0.53, y: 0.20, z: 0, visibility: 0.95 };
    points[23] = { x: 0.48, y: 0.48, z: 0, visibility: 0.95 };
    points[24] = { x: 0.52, y: 0.48, z: 0, visibility: 0.95 };
  } else {
    points[11] = { x: 0.38, y: 0.20, z: 0, visibility: 0.95 };
    points[12] = { x: 0.62, y: 0.20, z: 0, visibility: 0.95 };
    points[23] = { x: 0.42, y: 0.48, z: 0, visibility: 0.95 };
    points[24] = { x: 0.58, y: 0.48, z: 0, visibility: 0.95 };
  }
  return points;
}

it("creates a separate VIDEO-mode pose landmarker and uses detectForVideo", async () => {
  const detectForVideo = vi.fn().mockReturnValue({ landmarks: [pose()] });
  const createFromOptions = vi.fn().mockResolvedValue({ detectForVideo });
  const loader = createMediaPipeLivePoseLandmarkerLoader(
    { modelAssetPath: "/live-model.task", wasmBasePath: "/live-wasm" },
    async () => ({
      FilesetResolver: { forVisionTasks: vi.fn().mockResolvedValue("fileset") },
      PoseLandmarker: { createFromOptions },
    }),
  );

  const landmarker = await loader();
  const video = { videoWidth: 720, videoHeight: 1280 } as HTMLVideoElement;
  landmarker.detectForVideo(video, 1234);

  expect(createFromOptions).toHaveBeenCalledWith("fileset", expect.objectContaining({
    numPoses: 2,
    runningMode: "VIDEO",
  }));
  expect(detectForVideo).toHaveBeenCalledWith(video, 1234);
});

it("uses relaxed confidence thresholds for side view in live video mode", async () => {
  const createFromOptions = vi.fn().mockResolvedValue({ detectForVideo: vi.fn() });
  const loader = createMediaPipeLivePoseLandmarkerLoader(
    { modelAssetPath: "/live-model.task", wasmBasePath: "/live-wasm" },
    async () => ({
      FilesetResolver: { forVisionTasks: vi.fn().mockResolvedValue("fileset") },
      PoseLandmarker: { createFromOptions },
    }),
    "side",
  );

  await loader();

  expect(createFromOptions).toHaveBeenCalledWith("fileset", expect.objectContaining({
    numPoses: 2,
    runningMode: "VIDEO",
    minPoseDetectionConfidence: 0.15,
    minPosePresenceConfidence: 0.15,
  }));
});

describe("MediaPipeLivePoseGuide", () => {
  it("returns advisory warnings without creating a capture block", () => {
    const guide = new MediaPipeLivePoseGuide(
      "front",
      { detectForVideo: vi.fn().mockReturnValue({ landmarks: [] }) },
    );

    expect(guide.check({ videoWidth: 720, videoHeight: 1280 } as HTMLVideoElement, 10)).toEqual({
      status: "available",
      warnings: ["person_missing"],
    });
  });

  it("keeps the overlay usable when live inference fails", () => {
    const guide = new MediaPipeLivePoseGuide(
      "side",
      { detectForVideo: vi.fn().mockImplementation(() => { throw new Error("slow"); }) },
    );

    expect(guide.check({ videoWidth: 720, videoHeight: 1280 } as HTMLVideoElement, 10)).toEqual({
      status: "unavailable",
      warnings: [],
    });
  });

  it("does not turn the privacy line into a live pose gate", () => {
    const landmarks = pose();
    landmarks[11]!.y = 0.1;
    landmarks[12]!.y = 0.1;
    const guide = new MediaPipeLivePoseGuide(
      "front",
      { detectForVideo: vi.fn().mockReturnValue({ landmarks: [landmarks] }) },
    );

    expect(guide.check({ videoWidth: 720, videoHeight: 1280 } as HTMLVideoElement, 10).warnings)
      .not.toContain("body_out_of_frame");
  });

  it("accepts a side posture with broader athletic shoulders without wrong_view warning", () => {
    const landmarks = pose("side");
    // Broader shoulders (span 0.14)
    landmarks[11] = { x: 0.43, y: 0.20, z: 0, visibility: 0.95 };
    landmarks[12] = { x: 0.57, y: 0.20, z: 0, visibility: 0.95 };

    const guide = new MediaPipeLivePoseGuide(
      "side",
      { detectForVideo: vi.fn().mockReturnValue({ landmarks: [landmarks] }) },
      { sideProfile: "right", ghostScale: 1.0 },
    );

    const guidance = guide.check({ videoWidth: 720, videoHeight: 1280 } as HTMLVideoElement, 10);
    expect(guidance.status).toBe("available");
    expect(guidance.warnings).not.toContain("wrong_view");
  });

  it("does not warn body_out_of_frame when one foot landmark has lower visibility", () => {
    const landmarks = pose("front");
    landmarks[31]!.visibility = 0.2;
    landmarks[32]!.visibility = 0.95;

    const guide = new MediaPipeLivePoseGuide(
      "front",
      { detectForVideo: vi.fn().mockReturnValue({ landmarks: [landmarks] }) },
    );

    const guidance = guide.check({ videoWidth: 720, videoHeight: 1280 } as HTMLVideoElement, 10);
    expect(guidance.warnings).not.toContain("body_out_of_frame");
  });

  it("uses runtime ghostScale and sideProfile options", () => {
    const landmarks = pose("side");
    const guide = new MediaPipeLivePoseGuide(
      "side",
      { detectForVideo: vi.fn().mockReturnValue({ landmarks: [landmarks] }) },
    );

    const guidance = guide.check(
      { videoWidth: 720, videoHeight: 1280 } as HTMLVideoElement,
      10,
      { ghostScale: 0.85, sideProfile: "left" },
    );

    expect(guidance.status).toBe("available");
  });
});
