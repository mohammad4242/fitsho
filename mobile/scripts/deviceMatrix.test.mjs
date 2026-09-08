import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { validateDeviceMatrix } from "./validate-device-matrix.mjs";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

test("covers every required Android API level and device tier", async () => {
  const matrix = JSON.parse(
    await readFile(resolve(mobileRoot, "device-matrix.json"), "utf8"),
  );

  assert.doesNotThrow(() => validateDeviceMatrix(matrix));
});
