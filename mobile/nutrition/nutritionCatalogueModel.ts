import type {
  FoodCatalogueItem,
  FoodCataloguePortion,
  MealCatalogueCategory,
} from "./nutritionCatalogueApi";

const CARD_MACRO_ORDER = ["protein_g", "carbohydrate_g", "total_fat_g"] as const;

const macroLabels: Readonly<Record<(typeof CARD_MACRO_ORDER)[number], string>> = {
  carbohydrate_g: "کربوهیدرات",
  protein_g: "پروتئین",
  total_fat_g: "چربی",
};

const nutrientLabels: Readonly<Record<string, string>> = {
  calcium_mg: "کلسیم",
  carbohydrate_g: "کربوهیدرات",
  copper_mg: "مس",
  energy_kcal: "انرژی",
  fibre_g: "فیبر",
  folate_dfe_mcg: "فولات",
  iron_mg: "آهن",
  magnesium_mg: "منیزیم",
  potassium_mg: "پتاسیم",
  protein_g: "پروتئین",
  saturated_fat_g: "چربی اشباع",
  sodium_mg: "سدیم",
  total_fat_g: "چربی کل",
  total_sugars_g: "قند کل",
  vitamin_b12_mcg: "ویتامین B12",
  vitamin_c_mg: "ویتامین C",
  vitamin_d_mcg: "ویتامین D",
  zinc_mg: "روی",
};

export type CatalogueMacroRow = {
  readonly code: (typeof CARD_MACRO_ORDER)[number];
  readonly label: string;
  readonly value: string;
};

export type CatalogueMetric = {
  readonly label: string;
  readonly unit: string;
  readonly value: string;
};

export type CatalogueNutrientRow = {
  readonly code: string;
  readonly label: string;
  readonly unit: string;
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

export function scaleFoodCatalogueValue(
  value: number | string | null | undefined,
  portion: FoodCataloguePortion | null,
): number | null {
  if (value === null || value === undefined) return null;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  if (portion === null) return numeric;
  const grams = Number(portion.grams);
  return Number.isFinite(grams) ? numeric * grams / 100 : numeric;
}

export function foodCatalogueCalories(food: FoodCatalogueItem): CatalogueMetric {
  return {
    label: "کالری",
    unit: "kcal",
    value: formatScaledValue(food.macros.energy_kcal, selectDefaultFoodPortion(food)),
  };
}

export function foodCatalogueMacroRows(food: FoodCatalogueItem): CatalogueMacroRow[] {
  const portion = selectDefaultFoodPortion(food);
  return CARD_MACRO_ORDER.map((code) => ({
    code,
    label: macroLabels[code],
    value: formatScaledValue(food.macros[code], portion),
  }));
}

export function foodCatalogueNutrientRows(
  food: FoodCatalogueItem,
  portion: FoodCataloguePortion | null = selectDefaultFoodPortion(food),
): CatalogueNutrientRow[] {
  return food.nutrients.map((nutrient) => ({
    code: nutrient.nutrient_code,
    label: foodCatalogueNutrientLabel(nutrient.nutrient_code),
    unit: nutrient.unit,
    value: formatScaledValue(nutrient.value_per_100g, portion),
  }));
}

export function foodCatalogueBasisLabel(portion: FoodCataloguePortion | null): string {
  return portion ? `در ${portion.label_fa}` : "در هر ۱۰۰ گرم";
}

export function foodCataloguePortionRows(food: FoodCatalogueItem): CataloguePortionRow[] {
  return food.portions.map((portion) => ({
    code: portion.code,
    grams: formatCatalogueDisplayNumber(portion.grams, 0),
    label: portion.label_fa,
    quantity: formatCatalogueDisplayNumber(portion.quantity, 1),
  }));
}

export function foodCatalogueNutrientLabel(code: string): string {
  return nutrientLabels[code] ?? code.replaceAll("_", " ");
}

export function formatCatalogueDisplayNumber(value: number | string, maximumFractionDigits = 1): string {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits }).format(numeric);
}

export function foodCatalogueCategoryLabel(category: string): string {
  const labels: Readonly<Record<string, string>> = {
    dairy: "لبنیات",
    fats: "چربی‌ها",
    fruit: "میوه",
    grains: "غلات",
    legumes: "حبوبات",
    nuts_seeds: "مغزها و دانه‌ها",
    poultry: "مرغ و ماکیان",
    starchy_vegetables: "سبزیجات نشاسته‌ای",
    vegetables: "سبزیجات",
  };
  return labels[category] ?? category.replaceAll("_", " ");
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

function formatScaledValue(value: number | string | null | undefined, portion: FoodCataloguePortion | null): string {
  const scaled = scaleFoodCatalogueValue(value, portion);
  return scaled === null ? "—" : formatCatalogueDisplayNumber(scaled, 1);
}
