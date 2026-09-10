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
  body_regions: [
    { name_en: "Upper body", name_fa: "بالاتنه", value: "upper_body" },
    { name_en: "Lower body", name_fa: "پایین‌تنه", value: "lower_body" },
    { name_en: "Core", name_fa: "میان‌تنه", value: "core" },
  ],
  core: [{ name_en: "Abs", name_fa: "شکم", value: "abs" }],
  lower_body: [{ name_en: "Glutes", name_fa: "باسن", value: "glutes" }],
  muscle_focuses: {
    chest: [
      { name_en: "General chest", name_fa: "سینه عمومی", value: "general_chest" },
      { name_en: "Upper chest", name_fa: "بالاسینه", value: "upper_chest" },
      { name_en: "Mid chest", name_fa: "وسط سینه", value: "mid_chest" },
      { name_en: "Lower chest", name_fa: "زیر سینه", value: "lower_chest" },
    ],
    glutes: [],
  },
  upper_body: [
    { name_en: "Chest", name_fa: "سینه", value: "chest" },
    { name_en: "Back and lats", name_fa: "پشت و زیر بغل", value: "back" },
    { name_en: "Shoulders", name_fa: "سرشانه", value: "shoulders" },
  ],
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

const focusedGuidePage = {
  ...exercisePage,
  items: [
    {
      ...exercisePage.items[0],
      content_type: "guide",
      id: "upper-chest-guide",
      muscle_focus: "upper_chest",
      name_en: "Incline press guide",
      name_fa: "راهنمای پرس بالاسینه",
      slug: "upper-chest-guide",
    },
  ],
};

function queryResult<T>(data: T | undefined) {
  return {
    data,
    error: null,
    isError: false,
    isFetching: false,
    isPending: data === undefined,
    isStale: false,
  } as never;
}

type QueryOptions = {
  readonly enabled?: boolean;
  readonly queryKey?: readonly unknown[];
};

function latestExerciseQueryOptions(): QueryOptions {
  const calls = mockUseQuery.mock.calls;
  for (let index = calls.length - 1; index >= 0; index -= 1) {
    const options = calls[index]?.[0] as QueryOptions | undefined;
    if (options?.queryKey?.[1] === "list") return options;
  }
  throw new Error("Exercise list query was not registered");
}

function latestExerciseFilters(): Record<string, unknown> {
  const queryKey = latestExerciseQueryOptions().queryKey;
  return (queryKey?.[2] ?? {}) as Record<string, unknown>;
}

beforeEach(() => {
  mockUseQuery.mockClear();
  mockUseRouter.mockClear();
  mockUseMobileAuth.mockClear();
  mockUseRouter.mockReturnValue({ push: jest.fn() } as never);
  mockUseMobileAuth.mockReturnValue({ request: jest.fn() } as never);
  mockUseQuery.mockImplementation((options) => {
    const queryOptions = options as QueryOptions;
    if (queryOptions.queryKey?.[1] === "categories") return queryResult(categories);
    return queryResult(queryOptions.enabled === false ? undefined : exercisePage);
  });
});

function renderCatalog() {
  return render(
    <SafeAreaProvider initialMetrics={{ frame: { height: 800, width: 400, x: 0, y: 0 }, insets: { bottom: 0, left: 0, right: 0, top: 0 } }}>
      <ExerciseCatalogScreen />
    </SafeAreaProvider>,
  );
}

test("shows body regions directly below search without opening advanced filters", () => {
  renderCatalog();

  expect(screen.getByLabelText("جستجوی حرکت")).toBeTruthy();
  expect(screen.getByRole("button", { name: "بالاتنه" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "پایین‌تنه" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "میان‌تنه" })).toBeTruthy();
  expect(screen.queryByText("فیلترهای پیشرفته")).toBeNull();
});

