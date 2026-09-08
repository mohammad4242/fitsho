import { mkdir } from "node:fs/promises";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function releaseArtifactPaths(outputDirectory) {
  const outputRoot = isAbsolute(outputDirectory)
    ? outputDirectory
    : resolve(mobileRoot, outputDirectory);
  return {
    assets: join(outputRoot, "assets"),
    bundle: join(outputRoot, "index.android.js"),
    sourceMap: join(outputRoot, "index.android.js.map"),
  };
}

export function buildAndroidReleaseEmbedArgs(outputDirectory) {
  const paths = releaseArtifactPaths(outputDirectory);
  return [
    "expo",
    "export:embed",
    "--platform",
    "android",
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

async function main() {
  const outputDirectory = process.env.FITICIAN_ANDROID_RELEASE_DIR ?? "dist/android-release";
  const paths = releaseArtifactPaths(outputDirectory);
  await mkdir(paths.assets, { recursive: true });
  const command = process.platform === "win32" ? "npx.cmd" : "npx";
  const result = spawnSync(command, buildAndroidReleaseEmbedArgs(outputDirectory), {
    cwd: mobileRoot,
    stdio: "inherit",
  });
  if (result.error !== undefined) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await main();
}
