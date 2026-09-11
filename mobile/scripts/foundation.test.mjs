import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { basename } from "node:path";
import { test } from "node:test";

const projectRoot = new URL("../../", import.meta.url);

async function readJson(relativePath) {
  return JSON.parse(await readFile(new URL(relativePath, projectRoot), "utf8"));
}

test("declares the Fitician workspace and native foundation", async () => {
  const rootPackage = await readJson("package.json");
  const mobilePackage = await readJson("mobile/package.json");
  const corePackage = await readJson("packages/fitician-core/package.json");
  const appConfig = await readFile(new URL("mobile/app.config.ts", projectRoot), "utf8");
  const releaseSymbolsPlugin = await readFile(
    new URL("mobile/plugins/withAndroidReleaseSymbols.ts", projectRoot),
    "utf8",
  );
  const iosHardeningPlugin = await readFile(
    new URL("mobile/plugins/withIosHardening.ts", projectRoot),
    "utf8",
  );
  const mobileTsconfig = await readJson("mobile/tsconfig.json");

  assert.deepEqual(rootPackage.workspaces, ["frontend", "mobile", "packages/fitician-core"]);
  assert.equal(mobilePackage.name, "@fitician/mobile");
  assert.equal(corePackage.name, "@fitician/core");
  assert.match(mobilePackage.dependencies.expo, /^~?57\./);
  assert.match(mobilePackage.dependencies["expo-router"], /^~?57\./);
  assert.match(appConfig, /name:\s*["']Fitician["']/);
  assert.match(appConfig, /scheme:\s*["']fitician["']/);
  assert.match(appConfig, /package:\s*["']com\.fitician\.app["']/);
  assert.match(appConfig, /minSdkVersion:\s*24/);
  assert.match(appConfig, /compileSdkVersion:\s*36/);
  assert.match(appConfig, /targetSdkVersion:\s*36/);
  assert.match(appConfig, /autoVerify:\s*true/);
  assert.match(appConfig, /pathPrefix:\s*["']\/link["']/);
  assert.match(appConfig, /scheme:\s*["']https["']/);
  assert.match(appConfig, /associatedDomains/);
  assert.match(appConfig, /EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID/);
  assert.match(appConfig, /withAndroidReleaseSymbols/);
  assert.match(appConfig, /withIosHardening/);
  assert.match(appConfig, /bundleIdentifier:\s*["']com\.fitician\.app["']/);
  assert.match(iosHardeningPlugin, /NSCameraUsageDescription/u);
  assert.match(iosHardeningPlugin, /NSExceptionDomains/u);
  assert.match(iosHardeningPlugin, /NSAllowsArbitraryLoads/u);
  assert.match(iosHardeningPlugin, /NSExceptionAllowsInsecureHTTPLoads/u);
  assert.match(releaseSymbolsPlugin, /android\.enableMinifyInReleaseBuilds/);
  assert.equal(mobilePackage.scripts["export:android:source-maps"], "node scripts/releaseArtifacts.mjs");
  assert.equal(mobileTsconfig.compilerOptions.strict, true);
  assert.doesNotMatch(appConfig, /Fitsho|Fitition/);
});

test("keeps bundled image basenames unique for Android resources", async () => {
  const imageDirectory = new URL("mobile/assets/body-analysis/web/", projectRoot);
  const imageFiles = (await readdir(imageDirectory)).filter((file) => /\.(?:jpg|png|webp)$/u.test(file));
  const basenames = imageFiles.map((file) => basename(file).replace(/\.[^.]+$/u, ""));

  assert.equal(new Set(basenames).size, basenames.length);
});
