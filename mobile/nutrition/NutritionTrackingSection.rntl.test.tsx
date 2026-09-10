import { fireEvent, render, screen, waitFor, within } from "@testing-library/react-native";
import { afterEach, beforeEach, expect, jest, test } from "@jest/globals";
import * as ImagePicker from "expo-image-picker";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("@tanstack/react-query", () => ({
  onlineManager: { isOnline: jest.fn(() => true) },
  useQuery: jest.fn(),
  useQueryClient: jest.fn(),
}));
jest.mock("expo-file-system", () => ({
  File: class MockFile {
    async arrayBuffer(): Promise<ArrayBuffer> {
      return new ArrayBuffer(4);
    }
  },
}));
jest.mock("expo-crypto", () => ({ randomUUID: jest.fn(() => "nutrition-upload-id") }));
jest.mock("expo-image-picker", () => ({
  launchCameraAsync: jest.fn(),
  launchImageLibraryAsync: jest.fn(),
  requestCameraPermissionsAsync: jest.fn(),
}));
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
const mockLaunchCameraAsync = jest.mocked(ImagePicker.launchCameraAsync);
const mockLaunchImageLibraryAsync = jest.mocked(ImagePicker.launchImageLibraryAsync);
const mockRequestCameraPermissionsAsync = jest.mocked(ImagePicker.requestCameraPermissionsAsync);

const dailyEntry = {
  confidence: "high",
  display_name: "عدس",
  entry_date: "2026-09-09",
  food_id: "food-1",
  id: "entry-1",
  note: null,
  nutrients: { calories: 640, energy_kcal: 640, protein_g: 42 },
  plan_revision_id: null,
  planned_meal_id: null,
  quantity_grams: 125,
  source: "catalogue_manual",
  user_confirmed: true,
  warning_codes: [],
};

const dailyTracking = {
  actual_totals: { calories: 640, energy_kcal: 640, protein_g: 42 },
  check_in_status: "not_recorded",
  data_status: "sufficient",
  entries: [],
  entry_date: "2026-09-09",
  plan_revision_id: null,
};

const dailyTrackingWithEntry = {
  ...dailyTracking,
  entries: [dailyEntry],
};

