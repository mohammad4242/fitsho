import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
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
  assert.match(workflow, /environment:\s*\$\{\{ inputs\.profile \}\}/u);
});
