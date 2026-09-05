import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  BrowserBodyPhotoProcessor,
  type BodyLandmarkDetection,
  type BodyLandmarkDetector,
  type BodyPhotoRuntime,
  type BodyPhotoSegmenter,
  type DecodedBodyPhoto,
  type NormalizedBodyLandmark,
} from "./processor";

function createValidPose(shape: "front" | "side" = "front"): NormalizedBodyLandmark[] {
  const points = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, z: 0, visibility: 0.98 }));
  const span = shape === "side" ? 0.035 : 0.22;
  const pair = (left: number, right: number, y: number, pairSpan = span) => {
    points[left] = { x: 0.5 - pairSpan / 2, y, z: 0, visibility: 0.98 };
    points[right] = { x: 0.5 + pairSpan / 2, y, z: 0, visibility: 0.98 };
  };
  pair(11, 12, 0.18);
  pair(13, 14, 0.32, shape === "side" ? 0.08 : 0.32);
  pair(15, 16, 0.46, shape === "side" ? 0.1 : 0.38);
  pair(23, 24, 0.48, shape === "side" ? 0.03 : 0.16);
  pair(25, 26, 0.68, shape === "side" ? 0.04 : 0.15);
  pair(27, 28, 0.88, shape === "side" ? 0.04 : 0.14);
  pair(29, 30, 0.91, shape === "side" ? 0.04 : 0.14);
  pair(31, 32, 0.94, shape === "side" ? 0.08 : 0.2);
  return points;
}

function createInputFile() {
  return new File([new Uint8Array([0xff, 0xd8, 0xff, 0xdb])], "body.jpg", {
    type: "image/jpeg",
  });
}

function setupProcessor(pose: NormalizedBodyLandmark[]) {
  const detection: BodyLandmarkDetection = { poses: [pose] };
  const detector: BodyLandmarkDetector = { detect: vi.fn().mockResolvedValue(detection) };
  const segmenter: BodyPhotoSegmenter = {
    segment: vi.fn().mockResolvedValue({
      width: 2,
      height: 2,
      confidence: new Float32Array([0, 1, 1, 0]),
    }),
  };
  const decoded: DecodedBodyPhoto = {
    source: {} as CanvasImageSource,
    width: 1200,
    height: 1800,
    decodedMimeType: "image/jpeg",
    orientationNormalized: true,
    dispose: vi.fn(),
  };
  const standardized = new Blob(["standardized"], { type: "image/jpeg" });
  const runtime: BodyPhotoRuntime = {
    decode: vi.fn().mockResolvedValue(decoded),
    measureQuality: vi.fn().mockReturnValue({
      brightnessScore: 0.55,
      sharpnessScore: 0.35,
    }),
    normalizeBackground: vi.fn().mockResolvedValue({
      blob: standardized,
      width: 1200,
      height: 1800,
    }),
    createObjectUrl: vi.fn().mockReturnValue("blob:standardized"),
  };
  const processor = new BrowserBodyPhotoProcessor({ detector, segmenter, runtime });
  return { processor, decoded };
}

describe("Ghost validation baseline: failing cases under legacy rules", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("should accept a front photo that is visually correct inside Ghost even with one weak foot landmark", async () => {
    const pose = createValidPose("front");
    pose[31]!.visibility = 0.2;
    pose[32]!.visibility = 0.95;

    const { processor } = setupProcessor(pose);
    await expect(processor.process(createInputFile(), "front")).resolves.toMatchObject({
      validation: { expectedView: "front", isValid: true },
    });
  });

  it("should accept a side photo that is visually correct without failing due to broader shoulder span", async () => {
    const pose = createValidPose("side");
    // A person with broader shoulders or posture where shoulder span is 0.17 and hip span is 0.13
    pose[11] = { x: 0.415, y: 0.18, z: 0, visibility: 0.95 };
    pose[12] = { x: 0.585, y: 0.18, z: 0, visibility: 0.95 };
    pose[23] = { x: 0.435, y: 0.48, z: 0, visibility: 0.95 };
    pose[24] = { x: 0.565, y: 0.48, z: 0, visibility: 0.95 };

    const { processor } = setupProcessor(pose);
    await expect(processor.process(createInputFile(), "side")).resolves.toMatchObject({
      validation: { expectedView: "side", isValid: true },
    });
  });

  it("should accept a back photo that is visually correct without rigid front/back rejection", async () => {
    const pose = createValidPose("front");
    // Visually correct back pose with one slightly weaker lower-body landmark
    pose[31]!.visibility = 0.45;

    const { processor } = setupProcessor(pose);
    await expect(processor.process(createInputFile(), "back")).resolves.toMatchObject({
      validation: { expectedView: "back", isValid: true },
    });
  });

  it("should not trigger body_out_of_frame for coordinates slightly outside normalized bounds like 1.001", async () => {
    const pose = createValidPose("front");
    // Near bottom edge coordinate with tiny numeric overflow
    pose[31]!.y = 1.001;
    pose[32]!.y = 0.999;

    const { processor } = setupProcessor(pose);
    await expect(processor.process(createInputFile(), "front")).resolves.toMatchObject({
      validation: { expectedView: "front", isValid: true },
    });
  });

  it("demonstrates inconsistency between live camera guidance and final validation under legacy rules", async () => {
    // In live camera, a side posture with shoulder span 0.17 has no wrong_view warning (threshold is > 0.25)
    // But final validation rejects it as unexpected_body_view because shoulderSpan >= 0.16
    const pose = createValidPose("side");
    pose[11] = { x: 0.415, y: 0.18, z: 0, visibility: 0.95 };
    pose[12] = { x: 0.585, y: 0.18, z: 0, visibility: 0.95 };
    pose[23] = { x: 0.435, y: 0.48, z: 0, visibility: 0.95 };
    pose[24] = { x: 0.565, y: 0.48, z: 0, visibility: 0.95 };

    const { processor } = setupProcessor(pose);
    // User expects final validation to be consistent with live camera acceptance
    await expect(processor.process(createInputFile(), "side")).resolves.toMatchObject({
      validation: { expectedView: "side" },
    });
  });

});
