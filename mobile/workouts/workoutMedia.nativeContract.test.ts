import { readFile } from "node:fs/promises";

import { expect, it } from "vitest";

it("keeps only the first day media-first and preserves media in expanded exercise rows", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain('from "../exercises/ExerciseMedia"');
  expect(source).toContain("leadExercise");
  expect(source).toContain("dayIndex === 0");
  expect(source).toContain("focusDayCard");
  expect(source).toContain("secondaryDayCard");
  expect(source).toContain("mediaType={exercise.exercise.media_type}");
  expect(source).toContain("path={exercise.exercise.media_path}");
  expect(source).toContain("deferVideo");
});

it("keeps the focus media compact and secondary days in compact rows", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain("styles.focusDayMedia");
  expect(source).toContain("styles.secondaryDayNumber");
  expect(source).toContain("styles.secondaryDayCard");
  expect(source).toContain("numberOfLines={1}");
  expect(source).toContain("day.estimated_duration_minutes");
});
