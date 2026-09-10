import { readFile } from "node:fs/promises";
import { expect, it } from "vitest";

it("keeps the native coach workflow online-write gated and revision-aware", async () => {
  const source = await readFile(new URL("./CoachWorkoutReviewScreen.tsx", import.meta.url), "utf8");

  expect(source).toMatch(/createCoachWorkoutReviewApi/);
  expect(source).toMatch(/isCoachReviewReadOnly/);
  expect(source).toMatch(/api\.approve/);
  expect(source).toMatch(/api\.reject/);
  expect(source).toMatch(/api\.renew/);
  expect(source).toMatch(/api\.saveDraft/);
  expect(source).toMatch(/draft_revision/);
  expect(source).toMatch(/connectivityStatus/);
  expect(source).toMatch(/PageHeading/);
  expect(source).toMatch(/SegmentedControl/);
  expect(source).toMatch(/useAndroidBackHandler/);
  expect(source).toMatch(/قفل بازبینی تا/);
  expect(source).toMatch(/نسخه اولیه فعال می‌ماند تا نسخه تو با اعتبارسنجی کامل تأیید شود/);
  expect(source).toMatch(/برگشت برای اصلاح/);
  expect(source).toMatch(/تأیید و ارسال برای کاربر/);
  expect(source).toMatch(/DisclosureCard/);
  expect(source).toMatch(/انتخاب حرکت/);
});

it("keeps coach review layout logical for native RTL", async () => {
  const source = await readFile(new URL("./CoachWorkoutReviewScreen.tsx", import.meta.url), "utf8");

  expect(source).toMatch(/<Screen contentWidth="reading">/);
  expect(source).toContain('textAlign: "auto"');
  expect(source).toContain('writingDirection: "rtl"');
  expect(source).toMatch(
    /<View style=\{styles\.dayHeader\}>\s*<Text style=\{styles\.dayTitle\}>[\s\S]*?<Text style=\{styles\.dayNumber\}>/,
  );
  expect(source).toMatch(
    /<View style=\{styles\.headerCopy\}>[\s\S]*?<View style=\{styles\.memberIdentity\}>[\s\S]*?<Text style=\{styles\.detailTitle\}>/,
  );
});
