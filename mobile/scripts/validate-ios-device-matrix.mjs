import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const REQUIRED_IOS_DEVICE_TIERS = [
  "small",
  "standard",
  "large_dynamic_island",
  "older_supported",
  "physical_device",
];

export const REQUIRED_IOS_FLOWS = [
  "launch",
  "member",
  "coach",
  "physician",
  "role-boundary",
  "authentication",
  "body-analysis-entry",
];

export const REQUIRED_IOS_OS_TRACKS = [
  "minimum-supported",
  "previous-supported",
  "current-supported",
];

const safeIdentifier = /^[a-z0-9]+(?:-[a-z0-9]+)*$/u;
const safeDeviceFamily = /^[A-Za-z0-9 ,_-]+$/u;

export function validateIosDeviceMatrix(matrix) {
  assert.equal(matrix.schemaVersion, 1, "iOS device matrix schema must be version 1");
  assert.equal(matrix.appId, "com.fitician.app");
  assert.match(matrix.minimumOsVersion, /^\d+\.\d+$/u);
  assert.ok(Array.isArray(matrix.deviceTiers), "iOS device tiers are required");
  for (const tier of REQUIRED_IOS_DEVICE_TIERS) {
    assert.ok(matrix.deviceTiers.includes(tier), `missing iOS ${tier} device tier`);
  }
  assert.deepEqual(matrix.deviceTiers, REQUIRED_IOS_DEVICE_TIERS);
  assert.deepEqual(matrix.requiredFlows, REQUIRED_IOS_FLOWS);
  assert.deepEqual(matrix.osTracks, REQUIRED_IOS_OS_TRACKS);

  const profiles = matrix.profiles;
  assert.ok(Array.isArray(profiles) && profiles.length >= REQUIRED_IOS_DEVICE_TIERS.length);
  assert.equal(new Set(profiles.map((profile) => profile.id)).size, profiles.length);
  for (const profile of profiles) {
    assert.match(profile.id, safeIdentifier, `invalid iOS profile id: ${profile.id}`);
    assert.match(profile.deviceFamily, safeDeviceFamily, `${profile.id} device family is invalid`);
    assert.ok(matrix.deviceTiers.includes(profile.tier), `${profile.id} has an unknown device tier`);
    assert.ok(matrix.osTracks.includes(profile.osTrack), `${profile.id} has an unknown OS track`);
    assert.ok(
      profile.execution === "simulator" || profile.execution === "physical",
      `${profile.id} execution target is invalid`,
    );
  }

  for (const tier of REQUIRED_IOS_DEVICE_TIERS) {
    assert.ok(
      profiles.some((profile) => profile.tier === tier),
      `missing iOS ${tier} device tier`,
    );
  }
  for (const osTrack of REQUIRED_IOS_OS_TRACKS) {
    assert.ok(
      profiles.some((profile) => profile.osTrack === osTrack),
      `missing iOS ${osTrack} OS track`,
    );
  }
  assert.ok(
    profiles.some((profile) => profile.execution === "physical"),
    "iOS matrix must include a physical-device profile",
  );
  return matrix;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const matrix = JSON.parse(await readFile(resolve(mobileRoot, "ios-device-matrix.json"), "utf8"));
  validateIosDeviceMatrix(matrix);
  console.log("Fitician iOS device matrix is valid");
}
