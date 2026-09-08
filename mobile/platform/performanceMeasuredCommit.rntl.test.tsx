import { render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";
import { Text } from "react-native";

import { MobilePerformanceRecorder } from "./performance";
import { PerformanceMeasuredCommit } from "./performanceMeasuredCommit";

test("records a committed list render without exposing child data", () => {
  const recorder = new MobilePerformanceRecorder(() => 0);

  render(
    <PerformanceMeasuredCommit metric="large_list_render" now={() => 12} recorder={recorder}>
      <Text>تمرین</Text>
    </PerformanceMeasuredCommit>,
  );

  expect(screen.getByText("تمرین")).toBeTruthy();
  expect(recorder.getSamples()).toEqual([
    {
      budget: 250,
      metric: "large_list_render",
      passed: true,
      unit: "ms",
      value: 0,
    },
  ]);
  expect(JSON.stringify(recorder.getSamples())).not.toContain("تمرین");
  jest.clearAllMocks();
});
