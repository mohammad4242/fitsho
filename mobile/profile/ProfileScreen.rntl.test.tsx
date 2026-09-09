import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

import type { NutritionProfile } from "@fitician/core/nutrition";
import type { Profile, SharedProfile } from "@fitician/core/profile";

jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../ui/navigation/BackBehaviorProvider", () => ({ useAndroidBackHandler: jest.fn() }));
jest.mock("../ui/navigation/RouteGuards", () => ({
  useMobileRouteSnapshot: jest.fn(),
  useRefreshMobileProfileStatus: jest.fn(),
}));
jest.mock("./profileApi", () => ({ createProfileApi: jest.fn() }));
jest.mock("./ProfilePhotoControl", () => ({ ProfilePhotoControl: () => null }));
jest.mock("../accountDeletion/AccountPrivacyLinks", () => ({ AccountPrivacyLinks: () => null }));

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { useRouter } from "expo-router";
import { useMobileRouteSnapshot, useRefreshMobileProfileStatus } from "../ui/navigation/RouteGuards";
import { createProfileApi } from "./profileApi";
import { ProfileScreen } from "./ProfileScreen";

const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockUseRouter = jest.mocked(useRouter);
const mockUseRouteSnapshot = jest.mocked(useMobileRouteSnapshot);
const mockRefreshProfileStatus = jest.mocked(useRefreshMobileProfileStatus);
const mockCreateProfileApi = jest.mocked(createProfileApi);
const mockPush = jest.fn();

const shared = {
  birth_date: "1992-05-12",
  current_weight_kg: 64,
  display_name: "سارا احمدی",
  fitness_goal: "body_recomposition",
  height_cm: 168,
  product_mode: "both",
  profile_photo_url: null,
  sex: "female",
  user_id: "user-1",
  weight_measured_at: "2026-09-01T10:00:00Z",
} as SharedProfile;

const profile = {
  ...shared,
  available_equipment: ["bodyweight"],
  circumferences_measured_at: null,
  created_at: "2026-08-01T10:00:00Z",
  experience_level: "beginner",
  home_training_setup: "bodyweight_only",
  hip_circumference_cm: null,
  physical_limitations: null,
  plan_duration_weeks: 4,
  preferred_weekdays: [0, 2, 4],
  priority_muscles: ["glutes"],
  session_duration_minutes: 45,
  shoulder_circumference_cm: null,
  training_age_months: 8,
  training_cautions: [],
  training_days_per_week: 3,
  training_intensity: "moderate",
  training_location: "home",
  updated_at: "2026-09-01T10:00:00Z",
  waist_circumference_cm: null,
} as Profile;

const nutrition = {
  accepts_batch_cooking: true,
  accepts_leftovers: true,
  allergies: [],
  budget_style: "flexible",
  cooking_equipment: [],
  cooking_frequency_per_week: 0,
  cooking_skill: "none",
  currency: "IRR",
  created_at: "2026-08-01T10:00:00Z",
  daily_activity_level: "moderate",
  daily_check_in_enabled: false,
  dietary_pattern: "omnivore",
  disliked_foods: [],
  favourite_foods: [],
  foods_available_at_home: [],
  individual_monthly_food_budget_irr: 0,
  intolerances: [],
  main_meal_count_bucket: "three_main_meals",
  maximum_meal_repetition_per_week: 3,
  maximum_cooking_time_minutes: 0,
  meals_per_day: 3,
  meal_preparation_preference: "no_cooking",
  metabolic_basis: null,
  never_suggest_foods: [],
  onboarding_status: "completed",
  plan_style: "balanced",
  physician_review_required: false,
  preferred_check_in_time: null,
  preferred_plan_start_day: "saturday",
  preferred_variety: "medium",
  refrigerator_access: true,
  religious_cultural_exclusions: [],
  refused_foods: [],
  snacks_per_day: 1,
  supplied_meal_source: null,
  supplied_meals_per_week: 0,
  target_weight_change_kg_per_week: null,
  updated_at: "2026-09-01T10:00:00Z",
  user_id: "user-1",
  weekly_budget_irr: 0,
  weight_rate_mode: "safe",
  work_shift_context: null,
} as NutritionProfile;

function resolved<T>(value: T) {
  return jest.fn<() => Promise<T>>().mockResolvedValue(value);
}

