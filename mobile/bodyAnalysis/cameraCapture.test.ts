import { expect, it } from "vitest";

import {
  BODY_PHOTO_COUNTDOWN_SECONDS,
  advanceBodyPhotoCountdown,
  bodyPhotoCaptureErrorMessage,
  bodyPhotoMimeTypeForAsset,
  filePathToUri,
  type BodyPhotoCapturedAsset,
} from "./cameraCapture";

it("uses the five-second capture timer and cancels it safely", () => {
  expect(BODY_PHOTO_COUNTDOWN_SECONDS).toBe(5);
  expect(advanceBodyPhotoCountdown(5)).toBe(4);
  expect(advanceBodyPhotoCountdown(1)).toBe(0);
  expect(advanceBodyPhotoCountdown(0)).toBeNull();
  expect(advanceBodyPhotoCountdown(null)).toBeNull();
});

it("normalizes camera file paths without changing picker URIs", () => {
  expect(filePathToUri("/data/user/0/fitsho/cache/body.jpg")).toBe(
    "file:///data/user/0/fitsho/cache/body.jpg",
  );
  expect(filePathToUri("file:///data/user/0/fitsho/cache/body.jpg")).toBe(
    "file:///data/user/0/fitsho/cache/body.jpg",
  );
});

it("accepts supported image types from picker metadata or the URI extension", () => {
  expect(bodyPhotoMimeTypeForAsset("image/jpeg", "asset.bin")).toBe("image/jpeg");
  expect(bodyPhotoMimeTypeForAsset(null, "asset.PNG")).toBe("image/png");
  expect(bodyPhotoMimeTypeForAsset(undefined, "asset.webp?x=1")).toBe("image/webp");
  expect(bodyPhotoMimeTypeForAsset("image/gif", "asset.gif")).toBeNull();
});

it("accepts iOS HEIF sources only when the native iOS renderer will transcode them", () => {
  expect(bodyPhotoMimeTypeForAsset("image/heic", "asset.heic")).toBeNull();
  expect(bodyPhotoMimeTypeForAsset("image/heic", "asset.heic", { allowIosHeif: true })).toBe("image/heic");
  expect(bodyPhotoMimeTypeForAsset(undefined, "asset.HEIF", { allowIosHeif: true })).toBe("image/heif");
});

it("keeps capture failures user-safe and does not expose native details", () => {
  expect(bodyPhotoCaptureErrorMessage({ name: "NotAllowedError" })).toContain("دسترسی");
  expect(bodyPhotoCaptureErrorMessage(new Error("camera unavailable"))).toContain("دوربین");
  expect(bodyPhotoCaptureErrorMessage(new Error("native path /secret"))).not.toContain("/secret");
});

it("describes captured media without raw pixels", () => {
  const asset: BodyPhotoCapturedAsset = {
    height: 1280,
    mimeType: "image/jpeg",
    privacyCropApplied: true,
    source: "camera",
    uri: "file:///camera.jpg",
    width: 720,
  };

  expect(JSON.stringify(asset)).not.toMatch(/bytes|base64|pixels/i);
});
