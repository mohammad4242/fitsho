import { manipulateAsync, SaveFormat } from "expo-image-manipulator";

import type { BodyPhotoCaptureSource, BodyPhotoCapturedAsset } from "./cameraCapture";
import {
  createBodyPhotoCropAction,
  validateEncodedBodyPhoto,
  type BodyPhotoPrivacyCropRequest,
} from "./privacyCropEncoder";

export type BodyPhotoEncoderSource = {
  readonly height: number;
  readonly source: BodyPhotoCaptureSource;
  readonly uri: string;
  readonly width: number;
};

export type BodyPhotoEncoderOptions = Omit<BodyPhotoPrivacyCropRequest, "sourceSize">;

export async function encodeBodyPhotoWithPrivacyCrop(
  source: BodyPhotoEncoderSource,
  options: BodyPhotoEncoderOptions,
): Promise<BodyPhotoCapturedAsset> {
  const cropRequest: BodyPhotoPrivacyCropRequest = {
    ...options,
    sourceSize: { height: source.height, width: source.width },
  };
  const result = await manipulateAsync(
    source.uri,
    [createBodyPhotoCropAction(cropRequest)],
    { base64: false, compress: 0.92, format: SaveFormat.JPEG },
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
