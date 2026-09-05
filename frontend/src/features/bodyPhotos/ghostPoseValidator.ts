import {
  getGhostGeometry,
  pointZoneDistance,
  type GhostViewGeometry,
  type GhostZone,
} from "./ghostGeometry";
import type { BodyPhotoSide, BodyPhotoView } from "./types";
import type { NormalizedBodyLandmark } from "./processor";

export type GhostValidationWarning =
  | "person_missing"
  | "multiple_people"
  | "body_out_of_frame"
  | "too_close"
  | "too_far"
  | "wrong_view"
  | "minor_landmark_weakness"
  | "near_boundary_landmarks"
  | "view_ambiguous";

export type GhostValidationHardRejectCode =
  | "body_not_detected"
  | "multiple_people_detected"
  | "body_out_of_frame"
  | "unexpected_body_view"
  | "shoulders_not_visible"
  | "torso_not_visible"
  | "legs_or_feet_not_visible";

export type GhostValidationComponentScores = {
  personDetection: number;
  bodyBounds: number;
  centering: number;
  scaleFit: number;
  zoneAlignment: number;
  viewConsistency: number;
  lowerBodyCompletion: number;
  overallUsability: number;
};

export type GhostPoseValidationResult = {
  status: "pass" | "warn" | "fail";
  overallScore: number;
  componentScores: GhostValidationComponentScores;
  warnings: GhostValidationWarning[];
  hardRejectCode: GhostValidationHardRejectCode | null;
  viewAssessment: "matched" | "ambiguous";
  visibleLandmarks: Array<"shoulders" | "arms" | "hips" | "knees" | "ankles" | "feet">;
  minimumVisibility: number;
  primaryPose: NormalizedBodyLandmark[] | null;
  metrics: {
    bodySpan: number;
    expectedSpan: number;
    shoulderSpan: number;
    hipSpan: number;
    centerOffsetX: number;
    boundaryOverflow: number;
  };
};

export type GhostPoseValidatorOptions = {
  view: BodyPhotoView;
  sideProfile?: BodyPhotoSide;
  ghostScale?: number;
  poses: NormalizedBodyLandmark[][];
  imageDimensions?: { width: number; height: number };
};

const LANDMARK_INDICES = {
  leftShoulder: 11,
  rightShoulder: 12,
  leftElbow: 13,
  rightElbow: 14,
  leftWrist: 15,
  rightWrist: 16,
  leftHip: 23,
  rightHip: 24,
  leftKnee: 25,
  rightKnee: 26,
  leftAnkle: 27,
  rightAnkle: 28,
  leftHeel: 29,
  rightHeel: 30,
  leftFoot: 31,
  rightFoot: 32,
} as const;

const MIN_LANDMARK_VISIBILITY = 0.35;
const HIGH_LANDMARK_VISIBILITY = 0.60;

