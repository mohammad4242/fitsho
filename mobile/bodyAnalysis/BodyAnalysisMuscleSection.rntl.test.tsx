import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";

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

test("matches the Web interactive female map and highlights a clicked muscle", () => {
  render(<BodyAnalysisMuscleSection experience={experience} />);

  const image = screen.getByTestId("body-analysis-map-image");
  expect(image.props.accessibilityLabel).toBe("نمای روبه‌رو نقشه بدن زن");
  expect(image.props.source).toBe(bodyResultAssets.map.female.front);
  expect(screen.getByTestId("body-analysis-map-hit-region-shoulders")).toBeTruthy();
  expect(screen.getByTestId("body-analysis-map-hit-region-chest")).toBeTruthy();

  fireEvent.press(screen.getByTestId("body-analysis-map-hit-region-shoulders"));

  expect(screen.getByTestId("body-analysis-map-mask-shoulders")).toBeTruthy();
  expect(screen.getAllByText("سرشانه").length).toBeGreaterThan(0);
  expect(screen.getByText(/نسبت به بقیه بدنت عقب‌تره/)).toBeTruthy();
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
