import { expect, it } from "vitest";

import { applyAndroidManifestRtl, applyAndroidNativeRtl } from "./withAndroidRtl";

const kotlinProject = `package com.fitician.app

import android.app.Application
import com.facebook.react.ReactApplication
import com.facebook.react.ReactNativeApplicationEntryPoint.loadReactNative

class MainApplication : Application(), ReactApplication {
  override fun onCreate() {
    super.onCreate()
    loadReactNative(this)
  }
}
`;

it("boots Android RTL before the React Native bridge", () => {
  const result = applyAndroidNativeRtl({ language: "kt", contents: kotlinProject });

  expect(result.contents).toContain("import com.facebook.react.modules.i18nmanager.I18nUtil");
  expect(result.contents.indexOf("I18nUtil.instance.allowRTL(this, true)")).toBeGreaterThan(-1);
  expect(result.contents.indexOf("I18nUtil.instance.allowRTL(this, true"))
    .toBeLessThan(result.contents.indexOf("loadReactNative(this)"));
  expect(result.contents).toContain("I18nUtil.instance.forceRTL(this, true)");
});

it("does not duplicate the native RTL bootstrap", () => {
  const once = applyAndroidNativeRtl({ language: "kt", contents: kotlinProject });
  const twice = applyAndroidNativeRtl(once);

  expect(twice.contents).toBe(once.contents);
});

it("guarantees Android manifest RTL support without dropping existing attributes", () => {
  const result = applyAndroidManifestRtl({
    manifest: { $: { "android:label": "Fitician" } },
  });

  expect(result.manifest.$).toEqual({
    "android:label": "Fitician",
    "android:supportsRtl": "true",
  });
});

it("keeps the Java bootstrap before React Native", () => {
  const javaProject = `package com.fitician.app;

import android.app.Application;
import com.facebook.react.ReactApplication;
import com.facebook.react.ReactNativeApplicationEntryPoint;

public class MainApplication extends Application implements ReactApplication {
  @Override public void onCreate() {
    super.onCreate();
    ReactNativeApplicationEntryPoint.loadReactNative(this);
  }
}
`;

  const result = applyAndroidNativeRtl({ language: "java", contents: javaProject });

  expect(result.contents).toContain("I18nUtil.getInstance().allowRTL(this, true)");
  expect(result.contents.indexOf("I18nUtil.getInstance().allowRTL(this, true"))
    .toBeLessThan(result.contents.indexOf("loadReactNative(this)"));
});
