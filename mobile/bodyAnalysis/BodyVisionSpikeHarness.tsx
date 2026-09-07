import { Camera, type CameraDevice, useFrameOutput } from "react-native-vision-camera";
import { StyleSheet } from "react-native";

import { getNativeBodyVision } from "./nativeBodyVision";

export interface BodyVisionSpikeHarnessProps {
  device: CameraDevice | undefined;
  isActive: boolean;
}

/**
 * Isolated developer harness for the Android native vision spike.
 * It is intentionally not routed into the member wizard until the spike is reviewed.
 */
export function BodyVisionSpikeHarness({
  device,
  isActive,
}: BodyVisionSpikeHarnessProps): React.ReactElement | null {
  const nativeVision = getNativeBodyVision();
  const frameOutput = useFrameOutput({
    targetResolution: { width: 320, height: 480 },
    pixelFormat: "yuv",
    enablePreviewSizedOutputBuffers: true,
    enablePhysicalBufferRotation: false,
    dropFramesWhileBusy: true,
    onFrame(frame) {
      "worklet";
      try {
        if (nativeVision !== null) {
          nativeVision.process(frame);
        }
      } finally {
        frame.dispose();
      }
    },
    onFrameDropped() {
      "worklet";
      nativeVision?.recordDroppedFrame();
    },
  });

  if (device === undefined || nativeVision === null || nativeVision.modelStatus !== "ready") {
    return null;
  }

  return (
    <Camera
      style={StyleSheet.absoluteFill}
      device={device}
      outputs={[frameOutput]}
      isActive={isActive}
      mirrorMode="off"
    />
  );
}
