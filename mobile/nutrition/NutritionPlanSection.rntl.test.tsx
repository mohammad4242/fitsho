import { render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("@tanstack/react-query", () => ({
  useMutation: jest.fn(() => ({ isPending: false, mutate: jest.fn() })),
  useQuery: jest.fn(),
  useQueryClient: jest.fn(() => ({ invalidateQueries: jest.fn(), setQueryData: jest.fn() })),
}));
jest.mock("expo-file-system", () => ({ Directory: class {}, File: class {}, Paths: { document: "document" } }));
jest.mock("expo-crypto", () => ({ randomUUID: jest.fn(() => "uuid") }));
jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../platform/connectivity", () => ({
  connectivityMonitor: {
    getSnapshot: () => ({ status: "online" }),
    subscribe: jest.fn(() => jest.fn()),
  },
}));
jest.mock("./nutritionPlanApi", () => ({ createNutritionPlanApi: jest.fn() }));
jest.mock("./nutritionPlanActionsApi", () => ({ createNutritionPlanActionsApi: jest.fn() }));
jest.mock("./nutritionPlanPdfStore", () => ({
  ExpoNutritionPlanPdfStore: jest.fn().mockImplementation(() => ({
    get: jest.fn().mockImplementation(() => new Promise<null>(() => undefined)),
  }) as never),
}));

import { useQuery } from "@tanstack/react-query";
import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createNutritionPlanActionsApi } from "./nutritionPlanActionsApi";
import { NutritionPlanSection } from "./NutritionPlanSection";
import { createNutritionPlanApi } from "./nutritionPlanApi";

const mockUseQuery = jest.mocked(useQuery);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockCreatePlanApi = jest.mocked(createNutritionPlanApi);
const mockCreateActionsApi = jest.mocked(createNutritionPlanActionsApi);

const activePlan = {
  budget_status: "within_budget",
  created_at: "2026-09-07T00:00:00Z",
  days: [{
    cost_irr: 2_000_000,
    day_index: 0,
    meals: [],
    nutrient_totals: { energy_kcal: 2_100, protein_g: 140 },
    plan_date: "2026-09-07",
  }],
  explanation_codes: [],
  food_data_manifest: {},
  formula_version: "formula-v1",
  id: "plan-1",
  input_snapshot: { main_meals_per_day: 3, snacks_per_day: 1 },
  is_user_visible: true,
  lifecycle_status: "active",
  nutrients: {
    goal_calories: { data_confidence: "high", difference_from_limit: null, difference_from_preferred: 0, explanation_codes: [], minimum_or_maximum: null, nutrient_code: "goal_calories", planned: 2_100, preferred: 2_100, reason_codes: [], reference_kind: "target", status: "ok", unit: "kcal/day" },
    protein: { data_confidence: "high", difference_from_limit: null, difference_from_preferred: 0, explanation_codes: [], minimum_or_maximum: null, nutrient_code: "protein", planned: 140, preferred: 140, reason_codes: [], reference_kind: "target", status: "ok", unit: "g/day" },
    carbohydrate: { data_confidence: "high", difference_from_limit: null, difference_from_preferred: 0, explanation_codes: [], minimum_or_maximum: null, nutrient_code: "carbohydrate", planned: 220, preferred: 220, reason_codes: [], reference_kind: "target", status: "ok", unit: "g/day" },
    total_fat: { data_confidence: "high", difference_from_limit: null, difference_from_preferred: 0, explanation_codes: [], minimum_or_maximum: null, nutrient_code: "total_fat", planned: 65, preferred: 65, reason_codes: [], reference_kind: "target", status: "ok", unit: "g/day" },
  },
  physician_approved: true,
  physician_approved_at: "2026-09-07T00:00:00Z",
  physician_change_summary: [],
  physician_display_name: null,
  physician_user_visible_notes: null,
  plan_role: "budget",
  planner_policy_version: "planner-policy-v1",
  planner_version: "planner-v1",
  price_snapshot: { references: [{ source: "approved" }] },
  repair_actions: [],
  review_status: "approved",
  revision: 2,
  scientific_policy_version: "science-v1",
  start_date: "2026-09-07",
  supersedes_plan_id: null,
  warning_codes: [],
  weekly_budget_irr: 10_000_000,
  weekly_cost_irr: 9_000_000,
};

const shoppingList = {
  approval_status: "approved",
  items: [],
  plan_id: "plan-1",
  plan_revision: 2,
  total_cost_irr: 0,
  warning_codes: [],
};

const idealPlan = {
  ...activePlan,
  id: "ideal-plan",
  plan_role: "ideal",
  weekly_cost_irr: 12_000_000,
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
  mockUseMobileAuth.mockReturnValue({ download: jest.fn(), request: jest.fn() } as never);
  mockCreatePlanApi.mockReturnValue({
    downloadPdf: jest.fn(),
    generate: jest.fn(),
    get: jest.fn(),
    getActive: jest.fn(),
    getHistory: jest.fn(),
    getLatest: jest.fn(),
    getLatestBundle: jest.fn(),
    getShoppingList: jest.fn(),
    selectBundle: jest.fn(),
  } as never);
  mockCreateActionsApi.mockReturnValue({
    confirmRemoveMeal: jest.fn(),
    confirmReplaceFood: jest.fn(),
    confirmReplaceMeal: jest.fn(),
    getFeedback: jest.fn(),
    getFoodReplacementOptions: jest.fn(),
    getMealReplacementOptions: jest.fn(),
    previewRemoveMeal: jest.fn(),
    previewReplaceFood: jest.fn(),
    previewReplaceMeal: jest.fn(),
    setMealFeedback: jest.fn(),
    setMealLock: jest.fn(),
  } as never);
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "plan" && key[2] === "active") return queryResult(activePlan);
    if (key[1] === "plan" && key[2] === "latest") return queryResult(null);
    if (key[1] === "plan-bundle") return queryResult({
      budget_plan: activePlan,
      bundle_id: "bundle-1",
      comparison: {
        meaningful_quality_improvement: true,
        monthly_cost_gap_irr: 12_000_000,
        show_ideal_plan: true,
      },
      generation_id: "generation-1",
      ideal_plan: idealPlan,
      outcome: "success",
      reason_codes: [],
      selected_plan_id: activePlan.id,
      selected_plan_role: "budget",
      warning_codes: [],
    });
    if (key[1] === "plans") return queryResult([]);
    if (key[1] === "meal-feedback") return queryResult({ feedback: {} });
    if (key[1] === "shopping-list") return queryResult(shoppingList);
    return queryResult(undefined);
  });
});

test("shows active role, approval, date context, and weekly plan content first", () => {
  render(
    <SafeAreaProvider initialMetrics={{ frame: { height: 800, width: 390, x: 0, y: 0 }, insets: { bottom: 0, left: 0, right: 0, top: 0 } }}>
      <NutritionPlanSection safety={{ can_continue_onboarding: true } as never} />
    </SafeAreaProvider>,
  );

  expect(screen.getByText("برنامه فعال")).toBeTruthy();
  expect(screen.getByText("برنامه با بودجه شما")).toBeTruthy();
  expect(screen.getByText("تأیید شده")).toBeTruthy();
  expect(screen.getByText("شروع برنامه")).toBeTruthy();
  expect(screen.getByText("روزهای برنامه")).toBeTruthy();
  expect(screen.getByRole("radio", { name: "نسخه اقتصادی، برنامه فعال شما" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "نسخه ایده‌آل" })).toBeTruthy();
  expect(screen.getAllByText("کربوهیدرات").length).toBeGreaterThanOrEqual(1);
});
