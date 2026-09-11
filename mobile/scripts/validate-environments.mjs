import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseEnvFile, validateEnvironment } from "./environment.mjs";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const schema = JSON.parse(await readFile(resolve(mobileRoot, "config/environment.schema.json"), "utf8"));
const schemaKeys = new Set(Object.keys(schema.properties));

for (const variant of ["development", "preview", "production"]) {
  const path = resolve(mobileRoot, `.env.${variant}.example`);
  const values = parseEnvFile(await readFile(path, "utf8"));
  assert.deepEqual(Object.keys(values).sort(), [...schemaKeys].sort());
  for (const required of schema.required) {
    assert.ok(values[required], `${required} is required for ${variant}`);
  }
  validateEnvironment(variant, values, {
    allowPlaceholder: true,
    requireGoogleIosClientId: variant !== "development",
  });
}

console.log("Fitician mobile environment examples are valid");
