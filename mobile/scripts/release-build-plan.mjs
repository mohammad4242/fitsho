import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export const RELEASE_ARTIFACTS = Object.freeze({
  debugApk: Object.freeze({ extension: ".apk", profile: "development" }),
  internalAab: Object.freeze({ extension: ".aab", profile: "preview" }),
  productionAab: Object.freeze({ extension: ".aab", profile: "production" }),
});

export const RELEASE_ARTIFACTS_BY_PLATFORM = Object.freeze({
  android: RELEASE_ARTIFACTS,
  ios: Object.freeze({
    debugIpa: Object.freeze({ extension: ".ipa", profile: "development" }),
    internalIpa: Object.freeze({ extension: ".ipa", profile: "preview" }),
    productionIpa: Object.freeze({ extension: ".ipa", profile: "production" }),
  }),
});

function normalizeBuildArguments(platformOrProfile, maybeProfile) {
  return maybeProfile === undefined
    ? { platform: "android", profile: platformOrProfile }
    : { platform: platformOrProfile, profile: maybeProfile };
}

function artifactsForPlatform(platform) {
  const artifacts = RELEASE_ARTIFACTS_BY_PLATFORM[platform];
  assert.ok(artifacts, `Unknown release platform: ${platform}`);
  return artifacts;
}

export function buildEasArgs(platformOrProfile, maybeProfile) {
  const { platform, profile } = normalizeBuildArguments(platformOrProfile, maybeProfile);
  const artifacts = artifactsForPlatform(platform);
  assert.ok(
    Object.values(artifacts).some((artifact) => artifact.profile === profile),
    `Unknown ${platform} release profile: ${profile}`,
  );
  return [
    "eas",
    "build",
    "--platform",
    platform,
    "--profile",
    profile,
    "--non-interactive",
  ];
}

export function validateReleaseArtifactSet(artifacts, platform = "android") {
  const paths = {};
  for (const [name, requirement] of Object.entries(artifactsForPlatform(platform))) {
    const artifact = artifacts[name];
    assert.ok(artifact, `${name} artifact is missing`);
    assert.equal(typeof artifact.path, "string", `${name} artifact path is missing`);
    assert.match(artifact.path, new RegExp(`${requirement.extension.replace(".", "\\.")}$`, "u"));
    assert.ok(Number.isInteger(artifact.size) && artifact.size > 0, `${name} artifact is empty`);
    paths[name] = artifact.path;
  }
  return paths;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const profileIndex = process.argv.indexOf("--profile");
  const profile = profileIndex === -1 ? undefined : process.argv[profileIndex + 1];
  const platformIndex = process.argv.indexOf("--platform");
  const platform = platformIndex === -1 ? "android" : process.argv[platformIndex + 1];
  assert.ok(profile, "Use --profile development, preview, or production");
  assert.ok(platform, "Use --platform android or ios");
  assert.ok(process.env.EAS_TOKEN, "EAS_TOKEN is required for non-interactive EAS builds");

  const command = process.platform === "win32" ? "npx.cmd" : "npx";
  const args = ["--yes", "eas-cli@latest", ...buildEasArgs(platform, profile).slice(1)];
  const result = spawnSync(command, args, {
    cwd: mobileRoot,
    env: { ...process.env, CI: "1" },
    stdio: "inherit",
  });
  if (result.error !== undefined) throw result.error;
  process.exit(result.status ?? 1);
}
