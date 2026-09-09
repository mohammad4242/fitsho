import { render, screen, waitFor } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";
import { useQuery } from "@tanstack/react-query";

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(() => ({
    data: null,
    error: null,
    isError: false,
    isFetching: false,
    isPending: false,
    isStale: false,
  })),
}));
jest.mock("expo-router", () => ({ useRouter: jest.fn(() => ({ push: jest.fn() })), useFocusEffect: jest.fn() }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn(() => ({ request: jest.fn(), download: jest.fn() })) }));
jest.mock("./nutritionTrackingApi", () => ({ createNutritionTrackingApi: jest.fn(() => ({ getDailyTracking: jest.fn() })) }));

import { NutritionSummaryCard } from "./NutritionSummaryCard";
import type { NutritionEstimate } from "./nutritionApi";

const mockUseQuery = jest.mocked(useQuery);

const estimate = {
  confidence: "high",
  confidence_reasons: [],
  created_at: "2026-09-10T00:00:00Z",
  formula_version: "nutrition-formula-v1",
  id: "estimate-1",
  input_snapshot: {},
  is_stale: false,
  micronutrients: {},
  policy_version: "nutrition-science-v1",
  revision: 1,
  status: "active",
  targets: {
    bmr: { confidence: "high", explanation_codes: [], maximum: 1700, minimum: 1500, preferred: 1600, preferred_maximum: 1650, source_ids: [], unit: "kcal/day" },
    carbohydrate: { confidence: "high", explanation_codes: [], maximum: 240, minimum: 180, preferred: 210, preferred_maximum: 220, source_ids: [], unit: "g/day" },
    fat: { confidence: "high", explanation_codes: [], maximum: 80, minimum: 50, preferred: 65, preferred_maximum: 70, source_ids: [], unit: "g/day" },
    goal_calories: { confidence: "high", explanation_codes: [], maximum: 2300, minimum: 1900, preferred: 2100, preferred_maximum: 2200, source_ids: [], unit: "kcal/day" },
    protein: { confidence: "high", explanation_codes: [], maximum: 140, minimum: 100, preferred: 120, preferred_maximum: 130, source_ids: [], unit: "g/day" },
    tdee: { confidence: "high", explanation_codes: [], maximum: 2600, minimum: 2200, preferred: 2400, preferred_maximum: 2500, source_ids: [], unit: "kcal/day" },
  },
} as unknown as NutritionEstimate;

test("renders target calorie and TDEE rings with the web macro strip", async () => {
  render(<NutritionSummaryCard connectivityStatus="online" estimate={estimate} />);

  expect(screen.getByText("کالری هدف")).toBeTruthy();
  await waitFor(() => expect(screen.getByText("۲٬۱۰۰")).toBeTruthy(), { timeout: 1500 });
  expect(screen.getByRole("progressbar", { name: "پیشرفت کالری هدف" }).props.accessibilityValue)
    .toEqual({ max: 100, min: 0, now: 100 });
  expect(screen.getByText("TDEE (کل مصرف روزانه)")).toBeTruthy();
  await waitFor(() => expect(screen.getByText("BMR: ۱٬۶۰۰")).toBeTruthy(), { timeout: 1500 });
  await waitFor(() => expect(screen.getByText("کالری اضافه: ۸۰۰")).toBeTruthy(), { timeout: 1500 });
  expect(screen.getByRole("progressbar", { name: "تفکیک BMR و کالری اضافه در TDEE" })).toBeTruthy();
  expect(screen.getByText("پروتئین")).toBeTruthy();
  expect(screen.getByText("کربوهیدرات")).toBeTruthy();
  expect(screen.getByText("چربی")).toBeTruthy();
});

test("uses the web minimum-to-maximum fallback when a macro has no preferred target", () => {
  const rangeEstimate = {
    ...estimate,
    targets: {
      ...estimate.targets,
      protein: { ...estimate.targets.protein, preferred: null },
    },
  } as unknown as NutritionEstimate;

  render(<NutritionSummaryCard connectivityStatus="online" estimate={rangeEstimate} />);

  expect(screen.getByText("۱۰۰–۱۴۰ گرم")).toBeTruthy();
});

test("shows consumed-today context when tracking data is available", async () => {
  mockUseQuery.mockReturnValueOnce({
    data: {
      actual_totals: { energy_kcal: 1050, protein_g: 61 },
      data_status: "sufficient",
      entries: [],
    },
    error: null,
    isError: false,
    isFetching: false,
    isPending: false,
    isStale: false,
  } as never);

  render(<NutritionSummaryCard connectivityStatus="online" estimate={estimate} />);

  expect(screen.getByText("دریافت امروز ۱٬۰۵۰ کیلوکالری")).toBeTruthy();
  expect(screen.getByText("۶۱ گرم")).toBeTruthy();
  await waitFor(() => {
    expect(screen.getByText("۲٬۱۰۰")).toBeTruthy();
    expect(screen.getByText("۲٬۴۰۰")).toBeTruthy();
    expect(screen.getByText("BMR: ۱٬۶۰۰")).toBeTruthy();
    expect(screen.getByText("کالری اضافه: ۸۰۰")).toBeTruthy();
  }, { timeout: 1500 });
});