export function validatePoseWithGhost(
  options: GhostPoseValidatorOptions,
): GhostPoseValidationResult {
  const { view, poses } = options;
  const sideProfile = options.sideProfile ?? "right";
  const ghostScale = options.ghostScale ?? 1;

  const geometry = getGhostGeometry({ view, sideProfile, ghostScale });
  const warnings: GhostValidationWarning[] = [];

  if (!poses || poses.length === 0) {
    return failResult("body_not_detected", ["person_missing"], geometry);
  }

  const primaryPose = selectPrimaryPose(poses);
  if (!primaryPose) {
    return failResult("body_not_detected", ["person_missing"], geometry);
  }

  if (hasSecondaryCrediblePerson(poses, primaryPose)) {
    warnings.push("multiple_people");
    return failResult("multiple_people_detected", warnings, geometry, primaryPose);
  }

  // Evaluate visible landmark groups
  const shoulderVisLeft = primaryPose[LANDMARK_INDICES.leftShoulder]?.visibility ?? 0;
  const shoulderVisRight = primaryPose[LANDMARK_INDICES.rightShoulder]?.visibility ?? 0;
  const hipVisLeft = primaryPose[LANDMARK_INDICES.leftHip]?.visibility ?? 0;
  const hipVisRight = primaryPose[LANDMARK_INDICES.rightHip]?.visibility ?? 0;
  const kneeVisLeft = primaryPose[LANDMARK_INDICES.leftKnee]?.visibility ?? 0;
  const kneeVisRight = primaryPose[LANDMARK_INDICES.rightKnee]?.visibility ?? 0;
  const ankleVisLeft = primaryPose[LANDMARK_INDICES.leftAnkle]?.visibility ?? 0;
  const ankleVisRight = primaryPose[LANDMARK_INDICES.rightAnkle]?.visibility ?? 0;
  const footVisLeft = primaryPose[LANDMARK_INDICES.leftFoot]?.visibility ?? 0;
  const footVisRight = primaryPose[LANDMARK_INDICES.rightFoot]?.visibility ?? 0;

  const maxShoulderVis = Math.max(shoulderVisLeft, shoulderVisRight);
  const minShoulderVis = Math.min(shoulderVisLeft, shoulderVisRight);
  const maxHipVis = Math.max(hipVisLeft, hipVisRight);
  const minHipVis = Math.min(hipVisLeft, hipVisRight);
  const maxKneeVis = Math.max(kneeVisLeft, kneeVisRight);
  const maxAnkleVis = Math.max(ankleVisLeft, ankleVisRight);
  const maxFootVis = Math.max(footVisLeft, footVisRight);

  // Critical landmark visibility checks
  if (maxShoulderVis < MIN_LANDMARK_VISIBILITY) {
    return failResult("shoulders_not_visible", ["body_out_of_frame"], geometry, primaryPose);
  }
  if (maxHipVis < MIN_LANDMARK_VISIBILITY) {
    return failResult("torso_not_visible", ["body_out_of_frame"], geometry, primaryPose);
  }

  // Both knees missing or both feet missing means legs/feet not visible
  if (maxKneeVis < MIN_LANDMARK_VISIBILITY || maxFootVis < MIN_LANDMARK_VISIBILITY) {
    return failResult("legs_or_feet_not_visible", ["body_out_of_frame"], geometry, primaryPose);
  }

  // Upright orientation check: shoulders must be above hips, and hips above ankles
  const validShoulderY = [primaryPose[LANDMARK_INDICES.leftShoulder]?.y, primaryPose[LANDMARK_INDICES.rightShoulder]?.y]
    .filter((y): y is number => y !== undefined);
  const validHipY = [primaryPose[LANDMARK_INDICES.leftHip]?.y, primaryPose[LANDMARK_INDICES.rightHip]?.y]
    .filter((y): y is number => y !== undefined);
  const validAnkleY = [primaryPose[LANDMARK_INDICES.leftAnkle]?.y, primaryPose[LANDMARK_INDICES.rightAnkle]?.y]
    .filter((y): y is number => y !== undefined);

  if (validShoulderY.length > 0 && validHipY.length > 0 && validAnkleY.length > 0) {
    const avgShoulderY = validShoulderY.reduce((a, b) => a + b, 0) / validShoulderY.length;
    const avgHipY = validHipY.reduce((a, b) => a + b, 0) / validHipY.length;
    const avgAnkleY = validAnkleY.reduce((a, b) => a + b, 0) / validAnkleY.length;
    if (avgShoulderY >= avgHipY || avgHipY >= avgAnkleY) {
      return failResult("unexpected_body_view", ["wrong_view"], geometry, primaryPose);
    }
  }

  // Evaluate boundaries and out of frame
  const relevantIndices = [
    LANDMARK_INDICES.leftShoulder, LANDMARK_INDICES.rightShoulder,
    LANDMARK_INDICES.leftHip, LANDMARK_INDICES.rightHip,
    LANDMARK_INDICES.leftKnee, LANDMARK_INDICES.rightKnee,
    LANDMARK_INDICES.leftAnkle, LANDMARK_INDICES.rightAnkle,
    LANDMARK_INDICES.leftFoot, LANDMARK_INDICES.rightFoot,
  ];

  let maxOverflow = 0;
  let hasNearBoundary = false;
  let severeOutOfFrame = false;

  for (const idx of relevantIndices) {
    const pt = primaryPose[idx];
    if (!pt || pt.visibility < MIN_LANDMARK_VISIBILITY) continue;

    // Check overflow beyond [0, 1]
    const overflowX = Math.max(0, -pt.x, pt.x - 1);
    const overflowY = Math.max(0, -pt.y, pt.y - 1);
    const overflow = Math.max(overflowX, overflowY);

    if (overflow > maxOverflow) {
      maxOverflow = overflow;
    }

    // Upper body (torso/shoulders) has tighter edge tolerance than feet/ankles
    const isCoreLandmark = idx === LANDMARK_INDICES.leftShoulder
      || idx === LANDMARK_INDICES.rightShoulder
      || idx === LANDMARK_INDICES.leftHip
      || idx === LANDMARK_INDICES.rightHip;
    const overflowLimit = isCoreLandmark ? 0.015 : 0.035;

    if (overflow > overflowLimit) {
      severeOutOfFrame = true;
    } else if (overflow > 0) {
      // Within epsilon tolerance margin (e.g. 1.001)
      hasNearBoundary = true;
    } else if (pt.x < 0.02 || pt.x > 0.98 || pt.y > 0.98) {
      hasNearBoundary = true;
    }
  }

  if (severeOutOfFrame) {
    return failResult("body_out_of_frame", ["body_out_of_frame"], geometry, primaryPose);
  }
  if (hasNearBoundary) {
    warnings.push("near_boundary_landmarks");
  }

  // Calculate body dimensions and span
  const visiblePoints = relevantIndices
    .map((idx) => primaryPose[idx])
    .filter((pt): pt is NormalizedBodyLandmark => pt !== undefined && pt.visibility >= MIN_LANDMARK_VISIBILITY);

  const minY = Math.min(...visiblePoints.map((p) => p.y));
  const maxY = Math.max(...visiblePoints.map((p) => p.y));
  const minX = Math.min(...visiblePoints.map((p) => p.x));
  const maxX = Math.max(...visiblePoints.map((p) => p.x));
  const bodySpan = Math.max(0, maxY - minY);
  const centerOffsetX = Math.abs((minX + maxX) / 2 - geometry.centerX);

  // Body span checks
  if (bodySpan > 0.95) {
    warnings.push("too_close");
  } else if (bodySpan < geometry.expectedBodySpan.min * 0.75) {
    warnings.push("too_far");
  }

  // View consistency
  const leftShoulderVis = primaryPose[LANDMARK_INDICES.leftShoulder]?.visibility ?? 0;
  const rightShoulderVis = primaryPose[LANDMARK_INDICES.rightShoulder]?.visibility ?? 0;
  const leftHipVis = primaryPose[LANDMARK_INDICES.leftHip]?.visibility ?? 0;
  const rightHipVis = primaryPose[LANDMARK_INDICES.rightHip]?.visibility ?? 0;

  const bothShouldersVisible = leftShoulderVis >= MIN_LANDMARK_VISIBILITY && rightShoulderVis >= MIN_LANDMARK_VISIBILITY;
  const bothHipsVisible = leftHipVis >= MIN_LANDMARK_VISIBILITY && rightHipVis >= MIN_LANDMARK_VISIBILITY;

  const shoulderSpan = bothShouldersVisible
    ? Math.abs(
        (primaryPose[LANDMARK_INDICES.leftShoulder]?.x ?? 0) - (primaryPose[LANDMARK_INDICES.rightShoulder]?.x ?? 0),
      )
    : 0.04;
  const hipSpan = bothHipsVisible
    ? Math.abs(
        (primaryPose[LANDMARK_INDICES.leftHip]?.x ?? 0) - (primaryPose[LANDMARK_INDICES.rightHip]?.x ?? 0),
      )
    : 0.04;

  let viewAssessment: "matched" | "ambiguous" = view === "side" ? "matched" : "ambiguous";
  let viewConsistencyScore = 1.0;

  if (view === "side") {
    // If requested side view, reject only if user is clearly standing front-on with both sides visible
    const isObviousFront = bothShouldersVisible
      && bothHipsVisible
      && shoulderSpan >= 0.20 * ghostScale
      && hipSpan >= 0.12 * ghostScale;
    if (isObviousFront) {
      warnings.push("wrong_view");
      return failResult("unexpected_body_view", warnings, geometry, primaryPose);
    }
    if (shoulderSpan > 0.14 * ghostScale) {
      viewAssessment = "ambiguous";
      viewConsistencyScore = 0.8;
      warnings.push("view_ambiguous");
    }
  } else {
    // Requested front or back view
    // Reject only if user is clearly standing completely sideways
    const isObviousSide = (!bothShouldersVisible || shoulderSpan < 0.06 * ghostScale)
      && (!bothHipsVisible || hipSpan < 0.06 * ghostScale);
    if (isObviousSide) {
      warnings.push("wrong_view");
      return failResult("unexpected_body_view", warnings, geometry, primaryPose);
    }
    if (shoulderSpan < 0.12 * ghostScale) {
      viewConsistencyScore = 0.8;
      warnings.push("view_ambiguous");
    }
  }

  // Zone alignment scoring
  let zoneScoreSum = 0;
  let zoneCount = 0;

  function evaluateZone(pt: NormalizedBodyLandmark | undefined, zone: GhostZone) {
    if (!pt || pt.visibility < MIN_LANDMARK_VISIBILITY) return;
    zoneCount++;
    const dist = pointZoneDistance(pt, zone);
    if (dist <= 0) {
      zoneScoreSum += 1.0;
    } else {
      zoneScoreSum += Math.max(0, 1.0 - dist * 4);
    }
  }

  if (view === "side") {
    evaluateZone(primaryPose[LANDMARK_INDICES.leftShoulder], geometry.zones.shoulders);
    evaluateZone(primaryPose[LANDMARK_INDICES.rightShoulder], geometry.zones.shoulders);
    evaluateZone(primaryPose[LANDMARK_INDICES.leftHip], geometry.zones.hips);
    evaluateZone(primaryPose[LANDMARK_INDICES.rightHip], geometry.zones.hips);
    evaluateZone(primaryPose[LANDMARK_INDICES.leftKnee], geometry.zones.knees);
    evaluateZone(primaryPose[LANDMARK_INDICES.rightKnee], geometry.zones.knees);
    evaluateZone(primaryPose[LANDMARK_INDICES.leftAnkle], geometry.zones.ankles);
    evaluateZone(primaryPose[LANDMARK_INDICES.rightAnkle], geometry.zones.ankles);
  } else {
    evaluateZone(primaryPose[LANDMARK_INDICES.leftShoulder], geometry.zones.leftShoulder);
    evaluateZone(primaryPose[LANDMARK_INDICES.rightShoulder], geometry.zones.rightShoulder);
    evaluateZone(primaryPose[LANDMARK_INDICES.leftHip], geometry.zones.leftHip);
    evaluateZone(primaryPose[LANDMARK_INDICES.rightHip], geometry.zones.rightHip);
    evaluateZone(primaryPose[LANDMARK_INDICES.leftKnee], geometry.zones.leftKnee);
    evaluateZone(primaryPose[LANDMARK_INDICES.rightKnee], geometry.zones.rightKnee);
    evaluateZone(primaryPose[LANDMARK_INDICES.leftAnkle], geometry.zones.leftAnkle);
    evaluateZone(primaryPose[LANDMARK_INDICES.rightAnkle], geometry.zones.rightAnkle);
  }

  const zoneAlignmentScore = zoneCount > 0 ? zoneScoreSum / zoneCount : 0.8;

  // Component scores
  const personDetectionScore = 1.0;
  const bodyBoundsScore = Math.max(0, 1.0 - maxOverflow * 5);
  const centeringScore = Math.max(0, 1.0 - centerOffsetX * 3.5);
  const targetSpan = geometry.expectedBodySpan.target;
  const scaleFitScore = Math.max(0, 1.0 - Math.abs(bodySpan - targetSpan) / targetSpan);

  // Lower body completion score: allow one weak foot landmark without hard penalty
  const lowerGroupVis = [maxKneeVis, maxAnkleVis, maxFootVis];
  const avgLowerVis = lowerGroupVis.reduce((a, b) => a + b, 0) / lowerGroupVis.length;
  const lowerBodyCompletionScore = Math.min(1.0, avgLowerVis * 1.2);

  // Check for minor landmark weakness
  if (
    minShoulderVis < MIN_LANDMARK_VISIBILITY
    || minHipVis < MIN_LANDMARK_VISIBILITY
    || (view !== "side" && (footVisLeft < MIN_LANDMARK_VISIBILITY || footVisRight < MIN_LANDMARK_VISIBILITY))
  ) {
    warnings.push("minor_landmark_weakness");
  }

  // Visible landmark groups
  const visibleLandmarks = determineVisibleLandmarks(primaryPose);

  // Overall score calculation
  const overallScore = Number((
    personDetectionScore * 0.15
    + bodyBoundsScore * 0.15
    + centeringScore * 0.15
    + scaleFitScore * 0.15
    + zoneAlignmentScore * 0.15
    + viewConsistencyScore * 0.15
    + lowerBodyCompletionScore * 0.10
  ).toFixed(3));

  const componentScores: GhostValidationComponentScores = {
    personDetection: Number(personDetectionScore.toFixed(3)),
    bodyBounds: Number(bodyBoundsScore.toFixed(3)),
    centering: Number(centeringScore.toFixed(3)),
    scaleFit: Number(scaleFitScore.toFixed(3)),
    zoneAlignment: Number(zoneAlignmentScore.toFixed(3)),
    viewConsistency: Number(viewConsistencyScore.toFixed(3)),
    lowerBodyCompletion: Number(lowerBodyCompletionScore.toFixed(3)),
    overallUsability: overallScore,
  };

  const minimumVisibility = calculateMinimumVisibility(primaryPose, view);

  // Pass vs Warn vs Fail status determination
  let status: "pass" | "warn" | "fail" = "pass";
  if (warnings.length > 0 || overallScore < 0.80) {
    status = overallScore >= 0.55 ? "warn" : "fail";
  }

  return {
    status,
    overallScore,
    componentScores,
    warnings: [...new Set(warnings)],
    hardRejectCode: null,
    viewAssessment,
    visibleLandmarks,
    minimumVisibility,
    primaryPose,
    metrics: {
      bodySpan,
      expectedSpan: targetSpan,
      shoulderSpan,
      hipSpan,
      centerOffsetX,
      boundaryOverflow: maxOverflow,
    },
  };
}

