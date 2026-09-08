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

export function buildEasArgs(profile) {
  assert.ok(
    Object.values(RELEASE_ARTIFACTS).some((artifact) => artifact.profile === profile),
    `Unknown Android release profile: ${profile}`,
  );
  return [
    "eas",
    "build",
    "--platform",
    "android",
    "--profile",
    profile,
    "--non-interactive",
  ];
}

export function validateReleaseArtifactSet(artifacts) {
  const paths = {};
  for (const [name, requirement] of Object.entries(RELEASE_ARTIFACTS)) {
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
  assert.ok(profile, "Use --profile development, preview, or production");
  assert.ok(process.env.EAS_TOKEN, "EAS_TOKEN is required for non-interactive EAS builds");

  const command = process.platform === "win32" ? "npx.cmd" : "npx";
  const args = ["--yes", "eas-cli@latest", ...buildEasArgs(profile).slice(1)];
  const result = spawnSync(command, args, {
    cwd: mobileRoot,
    env: { ...process.env, CI: "1" },
    stdio: "inherit",
  });
  if (result.error !== undefined) throw result.error;
  process.exit(result.status ?? 1);
}
