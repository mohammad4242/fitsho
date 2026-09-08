import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

import type { AndroidManifest, ConfigPlugin } from "expo/config-plugins.js";
import {
  AndroidConfig,
  withAndroidManifest,
  withDangerousMod,
  withMainActivity,
} from "expo/config-plugins.js";

export const ANDROID_BLOCKED_PERMISSIONS = [
  "android.permission.READ_EXTERNAL_STORAGE",
  "android.permission.WRITE_EXTERNAL_STORAGE",
  "android.permission.READ_MEDIA_IMAGES",
  "android.permission.READ_MEDIA_VIDEO",
  "android.permission.READ_MEDIA_AUDIO",
  "android.permission.READ_MEDIA_VISUAL_USER_SELECTED",
  "android.permission.RECORD_AUDIO",
  "android.permission.SYSTEM_ALERT_WINDOW",
] as const;

export const FITICIAN_BACKUP_RULES = `<?xml version="1.0" encoding="utf-8"?>
<full-backup-content>
    <exclude domain="root" path="."/>
    <exclude domain="file" path="."/>
    <exclude domain="database" path="."/>
    <exclude domain="sharedpref" path="."/>
    <exclude domain="external" path="."/>
    <exclude domain="cache" path="."/>
    <exclude domain="noBackup" path="."/>
</full-backup-content>
`;

export const FITICIAN_DATA_EXTRACTION_RULES = `<?xml version="1.0" encoding="utf-8"?>
<data-extraction-rules>
    <cloud-backup>
        <exclude domain="root" path="."/>
        <exclude domain="file" path="."/>
        <exclude domain="database" path="."/>
        <exclude domain="sharedpref" path="."/>
        <exclude domain="external" path="."/>
        <exclude domain="cache" path="."/>
        <exclude domain="noBackup" path="."/>
    </cloud-backup>
    <device-transfer>
        <exclude domain="root" path="."/>
        <exclude domain="file" path="."/>
        <exclude domain="database" path="."/>
        <exclude domain="sharedpref" path="."/>
        <exclude domain="external" path="."/>
        <exclude domain="cache" path="."/>
        <exclude domain="noBackup" path="."/>
    </device-transfer>
</data-extraction-rules>
`;

export const FITICIAN_NETWORK_SECURITY_CONFIG = `<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system"/>
        </trust-anchors>
    </base-config>
</network-security-config>
`;

export const SCREENSHOT_POLICY_MARKER = "// Fitician sensitive-screen screenshot policy";
const screenshotFlag =
  "window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)";

type AndroidManifestLike = Pick<AndroidManifest, "manifest">;

export function applyAndroidSecurityManifest<T extends AndroidManifestLike>(manifest: T): T {
  const root = manifest.manifest;
  root.$ = {
    ...root.$,
    "xmlns:tools": "http://schemas.android.com/tools",
  };

  const blockedPermissions = new Set<string>(ANDROID_BLOCKED_PERMISSIONS);
  root["uses-permission"] = (root["uses-permission"] ?? [])
    .filter((permission) => !blockedPermissions.has(permission.$["android:name"]))
    .concat(
      ANDROID_BLOCKED_PERMISSIONS.map((permission) => ({
        $: { "android:name": permission, "tools:node": "remove" },
      })),
    );

  const application = root.application?.[0];
  if (application) {
    application.$ = {
      ...application.$,
      "android:allowBackup": "false",
      "android:dataExtractionRules": "@xml/fitician_data_extraction_rules",
      "android:fullBackupContent": "@xml/fitician_backup_rules",
      "android:networkSecurityConfig": "@xml/fitician_network_security_config",
      "android:usesCleartextTraffic": "false",
    };
  }

  return manifest;
}

function withSecurityManifest(config: Parameters<ConfigPlugin>[0]): ReturnType<ConfigPlugin> {
  return withAndroidManifest(config, (mod) => {
    mod.modResults = applyAndroidSecurityManifest(mod.modResults);
    return mod;
  });
}

function withSecurityResources(config: Parameters<ConfigPlugin>[0]): ReturnType<ConfigPlugin> {
  return withDangerousMod(config, ["android", async (mod) => {
    if (!mod.modRequest.introspect) {
      const xmlDirectory = join(
        mod.modRequest.platformProjectRoot,
        "app",
        "src",
        "main",
        "res",
        "xml",
      );
      await mkdir(xmlDirectory, { recursive: true });
      await Promise.all([
        writeFile(join(xmlDirectory, "fitician_backup_rules.xml"), FITICIAN_BACKUP_RULES),
        writeFile(
          join(xmlDirectory, "fitician_data_extraction_rules.xml"),
          FITICIAN_DATA_EXTRACTION_RULES,
        ),
        writeFile(
          join(xmlDirectory, "fitician_network_security_config.xml"),
          FITICIAN_NETWORK_SECURITY_CONFIG,
        ),
      ]);
    }
    return mod;
  }]);
}

function withScreenshotPolicy(config: Parameters<ConfigPlugin>[0]): ReturnType<ConfigPlugin> {
  return withMainActivity(config, (mod) => {
    const project = mod.modResults;
    if (project.contents.includes(SCREENSHOT_POLICY_MARKER)) {
      return mod;
    }

    if (project.language === "kt") {
      const contents = project.contents.includes("import android.view.WindowManager")
        ? project.contents
        : project.contents.replace(
            "import android.os.Bundle",
            "import android.os.Bundle\nimport android.view.WindowManager",
          );
      project.contents = contents.replace(
        "  override fun onCreate(savedInstanceState: Bundle?) {",
        `  override fun onCreate(savedInstanceState: Bundle?) {
    ${SCREENSHOT_POLICY_MARKER}
    ${screenshotFlag}`,
      );
    } else {
      const contents = project.contents.includes("import android.view.WindowManager;")
        ? project.contents
        : project.contents.replace(
            "import android.os.Bundle;",
            "import android.os.Bundle;\nimport android.view.WindowManager;",
          );
      project.contents = contents.replace(
        "  protected void onCreate(Bundle savedInstanceState) {",
        `  protected void onCreate(Bundle savedInstanceState) {
    ${SCREENSHOT_POLICY_MARKER}
    getWindow().setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE);`,
      );
    }

    mod.modResults = project;
    return mod;
  });
}

const withAndroidHardening: ConfigPlugin = (config) => {
  let hardened = config;
  hardened = AndroidConfig.Permissions.withBlockedPermissions(
    hardened,
    [...ANDROID_BLOCKED_PERMISSIONS],
  );
  hardened = withSecurityManifest(hardened);
  hardened = withSecurityResources(hardened);
  hardened = withScreenshotPolicy(hardened);
  return hardened;
};

export default withAndroidHardening;
