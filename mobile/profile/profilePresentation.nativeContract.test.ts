import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("keeps profile presentation grouped around real account data", async () => {
  const source = await readFile(resolve(import.meta.dirname, "ProfileScreen.tsx"), "utf8");

  expect(source).toMatch(/ProfileOverviewCard/);
  expect(source).toMatch(/PageHeading/);
  expect(source).not.toMatch(/ScreenHeader/);
  expect(source).toMatch(/auth\.user\?\.email/);
  expect(source).toMatch(/ageFromBirthDate/);
  expect(source).toMatch(/ProfileMeasurements/);
  expect(source).toMatch(/body-analysis-history/);
  expect(source).toMatch(/ProfileSectionProgress/);
  expect(source).not.toMatch(/SegmentedControl/);
  expect(source).toMatch(/shared\.fitness_goal/);
  expect(source).toMatch(/shared\.height_cm/);
  expect(source).toMatch(/shared\.current_weight_kg/);
  expect(source).toMatch(/AccountPrivacyLinks/);
  expect(source).toMatch(/<Screen[^>]*>/);
  expect(source).toContain('textAlign: "auto"');
  expect(source).toContain('writingDirection: "rtl"');
});

it("keeps the profile photo card on native RTL ordering", async () => {
  const source = await readFile(resolve(import.meta.dirname, "ProfilePhotoControl.tsx"), "utf8");

  expect(source).toMatch(/<Card[^>]*accessibilityLabel="عکس پروفایل"/);
  expect(source).toMatch(
    /<View style=\{styles\.identityRow\}>[\s\S]*?<Image[\s\S]*?<View style=\{styles\.copy\}>[\s\S]*?<Text style=\{styles\.title\}>/,
  );
  expect(source).toContain('textAlign: "auto"');
  expect(source).toContain('writingDirection: "rtl"');
});
