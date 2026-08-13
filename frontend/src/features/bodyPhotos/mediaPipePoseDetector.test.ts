import { describe, expect, it, vi } from "vitest";

import {
  createMediaPipePoseLandmarkerLoader,
  mediaPipePoseAssets,
  MediaPipePoseLandmarkDetector,
} from "./mediaPipePoseDetector";
import type { DecodedBodyPhoto } from "./processor";

const image: DecodedBodyPhoto = {
  source: {} as CanvasImageSource,
  width: 1200,
  height: 2400,
  decodedMimeType: "image/jpeg",
  orientationNormalized: true,
  dispose: vi.fn(),
};

function pose(visibility = 0.98) {
  return Array.from({ length: 33 }, (_, index) => ({
    x: index % 2 === 0 ? 0.58 : 0.42,
    y: 0.12 + (index / 40),
    z: 0,
    visibility,
  }));
}

describe("MediaPipePoseLandmarkDetector", () => {
  it("returns only real pose landmarks reported by MediaPipe", async () => {
    const landmarks = pose();
    const detector = new MediaPipePoseLandmarkDetector(async () => ({
      detect: vi.fn().mockReturnValue({ landmarks: [landmarks] }),
    }));

    const result = await detector.detect(image);

    expect(result.personCount).toBe(1);
    expect(result.landmarks).toEqual(landmarks);
    expect(result.landmarks[11]?.visibility).toBe(0.98);
  });

  it("reports multiple real poses without selecting a primary person", async () => {
    const detector = new MediaPipePoseLandmarkDetector(async () => ({
      detect: vi.fn().mockReturnValue({ landmarks: [pose(), pose(0.87)] }),
    }));

    await expect(detector.detect(image)).resolves.toMatchObject({ personCount: 2 });
  });

  it("loads Pose Landmarker and contains no face detector asset", async () => {
    const createFromOptions = vi.fn().mockResolvedValue({ detect: vi.fn() });
    const loader = createMediaPipePoseLandmarkerLoader(
      mediaPipePoseAssets,
      async () => ({
        FilesetResolver: { forVisionTasks: vi.fn().mockResolvedValue("fileset") },
        PoseLandmarker: { createFromOptions },
      }),
    );

    await loader();

    expect(mediaPipePoseAssets.modelAssetPath).toBe("/mediapipe/models/pose_landmarker_lite.task");
    expect(JSON.stringify(mediaPipePoseAssets)).not.toMatch(/face|blaze/i);
    expect(createFromOptions).toHaveBeenCalledWith("fileset", expect.objectContaining({
      numPoses: 2,
      runningMode: "IMAGE",
    }));
  });
});
