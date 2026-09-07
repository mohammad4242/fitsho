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
  expect(source).not.toMatch(/\/admin\//);
  expect(source).not.toMatch(/\/physician\//);
});

it("keeps photo results estimated until a member confirms them", async () => {
  const source = await readFile(resolve(nutritionDirectory, "NutritionTrackingSection.tsx"), "utf8");

  expect(source).toMatch(/photoEstimatePresentation/);
  expect(source).toMatch(/macro_totals_complete/);
  expect(source).toMatch(/confirmPhoto/);
});
