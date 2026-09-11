import { useCallback, useMemo } from "react";
import {
  Camera,
  useFrameOutput,
  type CameraDevice,
  type CameraPhotoOutput,
} from "react-native-vision-camera";
import { scheduleOnRN } from "react-native-worklets";
import type { FiticianBodyVision, NativeBodyVisionResult } from "@fitician/body-vision";

import { StyleSheet } from "react-native";

type BodyVisionFrame = Parameters<
  NonNullable<Parameters<typeof useFrameOutput>[0]["onFrame"]>
>[0];

const LIVE_RESULT_INTERVAL_SECONDS = 0.15;

export interface NativeBodyVisionCameraProps {
  readonly device: CameraDevice;
  readonly isActive: boolean;
  readonly nativeVision: FiticianBodyVision;
  readonly onError: (error: unknown) => void;
  readonly onNativeError?: () => void;
  readonly onNativeResult: (result: NativeBodyVisionResult) => void;
  readonly onPreviewStarted: () => void;
  readonly onPreviewStopped: () => void;
  readonly photoOutput: CameraPhotoOutput;
}

/**
 * Camera session with the optional on-device Body Vision output.
 *
 * This component owns the frame-output hook so it is mounted only while the
 * camera screen is active. The library/editor flow never creates a worker
 * runtime, which keeps VisionCamera lifecycle handling deterministic.
 */
export function NativeBodyVisionCamera({
  device,
  isActive,
  nativeVision,
  onError,
  onNativeError,
  onNativeResult,
  onPreviewStarted,
  onPreviewStopped,
  photoOutput,
}: NativeBodyVisionCameraProps) {
  const dispatchState = useMemo(
    () => ({ lastResultTimestampSeconds: Number.NEGATIVE_INFINITY }),
    [],
  );

  const onFrame = useCallback((frame: BodyVisionFrame) => {
    "worklet";
    try {
      if (!isActive || nativeVision.modelStatus !== "ready") return;

      const result = nativeVision.process(frame);
      // VisionCamera exposes seconds on iOS and nanoseconds on Android. Keep
      // the RN callback bounded without changing the public native contract.
      const timestampSeconds = result.frame.timestamp > 1_000_000
        ? result.frame.timestamp / 1_000_000_000
        : result.frame.timestamp;
      const shouldDispatch = Number.isFinite(timestampSeconds)
        && (
          dispatchState.lastResultTimestampSeconds === Number.NEGATIVE_INFINITY
          || timestampSeconds < dispatchState.lastResultTimestampSeconds
          || timestampSeconds - dispatchState.lastResultTimestampSeconds >= LIVE_RESULT_INTERVAL_SECONDS
        );

      if (shouldDispatch) {
        dispatchState.lastResultTimestampSeconds = timestampSeconds;
        scheduleOnRN(onNativeResult, result);
      }
    } catch {
      if (onNativeError !== undefined) {
        try {
          scheduleOnRN(onNativeError);
        } catch {
          // The frame still must be released if the RN runtime is unavailable.
        }
      }
    } finally {
      frame.dispose();
    }
  }, [dispatchState, isActive, nativeVision, onNativeError, onNativeResult]);

  const onFrameDropped = useCallback(() => {
    "worklet";
    nativeVision.recordDroppedFrame();
  }, [nativeVision]);

  const frameOutput = useFrameOutput({
    allowDeferredStart: true,
    dropFramesWhileBusy: true,
    enablePhysicalBufferRotation: false,
    enablePreviewSizedOutputBuffers: true,
    onFrame,
    onFrameDropped,
    pixelFormat: "yuv",
    targetResolution: { height: 480, width: 320 },
  });
  const outputs = useMemo(() => [photoOutput, frameOutput], [frameOutput, photoOutput]);

  return (
    <Camera
      device={device}
      enableNativeTapToFocusGesture
      isActive={isActive}
      mirrorMode="off"
      onError={onError}
      onPreviewStarted={onPreviewStarted}
      onPreviewStopped={onPreviewStopped}
      orientationSource="device"
      outputs={outputs}
      style={StyleSheet.absoluteFill}
    />
  );
}
