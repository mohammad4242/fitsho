import { GHOST_SCALE_MAX, GHOST_SCALE_MIN } from "./ghostScale";
import type { BodyPhotoSide, BodyPhotoView } from "./types";

export const GHOST_PRIVACY_CUT_RATIO = 0.16;
export const GHOST_SIDE_PRIVACY_CUT_RATIO = 0.28;
export const GHOST_BACK_PRIVACY_CUT_RATIO = 0.08;

export type GhostPoint = {
  x: number;
  y: number;
};

export type GhostZone = {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
};

export type GhostPrivacyLine = {
  anchor: GhostPoint;
  start: GhostPoint;
  end: GhostPoint;
};

export type GhostViewGeometry = {
  view: BodyPhotoView;
  sideProfile: BodyPhotoSide;
  ghostScale: number;
  mirrored: boolean;
  centerX: number;
  bodyBounds: GhostZone;
  expectedBodySpan: {
    min: number;
    target: number;
    max: number;
  };
  zones: {
    shoulders: GhostZone;
    leftShoulder: GhostZone;
    rightShoulder: GhostZone;
    hips: GhostZone;
    leftHip: GhostZone;
    rightHip: GhostZone;
    knees: GhostZone;
    leftKnee: GhostZone;
    rightKnee: GhostZone;
    ankles: GhostZone;
    leftAnkle: GhostZone;
    rightAnkle: GhostZone;
    feet: GhostZone;
    leftFoot: GhostZone;
    rightFoot: GhostZone;
  };
  privacyLine: GhostPrivacyLine;
  sideVisibleChain?: {
    shoulder: GhostZone;
    hip: GhostZone;
    knee: GhostZone;
    ankle: GhostZone;
    foot: GhostZone;
  };
};

export function clampGhostScale(scale: number): number {
  return Math.min(GHOST_SCALE_MAX, Math.max(GHOST_SCALE_MIN, Number.isFinite(scale) ? scale : 1));
}

export function ghostPrivacyCutRatioForView(view: BodyPhotoView): number {
  if (view === "back") return GHOST_BACK_PRIVACY_CUT_RATIO;
  if (view === "side") return GHOST_SIDE_PRIVACY_CUT_RATIO;
  return GHOST_PRIVACY_CUT_RATIO;
}

export function transformGhostPoint(
  point: GhostPoint,
  scale: number,
  mirrored = false,
): GhostPoint {
  const safeScale = clampGhostScale(scale);
  const relativeX = (point.x - 0.5) * safeScale;
  const relativeY = (point.y - 0.5) * safeScale;
  const transformedX = 0.5 + relativeX;
  const transformedY = 0.5 + relativeY;
  return {
    x: mirrored ? 1 - transformedX : transformedX,
    y: transformedY,
  };
}

export function transformGhostZone(
  zone: GhostZone,
  scale: number,
  mirrored = false,
): GhostZone {
  const p1 = transformGhostPoint({ x: zone.minX, y: zone.minY }, scale, mirrored);
  const p2 = transformGhostPoint({ x: zone.maxX, y: zone.maxY }, scale, mirrored);
  return {
    minX: Math.min(p1.x, p2.x),
    maxX: Math.max(p1.x, p2.x),
    minY: Math.min(p1.y, p2.y),
    maxY: Math.max(p1.y, p2.y),
  };
}

export function ghostPrivacyLineGeometry(
  view: BodyPhotoView,
  ghostScale = 1,
  mirrored = false,
): GhostPrivacyLine {
  const safeScale = clampGhostScale(ghostScale);
  const transformedAnchor = transformGhostPoint(
    { x: 0.5, y: ghostPrivacyCutRatioForView(view) },
    safeScale,
    false,
  );
  const halfLineLength = safeScale / 2;
  const transformedStart = {
    x: transformedAnchor.x - halfLineLength,
    y: transformedAnchor.y,
  };
  const transformedEnd = {
    x: transformedAnchor.x + halfLineLength,
    y: transformedAnchor.y,
  };

  if (mirrored) {
    return {
      anchor: { x: 1 - transformedAnchor.x, y: transformedAnchor.y },
      start: { x: 1 - transformedEnd.x, y: transformedEnd.y },
      end: { x: 1 - transformedStart.x, y: transformedStart.y },
    };
  }
  return {
    anchor: transformedAnchor,
    start: transformedStart,
    end: transformedEnd,
  };
}

