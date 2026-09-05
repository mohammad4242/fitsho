import { describe, expect, it } from "vitest";

import { validatePoseWithGhost } from "./ghostPoseValidator";
import type { NormalizedBodyLandmark } from "./processor";

function createPose(shape: "front" | "side" = "front"): NormalizedBodyLandmark[] {
  const points = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, z: 0, visibility: 0.95 }));
  const span = shape === "side" ? 0.04 : 0.22;
  const pair = (left: number, right: number, y: number, pairSpan = span) => {
    points[left] = { x: 0.5 - pairSpan / 2, y, z: 0, visibility: 0.95 };
    points[right] = { x: 0.5 + pairSpan / 2, y, z: 0, visibility: 0.95 };
  };
  pair(11, 12, 0.20);
  pair(13, 14, 0.34, shape === "side" ? 0.06 : 0.32);
  pair(15, 16, 0.46, shape === "side" ? 0.08 : 0.36);
  pair(23, 24, 0.48, shape === "side" ? 0.04 : 0.16);
  pair(25, 26, 0.68, shape === "side" ? 0.04 : 0.15);
  pair(27, 28, 0.88, shape === "side" ? 0.04 : 0.14);
  pair(29, 30, 0.91, shape === "side" ? 0.04 : 0.14);
  pair(31, 32, 0.94, shape === "side" ? 0.06 : 0.18);
  return points;
}

