import { fireEvent, render, screen } from "@testing-library/react-native";
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
    functional_role: null,
    is_required: true,
    max_grams: 100,
    min_grams: 50,
    reference_grams: 75,
  }],
  name_en: "Vegetable omelette",
  name_fa: "املت سبزیجات",
  verification_status: "verified",
};

function queryResult<T>(data: T) {
  return {
    data,
    error: null,
    isError: false,
    isFetching: false,
    isPending: false,
    isStale: false,
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

test("dedicated meal mode matches the meal hierarchy and opens native detail sheet", () => {
  renderCatalogue("meals");

  expect(screen.getByRole("header", { name: "کاتالوگ وعده‌ها" })).toBeTruthy();
  expect(screen.queryByRole("radiogroup")).toBeNull();
  expect(screen.getAllByText("صبحانه")).toHaveLength(2);

  fireEvent.press(screen.getByText("املت سبزیجات"));

  expect(screen.getByText("مواد تشکیل‌دهنده")).toBeTruthy();
  expect(screen.getByText("تخم‌مرغ")).toBeTruthy();
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
});
