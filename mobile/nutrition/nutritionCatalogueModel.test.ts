import { expect, it } from "vitest";

import type { FoodCatalogueItem } from "./nutritionCatalogueApi";
import {
  foodCatalogueCategoryLabel,
  foodCatalogueBasisLabel,
  foodCatalogueCalories,
  foodCatalogueMacroRows,
  foodCatalogueNutrientRows,
  foodCataloguePortionRows,
  formatCatalogueDisplayNumber,
  mealCatalogueCategoryLabel,
  preparedMealCatalogueLabel,
  selectDefaultFoodPortion,
} from "./nutritionCatalogueModel";

const food = {
  id: "food-1",
  image_url: null,
  measurement_basis: "raw",
  name_en: "Rice",
  name_fa: "برنج",
  slug: "rice",
  category: "grain",
  nutrient_basis: { quantity: "100", unit: "g" },
  macros: {
    energy_kcal: "130.25",
    fibre_g: null,
    protein_g: "2.70",
    carbohydrate_g: "28.17",
    total_fat_g: "0.30",
  },
  nutrients: [],
  portions: [
    {
      code: "cup",
      grams: "195.0000",
      is_default: false,
      label_en: "cup",
      label_fa: "پیمانه",
      quantity: "1",
      source_name: "USDA",
      source_reference: "usda-1",
    },
    {
      code: "piece",
      grams: "100.0000",
      is_default: true,
      label_en: "piece",
      label_fa: "واحد",
      quantity: "1",
      source_name: "USDA",
      source_reference: "usda-2",
    },
  ],
  allergen_metadata_verified: true,
  allergen_tags: [],
  source: {
    access_date: "2026-09-07",
    data_version: "v1",
    name: "USDA",
    reference: "usda-1",
    source_food_id: "1",
  },
} as FoodCatalogueItem;

it("selects verified default portions without changing stored precision", () => {
  expect(selectDefaultFoodPortion(food)?.code).toBe("piece");
  expect(foodCataloguePortionRows(food)).toEqual([
    { code: "cup", grams: "۱۹۵", label: "پیمانه", quantity: "۱" },
    { code: "piece", grams: "۱۰۰", label: "واحد", quantity: "۱" },
  ]);
});

it("formats catalogue macros for display while preserving source values", () => {
  expect(foodCatalogueMacroRows(food)).toEqual([
    { code: "protein_g", label: "پروتئین", value: "۲٫۷" },
    { code: "carbohydrate_g", label: "کربوهیدرات", value: "۲۸٫۲" },
    { code: "total_fat_g", label: "چربی", value: "۰٫۳" },
  ]);
  expect(formatCatalogueDisplayNumber("100.0000", 0)).toBe("۱۰۰");
});

it("scales the separate calories and three card macros to the selected portion", () => {
  const halfPortionFood = {
    ...food,
    macros: {
      ...food.macros,
      carbohydrate_g: "28.17",
      energy_kcal: "130.25",
      protein_g: "22.5",
      total_fat_g: "2.62",
    },
    portions: [{ ...food.portions[1], grams: "50.0000", is_default: true }],
  };

  expect(foodCatalogueCalories(halfPortionFood)).toEqual({ label: "کالری", unit: "kcal", value: "۶۵٫۱" });
  expect(foodCatalogueMacroRows(halfPortionFood)).toEqual([
    { code: "protein_g", label: "پروتئین", value: "۱۱٫۳" },
    { code: "carbohydrate_g", label: "کربوهیدرات", value: "۱۴٫۱" },
    { code: "total_fat_g", label: "چربی", value: "۱٫۳" },
  ]);
  expect(foodCatalogueMacroRows(halfPortionFood).some((row) => row.code === "energy_kcal")).toBe(false);
});

it("falls back to the first portion and uses the 100 gram basis when no portion exists", () => {
  const firstPortionFood = {
    ...food,
    portions: food.portions.map((portion) => ({ ...portion, is_default: false })),
  };
  expect(selectDefaultFoodPortion(firstPortionFood)?.code).toBe("cup");
  expect(foodCatalogueBasisLabel(selectDefaultFoodPortion(firstPortionFood))).toBe("در پیمانه");
  expect(foodCatalogueBasisLabel(null)).toBe("در هر ۱۰۰ گرم");
});

it("scales every nutrient row, including micronutrients, for the details sheet", () => {
  const micronutrientFood = {
    ...food,
    nutrients: [{
      confidence: "high" as const,
      nutrient_code: "iron_mg",
      source_name: "USDA",
      source_reference: "usda-iron",
      unit: "mg",
      unit_form: "nutrient_mass",
      value_per_100g: 0.37,
    }],
    portions: [{ ...food.portions[1], grams: "50.0000", is_default: true }],
  };

  expect(foodCatalogueNutrientRows(micronutrientFood)).toEqual([{
    code: "iron_mg",
    label: "آهن",
    unit: "mg",
    value: "۰٫۲",
  }]);
});

it("keeps prepared recipe catalogue rows summary-only", () => {
  expect(preparedMealCatalogueLabel("prepared_recipe")).toEqual({
    title: "دستور آماده",
    message: "خلاصه تأییدشده یا تخمینی در برنامه غذایی نمایش داده می‌شود.",
  });
  expect(preparedMealCatalogueLabel("simple")).toBeNull();
  expect(mealCatalogueCategoryLabel("post_workout")).toBe("پس از تمرین");
});

it("localizes food categories used by the web catalogue cards", () => {
  expect(foodCatalogueCategoryLabel("nuts_seeds")).toBe("مغزها و دانه‌ها");
  expect(foodCatalogueCategoryLabel("unknown_group")).toBe("unknown group");
});
