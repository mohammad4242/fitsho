import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = resolve(mobileRoot, "..");
const mobilePackage = JSON.parse(await readFile(resolve(mobileRoot, "package.json"), "utf8"));
const lockPath = resolve(projectRoot, "package-lock.json");
const lock = JSON.parse(await readFile(lockPath, "utf8"));

assert.equal(lock.lockfileVersion, 3, "root npm lockfile must use lockfile version 3");
const expected = {
  expo: "57",
  "expo-build-properties": "57",
  "expo-router": "57",
  react: "19",
  "react-native": "0.86",
};

for (const [name, majorMinor] of Object.entries(expected)) {
  const declared = mobilePackage.dependencies[name];
  assert.equal(typeof declared, "string", `${name} must be declared by mobile`);
  const locked = lock.packages[`node_modules/${name}`]?.version;
  assert.equal(typeof locked, "string", `${name} must be resolved in the root lockfile`);
  assert.match(locked, new RegExp(`^${majorMinor.replace(".", "\\.")}(?:\\.|$)`));
}

console.log("Fitician mobile dependency versions are valid");
