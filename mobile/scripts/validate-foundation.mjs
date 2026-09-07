import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = resolve(mobileRoot, "..");

const readJson = async (path) => JSON.parse(await readFile(path, "utf8"));

const rootPackage = await readJson(resolve(projectRoot, "package.json"));
const mobilePackage = await readJson(resolve(mobileRoot, "package.json"));
const corePackage = await readJson(resolve(projectRoot, "packages/fitician-core/package.json"));
const appConfig = await readFile(resolve(mobileRoot, "app.config.ts"), "utf8");
const tsconfig = await readJson(resolve(mobileRoot, "tsconfig.json"));

assert.deepEqual(rootPackage.workspaces, ["frontend", "mobile", "packages/fitician-core"]);
assert.equal(mobilePackage.name, "@fitician/mobile");
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
  /\["expo-sqlite",\s*\{\s*useSQLCipher:\s*true\s*\}\]/,
]) {
  assert.match(appConfig, required);
}

console.log("Fitician mobile foundation is valid");
