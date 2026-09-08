import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const bodyVisionRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "modules",
  "fitician-body-vision",
);

async function read(relativePath: string): Promise<string> {
  return readFile(resolve(bodyVisionRoot, relativePath), "utf8");
}

describe("Android body vision spike wiring", () => {
  it("uses the current VisionCamera frame-output and Nitro contract", async () => {
    const source = await read("src/FiticianBodyVision.nitro.ts");
    const harness = await read("../../bodyAnalysis/BodyVisionSpikeHarness.tsx");
    const packageSource = await read(
      "android/src/main/java/com/margelo/nitro/fitician/bodyvision/FiticianBodyVisionPackage.kt",
    );

    expect(source).toContain("HybridObject");
    expect(source).toContain("Frame");
    expect(source).toContain("NativeBodyVisionResult");
    expect(source).toContain("recordDroppedFrame");
    expect(harness).toContain("useFrameOutput");
    expect(harness).toContain("modelStatus");
    expect(harness).toContain("frame.dispose()");
    expect(packageSource).toContain("BaseReactPackage");
    expect(packageSource).toContain("initializeNative");
  });

  it("keeps MediaPipe native and avoids native pixel logging", async () => {
    const gradle = await read("android/build.gradle");
    const nativeSource = await read(
      "android/src/main/java/com/margelo/nitro/fitician/bodyvision/FiticianBodyVision.kt",
    );

    expect(gradle).toContain("com.google.mediapipe:tasks-vision:0.10.29");
    expect(nativeSource).toContain("NativeFrame");
    expect(nativeSource).toContain("PoseLandmarker");
    expect(nativeSource).toContain("ImageSegmenter");
    expect(nativeSource).toContain("confidenceMasks");
    expect(nativeSource).toContain("setOutputConfidenceMasks(true)");
    expect(nativeSource).toContain("setOutputCategoryMask(false)");
    expect(nativeSource).not.toMatch(/Log\.|println\(|console\./);
  });

  it("inherits the app Android Gradle Plugin instead of pinning a second version", async () => {
    const gradle = await read("android/build.gradle");

    expect(gradle).not.toContain("com.android.tools.build:gradle:9.2.1");
  });
});
