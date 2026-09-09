import { render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";
import { Animated } from "react-native";
import { Circle } from "react-native-svg";

import { fiticianTokens } from "../ui/tokens";

jest.mock("expo-router", () => ({
  useFocusEffect: (effect: () => void) => effect(),
}));

import { NutritionDualMetricRing } from "./NutritionDualMetricRing";

test("animates one segmented TDEE ring from empty to its BMR and additional-calorie shares", () => {
  const timing = jest.spyOn(Animated, "timing").mockReturnValue({ start: jest.fn() } as never);

  render(
    <NutritionDualMetricRing
      label="تفکیک BMR و کالری اضافه در TDEE"
      primaryValue={1600}
      additionalValue={800}
      total={2400}
    />,
  );

  expect(timing).toHaveBeenCalledWith(
    expect.anything(),
    expect.objectContaining({ duration: 900, toValue: 1, useNativeDriver: false }),
  );
  expect(screen.getByRole("progressbar", { name: "تفکیک BMR و کالری اضافه در TDEE" }).props.accessibilityValue)
    .toEqual({ max: 100, min: 0, now: 100 });
  timing.mockRestore();
});

test("uses one shared-radius track for contiguous BMR and additional-calorie segments", () => {
  render(
    <NutritionDualMetricRing
      animateOnFocus={false}
      label="تفکیک BMR و کالری اضافه در TDEE"
      primaryValue={1600}
      additionalValue={800}
      total={2400}
    />,
  );

  const circles = screen.UNSAFE_getAllByType(Circle);
  expect(circles).toHaveLength(3);
  expect(new Set(circles.map((circle) => circle.props.r)).size).toBe(1);

  const coloredCircles = circles.filter((circle) => (
    circle.props.stroke === fiticianTokens.colors.blue
    || circle.props.stroke === fiticianTokens.colors.aqua
  ));
  expect(coloredCircles).toHaveLength(2);
  expect(coloredCircles.map((circle) => circle.props.r)).toEqual([38, 38]);
  expect(coloredCircles.map((circle) => circle.props.strokeWidth)).toEqual([7, 7]);
  expect(coloredCircles[0]?.props.rotation).toBe("-90");
  expect(coloredCircles[1]?.props.rotation).toBe(150);
});
