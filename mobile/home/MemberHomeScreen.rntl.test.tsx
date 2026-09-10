import { fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("@tanstack/react-query", () => ({ useQuery: jest.fn() }));
jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../ui/navigation/RouteGuards", () => ({ useMobileRouteSnapshot: jest.fn() }));
jest.mock("../platform/connectivity", () => ({
  connectivityMonitor: {
    getSnapshot: () => ({ status: "online" }),
    subscribe: jest.fn(() => jest.fn()),
  },
}));
jest.mock("../profile/profileApi", () => ({ createProfileApi: jest.fn() }));
jest.mock("../workouts/workoutApi", () => ({ createWorkoutPlanApi: jest.fn() }));
jest.mock("../nutrition/nutritionApi", () => ({ createNutritionApi: jest.fn() }));
jest.mock("../nutrition/nutritionPlanApi", () => ({ createNutritionPlanApi: jest.fn() }));
jest.mock("../nutrition/nutritionTrackingApi", () => ({ createNutritionTrackingApi: jest.fn() }));

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createNutritionApi } from "../nutrition/nutritionApi";
import { createNutritionPlanApi } from "../nutrition/nutritionPlanApi";
import { createNutritionTrackingApi } from "../nutrition/nutritionTrackingApi";
import { createProfileApi } from "../profile/profileApi";
import { useMobileRouteSnapshot } from "../ui/navigation/RouteGuards";
import { createWorkoutPlanApi } from "../workouts/workoutApi";
import { MemberHomeScreen } from "./MemberHomeScreen";

const mockPush = jest.fn();
const mockUseQuery = jest.mocked(useQuery);
const mockUseRouter = jest.mocked(useRouter);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockUseRouteSnapshot = jest.mocked(useMobileRouteSnapshot);
const mockCreateProfileApi = jest.mocked(createProfileApi);
const mockCreateWorkoutApi = jest.mocked(createWorkoutPlanApi);
const mockCreateNutritionApi = jest.mocked(createNutritionApi);
const mockCreateNutritionPlanApi = jest.mocked(createNutritionPlanApi);
const mockCreateNutritionTrackingApi = jest.mocked(createNutritionTrackingApi);

let productMode: "both" | "training" = "both";

const dailyTracking = {
  actual_totals: {
    carbohydrate_g: 70,
    energy_kcal: 750,
    protein_g: 52,
    total_fat_g: 24,
  },
  check_in_status: "on_plan",
  data_status: "sufficient",
  entries: [],
  entry_date: "2026-09-09",
  plan_revision_id: null,
};

const nutritionPlan = {
  days: [{
    nutrient_totals: {
      carbohydrate_g: 220,
      energy_kcal: 2000,
      protein_g: 140,
      total_fat_g: 65,
    },
    plan_date: "2026-09-09",
  }],
  physician_approved: true,
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

function resolved<T>(value: T) {
  return jest.fn<() => Promise<T>>().mockResolvedValue(value);
}

function renderHome() {
  return render(
    <SafeAreaProvider initialMetrics={{
      frame: { height: 800, width: 400, x: 0, y: 0 },
      insets: { bottom: 0, left: 0, right: 0, top: 0 },
    }}>
      <MemberHomeScreen />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  productMode = "both";
  mockPush.mockClear();
  mockUseMobileAuth.mockReturnValue({
    download: jest.fn(),
    request: jest.fn(),
    status: "signed_in",
    user: { email: "mary@example.com", id: "user-1" },
  } as never);
  mockUseRouteSnapshot.mockImplementation(() => ({
    profile: { completionState: "complete", productMode, status: "resolved" },
    session: { status: "signed_in", user: { email: "mary@example.com", id: "user-1" } },
    specialistAccess: { coach: "denied", physician: "denied" },
  } as never));
  mockUseRouter.mockReturnValue({ push: mockPush } as never);
  mockCreateProfileApi.mockReturnValue({ getSharedProfile: resolved({ display_name: "مریم" }) } as never);
  mockCreateWorkoutApi.mockReturnValue({ getActive: resolved(null) } as never);
  mockCreateNutritionApi.mockReturnValue({ getCurrentEstimate: resolved(null) } as never);
  mockCreateNutritionPlanApi.mockReturnValue({ getLatest: resolved(nutritionPlan) } as never);
  mockCreateNutritionTrackingApi.mockReturnValue({ getDailyTracking: resolved(dailyTracking) } as never);
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[0] === "profile") return queryResult({ display_name: "مریم" });
    if (key[0] === "workouts") return queryResult(null);
    if (key[1] === "plan") return queryResult(nutritionPlan);
    if (key[1] === "estimate") return queryResult(null);
    return queryResult(dailyTracking);
  });
});

test("routes from the home dashboard to profile and feature destinations", () => {
  renderHome();

  expect(screen.getByRole("header", { name: "سلام، مریم" })).toBeTruthy();
  fireEvent.press(screen.getByLabelText("باز کردن پروفایل"));
  fireEvent.press(screen.getByRole("button", { name: "تحلیل بدن" }));
  fireEvent.press(screen.getByRole("button", { name: "ثبت غذا" }));
  fireEvent.press(screen.getByRole("button", { name: "نمایش جزئیات تغذیه" }));
  fireEvent.press(screen.getByRole("button", { name: "مشاهده برنامه" }));

  expect(mockPush.mock.calls).toEqual([
    ["/member/profile"],
    ["/member/body-analysis-capture"],
    ["/member/nutrition-tracking"],
    ["/member/nutrition"],
    ["/member/workouts"],
  ]);
});

test("hides nutrition dashboard content when the member selects training only", () => {
  productMode = "training";
  renderHome();

  expect(screen.getByRole("button", { name: "تحلیل بدن" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "ثبت غذا" })).toBeNull();
  expect(screen.queryByRole("button", { name: "نمایش جزئیات تغذیه" })).toBeNull();
});
