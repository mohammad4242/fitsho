import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const REQUIRED_ANDROID_API_LEVELS = [24, 29, 33, 36];

export function validateDeviceMatrix(matrix) {
  assert.equal(matrix.schemaVersion, 1, "device matrix schema must be version 1");
  assert.equal(matrix.appId, "com.fitician.app");
  assert.equal(matrix.minSdkVersion, 24);
  assert.equal(matrix.targetSdkVersion, 36);
  assert.deepEqual(matrix.apiLevels, REQUIRED_ANDROID_API_LEVELS);
  assert.deepEqual(matrix.physicalDeviceTiers, ["low", "mid"]);
  assert.deepEqual(matrix.requiredFlows, ["launch", "member", "coach", "physician", "role-boundary"]);

  const profiles = matrix.profiles;
  assert.ok(Array.isArray(profiles) && profiles.length >= REQUIRED_ANDROID_API_LEVELS.length);
  assert.equal(new Set(profiles.map((profile) => profile.id)).size, profiles.length);
  for (const apiLevel of REQUIRED_ANDROID_API_LEVELS) {
    const profile = profiles.find((candidate) => candidate.apiLevel === apiLevel);
    assert.ok(profile, `missing emulator profile for API ${apiLevel}`);
    assert.match(profile.device, /^[A-Za-z0-9 _-]+$/);
    assert.ok(profile.tier === "low" || profile.tier === "mid");
  }

  for (const tier of matrix.physicalDeviceTiers) {
    assert.ok(
      profiles.some((profile) => profile.physicalTier === tier),
      `missing representative physical ${tier}-range device tier`,
    );
  }
  return matrix;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const matrix = JSON.parse(await readFile(resolve(mobileRoot, "device-matrix.json"), "utf8"));
  validateDeviceMatrix(matrix);
  console.log("Fitician Android device matrix is valid");
}
