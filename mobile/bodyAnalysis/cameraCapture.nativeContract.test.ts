import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("uses the native VisionCamera photo and frame-output contracts", async () => {
  const source = await readFile(resolve(import.meta.dirname, "BodyPhotoCapture.tsx"), "utf8");

  expect(source).toMatch(/useCameraPermission/);
  expect(source).toMatch(/useCameraDevice/);
  expect(source).toMatch(/usePhotoOutput/);
  expect(source).toMatch(/capturePhotoToFile/);
  expect(source).toMatch(/useFrameOutput/);
  expect(source).toMatch(/scheduleOnRN/);
  expect(source).toMatch(/orientationSource="device"/);
  expect(source).toMatch(/mirrorMode="off"/);
  expect(source).not.toMatch(/getPixelBuffer|console\.|Log\./);
});
