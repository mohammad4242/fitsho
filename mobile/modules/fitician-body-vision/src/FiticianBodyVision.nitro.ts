import type { HybridObject } from "react-native-nitro-modules";
import type { Frame } from "react-native-vision-camera";

export interface NativeBodyLandmark {
  x: number;
  y: number;
  z: number;
  visibility: number;
}

export interface NativeBodyVisionMask {
  width: number;
  height: number;
  values: ArrayBuffer;
}

export interface NativeBodyVisionFrame {
  width: number;
  height: number;
  timestamp: number;
}

export interface NativeBodyVisionResult {
  landmarks: NativeBodyLandmark[][];
  mask: NativeBodyVisionMask;
  frame: NativeBodyVisionFrame;
}

export interface NativeBodyVisionBenchmark {
  frameCount: number;
  processedFrameCount: number;
  droppedFrameCount: number;
  averageFrameDurationMs: number;
  maxFrameDurationMs: number;
  modelStatus: string;
}

export interface FiticianBodyVision
  extends HybridObject<{
    android: "kotlin";
    ios: "swift";
  }> {
  readonly contractVersion: string;
  readonly modelStatus: string;
  process(frame: Frame): NativeBodyVisionResult;
  recordDroppedFrame(): void;
  benchmark(): NativeBodyVisionBenchmark;
}