test("starts in guided discovery without showing the full catalogue", () => {
  renderCatalog();

  expect(screen.getByText("برای شروع، بالاتنه، پایین‌تنه یا میان‌تنه را انتخاب کن.")).toBeTruthy();
  expect(screen.queryByText("نتایج حرکات")).toBeNull();
  expect(screen.queryByText("۱ نتیجه")).toBeNull();
  expect(latestExerciseQueryOptions().enabled).toBe(false);
});

test("selecting a body region reveals its target muscles", () => {
  renderCatalog();

  fireEvent.press(screen.getByRole("button", { name: "بالاتنه" }));

  expect(screen.getByText("عضله هدف")).toBeTruthy();
  expect(screen.getByRole("button", { name: "سینه" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "پشت و زیر بغل" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "سرشانه" })).toBeTruthy();
  expect(screen.getByText("حالا عضله هدفت را انتخاب کن.")).toBeTruthy();
  expect(latestExerciseQueryOptions().enabled).toBe(false);
});

test("selecting a muscle reveals focus controls and content type", () => {
  renderCatalog();

  fireEvent.press(screen.getByRole("button", { name: "بالاتنه" }));
  fireEvent.press(screen.getByRole("button", { name: "سینه" }));

  expect(screen.getByText("تمرکز عضلانی")).toBeTruthy();
  expect(screen.getByRole("button", { name: "همه بخش‌های این عضله" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "بالاسینه" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "وسط سینه" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "زیر سینه" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "حرکت‌ها" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "راهنماها" })).toBeTruthy();
  expect(latestExerciseQueryOptions().enabled).toBe(true);
  expect(latestExerciseFilters()).toMatchObject({
    body_region: "upper_body",
    primary_muscle: "chest",
  });
});

test("selecting another body region clears the previous muscle and focus", () => {
  renderCatalog();

  fireEvent.press(screen.getByRole("button", { name: "بالاتنه" }));
  fireEvent.press(screen.getByRole("button", { name: "سینه" }));
  fireEvent.press(screen.getByRole("button", { name: "بالاسینه" }));
  fireEvent.press(screen.getByRole("button", { name: "پایین‌تنه" }));

  expect(screen.getByRole("button", { name: "باسن" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "بالاسینه" })).toBeNull();
  expect(screen.queryByLabelText("حذف فیلتر: عضله: سینه")).toBeNull();
  expect(latestExerciseQueryOptions().enabled).toBe(false);
  expect(latestExerciseFilters()).toMatchObject({ body_region: "lower_body" });
  expect(latestExerciseFilters().primary_muscle).toBeUndefined();
  expect(latestExerciseFilters().muscle_focus).toBeUndefined();
});

test("cardio shortcut clears guided selection and uses the cardio label", () => {
  renderCatalog();

  fireEvent.press(screen.getByRole("button", { name: "بالاتنه" }));
  fireEvent.press(screen.getByRole("button", { name: "سینه" }));
  fireEvent.press(screen.getByRole("button", { name: "هوازی" }));

  expect(screen.getByRole("button", { name: "هوازی" }).props.accessibilityState.selected).toBe(true);
  expect(screen.queryByLabelText("حذف فیلتر: عضله: سینه")).toBeNull();
  expect(latestExerciseQueryOptions().enabled).toBe(true);
  expect(latestExerciseFilters()).toMatchObject({ labels: ["cardio"] });
  expect(latestExerciseFilters().body_region).toBeUndefined();
  expect(latestExerciseFilters().primary_muscle).toBeUndefined();
});

test("mobility shortcut clears guided selection and uses mobility mode", () => {
  renderCatalog();

  fireEvent.press(screen.getByRole("button", { name: "بالاتنه" }));
  fireEvent.press(screen.getByRole("button", { name: "سینه" }));
  fireEvent.press(screen.getByRole("button", { name: "تحرک و کشش" }));

  expect(screen.getByRole("button", { name: "تحرک و کشش" }).props.accessibilityState.selected).toBe(true);
  expect(latestExerciseQueryOptions().enabled).toBe(true);
  expect(latestExerciseFilters()).toMatchObject({ exercise_type: "mobility" });
  expect(latestExerciseFilters().body_region).toBeUndefined();
  expect(latestExerciseFilters().primary_muscle).toBeUndefined();
});

