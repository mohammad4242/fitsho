import { render, screen, waitFor } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";

jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));

import { NutritionAnimatedNumber } from "./NutritionAnimatedNumber";

test("animates a nutrition value from zero to its target", async () => {
  render(<NutritionAnimatedNumber value={2100} />);

  expect(screen.getByText("۰")).toBeTruthy();
  await waitFor(() => expect(screen.getByText("۲٬۱۰۰")).toBeTruthy(), { timeout: 1500 });
});
