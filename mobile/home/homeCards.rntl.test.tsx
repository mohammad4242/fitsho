import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";
import { Circle } from "react-native-svg";

import { NutritionSummaryCard } from "./NutritionSummaryCard";
import { QuickActionCard } from "./QuickActionCard";
import { WorkoutTodayCard } from "./WorkoutTodayCard";
import { AppIcon, CinematicSurface } from "../ui/components";

const mockPush = jest.fn();

jest.mock("expo-router", () => ({
  useRouter: () => ({ push: mockPush }),
  useFocusEffect: () => undefined,
}));
jest.mock("expo-video", () => ({
  VideoView: () => null,
  useVideoPlayer: () => ({}),
}));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../exercises/ExerciseMedia", () => ({ ExerciseMedia: () => null }));

test("renders calorie progress as a real accessible metric ring", () => {
  render(
    <NutritionSummaryCard
      loading={false}
      summary={{
        carbohydrate: 180,
        consumedCalories: 750,
        estimatedDailyExpenditureCalories: 2557,
        fat: 62,
        progress: 0.375,
        protein: 130,
        status: "on_plan",
        targetCalories: 2000,
      }}
    />,
  );

  expect(screen.getByRole("progressbar", { name: "پیشرفت کالری امروز" }).props.accessibilityValue)
    .toEqual({ max: 100, min: 0, now: 38 });
  expect(screen.UNSAFE_getAllByType(Circle)).toHaveLength(2);
  fireEvent.press(screen.getByRole("button", { name: "نمایش جزئیات تغذیه" }));
  expect(mockPush).toHaveBeenCalledWith("/member/nutrition");
});

test("keeps the nutrition summary on the quiet web card surface", () => {
  render(
    <NutritionSummaryCard
      loading={false}
      summary={{
        carbohydrate: 180,
        consumedCalories: 750,
        estimatedDailyExpenditureCalories: 2557,
        fat: 62,
        progress: 0.375,
        protein: 130,
        status: "on_plan",
        targetCalories: 2000,
      }}
    />,
  );

  expect(screen.UNSAFE_queryAllByType(CinematicSurface)).toHaveLength(0);
});

test("shows tracked calories beside the daily calorie goal", () => {
  render(
    <NutritionSummaryCard
      loading={false}
      summary={{
        carbohydrate: 180,
        consumedCalories: 750,
        estimatedDailyExpenditureCalories: 2557,
        fat: 62,
        progress: 0.375,
        protein: 130,
        status: "on_plan",
        targetCalories: 2000,
      }}
    />,
  );

  expect(screen.getByText("۷۵۰")).toBeTruthy();
  expect(screen.getByText("مصرف امروز")).toBeTruthy();
  expect(screen.getByText("۲٬۰۰۰")).toBeTruthy();
  expect(screen.getByText("هدف کالری روزانه")).toBeTruthy();
  expect(screen.getByText("۲٬۵۵۷")).toBeTruthy();
  expect(screen.getByText("مصرف تقریبی روزانه")).toBeTruthy();
});

test("omits estimated daily expenditure when the estimate has no TDEE", () => {
  render(
    <NutritionSummaryCard
      loading={false}
      summary={{
        carbohydrate: 180,
        consumedCalories: 750,
        estimatedDailyExpenditureCalories: null,
        fat: 62,
        progress: 0.375,
        protein: 130,
        status: "on_plan",
        targetCalories: 2000,
      }}
    />,
  );

  expect(screen.queryByText("مصرف تقریبی روزانه")).toBeNull();
});

test("does not render a decorative empty day number or stale snapshot sentence", () => {
  render(<WorkoutTodayCard day={null} state="stale" />);

  expect(screen.queryByText("01")).toBeNull();
  expect(screen.queryByText("آخرین نسخه ذخیره‌شده نمایش داده می‌شود.")).toBeNull();
});

test("uses the same moderately larger icon in both quick action cards", () => {
  render(
    <>
      <QuickActionCard
        icon="bodyAnalysis"
        image={1}
        onPress={jest.fn()}
        subtitle="پیشرفت بدنت را بهتر بشناس"
        title="تحلیل بدن"
      />
      <QuickActionCard
        icon="foodLog"
        image={1}
        onPress={jest.fn()}
        subtitle="وعده امروزت را ثبت کن"
        title="ثبت غذا"
      />
    </>,
  );

  expect(screen.UNSAFE_getAllByType(AppIcon).map((icon) => icon.props.size)).toEqual([26, 26]);
});
