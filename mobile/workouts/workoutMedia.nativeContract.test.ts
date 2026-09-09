import { readFile } from "node:fs/promises";

import { expect, it } from "vitest";

it("keeps workout plans media-first for lead days and exercise rows", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain('from "../exercises/ExerciseMedia"');
  expect(source).toContain("leadExercise");
  expect(source).toContain("mediaType={exercise.exercise.media_type}");
  expect(source).toContain("path={exercise.exercise.media_path}");
});

it("keeps plan status notices visually secondary", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain("styles.statusStack");
  expect(source).toContain("compact");
});
