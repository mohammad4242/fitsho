import { readFile } from "node:fs/promises";
import { expect, it } from "vitest";

it("keeps the nutrition plan shortcut before secondary forms and leaves catalogues to More", async () => {
  const source = await readFile(new URL("./NutritionFoundationScreen.tsx", import.meta.url), "utf8");
  expect(source.indexOf("<NutritionPlanShortcut")).toBeGreaterThan(0);
  expect(source.indexOf("<NutritionPlanShortcut")).toBeLessThan(source.indexOf("<NutritionProfileSection"));
  expect(source).not.toContain("<NutritionDestinations");
  expect(source).not.toContain("سه مسیر اصلی");
  expect(source).not.toContain('title="کاتالوگ مواد غذایی"');
  expect(source).not.toContain('title="کاتالوگ وعده‌ها"');
  for (const route of ["nutrition-plan", "food-catalogue", "meal-catalogue"]) {
    const text = await readFile(new URL(`../app/(member)/member/${route}.tsx`, import.meta.url), "utf8");
    expect(text).toContain('requiredCapability="nutrition"');
  }
});

it("passes contract images to native thumbnails for catalogues, meals, and replacements", async () => {
  const catalogue = await readFile(new URL("./NutritionCatalogueSection.tsx", import.meta.url), "utf8");
  const plan = await readFile(new URL("./NutritionPlanSection.tsx", import.meta.url), "utf8");
  expect(catalogue).toContain("imageUrl={food.image_url}");
  expect(catalogue).toContain("imageUrl={meal.image_url}");
  expect(plan).toContain("imageUrl={meal.image_url}");
  expect(plan).toContain("imageUrl={option.image_url}");
  expect(plan).toContain("<DisclosureCard");
});
