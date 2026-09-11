import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = resolve(mobileRoot, "..");

const readJson = async (path) => JSON.parse(await readFile(path, "utf8"));

const rootPackage = await readJson(resolve(projectRoot, "package.json"));
const mobilePackage = await readJson(resolve(mobileRoot, "package.json"));
const corePackage = await readJson(resolve(projectRoot, "packages/fitician-core/package.json"));
const appConfig = await readFile(resolve(mobileRoot, "app.config.ts"), "utf8");
const androidHardening = await readFile(
  resolve(mobileRoot, "plugins/withAndroidHardening.ts"),
  "utf8",
);
const androidReleaseSymbols = await readFile(
  resolve(mobileRoot, "plugins/withAndroidReleaseSymbols.ts"),
  "utf8",
);
const iosHardening = await readFile(
  resolve(mobileRoot, "plugins/withIosHardening.ts"),
  "utf8",
);
const bodyVisionPodspec = await readFile(
  resolve(mobileRoot, "modules/fitician-body-vision/FiticianBodyVision.podspec"),
  "utf8",
);
const bodyVisionNitroSpec = await readFile(
  resolve(mobileRoot, "modules/fitician-body-vision/nitro.json"),
  "utf8",
);
const bodyVisionIosSource = await readFile(
  resolve(mobileRoot, "modules/fitician-body-vision/ios/FiticianBodyVision.swift"),
  "utf8",
);
const androidManifestPath = resolve(mobileRoot, "android/app/src/main/AndroidManifest.xml");
const androidMainActivityPath = resolve(
  mobileRoot,
  "android/app/src/main/java/com/fitician/app/MainActivity.kt",
);
const tsconfig = await readJson(resolve(mobileRoot, "tsconfig.json"));
const fontFiles = [
  "Vazirmatn-Regular.ttf",
  "Vazirmatn-Medium.ttf",
  "Vazirmatn-SemiBold.ttf",
  "Vazirmatn-Bold.ttf",
  "Vazirmatn-ExtraBold.ttf",
  "Lalezar-Regular.otf",
  "Sora-Regular.otf",
  "Sora-SemiBold.otf",
  "Sora-Bold.otf",
  "Sora-ExtraBold.otf",
];