const adherence = {
  days: [{
    actual: { energy_kcal: 640, protein_g: 42 },
    budget_adherence: 90,
    calorie_adherence: 82,
    check_in_status: "not_recorded",
    composite_score: 86,
    date: "2026-09-09",
    exact_entry_ratio: 1,
    formula_version: "adherence-v1",
    major_deviations: 0,
    meal_adherence: 100,
    plan_revision_id: "plan-1",
    planned: { energy_kcal: 2200, protein_g: 150 },
    protein_adherence: 75,
    status: "sufficient",
    structured_exercise_calories: null,
    tracking_completeness: 100,
  }],
  end: "2026-09-09",
  explanation_codes: [],
  start: "2026-09-03",
  weight_causality_claimed: false,
  weight_trend: [],
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

const secondCatalogueFood = {
  ...catalogueFood,
  id: "food-2",
  name_en: "Rice",
  name_fa: "برنج",
  slug: "rice",
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

const photoEstimate = {
  expires_at: "2026-09-10T08:00:00.000Z",
  id: "photo-estimate-1",
  items: [{
    calories: 320,
    carbohydrate_g: 30,
    confidence: 0.8,
    estimated_amount: 180,
    fat_g: 12,
    food_id: "food-1",
    food_slug: "lentils",
    item_id: "photo-item-1",
    mapping_status: "resolved",
    name_guess: "عدس",
    protein_g: 20,
    uncertainties: [],
    unit: "g",
    visible_evidence: [],
  }],
  macro_totals: { calories: 320, carbohydrate_g: 30, fat_g: 12, protein_g: 20 },
  macro_totals_complete: true,
  model_id: "test-model",
  needs_user_confirmation: true,
  overall_confidence: 0.8,
  status: "estimated",
};

const queryClient = {
  invalidateQueries: jest.fn<(...args: unknown[]) => Promise<void>>().mockResolvedValue(undefined),
  setQueryData: jest.fn<(...args: unknown[]) => void>(),
};

type TrackingApiDouble = {
  readonly addCatalogueFood: jest.Mock<(input: unknown) => Promise<unknown>>;
  readonly addQuickApproximation: jest.Mock<(input: unknown) => Promise<unknown>>;
  readonly saveDailyCheckIn: jest.Mock<(input: unknown) => Promise<unknown>>;
  readonly confirmPhoto: jest.Mock<(estimateId: string, input: unknown) => Promise<unknown>>;
  readonly correctPhotoItem: jest.Mock<(estimateId: string, itemId: string, input: unknown) => Promise<unknown>>;
  readonly deletePhotoEstimate: jest.Mock<(estimateId: string) => Promise<unknown>>;
};

let trackingApi: TrackingApiDouble;
let currentDailyTracking: typeof dailyTracking | typeof dailyTrackingWithEntry;
const mockUpload = jest.fn<() => Promise<unknown>>();

function renderTracking() {
  return render(
    <SafeAreaProvider initialMetrics={{ frame: { height: 800, width: 400, x: 0, y: 0 }, insets: { bottom: 0, left: 0, right: 0, top: 0 } }}>
      <NutritionTrackingSection />
    </SafeAreaProvider>,
  );
}

function orderedTestIds(view: ReturnType<typeof render>): string[] {
  return view.UNSAFE_root
    .findAll((node) => typeof node.props.testID === "string")
    .map((node) => node.props.testID as string);
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

beforeEach(() => {
  jest.useFakeTimers();
  jest.setSystemTime(new Date("2026-09-09T08:00:00.000Z"));
  currentDailyTracking = dailyTracking;
  mockCreateTrackingApi.mockClear();
  mockCreateCatalogueApi.mockClear();
  mockCreateNutritionApi.mockClear();
  mockLaunchCameraAsync.mockReset();
  mockLaunchImageLibraryAsync.mockReset();
  mockRequestCameraPermissionsAsync.mockReset();
  mockUpload.mockReset();
  queryClient.invalidateQueries.mockClear();
  queryClient.setQueryData.mockClear();

  trackingApi = {
    addCatalogueFood: jest.fn<(input: unknown) => Promise<unknown>>().mockResolvedValue({}),
    addQuickApproximation: jest.fn<(input: unknown) => Promise<unknown>>().mockResolvedValue({}),
    saveDailyCheckIn: jest.fn<(input: unknown) => Promise<unknown>>().mockResolvedValue(dailyTracking),
    confirmPhoto: jest.fn<(estimateId: string, input: unknown) => Promise<unknown>>().mockResolvedValue([]),
    correctPhotoItem: jest.fn<(estimateId: string, itemId: string, input: unknown) => Promise<unknown>>().mockResolvedValue(photoEstimate),
    deletePhotoEstimate: jest.fn<(estimateId: string) => Promise<unknown>>().mockResolvedValue(undefined),
  };
  mockCreateTrackingApi.mockReturnValue(trackingApi as never);
  mockCreateCatalogueApi.mockReturnValue({ getFoodCatalogue: jest.fn() } as never);
  mockCreateNutritionApi.mockReturnValue({ getCurrentEstimate: jest.fn() } as never);
  mockUseQueryClient.mockReturnValue(queryClient as never);
  mockUseMobileAuth.mockReturnValue({
    download: jest.fn(),
    request: jest.fn(),
    upload: mockUpload,
  } as never);
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "tracking") return queryResult(currentDailyTracking);
    if (key[1] === "recent-foods") return queryResult([]);
    if (key[1] === "estimate") return queryResult(nutritionEstimate);
    if (key[1] === "adherence") return queryResult(adherence);
    if (key[1] === "tracking-history") return queryResult([currentDailyTracking]);
    return queryResult({ categories: ["grain"], items: [catalogueFood, secondCatalogueFood], page: 1, page_size: 40, total: 2 });
  });
});

