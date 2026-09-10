import type { ConfigPlugin } from "expo/config-plugins.js";
import { withMainApplication } from "expo/config-plugins.js";

const NATIVE_RTL_MARKER = "// Fitician native RTL bootstrap";

export interface AndroidMainApplicationProject {
  readonly language: "java" | "kt";
  contents: string;
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
    contents = contents.replace(
      "    loadReactNative(this);",
      `    ${NATIVE_RTL_MARKER}\n    I18nUtil.getInstance().allowRTL(this, true);\n    I18nUtil.getInstance().forceRTL(this, true);\n    loadReactNative(this);`,
    );
  }
  project.contents = contents;
  return project;
}

const withAndroidRtl: ConfigPlugin = (config) => withMainApplication(config, (mod) => {
  mod.modResults = applyAndroidNativeRtl(mod.modResults);
  return mod;
});

export default withAndroidRtl;
