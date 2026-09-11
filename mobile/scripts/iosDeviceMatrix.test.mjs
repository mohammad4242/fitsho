import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import {
  REQUIRED_IOS_DEVICE_TIERS,
  validateIosDeviceMatrix,
} from "./validate-ios-device-matrix.mjs";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

test("covers representative iPhone tiers, iOS support, and required native flows", async () => {
  const matrix = JSON.parse(
    await readFile(resolve(mobileRoot, "ios-device-matrix.json"), "utf8"),
  );

  assert.doesNotThrow(() => validateIosDeviceMatrix(matrix));
  assert.deepEqual(matrix.deviceTiers, REQUIRED_IOS_DEVICE_TIERS);
});

test("rejects a matrix without a physical-device tier", () => {
  assert.throws(
    () => validateIosDeviceMatrix({
      schemaVersion: 1,
      appId: "com.fitician.app",
      minimumOsVersion: "16.0",
      supportedOsMajorVersions: [16, 17, 18, 19],
      deviceTiers: ["small", "standard", "large_dynamic_island", "older_supported"],
      requiredFlows: ["launch", "member", "coach", "physician", "role-boundary", "authentication", "body-analysis-entry"],
      profiles: [],
    }),
    /physical/u,
  );
});
