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

function pose() {
  return Array.from({ length: 33 }, (_, index) => ({
    x: index % 2 === 0 ? 0.58 : 0.42,
    y: 0.2 + (index / 45),
    z: 0,
    visibility: 0.95,
  }));
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

  it("allows a shoulder at the back privacy boundary", () => {
    const landmarks = pose();
    landmarks[11]!.y = 0.1;
    landmarks[12]!.y = 0.1;
    const guide = new MediaPipeLivePoseGuide(
      "back",
      { detectForVideo: vi.fn().mockReturnValue({ landmarks: [landmarks] }) },
    );

    expect(guide.check({ videoWidth: 720, videoHeight: 1280 } as HTMLVideoElement, 10).warnings)
      .not.toContain("body_out_of_frame");
  });
});
