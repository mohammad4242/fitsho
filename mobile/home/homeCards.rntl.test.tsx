import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";
import { Circle } from "react-native-svg";

import { NutritionSummaryCard } from "./NutritionSummaryCard";
import { CinematicSurface } from "../ui/components";

const mockPush = jest.fn();

jest.mock("expo-router", () => ({
  useRouter: () => ({ push: mockPush }),
}));
jest.mock("expo-video", () => ({
  VideoView: () => null,
  useVideoPlayer: () => ({}),
}));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));

test("renders calorie progress as a real accessible metric ring", () => {
  render(
    <NutritionSummaryCard
      loading={false}
      summary={{
        carbohydrate: 180,
        consumedCalories: 750,
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
