import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = resolve(mobileRoot, "..");

const readJson = async (path) => JSON.parse(await readFile(path, "utf8"));

const rootPackage = await readJson(resolve(projectRoot, "package.json"));
const mobilePackage = await readJson(resolve(mobileRoot, "package.json"));
const corePackage = await readJson(resolve(projectRoot, "packages/fitician-core/package.json"));
const appConfig = await readFile(resolve(mobileRoot, "app.config.ts"), "utf8");
const androidHardening = await readFile(
  resolve(mobileRoot, "plugins/withAndroidHardening.ts"),
  "utf8",
);
const androidManifestPath = resolve(mobileRoot, "android/app/src/main/AndroidManifest.xml");
const tsconfig = await readJson(resolve(mobileRoot, "tsconfig.json"));
const fontFiles = [
  "Vazirmatn-Regular.ttf",
  "Vazirmatn-Medium.ttf",
  "Vazirmatn-SemiBold.ttf",
  "Vazirmatn-Bold.ttf",
  "Vazirmatn-ExtraBold.ttf",
  "Lalezar-Regular.otf",
  "Sora-Regular.otf",
  "Sora-SemiBold.otf",
  "Sora-Bold.otf",
  "Sora-ExtraBold.otf",
];

assert.deepEqual(rootPackage.workspaces, ["frontend", "mobile", "packages/fitician-core"]);
assert.equal(mobilePackage.name, "@fitician/mobile");
assert.equal(mobilePackage.scripts["audit:dependencies"], "node scripts/dependency-audit.mjs");
assert.equal(corePackage.name, "@fitician/core");
assert.match(mobilePackage.dependencies.expo, /^~?57\./);
assert.match(mobilePackage.dependencies["expo-router"], /^~?57\./);
assert.equal(tsconfig.compilerOptions.strict, true);
for (const identifier of ["Fitsho", "Fitition"]) {
  assert.equal(appConfig.includes(identifier), false, `permanent identifier contains ${identifier}`);
}
for (const required of [
  /name:\s*["']Fitician["']/,
  /slug:\s*["']fitician["']/,
  /scheme:\s*["']fitician["']/,
  /package:\s*["']com\.fitician\.app["']/,
  /minSdkVersion:\s*24/,
  /compileSdkVersion:\s*36/,
  /targetSdkVersion:\s*36/,
  /autoVerify:\s*true/,
  /scheme:\s*["']https["']/,
  /pathPrefix:\s*["']\/link["']/,
  /\["expo-sqlite",\s*\{\s*useSQLCipher:\s*true\s*\}\]/,
  /["']expo-background-task["']/,
  /["']expo-notifications["']/,
  /["']expo-font["']/,
  /cameraPermission:\s*["'][^"']+["']/,
  /microphonePermission:\s*false/,
  /photosPermission:\s*false/,
  /withAndroidHardening/,
]) {
  assert.match(appConfig, required);
}
for (const required of [
  /android:allowBackup["']?:\s*["']false["']/,
  /android:usesCleartextTraffic["']?:\s*["']false["']/,
  /fitician_backup_rules/,
  /FLAG_SECURE/,
]) {
  assert.match(androidHardening, required);
}
try {
  const androidManifest = await readFile(androidManifestPath, "utf8");
  assert.match(androidManifest, /android:scheme="fitician"/);
  assert.match(androidManifest, /android:autoVerify="true"/);
  assert.match(androidManifest, /android:allowBackup="false"/);
  assert.match(androidManifest, /android:usesCleartextTraffic="false"/);
  for (const permission of [
    "READ_EXTERNAL_STORAGE",
    "WRITE_EXTERNAL_STORAGE",
    "READ_MEDIA_IMAGES",
    "READ_MEDIA_VIDEO",
    "READ_MEDIA_AUDIO",
    "READ_MEDIA_VISUAL_USER_SELECTED",
    "RECORD_AUDIO",
    "SYSTEM_ALERT_WINDOW",
  ]) {
    assert.match(
      androidManifest,
      new RegExp(`android:name="android\\.permission\\.${permission}"[^>]*tools:node="remove"`),
    );
  }
  for (const identifier of ["Fitsho", "Fitition"]) {
    assert.equal(
      androidManifest.includes(identifier),
      false,
      `generated Android manifest contains ${identifier}`,
    );
  }
} catch (error) {
  if (error?.code !== "ENOENT") {
    throw error;
  }
}
for (const fontFile of fontFiles) {
  const info = await stat(resolve(mobileRoot, "assets/fonts", fontFile));
  assert.ok(info.isFile() && info.size > 0, `${fontFile} must be a non-empty font file`);
}

console.log("Fitician mobile foundation is valid");
