import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";

it("keeps primary discovery visible and moves secondary filters into a sheet", async () => {
  const source = await readFile(new URL("./ExerciseCatalogScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain("Sheet");
  expect(source).toContain("SegmentedControl");
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

it("keeps the web card ratio and native touch target for secondary filters", async () => {
  const source = await readFile(new URL("./ExerciseCatalogScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain("aspectRatio: 16 / 10");
  expect(source).toContain("minHeight: fiticianTokens.layout.minimumTouchTarget");
});

it("keeps result cards dark, labeled, and navigable through their CTA", async () => {
  const source = await readFile(new URL("./ExerciseCatalogScreen.tsx", import.meta.url), "utf8");
  const discoveryPanelStart = source.indexOf("discoveryPanel:");
  const discoveryPanelEnd = source.indexOf("discoveryPanelFooter:");
  const discoveryPanel = source.slice(discoveryPanelStart, discoveryPanelEnd);
  const exerciseCardStart = source.indexOf("exerciseCard:");
  const exerciseCardEnd = source.indexOf("exerciseName:", exerciseCardStart);
  const exerciseCard = source.slice(exerciseCardStart, exerciseCardEnd);

  expect(discoveryPanel).toContain("backgroundColor: fiticianTokens.colors.surface,");
  expect(exerciseCard).toContain("backgroundColor: fiticianTokens.colors.surface,");
  expect(exerciseCard).toContain("borderColor: fiticianTokens.colors.lineStrong,");
  expect(source).toContain("function ExerciseMetaRow");
  expect(source.match(/<ExerciseMetaRow/g)).toHaveLength(3);
  expect(source).toContain("label={exerciseCopy.primaryMuscleLabel}");
  expect(source).toContain("label={exerciseCopy.equipment}");
  expect(source).toContain("label={exerciseCopy.muscleFocusLabel}");
  expect(source).toContain("exerciseCopy.notSpecified");
  expect(source).toContain("exerciseCopy.needsReview");
  expect(source).toContain("exerciseCopy.viewExercise");
  expect(source).toContain("exerciseCopy.viewGuide");
  expect(source).not.toContain('variant="interactive"');
});

it("keeps the exercise library discoverable outside workout plan tools", async () => {
  const source = await readFile(new URL("../more/MoreScreen.tsx", import.meta.url), "utf8");
  expect(source).toContain('title: "کتابخانه حرکات"');
  expect(source).toContain('path: "/member/exercises"');
});
