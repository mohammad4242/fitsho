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
  const workflow = await readFile(resolve(root, ".github/workflows/android-release.yml"), "utf8");
  const packageJson = JSON.parse(await readFile(resolve(root, "mobile/package.json"), "utf8"));
  assert.match(workflow, /workflow_dispatch:/u);
  assert.match(workflow, /EAS_TOKEN/u);
  for (const profile of ["development", "preview", "production"]) {
    assert.match(workflow, new RegExp(profile, "u"));
  }
  assert.match(packageJson.scripts["build:android:debug"], /--profile development/u);
  assert.match(packageJson.scripts["build:android:internal"], /--profile preview/u);
  assert.match(packageJson.scripts["build:android:production"], /--profile production/u);
  assert.match(packageJson.scripts["build:ios:debug"], /--platform ios/u);
  assert.match(packageJson.scripts["build:ios:internal"], /--platform ios/u);
  assert.match(packageJson.scripts["build:ios:production"], /--platform ios/u);
  assert.match(workflow, /environment:\s*\$\{\{ inputs\.profile \}\}/u);
});
