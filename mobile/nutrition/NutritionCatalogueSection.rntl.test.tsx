import { fireEvent, render, screen, within } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StyleSheet } from "react-native";
import type { ReactTestInstance } from "react-test-renderer";

jest.mock("@tanstack/react-query", () => ({ useQuery: jest.fn() }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../platform/connectivity", () => ({
  connectivityMonitor: {
    getSnapshot: () => ({ status: "online" }),
    subscribe: jest.fn(() => jest.fn()),
  },
}));
jest.mock("./nutritionCatalogueApi", () => ({ createNutritionCatalogueApi: jest.fn() }));

import { useQuery } from "@tanstack/react-query";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createNutritionCatalogueApi } from "./nutritionCatalogueApi";
import { NutritionCatalogueSection } from "./NutritionCatalogueSection";

const mockUseQuery = jest.mocked(useQuery);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockCreateCatalogueApi = jest.mocked(createNutritionCatalogueApi);

const food = {
  allergen_metadata_verified: true,
  allergen_tags: [],
  category: "legumes",
  id: "food-1",
  image_url: null,
  macros: { carbohydrate_g: "20", energy_kcal: "120", protein_g: "8", total_fat_g: "2" },
  measurement_basis: "raw",
  name_en: "Lentils",
  name_fa: "عدس",
  nutrient_basis: { quantity: "100", unit: "g" },
  nutrients: [],
  portions: [],
  slug: "lentils",
  source: { access_date: "2026-09-09", data_version: "v1", name: "USDA", reference: "fdc-1", source_food_id: "1" },
};

const meal = {
  calculation_mode: "simple",
  category: "breakfast",
  code: "breakfast-1",
  id: "meal-1",
  image_url: null,
  items: [{
    food_id: "food-1",
    food_name_en: "Egg",
    food_name_fa: "تخم‌مرغ",
    food_slug: "egg",
    functional_role: "protein",
    is_required: true,
    max_grams: 100,
    min_grams: 50,
    reference_grams: 75,
  }],
  name_en: "Vegetable omelette",
  name_fa: "املت سبزیجات",
  verification_status: "verified",
};

function queryResult<T>(data: T, overrides: { readonly isFetching?: boolean; readonly isStale?: boolean } = {}) {
  return {
    data,
    error: null,
    isError: false,
    isFetching: overrides.isFetching ?? false,
    isPending: false,
    isStale: overrides.isStale ?? false,
  } as never;
}

function renderCatalogue(initialMode: "foods" | "meals") {
  return render(
    <SafeAreaProvider initialMetrics={{ frame: { height: 800, width: 400, x: 0, y: 0 }, insets: { bottom: 0, left: 0, right: 0, top: 0 } }}>
      <NutritionCatalogueSection initialMode={initialMode} />
    </SafeAreaProvider>,
  );
}

function findAncestorStyle(node: ReactTestInstance, key: string): Record<string, unknown> {
  let current = node.parent;
  while (current !== null) {
    const style = StyleSheet.flatten(current.props.style) as Record<string, unknown> | undefined;
    if (style?.[key] !== undefined) return style;
    current = current.parent;
  }
  throw new Error(`Ancestor style ${key} not found`);
}

function isDescendant(parent: ReactTestInstance, node: ReactTestInstance): boolean {
  let current = node.parent;
  while (current !== null) {
    if (current === parent) return true;
    current = current.parent;
  }
  return false;
}

beforeEach(() => {
  mockCreateCatalogueApi.mockReturnValue({
    getFoodCatalogue: jest.fn(),
    getMealCatalogue: jest.fn(),
  } as never);
  mockUseMobileAuth.mockReturnValue({ request: jest.fn() } as never);
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "meal-catalogue") {
      return queryResult({ categories: ["breakfast"], items: [meal] });
    }
    return queryResult({ categories: ["legumes"], items: [food], page: 1, page_size: 24, total: 1 });
  });
});