test("all exercises is an explicit mode that enables the full catalogue", () => {
  renderCatalog();

  fireEvent.press(screen.getByRole("button", { name: "همه حرکات" }));

  expect(screen.getByRole("button", { name: "همه حرکات" }).props.accessibilityState.selected).toBe(true);
  expect(screen.getByText("نتایج حرکات")).toBeTruthy();
  expect(screen.getByText("۱ نتیجه")).toBeTruthy();
  expect(latestExerciseQueryOptions().enabled).toBe(true);
  expect(latestExerciseFilters()).toEqual({ content_type: "exercise", page: 1, page_size: 12 });
});

test("renders labeled metadata and routes from the explicit exercise CTA", () => {
  const push = jest.fn();
  mockUseRouter.mockReturnValue({ push } as never);

  renderCatalog();
  fireEvent.press(screen.getByRole("button", { name: "همه حرکات" }));

  expect(screen.getByText("عضله اصلی")).toBeTruthy();
  expect(screen.getByText("سینه")).toBeTruthy();
  expect(screen.getByText("تجهیزات")).toBeTruthy();
  expect(screen.getByText("وزن بدن")).toBeTruthy();
  expect(screen.getByText("بخش هدف")).toBeTruthy();
  expect(screen.getByText("مشخص نشده")).toBeTruthy();
  expect(screen.getByRole("button", { name: "مشاهده حرکت" })).toBeTruthy();
  expect(screen.queryByText("ویرایش")).toBeNull();
  expect(screen.queryByText("حذف")).toBeNull();

  fireEvent.press(screen.getByRole("button", { name: "مشاهده حرکت" }));

  expect(push).toHaveBeenCalledWith({
    params: { slug: "push-up" },
    pathname: "/member/exercises/[slug]",
  });
});

test("renders localized focus metadata and the guide CTA", () => {
  mockUseQuery.mockImplementation((options) => {
    const queryOptions = options as QueryOptions;
    if (queryOptions.queryKey?.[1] === "categories") return queryResult(categories);
    return queryResult(queryOptions.enabled === false ? undefined : focusedGuidePage);
  });

  renderCatalog();
  fireEvent.press(screen.getByRole("button", { name: "همه حرکات" }));

  expect(screen.getByText("بالاسینه")).toBeTruthy();
  expect(screen.getByRole("button", { name: "مشاهده راهنما" })).toBeTruthy();
});

test("search enables matching results without a guided muscle selection", () => {
  renderCatalog();

  fireEvent.changeText(screen.getByLabelText("جستجوی حرکت"), "پرس سینه");

  expect(screen.getByText("نتایج حرکات")).toBeTruthy();
  expect(latestExerciseQueryOptions().enabled).toBe(true);
  expect(latestExerciseFilters()).toMatchObject({ search: "پرس سینه" });
  expect(latestExerciseFilters().body_region).toBeUndefined();
  expect(latestExerciseFilters().primary_muscle).toBeUndefined();
});

test("advanced filter Sheet opens from the secondary discovery action", () => {
  renderCatalog();

  fireEvent.press(screen.getByRole("button", { name: "فیلترهای بیشتر" }));

  expect(screen.getByText("فیلترهای پیشرفته")).toBeTruthy();
  expect(screen.getByRole("button", { name: "دمبل" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "پیشرفته" })).toBeTruthy();
});

test("equipment and difficulty remain selectable in the advanced Sheet", () => {
  renderCatalog();

  fireEvent.press(screen.getByRole("button", { name: "فیلترهای بیشتر" }));
  fireEvent.press(screen.getByRole("button", { name: "دمبل" }));
  fireEvent.press(screen.getByRole("button", { name: "پیشرفته" }));

  expect(screen.getByRole("button", { name: "دمبل" }).props.accessibilityState.selected).toBe(true);
  expect(screen.getByRole("button", { name: "پیشرفته" }).props.accessibilityState.selected).toBe(true);
  expect(latestExerciseQueryOptions().enabled).toBe(false);
  expect(latestExerciseFilters()).toMatchObject({ equipment: "dumbbell", difficulty: "advanced" });
});

