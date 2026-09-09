import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("@tanstack/react-query", () => ({ useQuery: jest.fn(), useQueryClient: jest.fn() }));
jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../platform/connectivity", () => ({
  connectivityMonitor: {
    getSnapshot: () => ({ status: "online" }),
    subscribe: () => () => undefined,
  },
}));
jest.mock("../ui/navigation/BackBehaviorProvider", () => ({ useAndroidBackHandler: jest.fn() }));
jest.mock("../accountDeletion/AccountPrivacyLinks", () => ({ AccountPrivacyLinks: () => null }));
jest.mock("./physicianNutritionReviewApi", () => ({ createPhysicianNutritionReviewApi: jest.fn() }));

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createPhysicianNutritionReviewApi } from "./physicianNutritionReviewApi";
import { PhysicianNutritionReviewScreen } from "./PhysicianNutritionReviewScreen";

const mockUseQuery = jest.mocked(useQuery);
const mockUseQueryClient = jest.mocked(useQueryClient);
const mockUseRouter = jest.mocked(useRouter);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockCreateApi = jest.mocked(createPhysicianNutritionReviewApi);

const queueItem = {
  member_display_name: "مریم احمدی",
  member_profile_photo_url: null,
  overdue: false,
  physician_user_id: "physician-1",
  plan_id: "plan-1",
  priority: 1,
  requested_at: "2026-09-09T08:00:00Z",
  review_id: "review-1",
  reviewed_at: null,
  status: "pending",
  target_review_by: null,
  user_id: "user-1",
};

const plan = {
  budget_status: "within_budget",
  created_at: "2026-09-09T08:00:00Z",
  days: [{
    cost_irr: 300_000,
    day_index: 0,
    meals: [{
      foods: [{
        cost_irr: 120_000,
        food_id: "food-1",
        grams: 100,
        item_kind: "food",
        name_en: "Chicken breast",
        name_fa: "سینه مرغ",
        nutrients: { protein_g: 31 },
        slug: "chicken-breast",
      }],
      id: "meal-1",
      name_en: "Lunch",
      name_fa: "ناهار",
    }],
    nutrient_totals: { protein_g: 31 },
    plan_date: "2026-09-09",
  }],
  explanation_codes: [],
  food_data_manifest: { version: "v1" },
  formula_version: "nutrition-v1",
  id: "plan-1",
  input_snapshot: { dietary_pattern: "omnivore" },
  is_user_visible: true,
  lifecycle_status: "active",
  nutrients: {
    protein: {
      data_confidence: "high",
      difference_from_limit: null,
      difference_from_preferred: 0,
      explanation_codes: [],
      minimum_or_maximum: null,
      nutrient_code: "protein_g",
      planned: 100,
      preferred: 100,
      reason_codes: [],
      reference_kind: "daily_target",
      status: "adequate",
      unit: "g/day",
    },
  },
  physician_approved: false,
  physician_approved_at: null,
  physician_change_summary: [],
  physician_display_name: null,
  physician_user_visible_notes: null,
  plan_role: "primary",
  planner_policy_version: "policy-v1",
  planner_version: "planner-v1",
  price_snapshot: { version: "v1" },
  repair_actions: [],
  review_status: "pending",
  revision: 1,
  scientific_policy_version: "science-v1",
  start_date: "2026-09-09",
  supersedes_plan_id: null,
  warning_codes: [],
  weekly_budget_irr: 10_000_000,
  weekly_cost_irr: 7_000_000,
};

const context = {
  conditions: [],
  flags: {},
  medical_condition_policy_version: "medical-v1",
  medications: [],
  other_relevant_condition: null,
  physician_dietary_restrictions: null,
  safety_outcome: "safe",
  safety_reason_codes: [],
};

const food = {
  canonical_unit: "g",
  id: "food-1",
  name_en: "Chicken breast",
  name_fa: "سینه مرغ",
  slug: "chicken-breast",
};

const supplement = {
  active_ingredients: [],
  allergen_codes: [],
  contraindication_codes: [],
  id: "supplement-1",
  interaction_codes: [],
  name_en: "Vitamin D",
  name_fa: "ویتامین دی",
  nutrient_contribution_per_unit: {},
  slug: "vitamin-d",
  source_name: "catalogue",
  source_reference: "catalogue-v1",
  upper_bound_rules: [],
  verification_status: "verified",
};

const queryClient = {
  invalidateQueries: jest.fn<() => Promise<undefined>>().mockResolvedValue(undefined),
  setQueryData: jest.fn(),
};

function queryResult<T>(data: T) {
  return {
    data,
    error: null,
    isError: false,
    isFetching: false,
    isPending: false,
    isStale: false,
    refetch: jest.fn<() => Promise<undefined>>().mockResolvedValue(undefined),
  } as never;
}

