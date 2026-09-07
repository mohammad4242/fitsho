import {
  ghostPrivacyLineGeometry,
} from "./body-ghost.js";
import type { BodyPhotoView, GhostTransform } from "./body-photos.js";

export { ghostPrivacyLineGeometry } from "./body-ghost.js";

export const GHOST_EDITOR_OUTPUT = {
  width: 1200,
  height: 1800,
} as const;

export const GHOST_EDITOR_TOLERANCE = 0.15;

const minimumPhotoScale = 0.75;
const maximumPhotoScale = 2.5;
const minimumRotation = -180;
const maximumRotation = 180;
const minimumTranslation = -0.5;
const maximumTranslation = 0.5;

export type GhostPhotoTransform = GhostTransform;

export const GHOST_EDITOR_DEFAULT_TRANSFORM: GhostPhotoTransform = {
  scale: 1,
  translateX: 0,
  translateY: 0,
  rotation: 0,
};

export type GhostPhotoRenderPlan = {
  canvasWidth: number;
  canvasHeight: number;
  sourceWidth: number;
  sourceHeight: number;
  baseScale: number;
  sourceCropY: number;
  privacyCutPixels: number;
  privacyLineDisplayY: number;
  draw: {
    translateX: number;
    translateY: number;
    rotationRadians: number;
    scale: number;
  };
};

export type GhostDisplaySize = {
  width: number;
  height: number;
};

export type GhostContainedImageRect = GhostDisplaySize & {
  x: number;
  y: number;
};

export function clampGhostPhotoTransform(
  transform: GhostPhotoTransform,
): GhostPhotoTransform {
  return {
    translateX: clamp(transform.translateX, minimumTranslation, maximumTranslation),
    translateY: clamp(transform.translateY, minimumTranslation, maximumTranslation),
    scale: clamp(transform.scale, minimumPhotoScale, maximumPhotoScale),
    rotation: clamp(transform.rotation, minimumRotation, maximumRotation),
  };
}

export function isGhostFramingWithinTolerance(
  transform: GhostPhotoTransform,
  tolerance = GHOST_EDITOR_TOLERANCE,
): boolean {
  const safeTolerance = clamp(tolerance, 0, 1);
  return Math.abs(transform.translateX) <= safeTolerance
    && Math.abs(transform.translateY) <= safeTolerance;
}

export function containImageRect(
  container: GhostDisplaySize,
  source: GhostDisplaySize,
): GhostContainedImageRect {
  if (container.width <= 0 || container.height <= 0 || source.width <= 0 || source.height <= 0) {
    throw new Error("Ghost image dimensions must be positive");
  }
  const scale = Math.min(container.width / source.width, container.height / source.height);
  const width = source.width * scale;
  const height = source.height * scale;
  return {
    x: (container.width - width) / 2,
    y: (container.height - height) / 2,
    width,
    height,
  };
}

export function privacyCropSourceYForView(
  view: BodyPhotoView,
  ghostScale: number,
  displaySize: GhostDisplaySize,
  sourceSize: GhostDisplaySize,
): number {
  const line = ghostPrivacyLineGeometry(view, ghostScale);
  const imageRect = containImageRect(displaySize, sourceSize);
  const displayY = line.anchor.y * displaySize.height;
  return clamp(
    ((displayY - imageRect.y) / imageRect.height) * sourceSize.height,
    0,
    sourceSize.height,
  );
}

export function createGhostPhotoRenderPlan(
  sourceWidth: number,
  sourceHeight: number,
  transform: GhostPhotoTransform,
  view: BodyPhotoView = "front",
  ghostScale = 1,
): GhostPhotoRenderPlan {
  if (sourceWidth <= 0 || sourceHeight <= 0) {
    throw new Error("Ghost photo source dimensions must be positive");
  }
  const baseScale = Math.min(
    GHOST_EDITOR_OUTPUT.width / sourceWidth,
    GHOST_EDITOR_OUTPUT.height / sourceHeight,
  );
  const safeTransform = clampGhostPhotoTransform(transform);
  const privacyLineDisplayY = Math.round(
    ghostPrivacyLineGeometry(view, ghostScale).anchor.y * GHOST_EDITOR_OUTPUT.height,
  );
  const sourceCropY = Math.round(privacyCropSourceYForView(
    view,
    ghostScale,
    GHOST_EDITOR_OUTPUT,
    { width: sourceWidth, height: sourceHeight },
  ));
  const privacyCutPixels = privacyLineDisplayY;
  return {
    canvasWidth: GHOST_EDITOR_OUTPUT.width,
    canvasHeight: Math.max(1, GHOST_EDITOR_OUTPUT.height - privacyCutPixels),
    sourceWidth,
    sourceHeight,
    baseScale,
    sourceCropY,
    privacyCutPixels,
    privacyLineDisplayY,
    draw: {
      translateX: GHOST_EDITOR_OUTPUT.width / 2
        + safeTransform.translateX * GHOST_EDITOR_OUTPUT.width,
      translateY: GHOST_EDITOR_OUTPUT.height / 2
        - privacyCutPixels
        + safeTransform.translateY * GHOST_EDITOR_OUTPUT.height,
      rotationRadians: safeTransform.rotation * Math.PI / 180,
      scale: baseScale * safeTransform.scale,
    },
  };
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, Number.isFinite(value) ? value : 0));
}
