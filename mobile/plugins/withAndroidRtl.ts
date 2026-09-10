import type { ConfigPlugin } from "expo/config-plugins.js";
import { withAndroidManifest, withMainApplication } from "expo/config-plugins.js";

const NATIVE_RTL_MARKER = "// Fitician native RTL bootstrap";

export interface AndroidMainApplicationProject {
  readonly language: "java" | "kt";
  contents: string;
}

export interface AndroidManifestProject {
  manifest: {
    $?: Record<string, string | undefined>;
  };
}

export function applyAndroidManifestRtl<T extends AndroidManifestProject>(project: T): T {
  project.manifest.$ = {
    ...project.manifest.$,
    "android:supportsRtl": "true",
  };
  return project;
}

export function applyAndroidNativeRtl<T extends AndroidMainApplicationProject>(project: T): T {
  if (project.language === "kt") {
    const importLine = "import com.facebook.react.modules.i18nmanager.I18nUtil";
    let contents = project.contents;
    if (!contents.includes(importLine)) {
      contents = contents.replace(
        "import android.app.Application",
        `${importLine}\nimport android.app.Application`,
      );
    }
    if (!contents.includes(NATIVE_RTL_MARKER)) {
      contents = contents.replace(
        "    loadReactNative(this)",
        `    ${NATIVE_RTL_MARKER}\n    I18nUtil.instance.allowRTL(this, true)\n    I18nUtil.instance.forceRTL(this, true)\n    loadReactNative(this)`,
      );
    }
    project.contents = contents;
    return project;
  }

  const importLine = "import com.facebook.react.modules.i18nmanager.I18nUtil;";
  let contents = project.contents;
  if (!contents.includes(importLine)) {
    contents = contents.replace(
      "import android.app.Application;",
      `${importLine}\nimport android.app.Application;`,
    );
  }
  if (!contents.includes(NATIVE_RTL_MARKER)) {
    const qualifiedLoad = "ReactNativeApplicationEntryPoint.loadReactNative(this);";
    const loadCall = contents.includes(qualifiedLoad) ? qualifiedLoad : "loadReactNative(this);";
    contents = contents.replace(
      loadCall,
      `    ${NATIVE_RTL_MARKER}\n    I18nUtil.getInstance().allowRTL(this, true);\n    I18nUtil.getInstance().forceRTL(this, true);\n    ${loadCall}`,
    );
  }
  project.contents = contents;
  return project;
}

const withAndroidRtl: ConfigPlugin = (config) => {
  const withManifest = withAndroidManifest(config, (mod) => {
    mod.modResults = applyAndroidManifestRtl(mod.modResults);
    return mod;
  });
  return withMainApplication(withManifest, (mod) => {
    mod.modResults = applyAndroidNativeRtl(mod.modResults);
    return mod;
  });
};

export default withAndroidRtl;
