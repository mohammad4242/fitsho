import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { afterEach, beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StyleSheet } from "react-native";
import type { ReactTestInstance } from "react-test-renderer";

jest.mock("@tanstack/react-query", () => ({ useQuery: jest.fn(), useQueryClient: jest.fn() }));
jest.mock("expo-file-system", () => ({ File: class {} }));
jest.mock("expo-image-picker", () => ({}));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../ui/navigation/BackBehaviorProvider", () => ({ useAndroidBackHandler: jest.fn() }));
jest.mock("./nutritionTrackingApi", () => ({ createNutritionTrackingApi: jest.fn() }));
jest.mock("./nutritionCatalogueApi", () => ({ createNutritionCatalogueApi: jest.fn() }));
jest.mock("./nutritionApi", () => ({ createNutritionApi: jest.fn() }));

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createNutritionCatalogueApi } from "./nutritionCatalogueApi";
import { createNutritionApi } from "./nutritionApi";
import { NutritionTrackingSection } from "./NutritionTrackingSection";
import { createNutritionTrackingApi } from "./nutritionTrackingApi";

const mockUseQuery = jest.mocked(useQuery);
const mockUseQueryClient = jest.mocked(useQueryClient);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockCreateCatalogueApi = jest.mocked(createNutritionCatalogueApi);
const mockCreateNutritionApi = jest.mocked(createNutritionApi);
const mockCreateTrackingApi = jest.mocked(createNutritionTrackingApi);

const dailyTracking = {
  actual_totals: { calories: 640, energy_kcal: 640, protein_g: 42 },
  check_in_status: "not_recorded",
  data_status: "sufficient",
  entries: [],
  entry_date: "2026-09-09",
  plan_revision_id: null,
};

const catalogueFood = {
  allergen_metadata_verified: true,
  allergen_tags: [],
  category: "grain",
  id: "food-1",
  image_url: null,
  macros: {},
  measurement_basis: "per_100g",
  name_en: "Lentils",
  name_fa: "عدس",
  nutrient_basis: { quantity: "100", unit: "g" },
  nutrients: [],
  portions: [],
  slug: "lentils",
  source: { dataset: "USDA", reference: "fdc-1" },
};

const nutritionEstimate = {
  confidence: "high",
  confidence_reasons: [],
  created_at: "2026-09-09T07:00:00.000Z",
  formula_version: "test",
  id: "estimate-1",
  is_stale: false,
  micronutrients: {},
  policy_version: "test",
  revision: 1,
  status: "active",
  targets: {
    goal_calories: {
      confidence: "high",
      explanation_codes: [],
      maximum: 2300,
      minimum: 2100,
      preferred: 2200,
      preferred_maximum: 2250,
      source_ids: [],
      unit: "kcal/day",
    },
    protein: {
      confidence: "high",
      explanation_codes: [],
      maximum: 170,
      minimum: 130,
      preferred: 150,
      preferred_maximum: 160,
      source_ids: [],
      unit: "g/day",
    },
  },
};

const queryClient = {
  invalidateQueries: jest.fn<(...args: unknown[]) => Promise<void>>().mockResolvedValue(undefined),
  setQueryData: jest.fn<(...args: unknown[]) => void>(),
};

type TrackingApiDouble = {
  readonly addCatalogueFood: jest.Mock<(input: unknown) => Promise<unknown>>;
  readonly addQuickApproximation: jest.Mock<(input: unknown) => Promise<unknown>>;
  readonly saveDailyCheckIn: jest.Mock<(input: unknown) => Promise<unknown>>;
};

let trackingApi: TrackingApiDouble;

function findAncestorStyle(node: ReactTestInstance, key: string): Record<string, unknown> {
  let current = node.parent;
  while (current !== null) {
    const style = StyleSheet.flatten(current.props.style) as Record<string, unknown> | undefined;
    if (style?.[key] !== undefined) return style;
    current = current.parent;
  }
  throw new Error(`Ancestor style ${key} not found`);
}

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

