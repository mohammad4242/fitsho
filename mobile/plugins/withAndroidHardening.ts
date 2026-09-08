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

export const FITICIAN_DEVELOPMENT_NETWORK_SECURITY_CONFIG = `<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="true">
        <trust-anchors>
            <certificates src="system"/>
        </trust-anchors>
    </base-config>
</network-security-config>
`;

export type AndroidBuildEnvironment = "development" | "preview" | "production";

export function resolveAndroidBuildEnvironment(value: unknown): AndroidBuildEnvironment {
  if (value === "development" || value === "preview" || value === "production") {
    return value;
  }
  return "production";
}

export function networkSecurityConfigForEnvironment(
  environment: AndroidBuildEnvironment,
): string {
  return environment === "development"
    ? FITICIAN_DEVELOPMENT_NETWORK_SECURITY_CONFIG
    : FITICIAN_NETWORK_SECURITY_CONFIG;
}

export const SCREENSHOT_POLICY_MARKER = "// Fitician sensitive-screen screenshot policy";
const screenshotFlag =
  "window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)";
const javaScreenshotFlag =
  "getWindow().setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE);";

export interface AndroidMainActivityProject {
  readonly language: "java" | "kt";
  contents: string;
}

type AndroidManifestLike = Pick<AndroidManifest, "manifest">;

export function applyAndroidSecurityManifest<T extends AndroidManifestLike>(
  manifest: T,
  environment: AndroidBuildEnvironment = resolveAndroidBuildEnvironment(process.env.APP_VARIANT),
): T {
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
      "android:usesCleartextTraffic": environment === "development" ? "true" : "false",
    };
  }

  return manifest;
}

function configuredEnvironment(config: Parameters<ConfigPlugin>[0]): AndroidBuildEnvironment {
  const extra = config.extra;
  const configured = extra && typeof extra === "object" && "environment" in extra
    ? (extra as { readonly environment?: unknown }).environment
    : undefined;
  const appVariant = process.env.APP_VARIANT?.trim();
  return resolveAndroidBuildEnvironment(appVariant || configured);
}

function withSecurityManifest(
  config: Parameters<ConfigPlugin>[0],
  environment: AndroidBuildEnvironment,
): ReturnType<ConfigPlugin> {
  return withAndroidManifest(config, (mod) => {
    mod.modResults = applyAndroidSecurityManifest(mod.modResults, environment);
    return mod;
  });
}

function withSecurityResources(
  config: Parameters<ConfigPlugin>[0],
  environment: AndroidBuildEnvironment,
): ReturnType<ConfigPlugin> {
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
          networkSecurityConfigForEnvironment(environment),
        ),
      ]);
    }
    return mod;
  }]);
}

function removeScreenshotPolicyLines(contents: string): string {
  const lines = contents.split(/\r?\n/u).filter((line) => {
    const trimmed = line.trim();
    return trimmed !== SCREENSHOT_POLICY_MARKER
      && trimmed !== screenshotFlag
      && trimmed !== javaScreenshotFlag;
  });
  const result = lines.join("\n");
  return result.includes("WindowManager")
    ? result
    : result.split(/\r?\n/u)
      .filter((line) => !/^\s*import android\.view\.WindowManager;?\s*$/u.test(line))
      .join("\n");
}

export function applyAndroidScreenshotPolicy<T extends AndroidMainActivityProject>(
  project: T,
  environment: AndroidBuildEnvironment,
): T {
  if (environment === "development") {
    project.contents = removeScreenshotPolicyLines(project.contents);
    return project;
  }

  if (project.contents.includes(SCREENSHOT_POLICY_MARKER)) {
    return project;
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
    ${javaScreenshotFlag}`,
    );
  }

  return project;
}

function withScreenshotPolicy(
  config: Parameters<ConfigPlugin>[0],
  environment: AndroidBuildEnvironment,
): ReturnType<ConfigPlugin> {
  return withMainActivity(config, (mod) => {
    mod.modResults = applyAndroidScreenshotPolicy(mod.modResults, environment);
    return mod;
  });
}

const withAndroidHardening: ConfigPlugin = (config) => {
  const environment = configuredEnvironment(config);
  let hardened = config;
  hardened = AndroidConfig.Permissions.withBlockedPermissions(
    hardened,
    [...ANDROID_BLOCKED_PERMISSIONS],
  );
  hardened = withSecurityManifest(hardened, environment);
  hardened = withSecurityResources(hardened, environment);
  hardened = withScreenshotPolicy(hardened, environment);
  return hardened;
};

export default withAndroidHardening;
