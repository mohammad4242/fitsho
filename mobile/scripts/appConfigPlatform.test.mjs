import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";

function loadConfig(platform, variant, googleIosClientId = "") {
  return spawnSync(process.execPath, ["--input-type=module", "-e", `
    import { loadModuleSync } from '@expo/require-utils';
    import { resolve } from 'node:path';
    const { default: config } = loadModuleSync(resolve('app.config.ts'));
    console.log(config.ios.bundleIdentifier);
  `], {
    cwd: new URL("../", import.meta.url),
    encoding: "utf8",
    env: {
      ...process.env,
      EAS_BUILD_PLATFORM: platform,
      APP_VARIANT: variant,
      EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID: googleIosClientId,
      EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID: "android.apps.googleusercontent.com",
      EXPO_PUBLIC_API_BASE_URL: "https://api.example.com",
      EXPO_PUBLIC_FRONTEND_ORIGIN: "https://app.example.com",
      FITICIAN_APP_LINK_HOST: "app.example.com",
    },
  });
}

test("Android preview config does not require credentials for iOS Google login", () => {
  const result = loadConfig("android", "preview");
  assert.equal(result.status, 0, result.stderr);
});

test("iOS preview still requires Google client configuration", () => {
  const result = loadConfig("ios", "preview");
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID is required/u);
  const configured = loadConfig("ios", "preview", "ios.apps.googleusercontent.com");
  assert.equal(configured.status, 0, configured.stderr);
});

test("development config can build before Google credentials are provisioned", () => {
  const result = loadConfig("ios", "development");
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /com\.fitician\.app/u);
});