function selectPrimaryPose(poses: NormalizedBodyLandmark[][]): NormalizedBodyLandmark[] | null {
  const valid = poses.filter((p) => p.length >= 33);
  if (valid.length === 0) return null;
  return valid[0] ?? null;
}

function hasSecondaryCrediblePerson(
  poses: NormalizedBodyLandmark[][],
  primary: NormalizedBodyLandmark[],
): boolean {
  if (poses.length <= 1) return false;
  const primaryCenter = poseCenterX(primary);
  for (let i = 1; i < poses.length; i++) {
    const candidate = poses[i];
    if (!candidate || candidate.length < 33) continue;
    const candidateCenter = poseCenterX(candidate);
    const separation = Math.abs(candidateCenter - primaryCenter);
    const visCount = candidate.filter((pt) => pt.visibility >= MIN_LANDMARK_VISIBILITY).length;
    // Distinct person separated horizontally with sufficient visible landmarks
    if (separation > 0.20 && visCount >= 10) {
      return true;
    }
  }
  return false;
}

function poseCenterX(landmarks: NormalizedBodyLandmark[]): number {
  const pts = [
    landmarks[LANDMARK_INDICES.leftShoulder],
    landmarks[LANDMARK_INDICES.rightShoulder],
    landmarks[LANDMARK_INDICES.leftHip],
    landmarks[LANDMARK_INDICES.rightHip],
  ].filter((p): p is NormalizedBodyLandmark => p !== undefined && p.visibility >= 0.2);

  if (pts.length === 0) return 0.5;
  return pts.reduce((sum, p) => sum + p.x, 0) / pts.length;
}

