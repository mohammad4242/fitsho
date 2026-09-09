import { readFile } from "node:fs/promises";

import { expect, it } from "vitest";

it("uses shared native hierarchy and icons instead of text glyph controls", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain("ScreenHeader");
  expect(source).toContain('name={expanded ? "chevronUp" : "chevronDown"}');
  expect(source).not.toContain('{expanded ? "⌃" : "⌄"}');
});

it("makes each exercise a single roomy detail action", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");
  const row = source.slice(source.indexOf("function WorkoutExerciseRow"), source.indexOf("function WorkoutMetric"));

  expect(row).toContain("accessibilityLabel={`باز کردن راهنمای");
  expect(row).not.toContain('label="راهنما"');
});

it("presents cycle status as a compact cinematic summary", async () => {
  const source = await readFile(new URL("./WorkoutCyclePanel.tsx", import.meta.url), "utf8");
  const summary = source.slice(source.indexOf("function CycleSummary"), source.indexOf("function WeeklyCheckInPanel"));

  expect(summary).toContain("CinematicSurface");
  expect(summary).toContain("MetricStrip");
  expect(summary).not.toContain("weekCard");
});
