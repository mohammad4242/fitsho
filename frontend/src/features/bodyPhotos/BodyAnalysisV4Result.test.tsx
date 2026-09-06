import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it } from "vitest";

import i18n from "../../i18n";
import { BodyAnalysisV4Result } from "./BodyAnalysisV4Result";
import type { BodyAnalysis, BodyAnalysisExperienceV4 } from "./types";

const experience: BodyAnalysisExperienceV4 = {
  schema_version: "4.0",
  presentation_version: "body-analysis-experience-v2",
  assessment_status: "complete",
  input_snapshot: {
    captured_at: "2026-08-03T10:00:00Z",
    confirmed_at: "2026-08-03T10:00:00Z",
    profile_updated_at: "2026-08-03T09:00:00Z",
    measurement_id: "measurement-1",
    measurement_measured_at: "2026-08-03T09:00:00Z",
    sex: "male",
    height_cm: 178,
    weight_kg: 82.5,
    shoulder_circumference_cm: 122,
    waist_circumference_cm: 84,
    hip_circumference_cm: 98,
    selected_goal: "build_muscle",
  },
  body_composition: {
    bmi: 26.0,
    estimated_body_fat_percent: 21.6,
    body_fat_estimation_method: "rfm",
    body_fat_is_estimate: true,
  },
  first_impression: {
    message_key: "body_analysis.first_impression.primary_priority",
    parameters: { areas: ["shoulders"] },
  },
  direction: {
    status: "aligned_with_current_goal",
    goal: "build_muscle",
    reason_codes: ["current_goal_preserved"],
  },
  indicators: {
    upper_lower_balance: {
      status: "balanced",
      message_key: "body_analysis.indicators.upper_lower_balance",
      parameters: { state: "balanced" },
      score_percent: 90,
    },
    visible_symmetry: {
      status: "no_clear_difference",
      message_key: "body_analysis.indicators.visible_symmetry",
      parameters: { state: "no_clear_difference" },
      score_percent: 90,
    },
    muscle_balance: {
      status: "available",
      message_key: "body_analysis.indicators.muscle_balance",
      parameters: {},
      score_percent: 85,
    },
    body_shape: {
      status: "available",
      message_key: "body_analysis.indicators.body_shape",
      parameters: {},
      score_percent: 82,
    },
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
      display_classification: "balanced",
      insight_key: "body_analysis.insights.balanced",
      insight_parameters: { area: "chest" },
      supporting_views: ["front"],
    },
    {
      area: "arms",
      display_classification: "stronger",
      insight_key: "body_analysis.insights.stronger",
      insight_parameters: { area: "arms" },
      supporting_views: ["front"],
    },
  ],
  review_notice_code: "review_pending",
};

const analysis = {
  id: "analysis-1",
  session_id: "session-1",
  revision: 1,
  status: "review_pending",
  provider: "openrouter",
  model_id: "vision-model",
  schema_version: "4.0",
  result_version: 1,
  result_source: "ai",
  normalized_result: null,
  experience_result: experience,
  overall_confidence: null,
  coach_review: { role: "coach", decision: null, reviewed_at: null, reviewed_result_version: null },
  doctor_review: { role: "doctor", decision: null, reviewed_at: null, reviewed_result_version: null },
  fully_reviewed: false,
  unverified_warning: true,
  error_code: null,
  safe_error_message: null,
  photo_validation: null,
  created_at: "2026-08-03T10:00:00Z",
  completed_at: "2026-08-03T10:01:00Z",
} as BodyAnalysis;

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