// Base unscaled normalized reference envelopes (at ghostScale = 1)
// These define tolerant positional bands supporting varied body sizes and proportions.
const BASE_FRONT_ZONES = {
  bodyBounds: { minX: 0.15, maxX: 0.85, minY: 0.14, maxY: 0.99 },
  shoulders: { minX: 0.25, maxX: 0.75, minY: 0.12, maxY: 0.30 },
  leftShoulder: { minX: 0.25, maxX: 0.52, minY: 0.12, maxY: 0.30 },
  rightShoulder: { minX: 0.48, maxX: 0.75, minY: 0.12, maxY: 0.30 },
  hips: { minX: 0.28, maxX: 0.72, minY: 0.40, maxY: 0.60 },
  leftHip: { minX: 0.28, maxX: 0.52, minY: 0.40, maxY: 0.60 },
  rightHip: { minX: 0.48, maxX: 0.72, minY: 0.40, maxY: 0.60 },
  knees: { minX: 0.30, maxX: 0.70, minY: 0.58, maxY: 0.78 },
  leftKnee: { minX: 0.30, maxX: 0.52, minY: 0.58, maxY: 0.78 },
  rightKnee: { minX: 0.48, maxX: 0.70, minY: 0.58, maxY: 0.78 },
  ankles: { minX: 0.28, maxX: 0.72, minY: 0.78, maxY: 0.97 },
  leftAnkle: { minX: 0.28, maxX: 0.52, minY: 0.78, maxY: 0.97 },
  rightAnkle: { minX: 0.48, maxX: 0.72, minY: 0.78, maxY: 0.97 },
  feet: { minX: 0.24, maxX: 0.76, minY: 0.82, maxY: 1.00 },
  leftFoot: { minX: 0.24, maxX: 0.54, minY: 0.82, maxY: 1.00 },
  rightFoot: { minX: 0.46, maxX: 0.76, minY: 0.82, maxY: 1.00 },
};

const BASE_SIDE_ZONES = {
  bodyBounds: { minX: 0.18, maxX: 0.82, minY: 0.07, maxY: 0.99 },
  shoulders: { minX: 0.25, maxX: 0.75, minY: 0.07, maxY: 0.35 },
  leftShoulder: { minX: 0.25, maxX: 0.75, minY: 0.07, maxY: 0.35 },
  rightShoulder: { minX: 0.25, maxX: 0.75, minY: 0.07, maxY: 0.35 },
  hips: { minX: 0.28, maxX: 0.72, minY: 0.38, maxY: 0.62 },
  leftHip: { minX: 0.28, maxX: 0.72, minY: 0.38, maxY: 0.62 },
  rightHip: { minX: 0.28, maxX: 0.72, minY: 0.38, maxY: 0.62 },
  knees: { minX: 0.28, maxX: 0.72, minY: 0.55, maxY: 0.80 },
  leftKnee: { minX: 0.28, maxX: 0.72, minY: 0.55, maxY: 0.80 },
  rightKnee: { minX: 0.28, maxX: 0.72, minY: 0.55, maxY: 0.80 },
  ankles: { minX: 0.26, maxX: 0.74, minY: 0.75, maxY: 0.98 },
  leftAnkle: { minX: 0.26, maxX: 0.74, minY: 0.75, maxY: 0.98 },
  rightAnkle: { minX: 0.26, maxX: 0.74, minY: 0.75, maxY: 0.98 },
  feet: { minX: 0.24, maxX: 0.76, minY: 0.80, maxY: 1.00 },
  leftFoot: { minX: 0.24, maxX: 0.76, minY: 0.80, maxY: 1.00 },
  rightFoot: { minX: 0.24, maxX: 0.76, minY: 0.80, maxY: 1.00 },
};

