import { clampGhostPhotoTransform } from "@fitician/core/body-ghost-editor";
import type { GhostPhotoTransform } from "@fitician/core/body-ghost-editor";

export { GHOST_EDITOR_DEFAULT_TRANSFORM, clampGhostPhotoTransform } from "@fitician/core/body-ghost-editor";
export type { GhostPhotoTransform } from "@fitician/core/body-ghost-editor";

export type GhostPhotoPoint = {
  readonly x: number;
  readonly y: number;
};

export type GhostPhotoStageSize = {
  readonly height: number;
  readonly width: number;
};

export type GhostPhotoPinchGesture = {
  readonly initialAngle: number;
  readonly initialCenter: GhostPhotoPoint;
  readonly initialDistance: number;
  readonly initialTransform: GhostPhotoTransform;
  readonly stage: GhostPhotoStageSize;
};

export function applyGhostPhotoDrag(
  transform: GhostPhotoTransform,
  delta: GhostPhotoPoint,
  stage: GhostPhotoStageSize,
): GhostPhotoTransform {
  const safeStage = normalizeStageSize(stage);
  return clampGhostPhotoTransform({
    ...transform,
    translateX: transform.translateX + delta.x / safeStage.width,
    translateY: transform.translateY + delta.y / safeStage.height,
  });
}

export function createGhostPhotoPinchGesture(
  first: GhostPhotoPoint,
  second: GhostPhotoPoint,
  transform: GhostPhotoTransform,
  stage: GhostPhotoStageSize,
): GhostPhotoPinchGesture {
  return {
    initialAngle: angle(first, second),
    initialCenter: midpoint(first, second),
    initialDistance: distance(first, second),
    initialTransform: clampGhostPhotoTransform(transform),
    stage: normalizeStageSize(stage),
  };
}

export function applyGhostPhotoPinchGesture(
  gesture: GhostPhotoPinchGesture,
  first: GhostPhotoPoint,
  second: GhostPhotoPoint,
): GhostPhotoTransform {
  const currentDistance = distance(first, second);
  const scaleRatio = gesture.initialDistance === 0
    ? 1
    : currentDistance / gesture.initialDistance;
  const currentCenter = midpoint(first, second);
  const rotationDelta = shortestAngleDelta(angle(first, second) - gesture.initialAngle);
  return clampGhostPhotoTransform({
    translateX: gesture.initialTransform.translateX
      + (currentCenter.x - gesture.initialCenter.x) / gesture.stage.width,
    translateY: gesture.initialTransform.translateY
      + (currentCenter.y - gesture.initialCenter.y) / gesture.stage.height,
    scale: gesture.initialTransform.scale * scaleRatio,
    rotation: gesture.initialTransform.rotation + (rotationDelta * 180) / Math.PI,
  });
}

function normalizeStageSize(stage: GhostPhotoStageSize): GhostPhotoStageSize {
  return {
    height: Number.isFinite(stage.height) && stage.height > 0 ? stage.height : 1,
    width: Number.isFinite(stage.width) && stage.width > 0 ? stage.width : 1,
  };
}

function midpoint(first: GhostPhotoPoint, second: GhostPhotoPoint): GhostPhotoPoint {
  return { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 };
}

function distance(first: GhostPhotoPoint, second: GhostPhotoPoint): number {
  return Math.hypot(second.x - first.x, second.y - first.y);
}

function angle(first: GhostPhotoPoint, second: GhostPhotoPoint): number {
  return Math.atan2(second.y - first.y, second.x - first.x);
}

function shortestAngleDelta(delta: number): number {
  if (delta > Math.PI) return delta - 2 * Math.PI;
  if (delta < -Math.PI) return delta + 2 * Math.PI;
  return delta;
}
