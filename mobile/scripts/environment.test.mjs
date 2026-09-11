import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { parseEnvFile, validateEnvironment } from "./environment.mjs";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

test("parses and validates each Fitician mobile environment", () => {
  const values = parseEnvFile(
    "APP_VARIANT=preview\nEXPO_PUBLIC_API_BASE_URL=https://api-preview.fitician.example\nEXPO_PUBLIC_FRONTEND_ORIGIN=https://preview.fitician.example\nEXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID=\nFITICIAN_APP_LINK_HOST=preview.fitician.example\n",
  );

  assert.equal(values.APP_VARIANT, "preview");
  assert.doesNotThrow(() => validateEnvironment("preview", values));
  assert.doesNotThrow(() => validateEnvironment("production", {
    ...values,
    APP_VARIANT: "production",
    EXPO_PUBLIC_API_BASE_URL: "http://100.97.78.5:8001",
    EXPO_PUBLIC_FRONTEND_ORIGIN: "http://100.97.78.5:5173",
    FITICIAN_APP_LINK_HOST: "app.fitician.example",
  }, { allowPlaceholder: true }));
  assert.throws(
    () =>
      validateEnvironment("production", {
        ...values,
        APP_VARIANT: "production",
        EXPO_PUBLIC_API_BASE_URL: "https://api.fitician.example",
        EXPO_PUBLIC_FRONTEND_ORIGIN: "http://100.97.78.5:5173",
        FITICIAN_APP_LINK_HOST: "app.fitician.example",
      }),
    /Tailscale backend/,
  );
});

test("requires a trusted HTTPS frontend origin outside development", () => {
  assert.throws(
    () =>
      validateEnvironment("preview", {
        APP_VARIANT: "preview",
        EXPO_PUBLIC_API_BASE_URL: "https://api-preview.fitician.example",
        EXPO_PUBLIC_FRONTEND_ORIGIN: "http://preview.fitician.example",
        FITICIAN_APP_LINK_HOST: "preview.fitician.example",
      }),
    /EXPO_PUBLIC_FRONTEND_ORIGIN must use HTTPS outside development/,
  );
});

test("validates each configured Google client ID without blocking the other platform", () => {
  const base = {
    APP_VARIANT: "preview",
    EXPO_PUBLIC_API_BASE_URL: "https://api-preview.fitician.example",
    EXPO_PUBLIC_FRONTEND_ORIGIN: "https://preview.fitician.example",
    FITICIAN_APP_LINK_HOST: "preview.fitician.example",
  };

  assert.doesNotThrow(() => validateEnvironment("preview", {
    ...base,
    EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID: "android.apps.googleusercontent.com",
  }));
  assert.throws(
    () => validateEnvironment("preview", {
      ...base,
      EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID: "android-client",
      EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID: "ios-client",
    }),
    /must be a Google OAuth client ID/u,
  );
  assert.doesNotThrow(() => validateEnvironment("preview", {
    ...base,
    EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID: "android.apps.googleusercontent.com",
    EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID: "ios.apps.googleusercontent.com",
  }));
});

test("documents emulator and physical Android development API targets", async () => {
  const example = await readFile(resolve(mobileRoot, ".env.development.example"), "utf8");

  assert.match(example, /10\.0\.2\.2:8001/u);
  assert.match(example, /physical Android|LAN|Tailscale|laptop/i);
  assert.match(example, /<[^>]*(?:LAN|TAILSCALE|LAPTOP)[^>]*>.*:8001/iu);
});
