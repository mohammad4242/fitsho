import { ghostPrivacyCutRatioForView } from "./ghostPhotoEditor";
import { mediaPipePoseAssets } from "./mediaPipePoseDetector";
import type { BodyPhotoView } from "./types";
import type { NormalizedBodyLandmark } from "./processor";

export type LivePoseWarning =
  | "person_missing"
  | "multiple_people"
  | "body_out_of_frame"
  | "too_close"
  | "too_far"
  | "wrong_view"
  | "low_lighting"
  | "phone_orientation";

export type LivePoseGuidance = {
  status: "available" | "unavailable";
  warnings: LivePoseWarning[];
};

export type LivePoseLandmarkerResult = {
  landmarks: NormalizedBodyLandmark[][];
};

export type LivePoseLandmarker = {
  detectForVideo(
    source: CanvasImageSource,
    timestampMs: number,
  ): LivePoseLandmarkerResult;
  close?: () => void;
};

export type LivePoseLandmarkerLoader = () => Promise<LivePoseLandmarker>;

export type LivePoseAssets = {
  modelAssetPath: string;
  wasmBasePath: string;
};

export interface LivePoseGuide {
  check(video: HTMLVideoElement, timestampMs: number): LivePoseGuidance;
  close(): void;
}

export type LivePoseGuideFactory = (view: BodyPhotoView) => Promise<LivePoseGuide>;

const poseBoxIndices = [11, 12, 23, 24, 27, 28] as const;
const lowResolutionWidth = 256;

export class MediaPipeLivePoseGuide implements LivePoseGuide {
  private closed = false;
  private readonly view: BodyPhotoView;
  private readonly landmarker: LivePoseLandmarker;

  constructor(
    view: BodyPhotoView,
    landmarker: LivePoseLandmarker,
  ) {
    this.view = view;
    this.landmarker = landmarker;
  }

  check(video: HTMLVideoElement, timestampMs: number): LivePoseGuidance {
    if (this.closed) {
      return { status: "unavailable", warnings: [] };
    }
    try {
      const result = this.landmarker.detectForVideo(
        lowResolutionFrame(video),
        timestampMs,
      );
      return {
        status: "available",
        warnings: evaluateGuidance(result.landmarks, this.view, video),
      };
    } catch {
      return { status: "unavailable", warnings: [] };
    }
  }

  close() {
    if (this.closed) return;
    this.closed = true;
    this.landmarker.close?.();
  }
}

export function createMediaPipeLivePoseLandmarkerLoader(
  assets: LivePoseAssets = mediaPipePoseAssets,
  loadVision: () => Promise<MediaPipeVisionModule> = loadMediaPipeVision,
): LivePoseLandmarkerLoader {
  return async () => {
    const { FilesetResolver, PoseLandmarker } = await loadVision();
    const fileset = await FilesetResolver.forVisionTasks(assets.wasmBasePath);
    return PoseLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: assets.modelAssetPath },
      runningMode: "VIDEO",
      numPoses: 2,
      minPoseDetectionConfidence: 0.55,
      minPosePresenceConfidence: 0.55,
    });
  };
}

export function createMediaPipeLivePoseGuide(
  view: BodyPhotoView,
  loader: LivePoseLandmarkerLoader = createMediaPipeLivePoseLandmarkerLoader(),
): Promise<LivePoseGuide> {
  return loader().then((landmarker) => new MediaPipeLivePoseGuide(view, landmarker));
}

type MediaPipeVisionModule = {
  FilesetResolver: { forVisionTasks(basePath: string): Promise<unknown> };
  PoseLandmarker: {
    createFromOptions(
      fileset: unknown,
      options: Record<string, unknown>,
    ): Promise<LivePoseLandmarker>;
  };
};

async function loadMediaPipeVision(): Promise<MediaPipeVisionModule> {
  const vision = await import("@mediapipe/tasks-vision");
  return {
    FilesetResolver: vision.FilesetResolver,
    PoseLandmarker: {
      createFromOptions: async (fileset, options) => {
        const landmarker = await vision.PoseLandmarker.createFromOptions(
          fileset as never,
          options as never,
        );
        return {
          detectForVideo: (source, timestampMs) => landmarker.detectForVideo(
            source as never,
            timestampMs,
          ) as LivePoseLandmarkerResult,
          close: () => landmarker.close(),
        };
      },
    },
  };
}

function evaluateGuidance(
  poses: NormalizedBodyLandmark[][],
  view: BodyPhotoView,
  video: HTMLVideoElement,
): LivePoseWarning[] {
  const warnings: LivePoseWarning[] = [];
  const privacyCutRatio = ghostPrivacyCutRatioForView(view);
  if (poses.length === 0) warnings.push("person_missing");
  if (poses.length > 1) warnings.push("multiple_people");

  const landmarks = poses[0];
  if (landmarks !== undefined) {
    const points = poseBoxIndices
      .map((index) => landmarks[index])
      .filter((point): point is NormalizedBodyLandmark => point !== undefined);
    if (points.length !== poseBoxIndices.length || points.some((point) => point.visibility < 0.35)) {
      warnings.push("body_out_of_frame");
    } else {
      const top = Math.min(...points.map((point) => point.y));
      const bottom = Math.max(...points.map((point) => point.y));
      const left = Math.min(...points.map((point) => point.x));
      const right = Math.max(...points.map((point) => point.x));
      if (top <= privacyCutRatio || bottom >= 0.995 || left <= 0.02 || right >= 0.98) {
        warnings.push("body_out_of_frame");
      }
      const bodySpan = bottom - top;
      if (bodySpan > 0.86) warnings.push("too_close");
      if (bodySpan < 0.5) warnings.push("too_far");

      const shoulderSpan = Math.abs((landmarks[11]?.x ?? 0) - (landmarks[12]?.x ?? 0));
      if ((view === "side" && shoulderSpan > 0.25) || (view !== "side" && shoulderSpan < 0.1)) {
        warnings.push("wrong_view");
      }
    }
  }

  if (video.videoWidth > 0 && video.videoWidth >= video.videoHeight) {
    warnings.push("phone_orientation");
  }
  const brightness = estimateBrightness(video);
  if (brightness !== null && (brightness < 0.12 || brightness > 0.94)) {
    warnings.push("low_lighting");
  }
  return [...new Set(warnings)];
}

function lowResolutionFrame(video: HTMLVideoElement): CanvasImageSource {
  if (typeof document === "undefined" || video.videoWidth <= 0 || video.videoHeight <= 0) {
    return video;
  }
  const canvas = document.createElement("canvas");
  canvas.width = lowResolutionWidth;
  canvas.height = Math.max(1, Math.round(lowResolutionWidth * video.videoHeight / video.videoWidth));
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (context === null) return video;
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas;
}

function estimateBrightness(video: HTMLVideoElement): number | null {
  if (typeof document === "undefined" || video.videoWidth <= 0 || video.videoHeight <= 0) {
    return null;
  }
  try {
    const canvas = document.createElement("canvas");
    canvas.width = 32;
    canvas.height = 18;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (context === null) return null;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let total = 0;
    for (let index = 0; index < pixels.length; index += 4) {
      total += (0.2126 * pixels[index]! + 0.7152 * pixels[index + 1]! + 0.0722 * pixels[index + 2]!) / 255;
    }
    return total / (pixels.length / 4);
  } catch {
    return null;
  }
}
