import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  RELEASE_ARTIFACTS_BY_PLATFORM,
  RELEASE_ARTIFACTS,
  buildEasArgs,
  validateReleaseArtifactSet,
} from "./release-build-plan.mjs";
import * as releasePlan from "./release-build-plan.mjs";

test("EAS builds the shared core package before app bundling", async () => {
  const packageJson = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
  assert.equal(packageJson.scripts["eas-build-post-install"], "npm --prefix .. run build:core");
});

test("release CLI accepts the standard Expo token and preserves legacy CI secrets", () => {
  const { buildEasEnvironment } = releasePlan;
  assert.equal(typeof buildEasEnvironment, "function");
  assert.deepEqual(buildEasEnvironment({ EXPO_TOKEN: "test-standard" }, "ios"), {
    EXPO_TOKEN: "test-standard", EAS_BUILD_PLATFORM: "ios", CI: "1",
  });
  assert.equal(buildEasEnvironment({ EAS_TOKEN: "test-legacy" }, "android").EXPO_TOKEN, "test-legacy");
  assert.equal(buildEasEnvironment({ EXPO_TOKEN: "test-standard", EAS_TOKEN: "test-legacy" }, "ios").EXPO_TOKEN, "test-standard");
  assert.throws(() => buildEasEnvironment({}, "ios"), /EXPO_TOKEN/u);
  assert.throws(() => buildEasEnvironment({ EXPO_TOKEN: " " }, "ios"), /EXPO_TOKEN/u);
});

test("release plan maps every Android artifact to the locked EAS profile", () => {
  assert.deepEqual(RELEASE_ARTIFACTS, {
    debugApk: { extension: ".apk", profile: "development" },
    internalAab: { extension: ".aab", profile: "preview" },
    productionAab: { extension: ".aab", profile: "production" },
  });
  assert.deepEqual(buildEasArgs("preview"), [
    "eas",
    "build",
    "--platform",
    "android",
    "--profile",
    "preview",
    "--non-interactive",
  ]);
  assert.deepEqual(RELEASE_ARTIFACTS_BY_PLATFORM.ios, {
    debugIpa: { extension: ".ipa", profile: "development" },
    internalIpa: { extension: ".ipa", profile: "preview" },
    productionIpa: { extension: ".ipa", profile: "production" },
  });
  assert.deepEqual(buildEasArgs("ios", "preview"), [
    "eas",
    "build",
    "--platform",
    "ios",
    "--profile",
    "preview",
    "--non-interactive",
  ]);
});

test("release artifact validation requires all three non-empty files", () => {
  assert.deepEqual(
    validateReleaseArtifactSet({
      debugApk: { path: "debug.apk", size: 10 },
      internalAab: { path: "internal.aab", size: 20 },
      productionAab: { path: "production.aab", size: 30 },
    }),
    { debugApk: "debug.apk", internalAab: "internal.aab", productionAab: "production.aab" },
  );
  assert.throws(
    () => validateReleaseArtifactSet({ debugApk: { path: "debug.apk", size: 10 } }),
    /internalAab/u,
  );
  assert.deepEqual(
    validateReleaseArtifactSet(
      {
        debugIpa: { path: "debug.ipa", size: 10 },
        internalIpa: { path: "internal.ipa", size: 20 },
        productionIpa: { path: "production.ipa", size: 30 },
      },
      "ios",
    ),
    { debugIpa: "debug.ipa", internalIpa: "internal.ipa", productionIpa: "production.ipa" },
  );
});

test("protected release workflow exposes all three EAS artifact profiles", async () => {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
  const [androidWorkflow, iosWorkflow, sideloadBuildScript] = await Promise.all([
    readFile(resolve(root, ".github/workflows/android-release.yml"), "utf8"),
    readFile(resolve(root, ".github/workflows/ios-release.yml"), "utf8"),
    readFile(resolve(root, "mobile/scripts/build-ios-sideload.sh"), "utf8"),
  ]);
  const packageJson = JSON.parse(await readFile(resolve(root, "mobile/package.json"), "utf8"));
  assert.match(androidWorkflow, /workflow_dispatch:/u);
  assert.match(androidWorkflow, /EAS_TOKEN/u);
  assert.match(androidWorkflow, /node-version:\s*["']20\.19\.4["']/u);
  assert.match(iosWorkflow, /name: Fitician iOS release/u);
  assert.match(iosWorkflow, /workflow_dispatch:/u);
  assert.match(iosWorkflow, /EAS_TOKEN/u);
  assert.match(iosWorkflow, /node-version:\s*["']20\.19\.4["']/u);
  for (const profile of ["development", "preview", "production"]) {
    assert.match(androidWorkflow, new RegExp(profile, "u"));
    assert.match(iosWorkflow, new RegExp(profile, "u"));
  }
  assert.match(packageJson.scripts["build:android:debug"], /--profile development/u);
  assert.match(packageJson.scripts["build:android:internal"], /--profile preview/u);
  assert.match(packageJson.scripts["build:android:production"], /--profile production/u);
  assert.match(packageJson.scripts["build:ios:debug"], /--platform ios/u);
  assert.match(packageJson.scripts["build:ios:internal"], /--platform ios/u);
  assert.match(packageJson.scripts["build:ios:production"], /--platform ios/u);
  assert.match(androidWorkflow, /environment:\s*\$\{\{ inputs\.profile \}\}/u);
  assert.match(iosWorkflow, /environment:\s*\$\{\{ inputs\.profile \}\}/u);
  assert.match(iosWorkflow, /build:ios:debug/u);
  assert.match(iosWorkflow, /build:ios:internal/u);
  assert.match(iosWorkflow, /build:ios:production/u);
  assert.match(iosWorkflow, /- sideload\s*$/mu);
  assert.match(iosWorkflow, /runs-on:\s*macos-26/u);
  assert.match(iosWorkflow, /xcode-select -s/u);
  assert.match(iosWorkflow, /Xcode_26\.5\.app/u);
  assert.match(iosWorkflow, /patch-ios-sideload-dependencies\.mjs/u);
  assert.match(iosWorkflow, /IOS_SIDELOAD_BUILD/u);
  assert.match(sideloadBuildScript, /generic\/platform=iOS/u);
  assert.match(sideloadBuildScript, /CODE_SIGNING_ALLOWED=NO/u);
  assert.match(iosWorkflow, /Fitician-unsigned\.ipa/u);
  assert.match(iosWorkflow, /fitician-ios-unsigned/u);
  assert.match(iosWorkflow, /actions\/upload-artifact@v4/u);
});
