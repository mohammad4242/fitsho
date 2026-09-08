import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const requiredAssets = {
  icon: { path: "assets/branding/fitician-icon.png", width: 1024, height: 1024 },
  adaptiveForeground: {
    path: "assets/branding/fitician-adaptive-foreground.png",
    width: 1024,
    height: 1024,
  },
  splash: { path: "assets/branding/fitician-splash.png", width: 1600, height: 1600 },
};

const requiredDocuments = [
  "play-store/data-safety.md",
  "play-store/health-declaration.md",
  "play-store/content-rating.md",
  "play-store/privacy-and-deletion.md",
  "play-store/tester-instructions.md",
  "play-store/screenshots/README.md",
];

function pngDimensions(buffer) {
  assert.equal(buffer.readUInt32BE(0), 0x89504e47, "asset is not a PNG");
  assert.equal(buffer.readUInt32BE(4), 0x0d0a1a0a, "asset is not a PNG");
  assert.equal(buffer.toString("ascii", 12, 16), "IHDR", "PNG has no IHDR chunk");
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
}

function requiredEnvironment(env, name) {
  const value = env[name]?.trim();
  assert.ok(value, `${name} must be supplied for production store metadata`);
  return value;
}

function assertHttpsUrl(value, name) {
  const parsed = new URL(value);
  assert.equal(parsed.protocol, "https:", `${name} must use HTTPS`);
  assert.ok(parsed.hostname, `${name} must include a hostname`);
  return parsed.toString().replace(/\/$/u, "");
}

export async function validateStoreReadiness({
  appConfig,
  metadata,
  mobileRoot: root = mobileRoot,
  production = false,
  env = process.env,
}) {
  assert.match(appConfig, /name:\s*["']Fitician["']/u);
  assert.match(appConfig, /scheme:\s*["']fitician["']/u);
  assert.match(appConfig, /package:\s*["']com\.fitician\.app["']/u);
  assert.match(appConfig, /compileSdkVersion:\s*36/u);
  assert.match(appConfig, /targetSdkVersion:\s*36/u);
  assert.doesNotMatch(appConfig, /Fitsho|Fitition/u);

  const expectedConfigPaths = {
    icon: requiredAssets.icon.path,
    adaptiveForeground: requiredAssets.adaptiveForeground.path,
    splash: requiredAssets.splash.path,
  };
  for (const [name, relativePath] of Object.entries(expectedConfigPaths)) {
    assert.match(appConfig, new RegExp(relativePath.replaceAll(".", "\\."), "u"), `${name} is not configured`);
  }

  for (const asset of Object.values(requiredAssets)) {
    const dimensions = pngDimensions(await readFile(resolve(root, asset.path)));
    assert.deepEqual(dimensions, { width: asset.width, height: asset.height }, `${asset.path} dimensions`);
  }

  assert.equal(metadata.applicationId, "com.fitician.app");
  assert.equal(metadata.applicationName, "Fitician");
  assert.equal(metadata.developerName, "Fitician");
  assert.deepEqual(Object.keys(metadata.locales), ["fa", "en"]);
  for (const locale of Object.values(metadata.locales)) {
    assert.ok(locale.title && locale.shortDescription && locale.fullDescription);
  }
  assert.equal(metadata.links.publicWebOriginEnv, "FITICIAN_PUBLIC_WEB_ORIGIN");
  assert.equal(metadata.links.privacyPath, "/privacy");
  assert.equal(metadata.links.accountDeletionPath, "/delete-account");
  assert.equal(metadata.links.supportEmailEnv, "FITICIAN_SUPPORT_EMAIL");
  assert.equal(metadata.contentRating.status, "draft");

  for (const document of requiredDocuments) {
    await readFile(resolve(root, document), "utf8");
  }

  if (production) {
    const origin = assertHttpsUrl(requiredEnvironment(env, "FITICIAN_PUBLIC_WEB_ORIGIN"), "public web origin");
    const supportEmail = requiredEnvironment(env, "FITICIAN_SUPPORT_EMAIL");
    assert.match(supportEmail, /^[^\s@]+@[^\s@]+\.[^\s@]+$/u, "support email is invalid");
    return {
      applicationId: metadata.applicationId,
      locales: Object.keys(metadata.locales),
      privacyUrl: `${origin}${metadata.links.privacyPath}`,
      accountDeletionUrl: `${origin}${metadata.links.accountDeletionPath}`,
      supportEmail,
    };
  }

  return {
    applicationId: metadata.applicationId,
    locales: Object.keys(metadata.locales),
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const metadata = JSON.parse(await readFile(resolve(mobileRoot, "play-store/store-metadata.json"), "utf8"));
  const appConfig = await readFile(resolve(mobileRoot, "app.config.ts"), "utf8");
  const result = await validateStoreReadiness({
    appConfig,
    metadata,
    production: process.argv.includes("--production"),
  });
  console.log(`Fitician store readiness is valid for ${result.locales.join(", ")}`);
}
