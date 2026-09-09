import { readFile } from "node:fs/promises";

import { expect, it } from "vitest";

it("renders real exercise media in catalogue cards", async () => {
  const source = await readFile(new URL("./ExerciseCatalogScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain('from "./ExerciseMedia"');
  expect(source).toContain("mediaType={exercise.media_type}");
  expect(source).toContain("path={exercise.media_path}");
  expect(source).toContain("styles.cardMedia");
});

it("places the primary exercise media before detail metadata", async () => {
  const source = await readFile(new URL("./ExerciseDetailScreen.tsx", import.meta.url), "utf8");

  expect(source.indexOf("<NativeExerciseMedia")).toBeLessThan(source.indexOf("styles.mediaHeader"));
  expect(source).toContain("styles.media");
  expect(source).toContain("styles.infoCard");
});
