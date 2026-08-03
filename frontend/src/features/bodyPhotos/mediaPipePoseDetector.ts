import type {
  BodyLandmarkDetection,
  BodyLandmarkDetector,
  DecodedBodyPhoto,
} from "./processor";
import type { BodyPhotoView } from "./types";

type Landmark = { x: number; y: number; visibility?: number };

export type PoseLandmarkerLike = {
  detect(image: CanvasImageSource): { landmarks: Landmark[][] };
};

type PoseLandmarkerLoader = () => Promise<PoseLandmarkerLike>;

const visibilityIndices = [0, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28];
const modelAssetPath = import.meta.env.VITE_BODY_PHOTO_POSE_MODEL_URL
  ?? "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task";
const wasmBasePath = import.meta.env.VITE_BODY_PHOTO_MEDIAPIPE_WASM_URL
  ?? "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.32/wasm";

/**
 * Real on-device landmark adapter. The model download contains only model assets;
 * the selected image stays in browser memory and is never sent to that URL.
 */
export class MediaPipePoseLandmarkDetector implements BodyLandmarkDetector {
  private loader: PoseLandmarkerLoader;
  private landmarkerPromise: Promise<PoseLandmarkerLike> | null = null;

  constructor(loader: PoseLandmarkerLoader = loadMediaPipeLandmarker) {
    this.loader = loader;
  }

  async detect(image: DecodedBodyPhoto, expectedView: BodyPhotoView): Promise<BodyLandmarkDetection> {
    const landmarker = await this.getLandmarker();
    const result = landmarker.detect(image.source);
    const poses = result.landmarks;
    if (poses.length !== 1) return rejectedDetection(poses.length);

    const landmarks = poses[0];
    const visibility = averageVisibility(landmarks);
    const leftShoulder = landmarks[11];
    const rightShoulder = landmarks[12];
    const nose = landmarks[0];
    const leftEar = landmarks[7];
    const rightEar = landmarks[8];
    if (!leftShoulder || !rightShoulder || !nose || !leftEar || !rightEar) {
      return incompleteDetection(expectedView, visibility);
    }

    const shoulderLineY = Math.min(leftShoulder.y, rightShoulder.y);
    const headBottomY = Math.max(nose.y, leftEar.y, rightEar.y);
    const safeHeadCropY = headBottomY + 0.02 < shoulderLineY - 0.012
      ? headBottomY + 0.02
      : null;
    const shoulderSpan = Math.abs(leftShoulder.x - rightShoulder.x);
    const detectedView = viewMatchesGeometry(expectedView, shoulderSpan)
      ? expectedView
      : "unknown";
    const completeness = bodyCompleteness(landmarks);
    // MediaPipe landmarks cannot diagnose clothing. Visibility and segmentation-aware
    // landmark confidence are used only as a conservative reliability proxy.
    const clothingVisibilityScore = Math.min(1, 0.35 + (visibility * 0.65));
    const poseScore = Math.min(1, (visibility + completeness) / 2);

    return {
      personCount: 1,
      detectedView,
      detectionConfidence: visibility,
      poseScore,
      bodyCompletenessScore: completeness,
      clothingVisibilityScore,
      backgroundReliabilityScore: completeness,
      isSafeAndRelevant: true,
      safeHeadCropY,
      shoulderLineY,
      headFullyExcluded: safeHeadCropY !== null,
      shouldersPreserved: safeHeadCropY !== null,
      headCropConfidence: safeHeadCropY === null ? 0 : Math.min(1, visibility),
      warnings: ["clothing_visibility_landmark_proxy"],
    };
  }

  private getLandmarker(): Promise<PoseLandmarkerLike> {
    if (this.landmarkerPromise === null) {
      this.landmarkerPromise = this.loader().catch((error: unknown) => {
        this.landmarkerPromise = null;
        throw error;
      });
    }
    return this.landmarkerPromise;
  }
}

async function loadMediaPipeLandmarker(): Promise<PoseLandmarkerLike> {
  const { FilesetResolver, PoseLandmarker } = await import("@mediapipe/tasks-vision");
  const fileset = await FilesetResolver.forVisionTasks(wasmBasePath);
  const poseLandmarker = await PoseLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath },
    runningMode: "IMAGE",
    numPoses: 2,
    minPoseDetectionConfidence: 0.7,
    minPosePresenceConfidence: 0.7,
    minTrackingConfidence: 0.7,
    outputSegmentationMasks: true,
  });
  return {
    detect: (image) => poseLandmarker.detect(image as never) as { landmarks: Landmark[][] },
  };
}

function rejectedDetection(personCount: number): BodyLandmarkDetection {
  return {
    personCount,
    detectedView: "unknown",
    detectionConfidence: 0,
    poseScore: 0,
    bodyCompletenessScore: 0,
    clothingVisibilityScore: 0,
    backgroundReliabilityScore: 0,
    isSafeAndRelevant: false,
    safeHeadCropY: null,
    shoulderLineY: null,
    headFullyExcluded: false,
    shouldersPreserved: false,
    headCropConfidence: 0,
    warnings: ["no_single_body_detected"],
  };
}

function incompleteDetection(view: BodyPhotoView, visibility: number): BodyLandmarkDetection {
  return {
    personCount: 1,
    detectedView: view,
    detectionConfidence: visibility,
    poseScore: visibility,
    bodyCompletenessScore: 0,
    clothingVisibilityScore: 0,
    backgroundReliabilityScore: 0,
    isSafeAndRelevant: true,
    safeHeadCropY: null,
    shoulderLineY: null,
    headFullyExcluded: false,
    shouldersPreserved: false,
    headCropConfidence: 0,
    warnings: ["required_landmarks_missing"],
  };
}

function averageVisibility(landmarks: Landmark[]): number {
  const visible = visibilityIndices
    .map((index) => landmarks[index]?.visibility ?? 0)
    .filter((score) => Number.isFinite(score));
  if (visible.length === 0) return 0;
  return visible.reduce((total, score) => total + score, 0) / visible.length;
}

function bodyCompleteness(landmarks: Landmark[]): number {
  const required = [11, 12, 23, 24, 25, 26, 27, 28];
  const scores = required.map((index) => landmarks[index]?.visibility ?? 0);
  return scores.reduce((total, score) => total + score, 0) / scores.length;
}

function viewMatchesGeometry(expectedView: BodyPhotoView, shoulderSpan: number): boolean {
  if (expectedView === "side") return shoulderSpan <= 0.2;
  return shoulderSpan >= 0.12;
}