assert.deepEqual(rootPackage.workspaces, ["frontend", "mobile", "packages/fitician-core"]);
assert.equal(mobilePackage.name, "@fitician/mobile");
assert.equal(mobilePackage.scripts["audit:dependencies"], "node scripts/dependency-audit.mjs");
assert.equal(
  mobilePackage.scripts["export:android:source-maps"],
  "node scripts/releaseArtifacts.mjs",
);
assert.equal(mobilePackage.scripts.ios, "expo run:ios");
assert.equal(
  mobilePackage.scripts["export:ios:source-maps"],
  "node scripts/releaseArtifacts.mjs --platform ios",
);
for (const script of ["build:ios:debug", "build:ios:internal", "build:ios:production"]) {
  assert.match(mobilePackage.scripts[script], /release-build-plan\.mjs --platform ios/u);
}
assert.equal(corePackage.name, "@fitician/core");
assert.match(mobilePackage.dependencies.expo, /^~?57\./);
assert.match(mobilePackage.dependencies["expo-router"], /^~?57\./);
assert.equal(tsconfig.compilerOptions.strict, true);
for (const identifier of ["Fitsho", "Fitition"]) {
  assert.equal(appConfig.includes(identifier), false, `permanent identifier contains ${identifier}`);
}
for (const required of [
  /name:\s*["']Fitician["']/,
  /slug:\s*["']fitician["']/,
  /scheme:\s*["']fitician["']/,
  /package:\s*["']com\.fitician\.app["']/,
  /minSdkVersion:\s*24/,
  /compileSdkVersion:\s*36/,
  /targetSdkVersion:\s*36/,
  /autoVerify:\s*true/,
  /scheme:\s*["']https["']/,
  /associatedDomains/,
  /EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID/,
  /pathPrefix:\s*["']\/link["']/,
  /\["expo-sqlite",\s*\{\s*useSQLCipher:\s*true\s*\}\]/,
  /["']expo-background-task["']/,
  /["']expo-notifications["']/,
  /["']expo-font["']/,
  /cameraPermission:\s*(?:["'][^"']+["']|iosHardening\.IOS_CAMERA_USAGE_DESCRIPTION)/,
  /microphonePermission:\s*false/,
  /photosPermission:\s*false/,
  /bundleIdentifier:\s*["']com\.fitician\.app["']/,
  /usesAppleSignIn:\s*true/,
  /["']expo-apple-authentication["']/,
  /withAndroidHardening/,
  /withAndroidReleaseSymbols/,
  /withIosHardening/,
]) {
  assert.match(appConfig, required);
}
assert.match(androidReleaseSymbols, /android\.enableMinifyInReleaseBuilds/);
for (const required of [
  /android:allowBackup["']?:\s*["']false["']/,
  /android:usesCleartextTraffic/u,
  /environment\s*===\s*["']development["']/u,
  /cleartextTrafficPermitted="false"/u,
  /fitician_backup_rules/,
  /FLAG_SECURE/,
]) {
  assert.match(androidHardening, required);
}
for (const required of [
  /NSCameraUsageDescription/u,
  /NSAllowsArbitraryLoads:\s*false/u,
  /NSExceptionDomains/u,
  /NSExceptionAllowsInsecureHTTPLoads/u,
  /NSIncludesSubdomains:\s*false/u,
]) {
  assert.match(iosHardening, required);
}
for (const required of [
  /add_nitrogen_files\(s\)/u,
  /MediaPipeTasksVision/u,
  /pose_landmarker_lite\.task/u,
  /selfie_segmenter\.tflite/u,
]) {
  assert.match(bodyVisionPodspec, required);
}
for (const required of [
  /"iosModuleName":\s*"FiticianBodyVision"/u,
  /"ios":\s*\{\s*"language":\s*"swift"/su,
  /"implementationClassName":\s*"FiticianBodyVision"/u,
]) {
  assert.match(bodyVisionNitroSpec, required);
}
for (const required of [
  /PoseLandmarker/u,
  /ImageSegmenter/u,
  /modelStatus/u,
  /pose_landmarker_lite/u,
  /selfie_segmenter/u,
]) {
  assert.match(bodyVisionIosSource, required);
}
for (const sourcePath of [
  "modules/fitician-body-vision/FiticianBodyVision.podspec",
  "modules/fitician-body-vision/ios/FiticianBodyVision.swift",
  "modules/fitician-body-vision/nitrogen/generated/ios/FiticianBodyVision+autolinking.rb",
  "modules/fitician-body-vision/nitrogen/generated/ios/swift/HybridFiticianBodyVisionSpec.swift",
  "modules/fitician-body-vision/android/src/main/assets/body_vision/pose_landmarker_lite.task",
  "modules/fitician-body-vision/android/src/main/assets/body_vision/selfie_segmenter.tflite",
]) {
  const info = await stat(resolve(mobileRoot, sourcePath));
  assert.ok(info.isFile() && info.size > 0, `${sourcePath} must be a non-empty source file`);
}
try {
  const androidManifest = await readFile(androidManifestPath, "utf8");
  assert.match(androidManifest, /android:scheme="fitician"/);
  assert.match(androidManifest, /android:autoVerify="true"/);
  assert.match(androidManifest, /android:allowBackup="false"/);
  const appVariant = process.env.APP_VARIANT?.trim() || "development";
  assert.ok(["development", "preview", "production"].includes(appVariant));
  assert.match(
    androidManifest,
    new RegExp(`android:usesCleartextTraffic="${appVariant === "development" ? "true" : "false"}"`),
  );
  for (const permission of [
    "READ_EXTERNAL_STORAGE",
    "WRITE_EXTERNAL_STORAGE",
    "READ_MEDIA_IMAGES",
    "READ_MEDIA_VIDEO",
    "READ_MEDIA_AUDIO",
    "READ_MEDIA_VISUAL_USER_SELECTED",
    "RECORD_AUDIO",
    "SYSTEM_ALERT_WINDOW",
  ]) {
    assert.match(
      androidManifest,
      new RegExp(`android:name="android\\.permission\\.${permission}"[^>]*tools:node="remove"`),
    );
  }
  for (const identifier of ["Fitsho", "Fitition"]) {
    assert.equal(
      androidManifest.includes(identifier),
      false,
      `generated Android manifest contains ${identifier}`,
    );
  }
  try {
    const mainActivity = await readFile(androidMainActivityPath, "utf8");
    if (appVariant === "development") {
      assert.doesNotMatch(mainActivity, /FLAG_SECURE/u);
    } else {
      assert.match(mainActivity, /FLAG_SECURE/u);
    }
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }
} catch (error) {
  if (error?.code !== "ENOENT") {
    throw error;
  }
}
try {
  const iosInfoPlist = await readFile(resolve(mobileRoot, "ios/Fitician/Info.plist"), "utf8");
  assert.match(iosInfoPlist, /NSCameraUsageDescription/u);
  assert.match(iosInfoPlist, /fitician/u);
  assert.match(iosInfoPlist, /com\.fitician\.app/u);
} catch (error) {
  if (error?.code !== "ENOENT") throw error;
}
try {
  const iosEntitlements = await readFile(
    resolve(mobileRoot, "ios/Fitician/Fitician.entitlements"),
    "utf8",
  );
  assert.match(iosEntitlements, /com\.apple\.developer\.associated-domains/u);
  assert.match(iosEntitlements, /applinks:/u);
} catch (error) {
  if (error?.code !== "ENOENT") throw error;
}
for (const fontFile of fontFiles) {
  const info = await stat(resolve(mobileRoot, "assets/fonts", fontFile));
  assert.ok(info.isFile() && info.size > 0, `${fontFile} must be a non-empty font file`);
}

console.log("Fitician mobile foundation is valid");