function determineVisibleLandmarks(
  pose: NormalizedBodyLandmark[],
): Array<"shoulders" | "arms" | "hips" | "knees" | "ankles" | "feet"> {
  const list: Array<"shoulders" | "arms" | "hips" | "knees" | "ankles" | "feet"> = [];
  const vis = (indices: readonly number[]) => Math.max(...indices.map((idx) => pose[idx]?.visibility ?? 0));

  if (vis([LANDMARK_INDICES.leftShoulder, LANDMARK_INDICES.rightShoulder]) >= MIN_LANDMARK_VISIBILITY) {
    list.push("shoulders");
  }
  if (vis([LANDMARK_INDICES.leftElbow, LANDMARK_INDICES.rightElbow, LANDMARK_INDICES.leftWrist, LANDMARK_INDICES.rightWrist]) >= MIN_LANDMARK_VISIBILITY) {
    list.push("arms");
  }
  if (vis([LANDMARK_INDICES.leftHip, LANDMARK_INDICES.rightHip]) >= MIN_LANDMARK_VISIBILITY) {
    list.push("hips");
  }
  if (vis([LANDMARK_INDICES.leftKnee, LANDMARK_INDICES.rightKnee]) >= MIN_LANDMARK_VISIBILITY) {
    list.push("knees");
  }
  if (vis([LANDMARK_INDICES.leftAnkle, LANDMARK_INDICES.rightAnkle]) >= MIN_LANDMARK_VISIBILITY) {
    list.push("ankles");
  }
  if (vis([LANDMARK_INDICES.leftFoot, LANDMARK_INDICES.rightFoot]) >= MIN_LANDMARK_VISIBILITY) {
    list.push("feet");
  }
  return list;
}