function renderTracking() {
  return render(
    <SafeAreaProvider initialMetrics={{ frame: { height: 800, width: 400, x: 0, y: 0 }, insets: { bottom: 0, left: 0, right: 0, top: 0 } }}>
      <NutritionTrackingSection />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  jest.useFakeTimers();
  jest.setSystemTime(new Date("2026-09-09T08:00:00.000Z"));
  mockCreateTrackingApi.mockClear();
  mockCreateCatalogueApi.mockClear();
  mockCreateNutritionApi.mockClear();
  queryClient.invalidateQueries.mockClear();
  queryClient.setQueryData.mockClear();

  trackingApi = {
    addCatalogueFood: jest.fn<(input: unknown) => Promise<unknown>>().mockResolvedValue({}),
    addQuickApproximation: jest.fn<(input: unknown) => Promise<unknown>>().mockResolvedValue({}),
    saveDailyCheckIn: jest.fn<(input: unknown) => Promise<unknown>>().mockResolvedValue(dailyTracking),
  };
  mockCreateTrackingApi.mockReturnValue(trackingApi as never);
  mockCreateCatalogueApi.mockReturnValue({ getFoodCatalogue: jest.fn() } as never);
  mockCreateNutritionApi.mockReturnValue({ getCurrentEstimate: jest.fn() } as never);
  mockUseQueryClient.mockReturnValue(queryClient as never);
  mockUseMobileAuth.mockReturnValue({
    download: jest.fn(),
    request: jest.fn(),
    upload: jest.fn(),
  } as never);
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "tracking") return queryResult(dailyTracking);
    if (key[1] === "recent-foods") return queryResult([]);
    if (key[1] === "estimate") return queryResult(nutritionEstimate);
    return queryResult({ categories: ["grain"], items: [catalogueFood], page: 1, page_size: 40, total: 1 });
  });
});

test("shows the web-aligned heading and real nutrition targets before entry tools", () => {
  renderTracking();

  expect(screen.getByRole("header", { name: "ثبت تغذیه" })).toBeTruthy();
  expect(screen.getAllByText(/هدف برنامه/)).toHaveLength(2);
  expect(screen.getByText("عکس وعده")).toBeTruthy();
  expect(findAncestorStyle(screen.getByText("مصرف واقعی امروز"), "flexDirection")).toMatchObject({ flexDirection: "row" });
});

afterEach(() => {
  jest.useRealTimers();
});

test("saves the selected daily check-in through the member tracking API", async () => {
  renderTracking();

  fireEvent.press(screen.getByLabelText("مطابق برنامه"));

  await waitFor(() => {
    expect(trackingApi.saveDailyCheckIn).toHaveBeenCalledWith({
      entry_date: "2026-09-09",
      status: "on_plan",
    });
  });
});

test("shows validation feedback before sending an incomplete quick approximation", async () => {
  renderTracking();

  fireEvent.press(screen.getByLabelText("ثبت برآورد سریع"));

  expect(await screen.findByText("نام وعده و کالری معتبر وارد کن.")).toBeTruthy();
  expect(trackingApi.addQuickApproximation).not.toHaveBeenCalled();
});

test("registers the selected catalogue food with the entered gram amount", async () => {
  renderTracking();

  fireEvent.press(screen.getByRole("button", { name: "عدس" }));
  fireEvent.changeText(screen.getByLabelText("مقدار به گرم"), "125");
  expect(screen.getByLabelText("ثبت از کاتالوگ").props.accessibilityState.disabled).toBe(false);
  fireEvent.press(screen.getByLabelText("ثبت از کاتالوگ"));

  await waitFor(() => {
    expect(trackingApi.addCatalogueFood).toHaveBeenCalledWith({
      entry_date: "2026-09-09",
      food_id: "food-1",
      grams: 125,
      note: null,
    });
  });
});
