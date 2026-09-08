import type { ConfigPlugin } from "expo/config-plugins.js";
import { withGradleProperties } from "expo/config-plugins.js";

export const ANDROID_RELEASE_SYMBOL_PROPERTY = "android.enableMinifyInReleaseBuilds";

export type AndroidGradleProperty =
  | { readonly type: "comment"; readonly value: string }
  | { readonly type: "empty" }
  | { type: "property"; key: string; value: string };

export function applyAndroidReleaseSymbolProperties(
  properties: AndroidGradleProperty[],
): AndroidGradleProperty[] {
  const existing = properties.find(
    (property): property is Extract<AndroidGradleProperty, { type: "property" }> =>
      property.type === "property" && property.key === ANDROID_RELEASE_SYMBOL_PROPERTY,
  );
  if (existing !== undefined) {
    existing.value = "true";
  } else {
    properties.push({
      key: ANDROID_RELEASE_SYMBOL_PROPERTY,
      type: "property",
      value: "true",
    });
  }
  return properties;
}

const withAndroidReleaseSymbols: ConfigPlugin = (config) => withGradleProperties(config, (mod) => {
  mod.modResults = applyAndroidReleaseSymbolProperties(mod.modResults);
  return mod;
});

export default withAndroidReleaseSymbols;
