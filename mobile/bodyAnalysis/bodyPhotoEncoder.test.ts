import { expect, it, vi } from "vitest";

const { manipulateAsync } = vi.hoisted(() => ({ manipulateAsync: vi.fn() }));

vi.mock("expo-image-manipulator", () => ({
  SaveFormat: { JPEG: "jpeg" },
  manipulateAsync,
}));

import { encodeBodyPhotoWithPrivacyCrop } from "./bodyPhotoEncoder";
import { MobilePerformanceRecorder } from "../platform/performance";

it("encodes a JPEG from the protected crop boundary without base64", async () => {
  const performance = new MobilePerformanceRecorder(() => 0);
  manipulateAsync.mockResolvedValue({
    height: 2208,
    uri: "file:///cache/body-front-cropped.jpg",
    width: 1600,
  });

  await expect(encodeBodyPhotoWithPrivacyCrop({
    height: 2400,
    source: "camera",
    uri: "file:///cache/body-raw.jpg",
    width: 1600,
  }, { performanceRecorder: performance, view: "front" })).resolves.toEqual({
    height: 2208,
    mimeType: "image/jpeg",
    privacyCropApplied: true,
    source: "camera",
    uri: "file:///cache/body-front-cropped.jpg",
    width: 1600,
  });

  expect(manipulateAsync).toHaveBeenCalledWith(
    "file:///cache/body-raw.jpg",
    [{ crop: { height: 2208, originX: 0, originY: 192, width: 1600 } }],
    { base64: false, compress: 0.92, format: "jpeg" },
  );
  expect(performance.getSamples()).toEqual([
    {
      budget: 1_500,
      metric: "image_processing",
      passed: true,
      unit: "ms",
      value: 0,
    },
  ]);
});

it("rejects an encoded result that exposes pixels above the privacy line", async () => {
  manipulateAsync.mockResolvedValue({
    height: 2400,
    uri: "file:///cache/body-raw.jpg",
    width: 1600,
  });

  await expect(encodeBodyPhotoWithPrivacyCrop({
    height: 2400,
    source: "library",
    uri: "file:///photos/body.jpg",
    width: 1600,
  }, { view: "front" })).rejects.toThrow("privacy crop");
});
