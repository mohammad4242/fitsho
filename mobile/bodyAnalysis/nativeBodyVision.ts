import type {
  FiticianBodyVision,
  NativeBodyVisionResult,
} from "@fitician/body-vision";
import {
  validatePoseWithGhost,
  type GhostPoseValidationResult,
  type GhostPoseValidatorOptions,
  type NormalizedBodyLandmark,
} from "@fitician/core/body-ghost-pose";
import {
  normalizeBodySegmentationMask,
  type BodySegmentationMask,
} from "@fitician/core/body-photos";

export const BODY_VISION_SPIKE_CONTRACT_VERSION = "1.0";

export interface NormalizedBodyVisionResult {
  contractVersion: typeof BODY_VISION_SPIKE_CONTRACT_VERSION;
  landmarks: NormalizedBodyLandmark[][];
  mask: BodySegmentationMask;
  frame: { width: number; height: number; timestamp: number };
}

interface RawBodyVisionResult {
  landmarks: unknown;
  mask: unknown;
  frame: unknown;
}

type NativeBodyVisionValidationOptions = Omit<GhostPoseValidatorOptions, "poses">;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readFiniteNumber(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${label} must be finite`);
  }
  return value;
}

function readUnitNumber(value: unknown, label: string): number {
  const number = readFiniteNumber(value, label);
  if (number < 0 || number > 1) {
    throw new Error(`${label} must be between 0 and 1`);
  }
  return number;
}

function readPositiveInteger(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value <= 0) {
    throw new Error(`${label} must be a positive integer`);
  }
  return value;
}

export function normalizeBodyVisionResult(value: unknown): NormalizedBodyVisionResult {
  if (!isRecord(value)) {
    throw new Error("native body vision result must be an object");
  }

  const raw = value as unknown as RawBodyVisionResult;
  if (!Array.isArray(raw.landmarks)) {
    throw new Error("native landmarks must be an array");
  }

  const landmarks = raw.landmarks.map((pose, poseIndex) => {
    if (!Array.isArray(pose)) {
      throw new Error(`native landmarks[${poseIndex}] must be an array`);
    }
    return pose.map((landmark, landmarkIndex) => {
      if (!isRecord(landmark)) {
        throw new Error(`native landmark ${poseIndex}:${landmarkIndex} must be an object`);
      }
      return {
        x: readUnitNumber(landmark.x, "normalized landmark x"),
        y: readUnitNumber(landmark.y, "normalized landmark y"),
        z: readFiniteNumber(landmark.z, "normalized landmark z"),
        visibility: readUnitNumber(landmark.visibility, "landmark visibility"),
      };
    });
  });

  if (!isRecord(raw.mask)) {
    throw new Error("native mask must be an object");
  }
  const maskWidth = readPositiveInteger(raw.mask.width, "mask width");
  const maskHeight = readPositiveInteger(raw.mask.height, "mask height");
  const mask = normalizeBodySegmentationMask({
    width: maskWidth,
    height: maskHeight,
    values: raw.mask.values,
  });

  if (!isRecord(raw.frame)) {
    throw new Error("native frame metadata must be an object");
  }
  const frameWidth = readPositiveInteger(raw.frame.width, "frame width");
  const frameHeight = readPositiveInteger(raw.frame.height, "frame height");
  const timestamp = readFiniteNumber(raw.frame.timestamp, "frame timestamp");

  return {
    contractVersion: BODY_VISION_SPIKE_CONTRACT_VERSION,
    landmarks,
    mask,
    frame: { width: frameWidth, height: frameHeight, timestamp },
  };
}


export interface BodyVisionBenchmarkFrame {
  durationMs: number;
  result: { landmarkCount: number; maskWidth: number; maskHeight: number };
  dropped?: boolean;
}

export interface BodyVisionBenchmark {
  contractVersion: typeof BODY_VISION_SPIKE_CONTRACT_VERSION;
  frameCount: number;
  processedFrameCount: number;
  droppedFrameCount: number;
  averageFrameDurationMs: number;
  maxFrameDurationMs: number;
  landmarkCount: number;
  maskSize: { width: number; height: number };
  rawPixelsObserved: false;
}

export function createBodyVisionBenchmark(input: {
  frames: readonly BodyVisionBenchmarkFrame[];
}): BodyVisionBenchmark {
  const droppedFrameCount = input.frames.filter((frame) => frame.dropped === true).length;
  const processedFrames = input.frames.filter((frame) => frame.dropped !== true);
  const durations = processedFrames.map((frame) => {
    if (!Number.isFinite(frame.durationMs) || frame.durationMs < 0) {
      throw new Error("benchmark frame duration must be a non-negative number");
    }
    return frame.durationMs;
  });
  const firstResult = processedFrames[0]?.result;
  const totalDuration = durations.reduce((total, duration) => total + duration, 0);

  return {
    contractVersion: BODY_VISION_SPIKE_CONTRACT_VERSION,
    frameCount: input.frames.length,
    processedFrameCount: processedFrames.length,
    droppedFrameCount,
    averageFrameDurationMs:
      processedFrames.length === 0 ? 0 : totalDuration / processedFrames.length,
    maxFrameDurationMs: durations.length === 0 ? 0 : Math.max(...durations),
    landmarkCount: firstResult?.landmarkCount ?? 0,
    maskSize: {
      width: firstResult?.maskWidth ?? 0,
      height: firstResult?.maskHeight ?? 0,
    },
    rawPixelsObserved: false,
  };
}

interface NitroModulesLike {
  hasHybridObject(name: string): boolean;
  createHybridObject<T>(name: string): T;
}

function getNitroModules(): NitroModulesLike | null {
  try {
    // Nitro is only available in a rebuilt native Android binary. Keeping this
    // lookup lazy lets web/jsdom tests exercise the shared contract safely.
    const module = require("react-native-nitro-modules") as {
      NitroModules?: NitroModulesLike;
    };
    return module.NitroModules ?? null;
  } catch {
    return null;
  }
}

export function getNativeBodyVision(): FiticianBodyVision | null {
  const nitroModules = getNitroModules();
  if (nitroModules === null || !nitroModules.hasHybridObject("FiticianBodyVision")) {
    return null;
  }
  return nitroModules.createHybridObject<FiticianBodyVision>("FiticianBodyVision");
}

export function normalizeNativeBodyVisionResult(
  value: NativeBodyVisionResult,
): NormalizedBodyVisionResult {
  return normalizeBodyVisionResult(value);
}

export function validateNativeBodyVisionResult(
  value: NativeBodyVisionResult,
  options: NativeBodyVisionValidationOptions,
): { normalized: NormalizedBodyVisionResult; validation: GhostPoseValidationResult } {
  const normalized = normalizeNativeBodyVisionResult(value);
  const validation = validatePoseWithGhost({
    ...options,
    poses: normalized.landmarks,
    imageDimensions: options.imageDimensions ?? normalized.frame,
  });
  return { normalized, validation };
}
