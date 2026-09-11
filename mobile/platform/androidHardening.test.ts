import { expect, it } from "vitest";
import type { AndroidManifest } from "expo/config-plugins";

import * as androidHardening from "../plugins/withAndroidHardening";
import { TAILSCALE_BACKEND_HOST } from "../config/productionApiConfig";
import {
  ANDROID_BLOCKED_PERMISSIONS,
  FITICIAN_BACKUP_RULES,
  FITICIAN_DATA_EXTRACTION_RULES,
  FITICIAN_DEVELOPMENT_NETWORK_SECURITY_CONFIG,
  FITICIAN_NETWORK_SECURITY_CONFIG,
  applyAndroidSecurityManifest,
  networkSecurityConfigForEnvironment,
  resolveAndroidBuildEnvironment,
} from "../plugins/withAndroidHardening";

type AndroidManifestApplier = (
  manifest: AndroidManifest,
  environment: "development" | "preview" | "production",
) => AndroidManifest;

const applyManifestForEnvironment = applyAndroidSecurityManifest as AndroidManifestApplier;

function manifestWithApplication(): AndroidManifest {
  return {
    manifest: {
      $: {},
      "uses-permission": [{ $: { "android:name": "android.permission.CAMERA" } }],
      application: [{ $: {} }],
    },
  } as unknown as AndroidManifest;
}

it("removes broad storage and overlay permissions from the final Android manifest", () => {
  const manifest = {
    manifest: {
      $: {},
      "uses-permission": [
        { $: { "android:name": "android.permission.CAMERA" } },
        ...ANDROID_BLOCKED_PERMISSIONS.map((name) => ({ $: { "android:name": name } })),
      ],
      application: [{ $: {} }],
    },
  } as unknown as AndroidManifest;

  applyAndroidSecurityManifest(manifest);

  const permissions = manifest.manifest["uses-permission"] as Array<{ $: Record<string, string> }>;
  expect(permissions).toContainEqual({ $: { "android:name": "android.permission.CAMERA" } });
  for (const permission of ANDROID_BLOCKED_PERMISSIONS) {
    expect(permissions).toContainEqual({
      $: { "android:name": permission, "tools:node": "remove" },
    });
  }
  expect(manifest.manifest.application![0].$).toMatchObject({
    "android:allowBackup": "false",
    "android:dataExtractionRules": "@xml/fitician_data_extraction_rules",
    "android:fullBackupContent": "@xml/fitician_backup_rules",
    "android:networkSecurityConfig": "@xml/fitician_network_security_config",
    "android:usesCleartextTraffic": "false",
  });
});

it("excludes all app data from legacy and modern Android backup paths", () => {
  expect(FITICIAN_BACKUP_RULES).toMatch(/<exclude domain="database" path="\."\/>/);
  expect(FITICIAN_BACKUP_RULES).toMatch(/<exclude domain="sharedpref" path="\."\/>/);
  expect(FITICIAN_BACKUP_RULES).toMatch(/<exclude domain="file" path="\."\/>/);
  expect(FITICIAN_DATA_EXTRACTION_RULES).toMatch(/<cloud-backup>/);
  expect(FITICIAN_DATA_EXTRACTION_RULES).toMatch(/<device-transfer>/);
  expect(FITICIAN_DATA_EXTRACTION_RULES).toMatch(/domain="database" path="\."/);
  expect(FITICIAN_DATA_EXTRACTION_RULES).toMatch(/domain="sharedpref" path="\."/);
  expect(FITICIAN_BACKUP_RULES).not.toContain('domain="cache"');
  expect(FITICIAN_BACKUP_RULES).not.toContain('domain="noBackup"');
  expect(FITICIAN_DATA_EXTRACTION_RULES).not.toContain('domain="cache"');
  expect(FITICIAN_DATA_EXTRACTION_RULES).not.toContain('domain="noBackup"');
});

it("requires system-trusted TLS and disallows cleartext traffic in release", () => {
  expect(FITICIAN_NETWORK_SECURITY_CONFIG).toContain("cleartextTrafficPermitted=\"false\"");
  expect(FITICIAN_NETWORK_SECURITY_CONFIG).toContain("certificates src=\"system\"");
  expect(FITICIAN_NETWORK_SECURITY_CONFIG).toContain(
    `<domain includeSubdomains=\"false\">${TAILSCALE_BACKEND_HOST}</domain>`,
  );
});

