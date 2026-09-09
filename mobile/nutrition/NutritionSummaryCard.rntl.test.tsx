import { render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";

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

test("renders target calorie and TDEE rings with the web macro strip", () => {
  render(<NutritionSummaryCard connectivityStatus="online" estimate={estimate} />);

  expect(screen.getByText("کالری هدف")).toBeTruthy();
  expect(screen.getByText("۲٬۱۰۰")).toBeTruthy();
  expect(screen.getByRole("progressbar", { name: "پیشرفت کالری هدف" }).props.accessibilityValue)
    .toEqual({ max: 100, min: 0, now: 100 });
  expect(screen.getByText("TDEE (کل مصرف روزانه)")).toBeTruthy();
  expect(screen.getByText("پایه: ۱٬۶۰۰")).toBeTruthy();
  expect(screen.getByText("فعالیت: ۸۰۰")).toBeTruthy();
  expect(screen.getByRole("progressbar", { name: "تفکیک مصرف انرژی روزانه" })).toBeTruthy();
  expect(screen.getByText("پروتئین")).toBeTruthy();
  expect(screen.getByText("کربوهیدرات")).toBeTruthy();
  expect(screen.getByText("چربی")).toBeTruthy();
});
