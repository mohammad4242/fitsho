import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const nutritionDirectory = dirname(fileURLToPath(import.meta.url));

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

it("keeps the daily target and photo entry ahead of lower-frequency entry tools", async () => {
  const source = await readFile(resolve(nutritionDirectory, "NutritionTrackingSection.tsx"), "utf8");

  expect(source.indexOf("<PageHeading")).toBeGreaterThan(-1);
  expect(source.indexOf("<Card style={styles.summaryCard}")).toBeLessThan(source.indexOf("<FoodPhotoCard"));
  expect(source.indexOf("<FoodPhotoCard")).toBeLessThan(source.indexOf('ثبت وضعیت امروز'));
  expect(source.indexOf('ثبت وضعیت امروز')).toBeLessThan(source.indexOf('ثبت دستی وعده'));
});
