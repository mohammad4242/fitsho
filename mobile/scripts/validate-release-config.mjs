import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const legacyBrandPattern = /Fitsho|Fitition/u;

export function validateReleaseConfig(easConfig, appConfig) {
  assert.equal(easConfig.cli?.appVersionSource, "remote");
  const profiles = easConfig.build;
  assert.deepEqual(Object.keys(profiles), ["development", "preview", "production"]);

  const expected = {
    development: { buildType: "apk", channel: "development", environment: "development" },
    preview: { buildType: "app-bundle", channel: "preview", environment: "preview" },
    production: { buildType: "app-bundle", channel: "production", environment: "production" },
  };
  for (const [name, requirement] of Object.entries(expected)) {
    const profile = profiles[name];
    assert.equal(profile.environment, requirement.environment, `${name} environment drifted`);
    assert.equal(profile.channel, requirement.channel, `${name} channel drifted`);
    assert.equal(profile.android?.buildType, requirement.buildType, `${name} build type drifted`);
    assert.equal(profile.android?.credentialsSource, "remote", `${name} Android credentials drifted`);
    assert.equal(profile.ios?.credentialsSource, "remote", `${name} iOS credentials drifted`);
    assert.equal(
      profile.distribution,
      name === "production" ? "store" : "internal",
      `${name} distribution drifted`,
    );
    assert.equal(profile.env?.APP_VARIANT, requirement.environment);
  }
  assert.equal(profiles.development.developmentClient, true);
  assert.equal(profiles.preview.distribution, "internal");
  assert.equal(profiles.production.autoIncrement, true);
  assert.equal(easConfig.submit?.production?.android?.track, "internal");
  assert.equal(easConfig.submit?.production?.android?.releaseStatus, "draft");
  assert.ok(easConfig.submit?.production?.ios, "production iOS submit config is missing");

  assert.match(appConfig, /runtimeVersion:\s*\{\s*policy:\s*["']appVersion["']/u);
  assert.match(appConfig, /["']expo-updates["']/u);
  assert.match(appConfig, /EXPO_UPDATES_URL/u);
  assert.match(appConfig, /GOOGLE_SERVICES_JSON/u);
  assert.match(appConfig, /bundleIdentifier:\s*["']com\.fitician\.app["']/u);
  assert.match(appConfig, /associatedDomains/u);
  assert.match(appConfig, /EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID/u);
  assert.match(appConfig, /usesAppleSignIn:\s*true/u);
  assert.match(appConfig, /withIosHardening/u);
  assert.equal(legacyBrandPattern.test(JSON.stringify(easConfig)), false);
  return easConfig;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const easConfig = JSON.parse(await readFile(resolve(mobileRoot, "eas.json"), "utf8"));
  const appConfig = await readFile(resolve(mobileRoot, "app.config.ts"), "utf8");
  validateReleaseConfig(easConfig, appConfig);
  console.log("Fitician EAS release profiles are valid");
}