function calculateMinimumVisibility(
  pose: NormalizedBodyLandmark[],
  view: BodyPhotoView,
): number {
  const pairMin = (idx1: number, idx2: number) => {
    if (view === "side") {
      // In side view, far side might be occluded, so take the max of the pair
      return Math.max(pose[idx1]?.visibility ?? 0, pose[idx2]?.visibility ?? 0);
    }
    // In front/back view, allow one weak lower landmark
    const v1 = pose[idx1]?.visibility ?? 0;
    const v2 = pose[idx2]?.visibility ?? 0;
    return Math.max(v1, v2) >= HIGH_LANDMARK_VISIBILITY ? Math.max(v1, v2) * 0.8 : Math.min(v1, v2);
  };

  const scores = [
    pairMin(LANDMARK_INDICES.leftShoulder, LANDMARK_INDICES.rightShoulder),
    pairMin(LANDMARK_INDICES.leftHip, LANDMARK_INDICES.rightHip),
    pairMin(LANDMARK_INDICES.leftKnee, LANDMARK_INDICES.rightKnee),
    pairMin(LANDMARK_INDICES.leftAnkle, LANDMARK_INDICES.rightAnkle),
    pairMin(LANDMARK_INDICES.leftFoot, LANDMARK_INDICES.rightFoot),
  ];

  return Number(Math.min(...scores).toFixed(4));
}

