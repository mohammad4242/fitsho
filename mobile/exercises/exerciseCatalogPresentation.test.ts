import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";

it("keeps primary discovery visible and moves secondary filters into a sheet", async () => {
  const source = await readFile(new URL("./ExerciseCatalogScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain("Sheet");
  expect(source).toContain("advancedFilterCount");
  expect(source).toContain("enabled: canLoadExercises");
  expect(source).toContain("showAll");
  expect(source).toContain("QuickFilterChip");
  expect(source).toContain("RegionOption");
  expect(source.indexOf("placeholder={exerciseCopy.searchPlaceholder}")).toBeLessThan(source.indexOf("discoveryPanel"));
  expect(source.indexOf("discoveryPanel")).toBeLessThan(source.indexOf("<Sheet"));
  expect(source.indexOf("<DiscoveryStage")).toBeLessThan(source.indexOf("<Sheet"));
  expect(source.indexOf("<ExerciseResults")).toBeLessThan(source.indexOf("<Sheet"));
  expect(source).not.toContain('accessibilityLabel="باز کردن فیلترها"');
});

it("exposes the library from the workout header", async () => {
  const source = await readFile(new URL("../workouts/WorkoutPlansScreen.tsx", import.meta.url), "utf8");
  expect(source).toContain('label="کتابخانه حرکات"');
  expect(source).toContain('router.push("/member/exercises")');
});
