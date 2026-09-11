import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const requiredDocuments = [
  "app-store/README.md",
  "app-store/privacy.md",
  "app-store/review-notes.md",
  "app-store/tester-instructions.md",
  "app-store/screenshots/README.md",
];

function requiredEnvironment(env, name) {
  const value = env[name]?.trim();
  assert.ok(value, `${name} must be supplied for production App Store metadata`);
  return value;
}

function assertHttpsUrl(value, name) {
  const parsed = new URL(value);
  assert.equal(parsed.protocol, "https:", `${name} must use HTTPS`);
  assert.ok(parsed.hostname, `${name} must include a hostname`);
  return parsed.toString().replace(/\/$/u, "");
}

export async function validateAppStoreReadiness({
  appConfig,
  metadata,
  mobileRoot: root = mobileRoot,
  production = false,
  env = process.env,
}) {
  assert.match(appConfig, /name:\s*["']Fitician["']/u);
  assert.match(appConfig, /scheme:\s*["']fitician["']/u);
  assert.match(appConfig, /bundleIdentifier:\s*["']com\.fitician\.app["']/u);
  assert.match(appConfig, /associatedDomains/u);
  assert.match(appConfig, /usesAppleSignIn:\s*true/u);
  assert.match(appConfig, /runtimeVersion:\s*\{\s*policy:\s*["']appVersion["']/u);
  assert.match(appConfig, /["']expo-apple-authentication["']/u);
  assert.match(appConfig, /EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID/u);
  assert.match(appConfig, /withIosHardening/u);
  assert.doesNotMatch(appConfig, /Fitsho|Fitition/u);

  assert.equal(metadata.platform, "ios");
  assert.equal(metadata.applicationId, "com.fitician.app");
  assert.equal(metadata.applicationName, "Fitician");
  assert.equal(metadata.developerName, "Fitician");
  assert.deepEqual(Object.keys(metadata.locales), ["fa", "en"]);
  for (const locale of Object.values(metadata.locales)) {
    assert.ok(locale.title && locale.subtitle && locale.description);
  }

  assert.equal(metadata.links.publicWebOriginEnv, "FITICIAN_PUBLIC_WEB_ORIGIN");
  assert.equal(metadata.links.privacyPath, "/privacy");
  assert.equal(metadata.links.accountDeletionPath, "/delete-account");
  assert.equal(metadata.links.supportUrlEnv, "FITICIAN_SUPPORT_URL");
  assert.equal(metadata.links.supportEmailEnv, "FITICIAN_SUPPORT_EMAIL");
  assert.equal(metadata.identifiers.appleTeamIdEnv, "APPLE_TEAM_ID");
  assert.equal(metadata.identifiers.appStoreConnectAppIdEnv, "APPLE_APP_STORE_CONNECT_APP_ID");
  assert.equal(metadata.review.demoAccountEnv, "FITICIAN_APP_REVIEW_ACCOUNT");
  assert.equal(metadata.review.demoPasswordEnv, "FITICIAN_APP_REVIEW_PASSWORD");
  assert.equal(metadata.contentRating.status, "draft");
  assert.deepEqual(metadata.screenshots.requiredLocales, ["fa", "en"]);

  for (const document of requiredDocuments) {
    const contents = await readFile(resolve(root, document), "utf8");
    assert.ok(contents.trim(), `${document} must not be empty`);
  }

  if (production) {
    const origin = assertHttpsUrl(
      requiredEnvironment(env, "FITICIAN_PUBLIC_WEB_ORIGIN"),
      "public web origin",
    );
    const supportUrl = assertHttpsUrl(
      requiredEnvironment(env, "FITICIAN_SUPPORT_URL"),
      "support URL",
    );
    const supportEmail = requiredEnvironment(env, "FITICIAN_SUPPORT_EMAIL");
    assert.match(supportEmail, /^[^\s@]+@[^\s@]+\.[^\s@]+$/u, "support email is invalid");
    const teamId = requiredEnvironment(env, "APPLE_TEAM_ID");
    assert.match(teamId, /^[A-Z0-9]{10}$/u, "Apple Team ID is invalid");
    const appStoreConnectAppId = requiredEnvironment(env, "APPLE_APP_STORE_CONNECT_APP_ID");
    assert.match(appStoreConnectAppId, /^\d+$/u, "App Store Connect App ID is invalid");
    requiredEnvironment(env, "FITICIAN_APP_REVIEW_ACCOUNT");
    requiredEnvironment(env, "FITICIAN_APP_REVIEW_PASSWORD");
    return {
      applicationId: metadata.applicationId,
      locales: Object.keys(metadata.locales),
      privacyUrl: `${origin}${metadata.links.privacyPath}`,
      accountDeletionUrl: `${origin}${metadata.links.accountDeletionPath}`,
      supportUrl,
    };
  }

  return {
    applicationId: metadata.applicationId,
    locales: Object.keys(metadata.locales),
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const metadata = JSON.parse(await readFile(resolve(mobileRoot, "app-store/store-metadata.json"), "utf8"));
  const appConfig = await readFile(resolve(mobileRoot, "app.config.ts"), "utf8");
  const result = await validateAppStoreReadiness({
    appConfig,
    metadata,
    production: process.argv.includes("--production"),
  });
  console.log(`Fitician App Store readiness is valid for ${result.locales.join(", ")}`);
}
