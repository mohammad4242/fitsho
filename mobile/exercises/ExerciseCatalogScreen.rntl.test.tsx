import { fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("@tanstack/react-query", () => ({ useQuery: jest.fn() }));
jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("./ExerciseMedia", () => ({ ExerciseMedia: () => null }));

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { ExerciseCatalogScreen } from "./ExerciseCatalogScreen";

const mockUseQuery = jest.mocked(useQuery);
const mockUseRouter = jest.mocked(useRouter);
const mockUseMobileAuth = jest.mocked(useMobileAuth);

const categories = {
  body_regions: [{ name_en: "Upper body", name_fa: "بالاتنه", value: "upper_body" }],
  core: [],
  lower_body: [],
  muscle_focuses: {
    chest: [{ name_en: "Upper chest", name_fa: "بخش بالایی سینه", value: "upper_chest" }],
  },
  upper_body: [{ name_en: "Chest", name_fa: "سینه", value: "chest" }],
};

const exercisePage = {
  items: [
    {
      body_region: "upper_body",
      content_type: "exercise",
      difficulty: "beginner",
      equipment: ["bodyweight"],
      id: "push-up",
      labels: [],
      media_path: "/media/push-up.mp4",
      media_type: "video",
      muscle_focus: null,
      name_en: "Push-up",
      name_fa: "شنا",
      primary_muscle: "chest",
      secondary_muscles: [],
      slug: "push-up",
    },
  ],
  page: 1,
  page_size: 12,
  total: 1,
  total_pages: 1,
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
  mockUseRouter.mockReturnValue({ push: jest.fn() } as never);
  mockUseMobileAuth.mockReturnValue({ request: jest.fn() } as never);
  mockUseQuery.mockImplementation(({ queryKey }) => {
    return queryKey[1] === "categories" ? queryResult(categories) : queryResult(exercisePage);
  });
});

function renderCatalog() {
  return render(
    <SafeAreaProvider initialMetrics={{ frame: { height: 800, width: 400, x: 0, y: 0 }, insets: { bottom: 0, left: 0, right: 0, top: 0 } }}>
      <ExerciseCatalogScreen />
    </SafeAreaProvider>,
  );
}

test("lets a user remove an active body-region filter without resetting other discovery controls", async () => {
  renderCatalog();

  fireEvent.press(screen.getByRole("button", { name: "فیلترها" }));
  fireEvent.press(screen.getByRole("button", { name: "بالاتنه" }));
  fireEvent.press(screen.getByLabelText("نمایش نتایج"));
  expect(screen.getByRole("button", { name: "همه حرکات" }).props.accessibilityState.selected).toBe(false);

  const removeBodyRegion = await screen.findByLabelText("حذف فیلتر: ناحیه بدن: بالاتنه");
  expect(removeBodyRegion).toBeTruthy();

  fireEvent.press(removeBodyRegion);

  expect(screen.queryByLabelText("حذف فیلتر: ناحیه بدن: بالاتنه")).toBeNull();
  expect(screen.getByRole("button", { name: "فیلترها" })).toBeTruthy();
});

test("exposes search as an individually removable active filter", () => {
  renderCatalog();

  fireEvent.changeText(screen.getByLabelText("جستجوی حرکت"), "شنا");

  const removeSearch = screen.getByLabelText("حذف فیلتر: جست‌وجو: شنا");
  fireEvent.press(removeSearch);

  expect(screen.getByLabelText("جستجوی حرکت").props.value).toBe("");
  expect(screen.queryByLabelText("حذف فیلتر: جست‌وجو: شنا")).toBeNull();
});
