import { readFile } from "node:fs/promises";

import { expect, it } from "vitest";

it("renders real exercise media in catalogue cards", async () => {
  const source = await readFile(new URL("./ExerciseCatalogScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain('from "./ExerciseMedia"');
  expect(source).toContain("mediaType={exercise.media_type}");
  expect(source).toContain("path={exercise.media_path}");
  expect(source).toContain("styles.cardMedia");
});

it("keeps network media loading visible and falls back safely", async () => {
  const source = await readFile(new URL("./ExerciseMedia.tsx", import.meta.url), "utf8");

  expect(source).toContain("onFirstFrameRender");
  expect(source).toContain("onError");
  expect(source).toContain("loadingOverlay");
  expect(source).toContain("isExerciseMediaRenderable");
});

it("places the primary exercise media before detail metadata", async () => {
  const source = await readFile(new URL("./ExerciseDetailScreen.tsx", import.meta.url), "utf8");

  expect(source.indexOf("<NativeExerciseMedia")).toBeLessThan(source.indexOf("styles.mediaHeader"));
  expect(source).toContain("styles.media");
  expect(source).toContain("styles.infoCard");
});
