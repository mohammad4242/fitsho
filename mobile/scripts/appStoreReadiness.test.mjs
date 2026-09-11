import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { validateAppStoreReadiness } from "./validate-app-store-readiness.mjs";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

async function inputs() {
  return {
    appConfig: await readFile(resolve(mobileRoot, "app.config.ts"), "utf8"),
    metadata: JSON.parse(await readFile(resolve(mobileRoot, "app-store/store-metadata.json"), "utf8")),
    mobileRoot,
  };
}

test("iOS App Store source package has identity, bilingual metadata, and review docs", async () => {
  const result = await validateAppStoreReadiness(await inputs());

  assert.equal(result.applicationId, "com.fitician.app");
  assert.deepEqual(result.locales, ["fa", "en"]);
});

test("production App Store metadata requires secure URLs and protected identifiers", async () => {
  await assert.rejects(
    validateAppStoreReadiness({ ...(await inputs()), production: true, env: {} }),
    /FITICIAN_PUBLIC_WEB_ORIGIN/u,
  );

  await assert.rejects(
    validateAppStoreReadiness({
      ...(await inputs()),
      production: true,
      env: {
        FITICIAN_PUBLIC_WEB_ORIGIN: "https://fitician.example",
        FITICIAN_SUPPORT_URL: "http://support.fitician.example",
        FITICIAN_SUPPORT_EMAIL: "support@fitician.example",
        APPLE_TEAM_ID: "AB12CD34EF",
        APPLE_APP_STORE_CONNECT_APP_ID: "1234567890",
        FITICIAN_APP_REVIEW_ACCOUNT: "review@example.com",
        FITICIAN_APP_REVIEW_PASSWORD: "not-a-real-password",
      },
    }),
    /support URL must use HTTPS/u,
  );
});

test("production App Store URLs resolve without storing live credentials", async () => {
  const result = await validateAppStoreReadiness({
    ...(await inputs()),
    production: true,
    env: {
      FITICIAN_PUBLIC_WEB_ORIGIN: "https://fitician.example",
      FITICIAN_SUPPORT_URL: "https://fitician.example/support",
      FITICIAN_SUPPORT_EMAIL: "support@fitician.example",
      APPLE_TEAM_ID: "AB12CD34EF",
      APPLE_APP_STORE_CONNECT_APP_ID: "1234567890",
      FITICIAN_APP_REVIEW_ACCOUNT: "review@example.com",
      FITICIAN_APP_REVIEW_PASSWORD: "not-a-real-password",
    },
  });

  assert.equal(result.privacyUrl, "https://fitician.example/privacy");
  assert.equal(result.accountDeletionUrl, "https://fitician.example/delete-account");
  assert.equal(result.supportUrl, "https://fitician.example/support");
});