it("renders top scan overview with body fat %, BMI, and first look summary", () => {
  render(<BodyAnalysisV4Result analysis={analysis} experience={experience} />);

  expect(screen.getByRole("heading", { name: "First look" })).toBeInTheDocument();
  expect(screen.getByText(/clearest focus is shoulders/i)).toBeInTheDocument();
  expect(screen.getByText(/current muscle-building direction/i)).toBeInTheDocument();

  // Metric cards
  expect(screen.getByTestId("body-fat-card")).toBeInTheDocument();
  expect(screen.getByText("21.6%")).toBeInTheDocument();
  expect(screen.getByTestId("bmi-card")).toBeInTheDocument();
  expect(screen.getByText("26")).toBeInTheDocument();

  // View buttons
  expect(screen.getByRole("button", { name: /^front$/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^side$/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^back$/i })).toBeInTheDocument();
});

it("toggles front / side / back views in top overview", async () => {
  const user = userEvent.setup();
  render(<BodyAnalysisV4Result analysis={analysis} experience={experience} />);

  const frontBtn = screen.getByRole("button", { name: /^front$/i });
  const sideBtn = screen.getByRole("button", { name: /^side$/i });
  const backBtn = screen.getByRole("button", { name: /^back$/i });

  expect(frontBtn).toHaveAttribute("aria-pressed", "true");
  expect(sideBtn).toHaveAttribute("aria-pressed", "false");

  await user.click(sideBtn);
  expect(sideBtn).toHaveAttribute("aria-pressed", "true");
  expect(frontBtn).toHaveAttribute("aria-pressed", "false");

  await user.click(backBtn);
  expect(backBtn).toHaveAttribute("aria-pressed", "true");
  expect(sideBtn).toHaveAttribute("aria-pressed", "false");
});

it("renders exactly three display score indicators", () => {
  render(<BodyAnalysisV4Result analysis={analysis} experience={experience} />);

  expect(screen.getByRole("heading", { name: /visual score indicators/i })).toBeInTheDocument();
  expect(screen.getAllByTestId("body-analysis-score-row")).toHaveLength(3);
  expect(screen.getByText("85%")).toBeInTheDocument();
  expect(screen.getByText("Muscle balance")).toBeInTheDocument();
  expect(screen.getByText(/vis(ible|ual) symmetry/i)).toBeInTheDocument();
  expect(screen.getByText("Upper / lower balance")).toBeInTheDocument();
  expect(screen.queryByText("Four useful signals")).not.toBeInTheDocument();
});

it("renders key weaknesses and key strengths summary cards", () => {
  render(<BodyAnalysisV4Result analysis={analysis} experience={experience} />);

  expect(screen.getByRole("heading", { name: /key weaknesses|important weaknesses/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /key strengths|important strengths/i })).toBeInTheDocument();
  expect(screen.getByText(/AI analysis can be wrong/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/Coach review pending/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/Doctor review pending/i)).toBeInTheDocument();
});

it("renders review colors from the real specialist decisions", () => {
  const reviewedAnalysis = {
    ...analysis,
    coach_review: { ...analysis.coach_review, decision: "approved" as const },
    doctor_review: { ...analysis.doctor_review, decision: "changes_required" as const },
  };
  render(<BodyAnalysisV4Result analysis={reviewedAnalysis} experience={experience} />);

  expect(screen.getByLabelText(/Coach review approved/i)).toHaveClass("body-analysis-review--approved");
  expect(screen.getByLabelText(/Doctor review changes required/i)).toHaveClass("body-analysis-review--changes_required");
  expect(document.querySelector(".body-analysis-review--approved .body-analysis-review__dot")).toBeInTheDocument();
});

it("leaves an unavailable display score neutral with a dash", () => {
  const partialExperience = {
    ...experience,
    indicators: {
      ...experience.indicators,
      muscle_balance: { ...experience.indicators.muscle_balance, score_percent: null },
    },
  };
  render(<BodyAnalysisV4Result analysis={analysis} experience={partialExperience} />);

  const scoreRows = screen.getAllByTestId("body-analysis-score-row");
  expect(within(scoreRows[0]).getByText("—")).toBeInTheDocument();
  expect(within(scoreRows[0]).getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");
});
