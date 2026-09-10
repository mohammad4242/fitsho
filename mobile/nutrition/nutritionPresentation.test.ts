import { readFile } from "node:fs/promises";
import { expect, it } from "vitest";

it("matches the web nutrition hierarchy and removes dashboard-only sections", async () => {
  const source = await readFile(new URL("./NutritionFoundationScreen.tsx", import.meta.url), "utf8");
  expect(source).toContain("<PageHeading");
  expect(source).toContain("<NutritionDailyTools");
  expect(source).toContain("<NutritionSummaryCard");
  expect(source).toContain("<NutritionWeightRateCard");
  expect(source).toContain("<NutritionTodayMeals");
  expect(source).toContain("<NutritionScienceDetails");
  expect(source).toContain("<NutritionDoctorSupervision");
  expect(source).toContain("<NutritionPlanSection");
  expect(source).not.toContain("<ScreenHeader");
  expect(source.indexOf("<PageHeading")).toBeLessThan(source.indexOf("<NutritionDailyTools"));
  expect(source.indexOf("<NutritionDailyTools")).toBeLessThan(source.indexOf("<NutritionSummaryCard"));
  expect(source.indexOf("<NutritionSummaryCard")).toBeLessThan(source.indexOf("<NutritionWeightRateCard"));
  expect(source.indexOf("<NutritionWeightRateCard")).toBeLessThan(source.indexOf("<NutritionTodayMeals"));
  expect(source.indexOf("<NutritionTodayMeals")).toBeLessThan(source.indexOf("<NutritionScienceDetails"));
  expect(source.indexOf("<NutritionScienceDetails")).toBeLessThan(source.indexOf("<NutritionDoctorSupervision"));
  expect(source.indexOf("<NutritionDoctorSupervision")).toBeLessThan(source.indexOf("<NutritionPlanSection"));
  for (const section of [
    "NutritionProfileSection",
    "SafetySection",
    "StructuredExerciseSection",
    "ReviewRequirementSection",
    "NutritionEstimateSection",
    "NutritionCatalogueSection",
    "NutritionTrackingSection",
    "NutritionAdherenceSection",
    "NutritionClinicalSection",
    "NutritionPlanShortcut",
  ]) {
    expect(source).not.toMatch(new RegExp(`\\n\\s*<${section}\\b`));
  }
  for (const route of ["nutrition-plan", "food-catalogue", "meal-catalogue", "nutrition-labs", "nutrition-supplements"]) {
    const text = await readFile(new URL(`../app/(member)/member/${route}.tsx`, import.meta.url), "utf8");
    expect(text).toContain('requiredCapability="nutrition"');
  }
});

it("passes contract images to native thumbnails for catalogues, meals, and replacements", async () => {
  const catalogue = await readFile(new URL("./NutritionCatalogueSection.tsx", import.meta.url), "utf8");
  const plan = await readFile(new URL("./NutritionPlanSection.tsx", import.meta.url), "utf8");
  const foodRoute = await readFile(new URL("../app/(member)/member/food-catalogue.tsx", import.meta.url), "utf8");
  const mealRoute = await readFile(new URL("../app/(member)/member/meal-catalogue.tsx", import.meta.url), "utf8");
  expect(catalogue).toContain("imageUrl={food.image_url}");
  expect(catalogue).toContain("imageUrl={meal.image_url}");
  expect(catalogue).toContain("<PageHeading");
  expect(catalogue).toContain('title="کاتالوگ مواد غذایی"');
  expect(catalogue).toContain("ترکیب‌های کنترل‌شده تغذیه");
  expect(catalogue).toContain("کاتالوگ وعده‌های غذایی");
  expect(catalogue).toContain("دسته‌بندی وعده‌ها:");
  expect(catalogue).toContain("RTL_ROW");
  expect(catalogue).toContain("RTL_TEXT");
  expect(catalogue).not.toContain("MealDetailsSheet");
  expect(foodRoute).toContain('initialMode="foods"');
  expect(mealRoute).toContain('initialMode="meals"');
  expect(plan).toContain("imageUrl={meal.image_url}");
  expect(plan).toContain("imageUrl={option.image_url}");
  expect(plan).toContain("<DisclosureCard");
});

it("keeps the meal catalogue background fixed behind a transparent native screen", async () => {
  const source = await readFile(new URL("../app/(member)/member/meal-catalogue.tsx", import.meta.url), "utf8");

  expect(source).toContain('require("../../../assets/home-food.webp")');
  expect(source).toContain("<ImageBackground");
  expect(source).toContain("<LinearGradient");
  expect(source).toContain("<Rect");
  expect(source).toContain("style={styles.transparentScreen}");
  expect(source).toContain("contentContainerStyle={styles.transparentContent}");
  expect(source).toContain('backgroundColor: "transparent"');
});

it("keeps the nutrition day selector in explicit RTL horizontal flow", async () => {
  const source = await readFile(new URL("./NutritionPlanSection.tsx", import.meta.url), "utf8");

  expect(source).toContain('contentContainerStyle={[styles.daySelector, RTL_ROW]}');
});
