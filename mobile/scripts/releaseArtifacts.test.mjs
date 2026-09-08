import assert from "node:assert/strict";
import { test } from "node:test";
import { buildAndroidReleaseEmbedArgs, releaseArtifactPaths } from "./releaseArtifacts.mjs";

test("defines private Android release bundle and source-map artifacts", () => {
  const paths = releaseArtifactPaths("dist/android-release");
  assert.equal(paths.bundle.endsWith("dist/android-release/index.android.js"), true);
  assert.equal(paths.sourceMap.endsWith("dist/android-release/index.android.js.map"), true);
  assert.equal(paths.assets.endsWith("dist/android-release/assets"), true);
});

test("exports a minified Android bundle with an external source map", () => {
  const args = buildAndroidReleaseEmbedArgs("dist/android-release");
  assert.deepEqual(args.slice(0, 8), [
    "expo",
    "export:embed",
    "--platform",
    "android",
    "--dev",
    "false",
    "--minify",
    "true",
  ]);
  assert.equal(args.includes("--sourcemap-output"), true);
  assert.equal(args.includes("--sourcemap-sources-root"), true);
  assert.equal(args.includes("--skip-server"), true);
});
