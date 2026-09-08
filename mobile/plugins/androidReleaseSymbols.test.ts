import { expect, it } from "vitest";

import {
  ANDROID_RELEASE_SYMBOL_PROPERTY,
  applyAndroidReleaseSymbolProperties,
  type AndroidGradleProperty,
} from "./withAndroidReleaseSymbols";

it("enables release shrinking so Android mapping files are generated", () => {
  const properties: AndroidGradleProperty[] = [
    { type: "comment", value: "existing" },
    { key: ANDROID_RELEASE_SYMBOL_PROPERTY, type: "property", value: "false" },
  ];

  expect(applyAndroidReleaseSymbolProperties(properties)).toEqual([
    { type: "comment", value: "existing" },
    { key: ANDROID_RELEASE_SYMBOL_PROPERTY, type: "property", value: "true" },
  ]);
});

it("adds the release shrink property without disturbing other Gradle settings", () => {
  const properties: AndroidGradleProperty[] = [
    { key: "hermesEnabled", type: "property", value: "true" },
    { type: "empty" },
  ];

  expect(applyAndroidReleaseSymbolProperties(properties)).toEqual([
    { key: "hermesEnabled", type: "property", value: "true" },
    { type: "empty" },
    { key: ANDROID_RELEASE_SYMBOL_PROPERTY, type: "property", value: "true" },
  ]);
});
