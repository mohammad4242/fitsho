import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { validateMaestroFlows } from "./validate-maestro.mjs";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const maestroRoot = resolve(mobileRoot, ".maestro");

async function readYamlFiles(directory, prefix = "") {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = {};
  for (const entry of entries) {
    const relativePath = prefix ? `${prefix}/${entry.name}` : entry.name;
    const fullPath = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      Object.assign(files, await readYamlFiles(fullPath, relativePath));
    } else if (entry.name.endsWith(".yaml")) {
      files[relativePath] = await readFile(fullPath, "utf8");
    }
  }
  return files;
}

test("keeps the Maestro acceptance flows Fitician-only and environment-driven", async () => {
  const flows = await readYamlFiles(maestroRoot);
  assert.doesNotThrow(() => validateMaestroFlows(flows));
});
