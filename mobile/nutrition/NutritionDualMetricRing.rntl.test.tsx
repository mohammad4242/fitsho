import { render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";
import { Animated } from "react-native";

jest.mock("expo-router", () => ({
  useFocusEffect: (effect: () => void) => effect(),
}));

import { NutritionDualMetricRing } from "./NutritionDualMetricRing";

test("animates the BMR and activity rings from empty to their TDEE shares", () => {
  const timing = jest.spyOn(Animated, "timing").mockReturnValue({ start: jest.fn() } as never);

  render(
    <NutritionDualMetricRing
      label="تفکیک مصرف انرژی روزانه"
      primaryValue={1600}
      secondaryValue={800}
      total={2400}
    />,
  );

  expect(timing).toHaveBeenCalledWith(
    expect.anything(),
    expect.objectContaining({ duration: 900, toValue: 1, useNativeDriver: false }),
  );
  expect(screen.getByRole("progressbar", { name: "تفکیک مصرف انرژی روزانه" }).props.accessibilityValue)
    .toEqual({ max: 100, min: 0, now: 100 });
  timing.mockRestore();
});
