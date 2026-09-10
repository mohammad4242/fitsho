import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { expect, it } from "vitest";

it("keeps the native landing scroll ranges aligned with the Web mobile story", async () => {
  const source = await readFile(resolve(import.meta.dirname, "PublicLandingScreen.tsx"), "utf8");

  expect(source).toMatch(/const compactLayout = width <= 650/);
  expect(source).toMatch(/viewportHeight \* \(compactLayout \? 4\.05 : 3\.9\)/);
  expect(source).toMatch(/viewportHeight \* \(compactLayout \? 2\.2 : 2\)/);
  expect(source).toMatch(/const analysisExit = .*progressBetween\(bodyProgress, 0\.48, 0\.66\)/);
  expect(source).toMatch(/const bodyDepth = .*progressBetween\(bodyProgress, 0\.58, 1\)/);
  expect(source).toMatch(/analysisProgress \* \(1 - analysisExit\)/);
});

it("keeps Web mobile composition hooks for process and body analysis", async () => {
  const source = await readFile(resolve(import.meta.dirname, "PublicLandingScreen.tsx"), "utf8");

  expect(source).toMatch(/accessibilityLabel=\{landing\.story\.label\}/);
  expect(source).toMatch(/accessibilityLabel=\{landing\.progression\.label\}/);
  expect(source).toMatch(/bodyMapping/);
  expect(source).toMatch(/aspectRatio: 0\.68/);
  expect(source).toMatch(/compactLayout && styles\.mealSceneCompact/);
  expect(source).toMatch(/compactLayout && styles\.processStageCompact/);
});
