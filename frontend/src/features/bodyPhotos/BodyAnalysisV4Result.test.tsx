import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";

import i18n from "../../i18n";
import { BodyAnalysisV4Result } from "./BodyAnalysisV4Result";
import type { BodyAnalysis, BodyAnalysisExperienceV4 } from "./types";

const experience: BodyAnalysisExperienceV4 = {
  schema_version: "4.0",
  presentation_version: "body-analysis-experience-v1",
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
    body_proportion: {
      status: "available",
      message_key: "body_analysis.indicators.body_proportion",
      parameters: { shoulder_to_waist_ratio: 1.45, waist_to_hip_ratio: 0.86 },
    },
    upper_lower_balance: {
      status: "balanced",
      message_key: "body_analysis.indicators.upper_lower_balance",
      parameters: { state: "balanced" },
    },
    visible_symmetry: {
      status: "no_clear_difference",
      message_key: "body_analysis.indicators.visible_symmetry",
      parameters: { state: "no_clear_difference" },
    },
    current_development_focus: {
      status: "primary_priority",
      message_key: "body_analysis.indicators.current_development_focus",
      parameters: { areas: ["shoulders"] },
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
      insight_key: null,
      insight_parameters: {},
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

it("renders the deterministic first impression, direction, and four indicators", () => {
  render(<BodyAnalysisV4Result analysis={analysis} experience={experience} />);

  expect(screen.getByRole("heading", { name: "What stands out first" })).toBeInTheDocument();
  expect(screen.getByText(/clearest direction is shoulders/i)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Your direction" })).toBeInTheDocument();
  expect(screen.getByText(/supports your current muscle-building direction/i)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Four useful signals" })).toBeInTheDocument();
  expect(screen.getByText("Body proportion")).toBeInTheDocument();
  expect(screen.getByText("Upper / lower balance")).toBeInTheDocument();
  expect(screen.getByText("Visible symmetry")).toBeInTheDocument();
  expect(screen.getByText("Current development focus")).toBeInTheDocument();
});

it("renders meaningful v4 insights without numeric confidence percentages", () => {
  render(<BodyAnalysisV4Result analysis={analysis} experience={experience} />);

  expect(screen.getByText(/primary area to work on is shoulders/i)).toBeInTheDocument();
  expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent(/provisional/i);
  expect(screen.getByText(/pending review/i)).toBeInTheDocument();
  expect(screen.getByText(/visible proportions and development/i)).toBeInTheDocument();
});