test("dedicated meal mode matches the web hierarchy and expands ingredients inline", () => {
  renderCatalogue("meals");

  expect(screen.getByText("ترکیب‌های کنترل‌شده تغذیه")).toBeTruthy();
  expect(screen.getByRole("header", { name: "کاتالوگ وعده‌های غذایی" })).toBeTruthy();
  expect(screen.getByText("ترکیب معتبر هر وعده و بازه مجاز مواد غذایی را مشاهده کنید. مقدار نهایی را موتور تغذیه تعیین می‌کند.")).toBeTruthy();
  expect(screen.queryByRole("radiogroup")).toBeNull();
  expect(screen.getByText("دسته‌بندی وعده‌ها:")).toBeTruthy();
  for (const category of ["همه", "صبحانه", "ناهار", "پس از تمرین", "میان‌وعده", "شام"]) {
    expect(screen.getByRole("button", { name: category })).toBeTruthy();
  }
  expect(screen.getByRole("button", { name: "همه" }).props.accessibilityState).toMatchObject({ selected: true });

  const card = screen.getByTestId("meal-card-meal-1");
  const summary = screen.getByTestId("meal-card-meal-1-summary");
  const image = screen.getByLabelText("تصویر املت سبزیجات موجود نیست");
  expect(within(card).getByText(/breakfast-1/)).toBeTruthy();
  expect(within(card).getByText(/صبحانه/)).toBeTruthy();
  expect(within(card).getByText("املت سبزیجات")).toBeTruthy();
  expect(within(card).getByText("تأییدشده")).toBeTruthy();
  expect(screen.queryByText("تخم‌مرغ")).toBeNull();
  expect(screen.queryByText("Vegetable omelette")).toBeNull();
  expect(screen.queryByText(/ماده تأییدشده در این وعده/)).toBeNull();
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(isDescendant(card, image)).toBe(true);
  expect(StyleSheet.flatten(summary.props.style)).toMatchObject({ direction: "rtl", flexDirection: "row" });

  fireEvent.press(summary);

  expect(within(card).getByText("تخم‌مرغ")).toBeTruthy();
  expect(within(card).getByText("پروتئین")).toBeTruthy();
  expect(within(card).getByText("۵۰ تا ۱۰۰ گرم")).toBeTruthy();
  expect(within(card).getByText("الزامی")).toBeTruthy();
  expect(summary.props.accessibilityState).toMatchObject({ expanded: true });
  expect(screen.queryByRole("dialog")).toBeNull();

  fireEvent.press(summary);
  expect(within(card).queryByText("۵۰ تا ۱۰۰ گرم")).toBeNull();
});

test("dedicated meal mode preserves server verification statuses", () => {
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "meal-catalogue") {
      return queryResult({
        categories: ["breakfast", "lunch", "dinner"],
        items: [
          meal,
          { ...meal, code: "DR01", id: "meal-draft", name_fa: "وعده پیش‌نویس", verification_status: "draft" },
          { ...meal, code: "RT01", id: "meal-retired", name_fa: "وعده بازنشسته", verification_status: "retired" },
        ],
      });
    }
    return queryResult({ categories: ["legumes"], items: [food], page: 1, page_size: 24, total: 1 });
  });

  renderCatalogue("meals");

  expect(screen.getByText("تأییدشده")).toBeTruthy();
  expect(screen.getByText("پیش‌نویس")).toBeTruthy();
  expect(screen.getByText("بازنشسته")).toBeTruthy();
});

test("dedicated meal mode starts with all categories and an unfiltered request", async () => {
  renderCatalogue("meals");

  const mealQuery = mockUseQuery.mock.calls
    .map(([options]) => options as { readonly queryKey: readonly unknown[]; readonly queryFn: () => Promise<unknown> })
    .find((options) => options.queryKey[1] === "meal-catalogue");
  expect(mealQuery?.queryKey).toEqual(["nutrition", "meal-catalogue", null]);

  await mealQuery?.queryFn();
  const catalogueApi = mockCreateCatalogueApi.mock.results[0]?.value as { getMealCatalogue: jest.Mock };
  expect(catalogueApi.getMealCatalogue).toHaveBeenCalledWith(undefined);
});

test("dedicated meal mode renders stale cached data without a warning card", () => {
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "meal-catalogue") {
      return queryResult({ categories: ["breakfast"], items: [meal] }, { isFetching: true, isStale: true });
    }
    return queryResult({ categories: ["legumes"], items: [food], page: 1, page_size: 24, total: 1 });
  });

  renderCatalogue("meals");

  expect(screen.getByText("املت سبزیجات")).toBeTruthy();
  expect(screen.queryByText("نتایج کاتالوگ تازه‌سازی نشده‌اند.")).toBeNull();
});

test("dedicated food mode keeps search and category before phone-friendly cards", () => {
  renderCatalogue("foods");

  expect(screen.getByRole("header", { name: "کاتالوگ مواد غذایی" })).toBeTruthy();
  expect(screen.getByLabelText("جستجوی مواد غذایی")).toBeTruthy();
  expect(screen.queryByRole("radiogroup")).toBeNull();
  expect(screen.getByText("حبوبات")).toBeTruthy();

  fireEvent.press(screen.getByText("عدس"));

  expect(screen.getByText("ماکروها در ۱۰۰ گرم")).toBeTruthy();
  expect(findAncestorStyle(screen.getByText("عدس"), "flexDirection")).toMatchObject({ flexDirection: "row" });
  expect(findAncestorStyle(screen.getByLabelText("تصویر عدس موجود نیست"), "alignSelf")).toMatchObject({ alignSelf: "flex-start" });
});