test("shows both entry methods closed on the initial page", () => {
  renderTracking();

  expect(screen.getByRole("header", { name: "ثبت تغذیه" })).toBeTruthy();
  const manual = screen.getByRole("button", { name: "ثبت دستی" });
  const photo = screen.getByRole("button", { name: "عکس وعده" });
  expect(manual.props.accessibilityState).toMatchObject({ expanded: false, selected: false });
  expect(photo.props.accessibilityState).toMatchObject({ expanded: false, selected: false });
  expect(screen.queryByTestId("nutrition-manual-entry-panel")).toBeNull();
  expect(screen.queryByTestId("nutrition-photo-entry-panel")).toBeNull();
  expect(screen.queryByText("ثبت دقیق از کاتالوگ")).toBeNull();
  expect(screen.queryByText("عکس غذا را انتخاب کن")).toBeNull();
});

test("opens only manual entry and closes it when the active method is pressed again", () => {
  renderTracking();

  const manual = screen.getByRole("button", { name: "ثبت دستی" });
  const photo = screen.getByRole("button", { name: "عکس وعده" });
  fireEvent.press(manual);
  expect(screen.getByTestId("nutrition-manual-entry-panel")).toBeTruthy();
  expect(screen.queryByTestId("nutrition-photo-entry-panel")).toBeNull();
  expect(manual.props.accessibilityState).toMatchObject({ expanded: true, selected: true });
  expect(photo.props.accessibilityState).toMatchObject({ expanded: false, selected: false });

  fireEvent.press(manual);
  expect(screen.queryByTestId("nutrition-manual-entry-panel")).toBeNull();
  expect(manual.props.accessibilityState).toMatchObject({ expanded: false, selected: false });
});

test("switches directly from manual entry to photo entry with one panel open", () => {
  renderTracking();

  const manual = screen.getByRole("button", { name: "ثبت دستی" });
  const photo = screen.getByRole("button", { name: "عکس وعده" });
  fireEvent.press(manual);
  fireEvent.press(photo);

  expect(screen.queryByTestId("nutrition-manual-entry-panel")).toBeNull();
  expect(screen.getByTestId("nutrition-photo-entry-panel")).toBeTruthy();
  expect(manual.props.accessibilityState).toMatchObject({ expanded: false, selected: false });
  expect(photo.props.accessibilityState).toMatchObject({ expanded: true, selected: true });
});

test("places the entry hub before the daily summary, entries, adherence, and final check-in", () => {
  currentDailyTracking = dailyTrackingWithEntry;
  const view = renderTracking();
  const ids = orderedTestIds(view);
  const expectedOrder = [
    "nutrition-entry-hub",
    "nutrition-daily-panel",
    "nutrition-today-entries",
    "nutrition-adherence",
    "nutrition-checkin",
  ];

  expect(expectedOrder.every((id) => ids.includes(id))).toBe(true);
  for (let index = 1; index < expectedOrder.length; index += 1) {
    expect(ids.indexOf(expectedOrder[index - 1]!)).toBeLessThan(ids.indexOf(expectedOrder[index]!));
  }
});

test("does not render a large empty today's entries section when there are no entries", () => {
  renderTracking();

  expect(screen.getByTestId("nutrition-daily-panel")).toBeTruthy();
  expect(screen.queryByTestId("nutrition-today-entries")).toBeNull();
  expect(screen.getByTestId("nutrition-adherence")).toBeTruthy();
});

