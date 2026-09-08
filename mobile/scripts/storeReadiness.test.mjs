import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { validateStoreReadiness } from "./validate-store-readiness.mjs";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

test("Fitician store package has branded assets, exact identity, and bilingual copy", async () => {
  const appConfig = await readFile(resolve(mobileRoot, "app.config.ts"), "utf8");
  const metadata = JSON.parse(await readFile(resolve(mobileRoot, "play-store/store-metadata.json"), "utf8"));

  const result = await validateStoreReadiness({
    appConfig,
    metadata,
    mobileRoot,
    production: false,
  });

  assert.equal(result.applicationId, "com.fitician.app");
  assert.deepEqual(result.locales, ["fa", "en"]);
});

test("production store links must be supplied as secure runtime configuration", async () => {
  const appConfig = await readFile(resolve(mobileRoot, "app.config.ts"), "utf8");
  const metadata = JSON.parse(await readFile(resolve(mobileRoot, "play-store/store-metadata.json"), "utf8"));

  await assert.rejects(
    validateStoreReadiness({ appConfig, metadata, mobileRoot, production: true, env: {} }),
    /FITICIAN_PUBLIC_WEB_ORIGIN/u,
  );
});

test("production store links resolve to the public privacy and deletion routes", async () => {
  const appConfig = await readFile(resolve(mobileRoot, "app.config.ts"), "utf8");
  const metadata = JSON.parse(await readFile(resolve(mobileRoot, "play-store/store-metadata.json"), "utf8"));

  await assert.doesNotReject(async () => {
    const result = await validateStoreReadiness({
      appConfig,
      metadata,
      mobileRoot,
      production: true,
      env: {
        FITICIAN_PUBLIC_WEB_ORIGIN: "https://fitician.example",
        FITICIAN_SUPPORT_EMAIL: "support@fitician.example",
      },
    });
    assert.equal(result.privacyUrl, "https://fitician.example/privacy");
    assert.equal(result.accountDeletionUrl, "https://fitician.example/delete-account");
  });
});
