import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const nutritionDirectory = dirname(fileURLToPath(import.meta.url));

it("removes stale/offline notices without dropping actionable workflow status", async () => {
  const source = await readFile(resolve(nutritionDirectory, "NutritionTrackingSection.tsx"), "utf8");
  const workflowView = source.indexOf('        <View style={styles.workflowStatus}');
  const workflowStart = source.lastIndexOf("      {", workflowView);
  const workflowEnd = source.indexOf('      <View aria-label="کالری ثبت‌شده"', workflowStart);
  const workflow = source.slice(workflowStart, workflowEnd);

  expect(source).not.toContain("آخرین ثبت ذخیره‌شده نمایش داده می‌شود؛ تغییرات جدید بعد از اتصال انجام می‌شوند.");
  expect(source).not.toContain("هدف‌های ذخیره‌شده نمایش داده می‌شوند؛ ممکن است با آخرین وضعیت پروفایل هماهنگ نباشند.");
  expect(workflow).not.toContain('dailyState.status === "offline"');
  expect(workflow).not.toContain('dailyState.status === "stale"');
  expect(workflow).not.toContain('estimateState.status === "offline"');
  expect(workflow).not.toContain('estimateState.status === "stale"');
  expect(workflow).not.toContain("estimate?.is_stale");
  expect(workflow).toContain('estimateState.status === "error" && estimate === null');
  expect(workflow).toContain("catalogueState.status ===");
  expect(workflow).toContain("actionError !== null");
  expect(workflow).toContain("photoError !== null");
  expect(workflow).toContain("photoSuccess !== null");
});

it("keeps native tracking on member nutrition contracts", async () => {
  const source = await readFile(resolve(nutritionDirectory, "NutritionTrackingSection.tsx"), "utf8");

  expect(source).toMatch(/getDailyTracking/);
  expect(source).toMatch(/saveDailyCheckIn/);
  expect(source).toMatch(/addCatalogueFood/);
  expect(source).toMatch(/addQuickApproximation/);
  expect(source).toMatch(/adjustPlannedMeal/);
  expect(source).toMatch(/removeEntry/);
  expect(source).toMatch(/createFoodPhotoUploadJob/);
  expect(source).toMatch(/FOOD_PHOTO_PICKER_OPTIONS/);
  expect(source).toMatch(/deletePhotoEstimate/);
  expect(source).toMatch(/listPhotoEstimates/);
  expect(source).toMatch(/getPhotoEstimate/);
  expect(source).toMatch(/photoEstimatePresentation/);
  expect(source).toMatch(/<PageHeading/);
  expect(source).toMatch(/nutritionKeys\.estimate\(\)/);
  expect(source).not.toMatch(/FITICIAN · پیگیری عضو/);
  expect(source).not.toMatch(/\/admin\//);
  expect(source).not.toMatch(/\/physician\//);
});

it("keeps photo results estimated until a member confirms them", async () => {
  const source = await readFile(resolve(nutritionDirectory, "NutritionTrackingSection.tsx"), "utf8");

  expect(source).toMatch(/photoEstimatePresentation/);
  expect(source).toMatch(/macro_totals_complete/);
  expect(source).toMatch(/confirmPhoto/);
});

it("keeps the native page in the web-aligned tracking order", async () => {
  const source = await readFile(resolve(nutritionDirectory, "NutritionTrackingSection.tsx"), "utf8");

  const pageHeading = source.indexOf("<PageHeading");
  const entryHub = source.indexOf('testID="nutrition-entry-hub"');
  const manualPanel = source.indexOf("<ManualEntryPanel");
  const photoPanel = source.indexOf("<FoodPhotoCard");
  const dailyPanel = source.indexOf('testID="nutrition-daily-panel"');
  const entriesPanel = source.indexOf('testID="nutrition-today-entries"');
  const adherencePanel = source.indexOf('testID="nutrition-adherence"');
  const checkInPanel = source.indexOf('testID="nutrition-checkin"');

  expect(pageHeading).toBeGreaterThan(-1);
  expect(entryHub).toBeGreaterThan(pageHeading);
  expect(entryHub).toBeLessThan(manualPanel);
  expect(entryHub).toBeLessThan(photoPanel);
  expect(dailyPanel).toBeLessThan(entriesPanel);
  expect(entriesPanel).toBeLessThan(adherencePanel);
  expect(adherencePanel).toBeLessThan(checkInPanel);
});
