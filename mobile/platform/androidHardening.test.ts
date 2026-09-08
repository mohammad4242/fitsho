import { expect, it } from "vitest";
import type { AndroidManifest } from "expo/config-plugins";

import {
  ANDROID_BLOCKED_PERMISSIONS,
  FITICIAN_BACKUP_RULES,
  FITICIAN_DATA_EXTRACTION_RULES,
  FITICIAN_NETWORK_SECURITY_CONFIG,
  applyAndroidSecurityManifest,
} from "../plugins/withAndroidHardening";

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
});

it("requires system-trusted TLS and disallows cleartext traffic in release", () => {
  expect(FITICIAN_NETWORK_SECURITY_CONFIG).toContain("cleartextTrafficPermitted=\"false\"");
  expect(FITICIAN_NETWORK_SECURITY_CONFIG).toContain("certificates src=\"system\"");
});