function renderProfile() {
  return render(
    <SafeAreaProvider initialMetrics={{
      frame: { height: 800, width: 390, x: 0, y: 0 },
      insets: { bottom: 0, left: 0, right: 0, top: 0 },
    }}>
      <ProfileScreen />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  mockPush.mockClear();
  mockUseMobileAuth.mockReturnValue({
    download: jest.fn(),
    request: jest.fn(),
    status: "signed_in",
    upload: jest.fn(),
    user: { email: "sara@example.com", id: "user-1" },
  } as never);
  mockUseRouter.mockReturnValue({ back: jest.fn(), push: mockPush } as never);
  mockUseRouteSnapshot.mockReturnValue({
    profile: { completionState: "complete", productMode: "both", status: "resolved" },
  } as never);
  mockRefreshProfileStatus.mockReturnValue(jest.fn<() => Promise<void>>().mockResolvedValue(undefined));
  mockCreateProfileApi.mockReturnValue({
    getNutritionProfile: resolved(nutrition),
    getProfile: resolved(profile),
    getSharedProfile: resolved(shared),
    saveNutritionProfile: resolved(nutrition),
    saveSharedProfile: resolved(shared),
    updateProfile: resolved(profile),
  } as never);
});

test("renders the Web profile summary before the native section editor", async () => {
  renderProfile();

  expect(await screen.findByRole("header", { name: "پروفایل ورزشی" })).toBeTruthy();
  expect(screen.getByText("سارا احمدی")).toBeTruthy();
  expect(screen.getByText("sara@example.com")).toBeTruthy();
  expect(screen.getByText("قد")).toBeTruthy();
  expect(screen.getByText("۱۶۸ سانتی‌متر")).toBeTruthy();
  expect(screen.getByText("وزن")).toBeTruthy();
  expect(screen.getAllByText("۶۴ کیلوگرم").length).toBeGreaterThanOrEqual(2);
  expect(screen.getByText("سن")).toBeTruthy();
  expect(screen.getByText("۳۴")).toBeTruthy();
  expect(screen.getByText("فعالیت")).toBeTruthy();
  expect(screen.getByText("۳ روز در هفته")).toBeTruthy();
  expect(screen.getByText("هدف")).toBeTruthy();
  expect(screen.getAllByText("ریکامپ").length).toBeGreaterThanOrEqual(2);
  expect(screen.queryByText("بازترکیب بدنی")).toBeNull();
  expect(screen.getByText("زن")).toBeTruthy();
  expect(screen.getByText("مرد")).toBeTruthy();
  expect(screen.queryByRole("radio", { name: "سایر" })).toBeNull();
  expect(screen.queryByRole("radio", { name: "ترجیح می‌دهم نگویم" })).toBeNull();
  expect(screen.getByText("مشخصات فردی")).toBeTruthy();
  expect(screen.getByText("بدن و هدف")).toBeTruthy();
  expect(screen.getByText("مرحله ۱ از ۳")).toBeTruthy();
  expect(screen.getByRole("button", { name: "ویرایش پروفایل" })).toBeTruthy();
  expect(screen.getByRole("header", { name: "آخرین اندازه‌گیری وزن" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "مشاهده روند بدن" })).toBeTruthy();
});

test("keeps profile edits sectioned and routes body progress through the member flow", async () => {
  renderProfile();

  await screen.findByRole("header", { name: "پروفایل ورزشی" });
  fireEvent.press(screen.getByRole("radio", { name: "تمرینی" }));
  expect(screen.getByText("تنظیمات تمرین")).toBeTruthy();
  expect(screen.queryByRole("header", { name: "آخرین اندازه‌گیری وزن" })).toBeNull();

  fireEvent.press(screen.getByRole("radio", { name: "شخصی" }));
  expect(screen.getByText("مشخصات فردی")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "مشاهده روند بدن" }));

  expect(mockPush).toHaveBeenCalledWith("/member/body-analysis-history");
});

test("keeps progress limited to sections available for the loaded mode", async () => {
  mockUseRouteSnapshot.mockReturnValue({
    profile: { completionState: "training_ready", productMode: "training", status: "resolved" },
  } as never);
  mockCreateProfileApi.mockReturnValue({
    getNutritionProfile: resolved(null),
    getProfile: resolved(profile),
    getSharedProfile: resolved(shared),
    saveNutritionProfile: resolved(nutrition),
    saveSharedProfile: resolved(shared),
    updateProfile: resolved(profile),
  } as never);

  renderProfile();

  await screen.findByRole("header", { name: "پروفایل ورزشی" });
  expect(screen.getByRole("radio", { name: "شخصی" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "تمرینی" })).toBeTruthy();
  expect(screen.queryByRole("radio", { name: "تغذیه‌ای" })).toBeNull();
  expect(screen.getByText("مرحله ۱ از ۲")).toBeTruthy();
});

test("saves personal edits through the existing updateProfile API", async () => {
  renderProfile();

  await screen.findByRole("header", { name: "پروفایل ورزشی" });
  fireEvent.changeText(screen.getByLabelText("نام نمایشی"), "سارا جدید");
  fireEvent.press(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  const api = mockCreateProfileApi.mock.results[mockCreateProfileApi.mock.results.length - 1]?.value as {
    readonly updateProfile: jest.Mock;
  };
  await waitFor(() => expect(api.updateProfile).toHaveBeenCalledWith({ display_name: "سارا جدید" }));
});
