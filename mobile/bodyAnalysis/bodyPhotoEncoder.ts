import { manipulateAsync, SaveFormat } from "expo-image-manipulator";

import type { BodyPhotoCaptureSource, BodyPhotoCapturedAsset } from "./cameraCapture";
import {
  createBodyPhotoCropAction,
  validateEncodedBodyPhoto,
  type BodyPhotoPrivacyCropRequest,
} from "./privacyCropEncoder";
import {
  mobilePerformanceRecorder,
  type MobilePerformanceRecorder,
} from "../platform/performance";

export type BodyPhotoEncoderSource = {
  readonly height: number;
  readonly source: BodyPhotoCaptureSource;
  readonly uri: string;
  readonly width: number;
};

export type BodyPhotoEncoderOptions = Omit<BodyPhotoPrivacyCropRequest, "sourceSize"> & {
  readonly performanceRecorder?: MobilePerformanceRecorder;
};

export async function encodeBodyPhotoWithPrivacyCrop(
  source: BodyPhotoEncoderSource,
  options: BodyPhotoEncoderOptions,
): Promise<BodyPhotoCapturedAsset> {
  const {
    performanceRecorder = mobilePerformanceRecorder,
    ...cropOptions
  } = options;
  const cropRequest: BodyPhotoPrivacyCropRequest = {
    ...cropOptions,
    sourceSize: { height: source.height, width: source.width },
  };
  const result = await performanceRecorder.measureAsync(
    "image_processing",
    () => manipulateAsync(
      source.uri,
      [createBodyPhotoCropAction(cropRequest)],
      { base64: false, compress: 0.92, format: SaveFormat.JPEG },
    ),
  );
  const encoded = validateEncodedBodyPhoto({
    height: result.height,
    mimeType: "image/jpeg",
    uri: result.uri,
    width: result.width,
  }, cropRequest);
  return {
    height: encoded.height,
    mimeType: "image/jpeg",
    privacyCropApplied: true,
    source: source.source,
    uri: encoded.uri,
    width: encoded.width,
  };
}