test("the prominent header filter action is removed", () => {
  renderCatalog();

  expect(screen.queryByRole("button", { name: "فیلترها" })).toBeNull();
  expect(screen.getByRole("button", { name: "فیلترهای بیشتر" })).toBeTruthy();
});

test("primary selectors are not duplicated inside the advanced Sheet", () => {
  renderCatalog();

  fireEvent.press(screen.getByRole("button", { name: "بالاتنه" }));
  fireEvent.press(screen.getByRole("button", { name: "سینه" }));
  expect(screen.queryAllByRole("button", { name: /^بالاتنه$/ })).toHaveLength(1);

  fireEvent.press(screen.getByRole("button", { name: "فیلترهای بیشتر" }));

  expect(screen.getByText("فیلترهای پیشرفته")).toBeTruthy();
  expect(screen.queryByText("ناحیه بدن")).toBeNull();
  expect(screen.queryByText("عضله هدف")).toBeNull();
});

test("clear filters returns to guided discovery instead of all exercises", () => {
  renderCatalog();

  fireEvent.press(screen.getByRole("button", { name: "بالاتنه" }));
  fireEvent.press(screen.getByRole("button", { name: "سینه" }));
  fireEvent.press(screen.getByRole("button", { name: "فیلترهای بیشتر" }));
  fireEvent.press(screen.getByRole("button", { name: "پاک کردن فیلترها" }));
  fireEvent.press(screen.getAllByRole("button", { name: "بستن" })[1]);

  expect(screen.getByText("برای شروع، بالاتنه، پایین‌تنه یا میان‌تنه را انتخاب کن.")).toBeTruthy();
  expect(screen.queryByText("نتایج حرکات")).toBeNull();
  expect(screen.getByRole("button", { name: "همه حرکات" }).props.accessibilityState.selected).toBe(false);
  expect(latestExerciseQueryOptions().enabled).toBe(false);
});

test("guide content type stays in stage three and hides muscle focus choices", () => {
  renderCatalog();

  fireEvent.press(screen.getByRole("button", { name: "بالاتنه" }));
  fireEvent.press(screen.getByRole("button", { name: "سینه" }));
  fireEvent.press(screen.getByRole("radio", { name: "راهنماها" }));

  expect(screen.getByRole("radio", { name: "راهنماها" }).props.accessibilityState.selected).toBe(true);
  expect(screen.queryByRole("button", { name: "بالاسینه" })).toBeNull();
  expect(latestExerciseFilters()).toMatchObject({ content_type: "guide", primary_muscle: "chest" });
});

test("a body-region active filter remains removable", () => {
  renderCatalog();

  fireEvent.press(screen.getByRole("button", { name: "بالاتنه" }));
  const removeBodyRegion = screen.getByLabelText("حذف فیلتر: ناحیه بدن: بالاتنه");

  fireEvent.press(removeBodyRegion);

  expect(screen.queryByLabelText("حذف فیلتر: ناحیه بدن: بالاتنه")).toBeNull();
  expect(screen.getByText("برای شروع، بالاتنه، پایین‌تنه یا میان‌تنه را انتخاب کن.")).toBeTruthy();
});

test("search remains individually removable", () => {
  renderCatalog();

  fireEvent.changeText(screen.getByLabelText("جستجوی حرکت"), "شنا");
  const removeSearch = screen.getByLabelText("حذف فیلتر: جست‌وجو: شنا");

  fireEvent.press(removeSearch);

  expect(screen.getByLabelText("جستجوی حرکت").props.value).toBe("");
  expect(screen.queryByLabelText("حذف فیلتر: جست‌وجو: شنا")).toBeNull();
  expect(latestExerciseQueryOptions().enabled).toBe(false);
});
