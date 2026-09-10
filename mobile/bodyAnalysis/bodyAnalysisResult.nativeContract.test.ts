import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("keeps result display versioned, quality-aware, and private", async () => {
  const source = await readFile(resolve(import.meta.dirname, "BodyAnalysisResultScreen.tsx"), "utf8");

  expect(source).toMatch(/getAnalysis/);
  expect(source).toMatch(/getComparison/);
  expect(source).toMatch(/result_version/);
  expect(source).toMatch(/photo_validation/);
  expect(source).toMatch(/coach_review/);
  expect(source).toMatch(/doctor_review/);
  expect(source).toMatch(/BodyProgressComparisonCard/);
  expect(source).not.toMatch(/نسخه قرارداد:/);
  expect(source).not.toMatch(/قرارداد داده:/);
  expect(source).not.toMatch(/نسخه پردازش:/);
  expect(source).toMatch(/BodyAnalysisExperienceTabs/);
  expect(source).toMatch(/BodyProgressTimelineItem/);
  expect(source).toMatch(/DisclosureCard/);
  expect(source).toMatch(/PrivacyDisclaimer/);
  expect(source).toMatch(/createPrivateBodyPhotoClient/);
  expect(source).toMatch(/loadPrivateBodyPhotoUris/);
  expect(source).not.toMatch(/source=\{\{ uri: photo\.content_url/);
  expect(source).not.toMatch(/console\.|Log\./);
});
