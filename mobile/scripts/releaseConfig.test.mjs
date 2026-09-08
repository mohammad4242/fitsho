import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { validateReleaseConfig } from "./validate-release-config.mjs";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

test("keeps EAS profiles isolated and remotely signed", async () => {
  const easConfig = JSON.parse(await readFile(resolve(mobileRoot, "eas.json"), "utf8"));
  const appConfig = await readFile(resolve(mobileRoot, "app.config.ts"), "utf8");

  assert.doesNotThrow(() => validateReleaseConfig(easConfig, appConfig));
});
