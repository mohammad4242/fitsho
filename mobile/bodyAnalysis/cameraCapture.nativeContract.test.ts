import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("keeps frame processing isolated from the upload-first and editor flows", async () => {
  const source = await readFile(resolve(import.meta.dirname, "BodyPhotoCapture.tsx"), "utf8");
  const visionCameraSource = await readFile(resolve(import.meta.dirname, "NativeBodyVisionCamera.tsx"), "utf8");
  const rendererSource = await readFile(resolve(import.meta.dirname, "nativeGhostPhotoRenderer.ts"), "utf8");

  expect(source).toMatch(/useCameraPermission/);
  expect(source).toMatch(/useCameraDevice/);
  expect(source).toMatch(/usePhotoOutput/);
  expect(source).toMatch(/capturePhotoToFile/);
  expect(source).toMatch(/NativeGhostPhotoEditor/);
  expect(source).toMatch(/NativeBodyVisionCamera/);
  expect(source).toMatch(/bodyPhotoUploadErrorMessage/);
  expect(source).toMatch(/deleteLocalFile\(rawUri\)/);
  expect(rendererSource).toMatch(/privacyCropApplied/);
  expect(source).not.toMatch(/useFrameOutput/);
  expect(source).not.toMatch(/scheduleOnRN/);
  expect(source).toMatch(/outputs=\{\[photoOutput\]\}/);
  expect(visionCameraSource).toMatch(/useFrameOutput/);
  expect(visionCameraSource).toMatch(/scheduleOnRN/);
  expect(visionCameraSource).toMatch(/frame\.dispose\(\)/);
  expect(visionCameraSource).toMatch(/outputs=\{outputs\}/);
  expect(visionCameraSource).not.toMatch(/getPixelBuffer|console\.|Log\./);
  expect(source).toMatch(/orientationSource="device"/);
  expect(source).toMatch(/mirrorMode="off"/);
  expect(source).toMatch(/containerFormat: "jpeg"/);
  expect(source).toMatch(/mediaTypes: \["images"\]/);
  expect(source).toMatch(/base64: false/);
  expect(source).toMatch(/exif: false/);
  expect(source).not.toMatch(/getPixelBuffer|console\.|Log\./);
});
