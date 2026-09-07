import type { FoodCatalogueItem, FoodCataloguePortion, MealCatalogueCategory } from "./nutritionCatalogueApi";

const MACRO_ORDER = [
  "energy_kcal",
  "protein_g",
  "carbohydrate_g",
  "total_fat_g",
] as const;

const macroLabels: Readonly<Record<(typeof MACRO_ORDER)[number], string>> = {
  carbohydrate_g: "کربوهیدرات",
  energy_kcal: "انرژی",
  protein_g: "پروتئین",
  total_fat_g: "چربی",
};

export type CatalogueMacroRow = {
  readonly code: (typeof MACRO_ORDER)[number];
  readonly label: string;
  readonly value: string;
};

export type CataloguePortionRow = {
  readonly code: FoodCataloguePortion["code"];
  readonly grams: string;
  readonly label: string;
  readonly quantity: string;
};

export function selectDefaultFoodPortion(
  food: FoodCatalogueItem,
): FoodCataloguePortion | null {
  return food.portions.find((portion) => portion.is_default) ?? food.portions[0] ?? null;
}

export function foodCataloguePortionRows(food: FoodCatalogueItem): CataloguePortionRow[] {
  return food.portions.map((portion) => ({
    code: portion.code,
    grams: formatCatalogueDisplayNumber(portion.grams, 0),
    label: portion.label_fa,
    quantity: formatCatalogueDisplayNumber(portion.quantity, 1),
  }));
}

export function foodCatalogueMacroRows(food: FoodCatalogueItem): CatalogueMacroRow[] {
  return MACRO_ORDER.flatMap((code) => {
    const value = food.macros[code];
    return value === null || value === undefined
      ? []
      : [{ code, label: macroLabels[code], value: formatCatalogueDisplayNumber(value, 1) }];
  });
}

export function formatCatalogueDisplayNumber(value: number | string, maximumFractionDigits = 1): string {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits }).format(numeric);
}

export function preparedMealCatalogueLabel(
  calculationMode: "simple" | "prepared_recipe",
): { readonly message: string; readonly title: string } | null {
  return calculationMode === "prepared_recipe"
    ? {
      message: "خلاصه تأییدشده یا تخمینی در برنامه غذایی نمایش داده می‌شود.",
      title: "دستور آماده",
    }
    : null;
}

export function mealCatalogueCategoryLabel(category: MealCatalogueCategory): string {
  switch (category) {
    case "breakfast":
      return "صبحانه";
    case "lunch":
      return "ناهار";
    case "post_workout":
      return "پس از تمرین";
    case "snack":
      return "میان‌وعده";
    case "dinner":
      return "شام";
  }
}
