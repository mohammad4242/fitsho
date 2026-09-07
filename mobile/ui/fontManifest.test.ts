import { existsSync, statSync } from "node:fs";
import { resolve } from "node:path";

import { expect, it } from "vitest";

import { fiticianFontFiles, fiticianFontManifest } from "./fontManifest";

it("bundles static TTF/OTF files for all Fitician font families", () => {
  expect(fiticianFontFiles).toHaveLength(10);
  for (const relativePath of fiticianFontFiles) {
    const path = resolve(process.cwd(), relativePath);
    expect(existsSync(path), `${relativePath} is missing`).toBe(true);
    expect(statSync(path).size, `${relativePath} is empty`).toBeGreaterThan(0);
    expect(relativePath).toMatch(/\.(?:ttf|otf)$/u);
  }
});

it("maps the bundled static weights to stable native family names", () => {
  expect(fiticianFontManifest.android.map((family) => family.fontFamily)).toEqual([
    "Vazirmatn",
    "Lalezar",
    "Sora",
  ]);
  expect(fiticianFontManifest.android[0].fontDefinitions.map((font) => font.weight)).toEqual([
    400,
    500,
    600,
    700,
    800,
  ]);
  expect(fiticianFontManifest.android[2].fontDefinitions.map((font) => font.weight)).toEqual([
    400,
    600,
    700,
    800,
  ]);
});