function renderScreen() {
  return render(
    <SafeAreaProvider initialMetrics={{
      frame: { height: 800, width: 390, x: 0, y: 0 },
      insets: { bottom: 0, left: 0, right: 0, top: 0 },
    }}>
      <PhysicianNutritionReviewScreen />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  mockUseRouter.mockReturnValue({ back: jest.fn() } as never);
  mockUseMobileAuth.mockReturnValue({ request: jest.fn() } as never);
  mockUseQueryClient.mockReturnValue(queryClient as never);
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "access") return queryResult({ authorized: true });
    if (key[1] === "list") return queryResult([queueItem]);
    if (key[1] === "detail") {
      const detailKey = String(key[2]);
      if (detailKey.endsWith(":medical-context")) return queryResult(context);
      if (detailKey.endsWith(":labs")) return queryResult([]);
      if (detailKey.endsWith(":supplement-orders")) return queryResult([]);
      return detailKey === "selected" ? queryResult(undefined) : queryResult(plan);
    }
    if (key[1] === "foods") return queryResult([food]);
    if (key[1] === "supplement-catalogue") return queryResult([supplement]);
    return queryResult(undefined);
  });
  mockCreateApi.mockReturnValue({
    action: jest.fn<() => Promise<typeof plan>>().mockResolvedValue(plan),
    adjustFoodQuantity: jest.fn<() => Promise<typeof plan>>().mockResolvedValue(plan),
    claim: jest.fn<() => Promise<{ review_id: string; status: string }>>().mockResolvedValue({ review_id: "review-1", status: "claimed" }),
    createSupplementOrder: jest.fn<() => Promise<never>>().mockResolvedValue(undefined as never),
    getAccess: jest.fn<() => Promise<{ authorized: true }>>().mockResolvedValue({ authorized: true }),
    getLabs: jest.fn<() => Promise<never[]>>().mockResolvedValue([]),
    getMedicalContext: jest.fn<() => Promise<typeof context>>().mockResolvedValue(context),
    getPlan: jest.fn<() => Promise<typeof plan>>().mockResolvedValue(plan),
    list: jest.fn<() => Promise<typeof queueItem[]>>().mockResolvedValue([queueItem]),
    listFoods: jest.fn<() => Promise<typeof food[]>>().mockResolvedValue([food]),
    listSupplementCatalogue: jest.fn<() => Promise<typeof supplement[]>>().mockResolvedValue([supplement]),
    listSupplementOrders: jest.fn<() => Promise<never[]>>().mockResolvedValue([]),
    removeMeal: jest.fn<() => Promise<typeof plan>>().mockResolvedValue(plan),
    replaceFood: jest.fn<() => Promise<typeof plan>>().mockResolvedValue(plan),
    requestLabs: jest.fn<() => Promise<{ id: string; requested_tests: string[]; status: string }>>().mockResolvedValue({ id: "request-1", requested_tests: ["CBC"], status: "requested" }),
    reviewLab: jest.fn<() => Promise<never>>().mockResolvedValue(undefined as never),
    transitionSupplementOrder: jest.fn<() => Promise<never>>().mockResolvedValue(undefined as never),
    updateSupplementOrder: jest.fn<() => Promise<never>>().mockResolvedValue(undefined as never),
  } as never);
});

test("moves from queue to a native case with segmented clinical sections", async () => {
  renderScreen();

  fireEvent.press(await screen.findByRole("button", { name: "شروع بررسی" }));
  expect(await screen.findByText("وضعیت مواد مغذی")).toBeTruthy();

  fireEvent.press(screen.getByRole("radio", { name: "مکمل‌ها" }));
  expect(screen.getByText("دستورهای مکمل")).toBeTruthy();

  fireEvent.press(screen.getByRole("radio", { name: "یادداشت‌ها" }));
  expect(screen.getByLabelText("یادداشت قابل مشاهده برای کاربر")).toBeTruthy();
});

test("returns from the selected physician case to the queue before leaving the route", async () => {
  const routerBack = jest.fn();
  mockUseRouter.mockReturnValue({ back: routerBack } as never);
  renderScreen();

  fireEvent.press(await screen.findByRole("button", { name: "شروع بررسی" }));
  expect(await screen.findByText("وضعیت مواد مغذی")).toBeTruthy();

  fireEvent.press(screen.getByRole("button", { name: "بازگشت به صف" }));
  await waitFor(() => expect(screen.getByText("صف پرونده‌ها")).toBeTruthy());
  expect(routerBack).not.toHaveBeenCalled();

  fireEvent.press(screen.getByRole("button", { name: "بازگشت" }));
  expect(routerBack).toHaveBeenCalledTimes(1);
});