test("sends the unchanged catalogue payload from the compact manual selector", async () => {
  renderTracking();
  fireEvent.press(screen.getByRole("button", { name: "ثبت دستی" }));
  fireEvent.press(screen.getByTestId("nutrition-catalogue-selector"));
  fireEvent.press(screen.getByRole("button", { name: "برنج" }));
  fireEvent.changeText(screen.getByLabelText("مقدار به گرم"), "175");
  fireEvent.press(screen.getByLabelText("ثبت از کاتالوگ"));

  await waitFor(() => {
    expect(trackingApi.addCatalogueFood).toHaveBeenCalledWith({
      entry_date: "2026-09-09",
      food_id: "food-2",
      grams: 175,
      note: null,
    });
  });
});

test("sends the web-equivalent quick approximation payload", async () => {
  renderTracking();
  fireEvent.press(screen.getByRole("button", { name: "ثبت دستی" }));
  fireEvent.changeText(screen.getByLabelText("کالری تقریبی"), "430");
  fireEvent.press(screen.getByLabelText("ثبت تقریبی"));

  await waitFor(() => {
    expect(trackingApi.addQuickApproximation).toHaveBeenCalledWith({
      entry_date: "2026-09-09",
      display_name: "وعده تقریبی",
      calories: 430,
      protein_g: null,
    });
  });
});

test("validates quick approximation without the removed name and protein fields", async () => {
  renderTracking();
  fireEvent.press(screen.getByRole("button", { name: "ثبت دستی" }));
  fireEvent.press(screen.getByLabelText("ثبت تقریبی"));

  expect(await screen.findByText("یک کالری معتبر وارد کن.")).toBeTruthy();
  expect(trackingApi.addQuickApproximation).not.toHaveBeenCalled();
  expect(screen.queryByLabelText("نام برآورد سریع")).toBeNull();
  expect(screen.queryByLabelText("پروتئین تقریبی")).toBeNull();
});

test("keeps recent food shortcuts inside the manual entry panel", () => {
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "tracking") return queryResult(currentDailyTracking);
    if (key[1] === "recent-foods") return queryResult([{ food_id: "food-1", display_name: "عدس", last_entry_date: "2026-09-08", last_quantity_grams: 120 }]);
    if (key[1] === "estimate") return queryResult(nutritionEstimate);
    if (key[1] === "adherence") return queryResult(adherence);
    if (key[1] === "tracking-history") return queryResult([]);
    return queryResult({ categories: ["grain"], items: [catalogueFood], page: 1, page_size: 40, total: 1 });
  });
  renderTracking();

  fireEvent.press(screen.getByRole("button", { name: "ثبت دستی" }));
  expect(screen.getByText("غذاهای اخیر")).toBeTruthy();
  expect(screen.getByText("برای ثبت سریع، یکی را انتخاب کن")).toBeTruthy();
  expect(screen.getByRole("button", { name: "عدس · ۱۲۰ گرم" })).toBeTruthy();
});

test("keeps photo consent required and styles the camera/gallery controls as photo actions", () => {
  renderTracking();
  fireEvent.press(screen.getByRole("button", { name: "عکس وعده" }));

  const consent = screen.getByRole("checkbox", { name: "با پردازش عکس توسط سرویس ثالث موافقم" });
  const camera = screen.getByRole("button", { name: "گرفتن عکس" });
  const gallery = screen.getByRole("button", { name: "انتخاب از گالری" });
  expect(consent.props.accessibilityState).toMatchObject({ checked: false });
  expect(camera.props.accessibilityState.disabled).toBe(true);
  expect(gallery.props.accessibilityState.disabled).toBe(true);

  fireEvent.press(consent);
  expect(consent.props.accessibilityState).toMatchObject({ checked: true });
  expect(camera.props.accessibilityState.disabled).toBe(false);
  expect(gallery.props.accessibilityState.disabled).toBe(false);
});

