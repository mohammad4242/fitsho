import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";
import { StyleSheet } from "react-native";
import type { ReactTestInstance } from "react-test-renderer";

const mockPush = jest.fn();
jest.mock("expo-router", () => ({ useRouter: jest.fn(() => ({ push: mockPush })) }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));

import { NutritionTodayMeals } from "./NutritionTodayMeals";
import type { WeeklyPlan } from "./nutritionPlanApi";

const today = new Date().toISOString().slice(0, 10);
const plan = {
  days: [{
    day_index: 0,
    meals: [
      { id: "breakfast", name_fa: null, nutrient_totals: { energy_kcal: 1000 }, slot_index: 0, slot_role: "main_meal" },
      { id: "snack", name_fa: null, nutrient_totals: { energy_kcal: 250 }, slot_index: 0, slot_role: "snack" },
      { id: "lunch", name_fa: null, nutrient_totals: {}, slot_index: 1, slot_role: "main_meal" },
    ],
    nutrient_totals: {},
    plan_date: today,
  }],
} as unknown as WeeklyPlan;

function findAncestorStyle(node: ReactTestInstance, key: string): Record<string, unknown> {
  let current = node.parent;
  while (current !== null) {
    const style = StyleSheet.flatten(current.props.style) as Record<string, unknown> | undefined;
    if (style?.[key] !== undefined) return style;
    current = current.parent;
  }
  throw new Error(`Ancestor style ${key} not found`);
}

test("shows only today's planned meal rows and the track-meal action", () => {
  render(<NutritionTodayMeals plan={plan} />);

  expect(screen.getByText("وعده‌های امروز")).toBeTruthy();
  expect(screen.getByRole("button", { name: "ثبت وعده" })).toBeTruthy();
  expect(screen.getByText("صبحانه")).toBeTruthy();
  expect(screen.getByText("میان‌وعده ۱")).toBeTruthy();
  expect(screen.getByText("ناهار")).toBeTruthy();
  expect(screen.getByText("۱٬۰۰۰ کیلوکالری")).toBeTruthy();
  expect(screen.getByText("۲۵۰ کیلوکالری")).toBeTruthy();
  expect(screen.getByText("—")).toBeTruthy();
  expect(findAncestorStyle(screen.getByText("وعده‌های امروز"), "flexDirection")).toMatchObject({ flexDirection: "row" });
  expect(findAncestorStyle(screen.getByText("صبحانه"), "flexDirection")).toMatchObject({ flexDirection: "row" });
  expect(StyleSheet.flatten(screen.getByText("۱٬۰۰۰ کیلوکالری").props.style)).toMatchObject({
    textAlign: "right",
    writingDirection: "rtl",
  });

  fireEvent.press(screen.getByRole("button", { name: "ثبت وعده" }));
  expect(mockPush).toHaveBeenCalledWith("/member/nutrition-tracking");
});

test("does not invent a meal card without a plan day", () => {
  render(<NutritionTodayMeals plan={null} />);
  expect(screen.queryByText("وعده‌های امروز")).toBeNull();
});
