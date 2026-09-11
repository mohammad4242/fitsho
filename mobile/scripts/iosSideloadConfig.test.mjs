import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function loadConfig(sideload) {
  const environment = {
    ...process.env,
    CI: "1",
    APP_VARIANT: "development",
    EXPO_PUBLIC_API_BASE_URL: "http://100.97.78.5:8001",
    EXPO_PUBLIC_FRONTEND_ORIGIN: "http://100.97.78.5:5173",
  };
  if (sideload) environment.IOS_SIDELOAD_BUILD = "1";
  else delete environment.IOS_SIDELOAD_BUILD;

  return JSON.parse(
    execFileSync("npx", ["--no-install", "expo", "config", "--json"], {
      cwd: mobileRoot,
      env: environment,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "inherit"],
    }),
  );
}

test("normal iOS config keeps signing-related capabilities", () => {
  const config = loadConfig(false);
  assert.equal(config.ios.bundleIdentifier, "com.fitician.app");
  assert.deepEqual(config.ios.associatedDomains, ["applinks:app.fitician.example"]);
  assert.equal(config.ios.usesAppleSignIn, true);
  assert.ok(config.plugins.some((plugin) => plugin === "expo-apple-authentication"));
  assert.ok(config.plugins.some((plugin) => Array.isArray(plugin) && plugin[0] === "expo-notifications"));
});

test("sideload iOS config preserves app fundamentals and disables unsupported capabilities", () => {
  const config = loadConfig(true);
  assert.equal(config.ios.bundleIdentifier, "com.fitician.app");
  assert.equal(config.ios.associatedDomains, undefined);
  assert.equal(config.ios.usesAppleSignIn, undefined);
  assert.equal(config.plugins.includes("expo-apple-authentication"), false);
  assert.ok(config.plugins.some((plugin) => Array.isArray(plugin) && plugin[0] === "expo-notifications"));
  assert.equal(config.extra.apiBaseUrl, "http://100.97.78.5:8001");
  assert.equal(config.extra.frontendOrigin, "http://100.97.78.5:5173");
});