test("camera and gallery sources keep invoking the existing upload workflow and show the selected preview", async () => {
  mockRequestCameraPermissionsAsync.mockResolvedValue({ granted: true, canAskAgain: true, expires: "never", status: "granted" } as never);
  mockLaunchCameraAsync.mockResolvedValue({
    canceled: false,
    assets: [{ exif: {}, height: 400, mimeType: "image/jpeg", uri: "file:///camera-meal.jpg", width: 400 }],
  } as never);
  mockLaunchImageLibraryAsync.mockResolvedValue({
    canceled: false,
    assets: [{ exif: {}, height: 300, mimeType: "image/jpeg", uri: "file:///gallery-meal.jpg", width: 300 }],
  } as never);
  mockUpload.mockResolvedValue(photoEstimate);
  renderTracking();
  fireEvent.press(screen.getByRole("button", { name: "عکس وعده" }));
  fireEvent.press(screen.getByRole("checkbox", { name: "با پردازش عکس توسط سرویس ثالث موافقم" }));

  fireEvent.press(screen.getByRole("button", { name: "گرفتن عکس" }));
  await waitFor(() => {
    expect(mockRequestCameraPermissionsAsync).toHaveBeenCalled();
    expect(mockLaunchCameraAsync).toHaveBeenCalled();
    expect(mockUpload).toHaveBeenCalled();
    expect(screen.getByTestId("nutrition-photo-preview")).toBeTruthy();
  });

  fireEvent.press(screen.getByRole("button", { name: "انتخاب از گالری" }));
  await waitFor(() => {
    expect(mockLaunchImageLibraryAsync).toHaveBeenCalled();
    expect(mockUpload).toHaveBeenCalledTimes(2);
  });
});

test("renders the photo result with estimated calories and all three macros", async () => {
  mockRequestCameraPermissionsAsync.mockResolvedValue({ granted: true } as never);
  mockLaunchCameraAsync.mockResolvedValue({
    canceled: false,
    assets: [{ exif: {}, height: 400, mimeType: "image/jpeg", uri: "file:///meal.jpg", width: 400 }],
  } as never);
  mockUpload.mockResolvedValue(photoEstimate);
  renderTracking();
  fireEvent.press(screen.getByRole("button", { name: "عکس وعده" }));
  fireEvent.press(screen.getByRole("checkbox", { name: "با پردازش عکس توسط سرویس ثالث موافقم" }));
  fireEvent.press(screen.getByRole("button", { name: "گرفتن عکس" }));

  expect(await screen.findByText("کالری تخمینی")).toBeTruthy();
  expect(screen.getByText("۳۲۰ kcal")).toBeTruthy();
  const photoResult = within(screen.getByTestId("nutrition-photo-result"));
  expect(photoResult.getByText("پروتئین")).toBeTruthy();
  expect(photoResult.getByText("کربوهیدرات")).toBeTruthy();
  expect(photoResult.getByText("چربی")).toBeTruthy();
});

test("keeps the adherence accordion closed until opened and preserves its date selector", () => {
  renderTracking();

  const adherenceToggle = screen.getByRole("button", { name: "روند پایبندی" });
  expect(adherenceToggle.props.accessibilityState).toMatchObject({ expanded: false });
  expect(screen.getByLabelText("شروع بازه پایبندی")).toBeTruthy();
  expect(screen.queryByText("کامل بودن ثبت")).toBeNull();

  fireEvent.press(adherenceToggle);
  expect(adherenceToggle.props.accessibilityState).toMatchObject({ expanded: true });
  expect(screen.getByText(/کامل بودن ثبت/)).toBeTruthy();
});

test("saves the selected daily check-in with the existing API payload", async () => {
  renderTracking();

  const checkIn = screen.getByRole("button", { name: "طبق برنامه" });
  expect(checkIn.props.accessibilityState.selected).toBe(false);
  fireEvent.press(checkIn);

  await waitFor(() => {
    expect(trackingApi.saveDailyCheckIn).toHaveBeenCalledWith({
      entry_date: "2026-09-09",
      status: "on_plan",
    });
    expect(checkIn.props.accessibilityState.selected).toBe(true);
  });
});

afterEach(() => {
  jest.useRealTimers();
});
