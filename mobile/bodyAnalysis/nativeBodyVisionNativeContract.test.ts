import { readdir, readFile } from "node:fs/promises";
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

describe("iOS body vision module wiring", () => {
  it("declares the generated Swift implementation without changing the public contract", async () => {
    const source = await read("src/FiticianBodyVision.nitro.ts");
    const nitro = await read("nitro.json");
    const packageJson = JSON.parse(await read("package.json")) as {
      files?: string[];
    };
    const podspec = await read("FiticianBodyVision.podspec");
    const swift = await read("ios/FiticianBodyVision.swift");

    expect(source).toContain('android: "kotlin";');
    expect(source).toContain('ios: "swift";');
    expect(source).toContain("contractVersion");
    expect(source).toContain("NativeBodyVisionResult");
    expect(nitro).toMatch(/"ios"\s*:\s*\{[\s\S]*"language"\s*:\s*"swift"/u);
    expect(nitro).toContain('"implementationClassName": "FiticianBodyVision"');
    expect(packageJson.files).toEqual(expect.arrayContaining(["ios", "FiticianBodyVision.podspec"]));
    expect(podspec).toContain("add_nitrogen_files");
    expect(podspec).toContain("MediaPipeTasksVision");
    expect(podspec).toMatch(/s\.source\s*=\s*\{/u);
    expect(podspec).toContain("pose_landmarker_lite.task");
    expect(podspec).toContain("selfie_segmenter.tflite");
    expect(swift).toContain("HybridFiticianBodyVisionSpec");
    expect(swift).toContain("PoseLandmarker");
    expect(swift).toContain("ImageSegmenter");
    expect(swift).toContain("MODEL_STATUS_NOT_PACKAGED");
    expect(swift).toContain("visibility: Double(landmark.visibility ?? 0)");
    expect(swift).not.toContain("landmark.visibility?.doubleValue");
    expect(swift).not.toMatch(/override\s+func\s+dispose\s*\(/u);
  });

  it("uses the non-optional image-mode MediaPipe result APIs", async () => {
    const swift = await read("ios/FiticianBodyVision.swift");

    expect(swift).toContain("let poseResult = try poseLandmarker.detect(image: image)");
    expect(swift).toContain("let segmentationResult = try imageSegmenter.segment(image: image)");
    expect(swift).not.toContain("guard let poseResult = try poseLandmarker.detect");
    expect(swift).not.toContain("guard let segmentationResult = try imageSegmenter.segment");
  });

  it("regenerates the iOS Nitrogen bridge instead of hand-writing it", async () => {
    const generatedIos = await readdir(resolve(bodyVisionRoot, "nitrogen/generated/ios"));

    expect(generatedIos).toEqual(expect.arrayContaining([
      "FiticianBodyVision+autolinking.rb",
      "FiticianBodyVisionAutolinking.swift",
    ]));
  });
});