it("allows cleartext development traffic while retaining the network security resource", () => {
  const manifest = manifestWithApplication();

  applyManifestForEnvironment(manifest, "development");

  expect(manifest.manifest.application![0].$).toMatchObject({
    "android:networkSecurityConfig": "@xml/fitician_network_security_config",
    "android:usesCleartextTraffic": "true",
  });
});

it.each(["preview", "production"] as const)(
  "blocks cleartext traffic for %s builds",
  (environment) => {
    const manifest = manifestWithApplication();

    applyManifestForEnvironment(manifest, environment);

    expect(manifest.manifest.application![0].$).toMatchObject({
      "android:networkSecurityConfig": "@xml/fitician_network_security_config",
      "android:usesCleartextTraffic": "false",
    });
  },
);

it("fails closed to the release policy for an unknown build environment", () => {
  expect(resolveAndroidBuildEnvironment("unexpected")).toBe("production");
});

it("generates a cleartext-enabled development network policy with system trust", () => {
  const policy = networkSecurityConfigForEnvironment("development");

  expect(policy).toBe(FITICIAN_DEVELOPMENT_NETWORK_SECURITY_CONFIG);
  expect(policy).toContain("cleartextTrafficPermitted=\"true\"");
  expect(policy).toContain("certificates src=\"system\"");
});

it.each(["preview", "production"] as const)(
  "generates a system-trusted TLS-only network policy for %s",
  (environment) => {
    const policy = networkSecurityConfigForEnvironment(environment);

    expect(policy).toBe(FITICIAN_NETWORK_SECURITY_CONFIG);
    expect(policy).toContain("cleartextTrafficPermitted=\"false\"");
    expect(policy).toContain("certificates src=\"system\"");
  },
);

it("does not apply the global screenshot block to development activities", () => {
  type MainActivityProject = {
    language: "kt";
    contents: string;
  };
  const applyScreenshotPolicy = (
    androidHardening as unknown as {
      applyAndroidScreenshotPolicy?: (
        project: MainActivityProject,
        environment: "development" | "preview" | "production",
      ) => MainActivityProject;
    }
  ).applyAndroidScreenshotPolicy;

  expect(applyScreenshotPolicy).toEqual(expect.any(Function));
  if (typeof applyScreenshotPolicy !== "function") return;

  const project = applyScreenshotPolicy(
    {
      language: "kt",
      contents: [
        "import android.os.Bundle",
        "import android.view.WindowManager",
        "class MainActivity {",
        "  override fun onCreate(savedInstanceState: Bundle?) {",
        `    ${androidHardening.SCREENSHOT_POLICY_MARKER}`,
        "    window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)",
        "  }",
        "}",
      ].join("\n"),
    },
    "development",
  );

  expect(project.contents).not.toContain(androidHardening.SCREENSHOT_POLICY_MARKER);
  expect(project.contents).not.toContain("FLAG_SECURE");
});

it.each(["preview", "production"] as const)(
  "keeps the global screenshot block for %s activities",
  (environment) => {
    type MainActivityProject = { language: "kt"; contents: string };
    const applyScreenshotPolicy = (
      androidHardening as unknown as {
        applyAndroidScreenshotPolicy?: (
          project: MainActivityProject,
          environment: "development" | "preview" | "production",
        ) => MainActivityProject;
      }
    ).applyAndroidScreenshotPolicy;

    expect(applyScreenshotPolicy).toEqual(expect.any(Function));
    if (typeof applyScreenshotPolicy !== "function") return;

    const project = applyScreenshotPolicy(
      {
        language: "kt",
        contents: [
          "import android.os.Bundle",
          "class MainActivity {",
          "  override fun onCreate(savedInstanceState: Bundle?) {",
          "  }",
          "}",
        ].join("\n"),
      },
      environment,
    );

    expect(project.contents).toContain(androidHardening.SCREENSHOT_POLICY_MARKER);
    expect(project.contents).toContain("FLAG_SECURE");
  },
);
