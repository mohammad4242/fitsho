import { fireEvent, render, screen, within } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";
import type { ReactTestInstance } from "react-test-renderer";

jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));

import type { BodyAnalysisExperienceV4 } from "@fitician/core/body-photos";

import { BodyAnalysisMuscleSection } from "./BodyAnalysisMuscleSection";
import { bodyResultAssets } from "./bodyAnalysisAssets";

const experience = {
  schema_version: "4.0",
  presentation_version: "body-analysis-experience-v2",
  assessment_status: "complete",
  input_snapshot: {
    captured_at: "2026-09-08T10:00:00Z",
    confirmed_at: "2026-09-08T10:00:00Z",
    profile_updated_at: "2026-09-08T09:00:00Z",
    measurement_id: "measurement-1",
    measurement_measured_at: "2026-09-08T09:00:00Z",
    sex: "female",
    height_cm: 165,
    weight_kg: 62,
    shoulder_circumference_cm: 98,
    waist_circumference_cm: 70,
    hip_circumference_cm: 96,
    selected_goal: "build_muscle",
  },
  body_composition: {
    bmi: 22.8,
    estimated_body_fat_percent: 24.1,
    body_fat_estimation_method: "rfm",
    body_fat_is_estimate: true,
  },
  first_impression: {
    message_key: "body_analysis.first_impression.balanced",
    parameters: {},
  },
  direction: {
    status: "aligned_with_current_goal",
    goal: "build_muscle",
    reason_codes: ["current_goal_preserved"],
  },
  indicators: {
    upper_lower_balance: { status: "balanced", score_percent: 90 },
    visible_symmetry: { status: "no_clear_difference", score_percent: 91 },
    muscle_balance: { status: "available", score_percent: 85 },
    body_shape: { status: "available", score_percent: 82 },
  },
  regions: [
    {
      area: "shoulders",
      display_classification: "primary_priority",
      insight_key: "body_analysis.insights.primary_priority",
      insight_parameters: { area: "shoulders" },
      supporting_views: ["front", "back"],
    },
    {
      area: "chest",
      display_classification: "stronger",
      insight_key: "body_analysis.insights.stronger",
      insight_parameters: { area: "chest" },
      supporting_views: ["front"],
    },
  ],
  review_notice_code: "review_pending",
} as unknown as BodyAnalysisExperienceV4;

function directChildTestIDs(node: ReactTestInstance): string[] {
  return node.children
    .filter((child): child is ReactTestInstance => typeof child !== "string")
    .map((child) => child.props.testID)
    .filter((testID): testID is string => typeof testID === "string");
}

test("uses the Ghost as the only muscle selector", () => {
  render(<BodyAnalysisMuscleSection experience={experience} />);

  const image = screen.getByTestId("body-analysis-map-image");
  expect(image.props.accessibilityLabel).toBe("نمای روبه‌رو نقشه بدن زن");
  expect(image.props.source).toBe(bodyResultAssets.map.female.front);
  expect(screen.getByTestId("body-analysis-map-hit-region-shoulders")).toBeTruthy();
  expect(screen.getByTestId("body-analysis-map-hit-region-chest")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "سرشانه" })).toBeNull();
  expect(screen.queryByRole("button", { name: "سینه" })).toBeNull();
  expect(screen.queryByText("ناحیهٔ انتخاب‌شده")).toBeNull();

  fireEvent.press(screen.getByTestId("body-analysis-map-hit-region-shoulders"));

  expect(screen.getByTestId("body-analysis-map-mask-shoulders")).toBeTruthy();
  const detail = within(screen.getByTestId("body-analysis-selected-detail"));
  expect(detail.getByText("سرشانه")).toBeTruthy();
  expect(detail.getByText("ناحیهٔ اولویت‌دار")).toBeTruthy();
  expect(detail.getByText(/نسبت به بقیه بدنت عقب‌تره/)).toBeTruthy();
});

test("places selected details above the Ghost and replaces them on the next tap", () => {
  render(<BodyAnalysisMuscleSection experience={experience} />);

  fireEvent.press(screen.getByTestId("body-analysis-map-hit-region-shoulders"));

  const section = screen.getByTestId("body-analysis-muscle-section");
  const childTestIDs = directChildTestIDs(section);
  expect(childTestIDs.indexOf("body-analysis-selected-detail"))
    .toBeLessThan(childTestIDs.indexOf("body-analysis-map-card"));

  fireEvent.press(screen.getByTestId("body-analysis-map-hit-region-chest"));

  expect(screen.getByTestId("body-analysis-map-mask-chest")).toBeTruthy();
  const detail = within(screen.getByTestId("body-analysis-selected-detail"));
  expect(detail.getByText("سینه")).toBeTruthy();
  expect(detail.getByText("نقطهٔ قوت ظاهری")).toBeTruthy();
  expect(detail.getByText("سینه خوب جلو افتاده و فعلاً جزو اولویت‌های اصلیت نیست.")).toBeTruthy();
  expect(screen.queryByText("سرشانه نسبت به بقیه بدنت عقب‌تره و بهتره فعلاً بیشتر روش کار کنی.")).toBeNull();
});

test("changes the map artwork and available hit regions with the selected view", () => {
  render(<BodyAnalysisMuscleSection experience={experience} />);

  fireEvent.press(screen.getByRole("radio", { name: "نمای پشت" }));

  expect(screen.getByTestId("body-analysis-map-image").props.accessibilityLabel)
    .toBe("نمای پشت نقشه بدن زن");
  expect(screen.getByTestId("body-analysis-map-image").props.source).toBe(bodyResultAssets.map.female.back);
  expect(screen.getByTestId("body-analysis-map-hit-region-shoulders")).toBeTruthy();
  expect(screen.queryByTestId("body-analysis-map-hit-region-chest")).toBeNull();
});