export function getGhostGeometry(options: {
  view: BodyPhotoView;
  ghostScale?: number;
  sideProfile?: BodyPhotoSide;
}): GhostViewGeometry {
  const { view } = options;
  const sideProfile: BodyPhotoSide = options.sideProfile ?? "right";
  const ghostScale = clampGhostScale(options.ghostScale ?? 1);
  const mirrored = view === "side" && sideProfile === "left";

  const base = view === "side" ? BASE_SIDE_ZONES : BASE_FRONT_ZONES;

  const transformedZones = {
    shoulders: transformGhostZone(base.shoulders, ghostScale, mirrored),
    leftShoulder: transformGhostZone(base.leftShoulder, ghostScale, mirrored),
    rightShoulder: transformGhostZone(base.rightShoulder, ghostScale, mirrored),
    hips: transformGhostZone(base.hips, ghostScale, mirrored),
    leftHip: transformGhostZone(base.leftHip, ghostScale, mirrored),
    rightHip: transformGhostZone(base.rightHip, ghostScale, mirrored),
    knees: transformGhostZone(base.knees, ghostScale, mirrored),
    leftKnee: transformGhostZone(base.leftKnee, ghostScale, mirrored),
    rightKnee: transformGhostZone(base.rightKnee, ghostScale, mirrored),
    ankles: transformGhostZone(base.ankles, ghostScale, mirrored),
    leftAnkle: transformGhostZone(base.leftAnkle, ghostScale, mirrored),
    rightAnkle: transformGhostZone(base.rightAnkle, ghostScale, mirrored),
    feet: transformGhostZone(base.feet, ghostScale, mirrored),
    leftFoot: transformGhostZone(base.leftFoot, ghostScale, mirrored),
    rightFoot: transformGhostZone(base.rightFoot, ghostScale, mirrored),
  };

  const bodyBounds = transformGhostZone(base.bodyBounds, ghostScale, mirrored);
  const privacyLine = ghostPrivacyLineGeometry(view, ghostScale, mirrored);

  // Target vertical span: shoulder to foot distance scales with ghostScale
  const targetSpan = 0.75 * ghostScale;
  const expectedBodySpan = {
    min: targetSpan * 0.75, // allows slightly farther/shorter posture
    target: targetSpan,
    max: targetSpan * 1.25, // allows slightly closer/taller posture
  };

  let sideVisibleChain;
  if (view === "side") {
    sideVisibleChain = {
      shoulder: transformedZones.shoulders,
      hip: transformedZones.hips,
      knee: transformedZones.knees,
      ankle: transformedZones.ankles,
      foot: transformedZones.feet,
    };
  }

  return {
    view,
    sideProfile,
    ghostScale,
    mirrored,
    centerX: 0.5,
    bodyBounds,
    expectedBodySpan,
    zones: transformedZones,
    privacyLine,
    sideVisibleChain,
  };
}

export function isPointInZone(
  point: GhostPoint,
  zone: GhostZone,
  margin = 0,
): boolean {
  return (
    point.x >= zone.minX - margin
    && point.x <= zone.maxX + margin
    && point.y >= zone.minY - margin
    && point.y <= zone.maxY + margin
  );
}

export function pointZoneDistance(point: GhostPoint, zone: GhostZone): number {
  const dx = Math.max(0, zone.minX - point.x, point.x - zone.maxX);
  const dy = Math.max(0, zone.minY - point.y, point.y - zone.maxY);
  return Math.hypot(dx, dy);
}
