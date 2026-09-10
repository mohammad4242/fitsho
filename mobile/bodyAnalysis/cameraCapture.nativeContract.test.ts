import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("uses photo capture without mounting the crashing live frame processor", async () => {
  const source = await readFile(resolve(import.meta.dirname, "BodyPhotoCapture.tsx"), "utf8");
  const encoderSource = await readFile(resolve(import.meta.dirname, "bodyPhotoEncoder.ts"), "utf8");

  expect(source).toMatch(/useCameraPermission/);
  expect(source).toMatch(/useCameraDevice/);
  expect(source).toMatch(/usePhotoOutput/);
  expect(source).toMatch(/capturePhotoToFile/);
  expect(source).toMatch(/encodeBodyPhotoWithPrivacyCrop/);
  expect(source).toMatch(/bodyPhotoPrivacyProcessingErrorMessage/);
  expect(source).toMatch(/deleteLocalFile\(rawUri\)/);
  expect(encoderSource).toMatch(/privacyCropApplied/);
  expect(source).not.toMatch(/useFrameOutput/);
  expect(source).not.toMatch(/scheduleOnRN/);
  expect(source).toMatch(/outputs=\{\[photoOutput\]\}/);
  expect(source).toMatch(/orientationSource="device"/);
  expect(source).toMatch(/mirrorMode="off"/);
  expect(source).not.toMatch(/getPixelBuffer|console\.|Log\./);
});
