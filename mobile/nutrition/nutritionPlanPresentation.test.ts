import { readFile } from "node:fs/promises";
import { expect, it } from "vitest";

it("uses a status-first native nutrition plan hierarchy", async () => {
  const route = await readFile(new URL("../app/(member)/member/nutrition-plan.tsx", import.meta.url), "utf8");
  const source = await readFile(new URL("./NutritionPlanSection.tsx", import.meta.url), "utf8");
  const shopping = await readFile(new URL("./NutritionShoppingList.tsx", import.meta.url), "utf8");

  expect(route).toContain("PageHeading");
  expect(route).not.toContain("ScreenHeader");
  expect(source).toContain("planRoleLabel");
  expect(source).toContain("planApprovalLabel");
  expect(source).toContain("برنامه فعال شما");
  expect(source).toContain("PlanChoiceMetric");
  expect(source).not.toContain("warning_codes.join");
  expect(source).not.toContain("reason_codes.join");
  expect(source).not.toContain("این برنامه قدیمی است؛ قبل از خرید یا تصمیم جدید، اتصال را بررسی کن.");
  expect(source).not.toContain("این نسخه هنوز برای استفاده نهایی فعال نشده است.");
  expect(shopping).not.toContain("warning_codes.join");
  expect(shopping).toContain("DisclosureCard");
  expect(shopping).toContain('title="لیست خرید"');
  expect(shopping).toContain('summary="مواد لازم برای این نسخه از برنامه"');
  expect(shopping).not.toContain('direction="rtl"');
  expect(shopping).toContain("defaultExpanded={false}");
  expect(shopping).not.toContain("این لیست تازه‌سازی نشده است؛ قبل از خرید اتصال را بررسی کن.");
  expect(shopping).not.toContain("قیمت نهایی تا تأیید پزشک نمایش داده نمی‌شود.");
  expect(shopping).toContain("api.getShoppingList(planId)");
  expect(shopping).toContain("approvedShoppingPriceVisibility");
});
