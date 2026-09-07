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
  "@fitician/core": { declared: "0.1.0", version: /^0\.1\./ },
  "@react-native-community/netinfo": { declared: "^12.0.1", version: /^12\./ },
  "@tanstack/react-query": { declared: "^5.102.8", version: /^5\./ },
  "expo-background-task": { declared: "~57.0.16", version: /^57\./ },
  "expo-crypto": { declared: "~57.0.2", version: /^57\./ },
  expo: { declared: "~57.0.0", version: /^57\./ },
  "expo-build-properties": { declared: "~57.0.2", version: /^57\./ },
  "expo-constants": { declared: "~57.0.2", version: /^57\./ },
  "expo-dev-client": { declared: "~57.0.2", version: /^57\./ },
  "expo-font": { declared: "~57.0.3", version: /^57\./ },
  "expo-file-system": { declared: "~57.0.6", version: /^57\./ },
  "expo-linking": { declared: "~57.0.1", version: /^57\./ },
  "expo-router": { declared: "~57.0.2", version: /^57\./ },
  "expo-secure-store": { declared: "~57.0.3", version: /^57\./ },
  "expo-sqlite": { declared: "~57.0.2", version: /^57\./ },
  "expo-splash-screen": { declared: "~57.0.1", version: /^57\./ },
  "expo-status-bar": { declared: "~57.0.0", version: /^57\./ },
  "expo-system-ui": { declared: "~57.0.0", version: /^57\./ },
  "expo-task-manager": { declared: "~57.0.16", version: /^57\./ },
  react: { declared: "19.2.3", version: /^19\.2\./ },
  "react-dom": { declared: "19.2.3", version: /^19\.2\./ },
  "react-native": { declared: "0.86.3", version: /^0\.86\./ },
  "react-native-gesture-handler": { declared: "~2.32.0", version: /^2\.32\./ },
  "react-native-reanimated": { declared: "4.5.1", version: /^4\.5\./ },
  "react-native-safe-area-context": { declared: "~5.7.0", version: /^5\.7\./ },
  "react-native-screens": { declared: "~4.26.0", version: /^4\.26\./ },
  "react-native-web": { declared: "~0.21.0", version: /^0\.21\./ },
  "react-native-worklets": { declared: "0.10.1", version: /^0\.10\./ },
};

for (const [name, requirement] of Object.entries(expected)) {
  const declared = mobilePackage.dependencies[name];
  assert.equal(declared, requirement.declared, `${name} declaration drifted`);
  const locked = name === "@fitician/core"
    ? lock.packages["packages/fitician-core"]?.version
    : lock.packages[`node_modules/${name}`]?.version;
  assert.equal(typeof locked, "string", `${name} must be resolved in the root lockfile`);
  assert.match(locked, requirement.version, `${name} resolved outside the SDK-57 pin`);
}

console.log("Fitician mobile dependency versions are valid");
