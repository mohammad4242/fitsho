import { fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
  useQueryClient: jest.fn(),
}));
jest.mock("expo-document-picker", () => ({}));
jest.mock("expo-file-system", () => ({ File: class {} }));
jest.mock("expo-image-picker", () => ({}));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../media/privateMediaStore", () => ({ ExpoPrivateMediaStore: class {} }));
jest.mock("../platform/connectivity", () => ({
  connectivityMonitor: {
    getSnapshot: () => ({ status: "online" }),
    subscribe: jest.fn(() => jest.fn()),
  },
}));
jest.mock("../ui/navigation/BackBehaviorProvider", () => ({ useAndroidBackHandler: jest.fn() }));
jest.mock("./nutritionTrackingApi", () => ({ createNutritionTrackingApi: jest.fn() }));

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { NutritionClinicalSection } from "./NutritionClinicalSection";
import { createNutritionTrackingApi } from "./nutritionTrackingApi";

const mockUseQuery = jest.mocked(useQuery);
const mockUseQueryClient = jest.mocked(useQueryClient);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockCreateTrackingApi = jest.mocked(createNutritionTrackingApi);

const order = {
  acknowledged_at: null,
  combined_exposure_safety: {
    combined_exposure: {},
    food_contribution: {},
    hard_blocks: [],
    supplement_contribution: { protein_g: "20" },
  },
  daily_units: 1,
  dose_amount: 1,
  dose_unit: "قرص",
  duration_days: 30,
  ends_on: null,
  food_nutrient_contribution: {},
  frequency: "روزانه",
  id: "order-1",
  instructions: "بعد از صبحانه",
  linked_gap_codes: [],
  linked_lab_document_ids: [],
  name: "پروتئین وی",
  plan_id: "plan-1",
  rationale: "پشتیبانی از دریافت پروتئین",
  starts_on: null,
  status: "active",
  supplement_id: "supplement-1",
  supplement_nutrient_contribution: { protein_g: "20" },
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

beforeEach(() => {
  mockCreateTrackingApi.mockReturnValue({} as never);
  mockUseMobileAuth.mockReturnValue({
    download: jest.fn(),
    request: jest.fn(),
    upload: jest.fn(),
    user: null,
  } as never);
  mockUseQueryClient.mockReturnValue({ invalidateQueries: jest.fn() } as never);
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "supplement-orders") return queryResult([order]);
    if (key[1] === "supplement-catalogue") return queryResult([]);
    if (key[1] === "labs" || key[1] === "lab-requests") return queryResult([]);
    return queryResult([]);
  });
});

test("shows clinical heading, status filter, and disclosure without changing supplement safety flow", () => {
  render(
    <SafeAreaProvider initialMetrics={{ frame: { height: 900, width: 400, x: 0, y: 0 }, insets: { bottom: 0, left: 0, right: 0, top: 0 } }}>
      <NutritionClinicalSection />
    </SafeAreaProvider>,
  );

  expect(screen.getByRole("header", { name: "آزمایش‌ها و مکمل‌ها" })).toBeTruthy();
  expect(screen.getByTestId("supplement-status-filter")).toBeTruthy();
  expect(screen.getByText("پروتئین وی")).toBeTruthy();

  fireEvent.press(screen.getByLabelText("سهم تغذیه و کنترل مواجهه"));
  expect(screen.getByText("پروتئین")).toBeTruthy();

  fireEvent.press(screen.getByRole("radio", { name: "تمام‌شده" }));
  expect(screen.getByText("موردی با این وضعیت نیست")).toBeTruthy();
});
