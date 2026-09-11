import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";

jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));

import type { BodyAnalysisExperienceV4 } from "@fitician/core/body-photos";

import { BodyAnalysisOverviewCard } from "./BodyAnalysisOverviewCard";
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
  regions: [],
  review_notice_code: "review_pending",
} as unknown as BodyAnalysisExperienceV4;

test("uses the sex-specific Web overview artwork for every body view", () => {
  render(<BodyAnalysisOverviewCard experience={experience} />);

  const image = screen.getByTestId("body-analysis-overview-image");
  expect(image.props.accessibilityLabel).toBe("نمای روبه‌رو آنالیز بدن زن");
  expect(image.props.source).toBe(bodyResultAssets.overview.female.front);

  fireEvent.press(screen.getByRole("tab", { name: "نمای نیم‌رخ" }));
  expect(screen.getByTestId("body-analysis-overview-image").props.accessibilityLabel)
    .toBe("نمای نیم‌رخ آنالیز بدن زن");

  fireEvent.press(screen.getByRole("tab", { name: "نمای پشت" }));
  expect(screen.getByTestId("body-analysis-overview-image").props.accessibilityLabel)
    .toBe("نمای پشت آنالیز بدن زن");
});

test("uses the male Web overview artwork when the profile is male", () => {
  const maleExperience = {
    ...experience,
    input_snapshot: { ...experience.input_snapshot, sex: "male" },
  } as unknown as BodyAnalysisExperienceV4;

  render(<BodyAnalysisOverviewCard experience={maleExperience} />);

  const image = screen.getByTestId("body-analysis-overview-image");
  expect(image.props.accessibilityLabel).toBe("نمای روبه‌رو آنالیز بدن مرد");
  expect(image.props.source).toBe(bodyResultAssets.overview.male.front);
});