describe("ghostPoseValidator", () => {
  it("passes a standard front photo", () => {
    const pose = createPose("front");
    const result = validatePoseWithGhost({
      view: "front",
      poses: [pose],
    });

    expect(result.status).toBe("pass");
    expect(result.hardRejectCode).toBeNull();
    expect(result.overallScore).toBeGreaterThanOrEqual(0.75);
    expect(result.visibleLandmarks).toContain("shoulders");
    expect(result.visibleLandmarks).toContain("feet");
  });

  it("passes a front photo with one weak foot landmark (reduces score or warns, but does not hard reject)", () => {
    const pose = createPose("front");
    pose[31]!.visibility = 0.2; // one foot landmark weak
    pose[32]!.visibility = 0.95; // other foot landmark strong

    const result = validatePoseWithGhost({
      view: "front",
      poses: [pose],
    });

    expect(result.hardRejectCode).toBeNull();
    expect(["pass", "warn"]).toContain(result.status);
    expect(result.overallScore).toBeGreaterThanOrEqual(0.55);
  });

  it("passes a back photo in realistic posture", () => {
    const pose = createPose("front");
    pose[31]!.visibility = 0.45;

    const result = validatePoseWithGhost({
      view: "back",
      poses: [pose],
    });

    expect(result.hardRejectCode).toBeNull();
    expect(["pass", "warn"]).toContain(result.status);
    expect(result.overallScore).toBeGreaterThanOrEqual(0.55);
  });

  it("passes a side photo for both right and left profile orientations", () => {
    const rightPose = createPose("side");
    const rightResult = validatePoseWithGhost({
      view: "side",
      sideProfile: "right",
      poses: [rightPose],
    });
    expect(rightResult.hardRejectCode).toBeNull();
    expect(rightResult.status).toBe("pass");

    const leftPose = createPose("side");
    const leftResult = validatePoseWithGhost({
      view: "side",
      sideProfile: "left",
      poses: [leftPose],
    });
    expect(leftResult.hardRejectCode).toBeNull();
    expect(leftResult.status).toBe("pass");
  });

  it("accepts a side photo with broader athletic shoulder span without rigid failure", () => {
    const pose = createPose("side");
    // Broader shoulders (0.16 span)
    pose[11] = { x: 0.42, y: 0.20, z: 0, visibility: 0.95 };
    pose[12] = { x: 0.58, y: 0.20, z: 0, visibility: 0.95 };

    const result = validatePoseWithGhost({
      view: "side",
      poses: [pose],
    });

    expect(result.hardRejectCode).toBeNull();
    expect(["pass", "warn"]).toContain(result.status);
  });

  it("does not hard fail on coordinates slightly outside [0, 1] like 1.001", () => {
    const pose = createPose("front");
    pose[31]!.y = 1.001; // tiny overflow from model regression
    pose[32]!.y = 0.999;

    const result = validatePoseWithGhost({
      view: "front",
      poses: [pose],
    });

    expect(result.hardRejectCode).toBeNull();
    expect(["pass", "warn"]).toContain(result.status);
    expect(result.warnings).toContain("near_boundary_landmarks");
  });

  it("hard fails when an obviously wrong view is provided", () => {
    const frontPose = createPose("front");
    // Provided front posture when side view requested
    const result = validatePoseWithGhost({
      view: "side",
      poses: [frontPose],
    });

    expect(result.status).toBe("fail");
    expect(result.hardRejectCode).toBe("unexpected_body_view");
  });

  it("hard fails on severe cropping out of frame", () => {
    const pose = createPose("front");
    // Severely outside frame (> 0.12 beyond bounds)
    pose[11]!.x = -0.15;

    const result = validatePoseWithGhost({
      view: "front",
      poses: [pose],
    });

    expect(result.status).toBe("fail");
    expect(result.hardRejectCode).toBe("body_out_of_frame");
  });

  it("hard fails when multiple people are detected", () => {
    const primary = createPose("front");
    const secondary = createPose("front").map((p) => ({ ...p, x: p.x + 0.35 }));

    const result = validatePoseWithGhost({
      view: "front",
      poses: [primary, secondary],
    });

    expect(result.status).toBe("fail");
    expect(result.hardRejectCode).toBe("multiple_people_detected");
  });

  it("consistently moves expectations when ghostScale changes", () => {
    const poseSmall = createPose("front").map((p) => ({
      ...p,
      y: 0.5 + (p.y - 0.5) * 0.8,
    }));

    const resultSmall = validatePoseWithGhost({
      view: "front",
      ghostScale: 0.8,
      poses: [poseSmall],
    });

    expect(resultSmall.hardRejectCode).toBeNull();
    expect(resultSmall.componentScores.scaleFit).toBeGreaterThan(0.7);
  });

  it("tolerates different body shapes (wide hips / pear, broad shoulders / athletic) without sex-specific dependencies", () => {
    const pearPose = createPose("front");
    pearPose[11] = { x: 0.41, y: 0.20, z: 0, visibility: 0.95 };
    pearPose[12] = { x: 0.59, y: 0.20, z: 0, visibility: 0.95 };
    pearPose[23] = { x: 0.35, y: 0.48, z: 0, visibility: 0.95 };
    pearPose[24] = { x: 0.65, y: 0.48, z: 0, visibility: 0.95 };

    const pearResult = validatePoseWithGhost({
      view: "front",
      poses: [pearPose],
    });
    expect(pearResult.status).toBe("pass");
    expect(pearResult.hardRejectCode).toBeNull();

    const athleticPose = createPose("front");
    athleticPose[11] = { x: 0.34, y: 0.20, z: 0, visibility: 0.95 };
    athleticPose[12] = { x: 0.66, y: 0.20, z: 0, visibility: 0.95 };
    athleticPose[23] = { x: 0.42, y: 0.48, z: 0, visibility: 0.95 };
    athleticPose[24] = { x: 0.58, y: 0.48, z: 0, visibility: 0.95 };

    const athleticResult = validatePoseWithGhost({
      view: "front",
      poses: [athleticPose],
    });
    expect(athleticResult.status).toBe("pass");
    expect(athleticResult.hardRejectCode).toBeNull();
  });

  it("passes a side photo with low visibility on far-side landmarks (down to 0.20)", () => {
    const pose = createPose("side");
    pose[11] = { x: 0.49, y: 0.20, z: 0, visibility: 0.22 };
    pose[12] = { x: 0.51, y: 0.20, z: 0, visibility: 0.95 };
    pose[23] = { x: 0.49, y: 0.48, z: 0, visibility: 0.22 };
    pose[24] = { x: 0.51, y: 0.48, z: 0, visibility: 0.95 };

    const result = validatePoseWithGhost({
      view: "side",
      poses: [pose],
    });

    expect(result.status).not.toBe("fail");
    expect(result.hardRejectCode).toBeNull();
    expect(result.visibleLandmarks).toContain("shoulders");
    expect(result.visibleLandmarks).toContain("hips");
  });
});
