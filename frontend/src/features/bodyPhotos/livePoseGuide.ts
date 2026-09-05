import { validatePoseWithGhost } from "./ghostPoseValidator";
import { mediaPipePoseAssets } from "./mediaPipePoseDetector";
import type { BodyPhotoSide, BodyPhotoView } from "./types";
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

export type LivePoseGuideOptions = {
  ghostScale?: number;
  sideProfile?: BodyPhotoSide;
};

export interface LivePoseGuide {
  check(
    video: HTMLVideoElement,
    timestampMs: number,
    options?: LivePoseGuideOptions,
  ): LivePoseGuidance;
  setGhostScale?(scale: number): void;
  setSideProfile?(profile: BodyPhotoSide): void;
  close(): void;
}

export type LivePoseGuideFactory = (
  view: BodyPhotoView,
  options?: LivePoseGuideOptions,
) => Promise<LivePoseGuide>;

const lowResolutionWidth = 256;

export class MediaPipeLivePoseGuide implements LivePoseGuide {
  private closed = false;
  private readonly view: BodyPhotoView;
  private sideProfile: BodyPhotoSide;
  private ghostScale: number;
  private readonly landmarker: LivePoseLandmarker;

  constructor(
    view: BodyPhotoView,
    landmarker: LivePoseLandmarker,
    options?: LivePoseGuideOptions,
  ) {
    this.view = view;
    this.landmarker = landmarker;
    this.sideProfile = options?.sideProfile ?? "right";
    this.ghostScale = options?.ghostScale ?? 1;
  }

  setGhostScale(scale: number) {
    this.ghostScale = scale;
  }

  setSideProfile(profile: BodyPhotoSide) {
    this.sideProfile = profile;
  }

  check(
    video: HTMLVideoElement,
    timestampMs: number,
    options?: LivePoseGuideOptions,
  ): LivePoseGuidance {
    if (this.closed) {
      return { status: "unavailable", warnings: [] };
    }
    try {
      const activeScale = options?.ghostScale ?? this.ghostScale;
      const activeProfile = options?.sideProfile ?? this.sideProfile;

      const result = this.landmarker.detectForVideo(
        lowResolutionFrame(video),
        timestampMs,
      );

      const warnings = evaluateLiveGuidance(
        result.landmarks,
        this.view,
        activeProfile,
        activeScale,
        video,
      );

      return {
        status: "available",
        warnings,
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
  options?: LivePoseGuideOptions,
): Promise<LivePoseGuide> {
  return loader().then((landmarker) => new MediaPipeLivePoseGuide(view, landmarker, options));
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

function evaluateLiveGuidance(
  poses: NormalizedBodyLandmark[][],
  view: BodyPhotoView,
  sideProfile: BodyPhotoSide,
  ghostScale: number,
  video: HTMLVideoElement,
): LivePoseWarning[] {
  const warnings: LivePoseWarning[] = [];

  // Run shared Ghost-based pose validator
  const validation = validatePoseWithGhost({
    view,
    sideProfile,
    ghostScale,
    poses,
  });

  // Map validator outcomes to user-facing live warnings
  if (validation.warnings.includes("person_missing") || validation.hardRejectCode === "body_not_detected") {
    warnings.push("person_missing");
  }
  if (validation.warnings.includes("multiple_people") || validation.hardRejectCode === "multiple_people_detected") {
    warnings.push("multiple_people");
  }
  if (validation.warnings.includes("body_out_of_frame") || validation.hardRejectCode === "body_out_of_frame") {
    warnings.push("body_out_of_frame");
  }
  if (validation.warnings.includes("too_close")) {
    warnings.push("too_close");
  }
  if (validation.warnings.includes("too_far")) {
    warnings.push("too_far");
  }
  if (validation.warnings.includes("wrong_view") || validation.hardRejectCode === "unexpected_body_view") {
    warnings.push("wrong_view");
  }

  // Device orientation check
  if (video.videoWidth > 0 && video.videoWidth >= video.videoHeight) {
    warnings.push("phone_orientation");
  }

  // Lighting check
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
