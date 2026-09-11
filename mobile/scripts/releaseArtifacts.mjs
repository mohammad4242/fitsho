import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function releaseArtifactPaths(outputDirectory, platform = "android") {
  assert.ok(platform === "android" || platform === "ios", `Unknown release platform: ${platform}`);
  const outputRoot = isAbsolute(outputDirectory)
    ? outputDirectory
    : resolve(mobileRoot, outputDirectory);
  return {
    assets: join(outputRoot, "assets"),
    bundle: join(outputRoot, `index.${platform}.js`),
    sourceMap: join(outputRoot, `index.${platform}.js.map`),
  };
}

export function buildReleaseEmbedArgs(platformOrOutputDirectory, maybeOutputDirectory) {
  const platform = maybeOutputDirectory === undefined ? "android" : platformOrOutputDirectory;
  const outputDirectory = maybeOutputDirectory === undefined
    ? platformOrOutputDirectory
    : maybeOutputDirectory;
  const paths = releaseArtifactPaths(outputDirectory, platform);
  return [
    "expo",
    "export:embed",
    "--platform",
    platform,
    "--dev",
    "false",
    "--minify",
    "true",
    "--bundle-output",
    paths.bundle,
    "--sourcemap-output",
    paths.sourceMap,
    "--sourcemap-sources-root",
    mobileRoot,
    "--assets-dest",
    paths.assets,
    "--skip-server",
  ];
}

export function buildAndroidReleaseEmbedArgs(outputDirectory) {
  return buildReleaseEmbedArgs("android", outputDirectory);
}

export function buildIosReleaseEmbedArgs(outputDirectory) {
  return buildReleaseEmbedArgs("ios", outputDirectory);
}

async function main() {
  const platformIndex = process.argv.indexOf("--platform");
  const platform = platformIndex === -1
    ? process.env.FITICIAN_RELEASE_PLATFORM ?? "android"
    : process.argv[platformIndex + 1];
  assert.ok(platform === "android" || platform === "ios", "Use --platform android or ios");
  const outputIndex = process.argv.indexOf("--output-directory");
  const outputDirectory = outputIndex === -1
    ? process.env[`FITICIAN_${platform.toUpperCase()}_RELEASE_DIR`] ?? `dist/${platform}-release`
    : process.argv[outputIndex + 1];
  assert.ok(outputDirectory, "A release output directory is required");
  const paths = releaseArtifactPaths(outputDirectory, platform);
  await mkdir(paths.assets, { recursive: true });
  const command = process.platform === "win32" ? "npx.cmd" : "npx";
  const result = spawnSync(command, buildReleaseEmbedArgs(platform, outputDirectory), {
    cwd: mobileRoot,
    stdio: "inherit",
  });
  if (result.error !== undefined) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await main();
}