function failResult(
  code: GhostValidationHardRejectCode,
  warnings: GhostValidationWarning[],
  geometry: GhostViewGeometry,
  primaryPose: NormalizedBodyLandmark[] | null = null,
): GhostPoseValidationResult {
  return {
    status: "fail",
    overallScore: 0,
    componentScores: {
      personDetection: code === "body_not_detected" || code === "multiple_people_detected" ? 0 : 1,
      bodyBounds: code === "body_out_of_frame" ? 0 : 0.5,
      centering: 0.5,
      scaleFit: 0.5,
      zoneAlignment: 0.5,
      viewConsistency: code === "unexpected_body_view" ? 0 : 0.5,
      lowerBodyCompletion: code === "legs_or_feet_not_visible" ? 0 : 0.5,
      overallUsability: 0,
    },
    warnings,
    hardRejectCode: code,
    viewAssessment: "ambiguous",
    visibleLandmarks: primaryPose ? determineVisibleLandmarks(primaryPose) : [],
    minimumVisibility: 0,
    primaryPose,
    metrics: {
      bodySpan: 0,
      expectedSpan: geometry.expectedBodySpan.target,
      shoulderSpan: 0,
      hipSpan: 0,
      centerOffsetX: 0,
      boundaryOverflow: code === "body_out_of_frame" ? 0.2 : 0,
    },
  };
}
