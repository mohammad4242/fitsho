import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";

import i18n from "../../i18n";
import { BodyAnalysisProgressStrip } from "./BodyAnalysisProgressStrip";
import type { BodyProgressTimelineItem } from "./types";

const createMockTimelineItem = (
  id: string,
  date: string,
  weight: number,
  bf: number,
): BodyProgressTimelineItem => ({
  session: {
    id,
    cycle_id: null,
    purpose: "progress_check",
    state: "completed",
    submitted_at: date,
    created_at: date,
    updated_at: date,
  },
  photos: [],
  snapshot: {
    captured_at: date,
    confirmed_at: date,
    profile_updated_at: date,
    measurement_id: "m-1",
    measurement_measured_at: date,
    sex: "male",
    height_cm: 180,
    weight_kg: weight,
    shoulder_circumference_cm: 120,
    waist_circumference_cm: 85,
    hip_circumference_cm: 100,
    selected_goal: "build_muscle",
  },
  analysis: {
    id: `analysis-${id}`,
    session_id: id,
    revision: 1,
    status: "completed",
    provider: "opencode_zen",
    model_id: "zen",
    schema_version: "4.0",
    result_version: 1,
    result_source: "ai",
    normalized_result: null,
    experience_result: {
      schema_version: "4.0",
      presentation_version: "body-analysis-experience-v2",
      assessment_status: "complete",
      input_snapshot: {} as any,
      body_composition: {
        bmi: 25.0,
        estimated_body_fat_percent: bf,
        body_fat_estimation_method: "rfm",
        body_fat_is_estimate: true,
      },
      first_impression: { message_key: "k", parameters: {} },
      direction: { status: "aligned_with_current_goal", goal: "build_muscle", reason_codes: [] },
      indicators: {} as any,
      regions: [],
      review_notice_code: "approved",
    },
    overall_confidence: null,
    coach_review: { role: "coach", decision: null, reviewed_at: null, reviewed_result_version: null },
    doctor_review: { role: "doctor", decision: null, reviewed_at: null, reviewed_result_version: null },
    fully_reviewed: true,
    unverified_warning: false,
    error_code: null,
    safe_error_message: null,
    photo_validation: null,
    created_at: date,
    completed_at: date,
  },
  comparison: null,
  review_state: {
    coach: { role: "coach", decision: null, reviewed_at: null, reviewed_result_version: null },
    doctor: { role: "doctor", decision: null, reviewed_at: null, reviewed_result_version: null },
    fully_reviewed: true,
  },
});

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

it("renders single-scan friendly state when only 1 scan is available", () => {
  const items = [createMockTimelineItem("s-1", "2026-08-01T10:00:00Z", 80, 20.0)];

  render(<BodyAnalysisProgressStrip currentSessionId="s-1" initialItems={items} />);

  expect(screen.getByRole("heading", { name: "Your first scan is logged" })).toBeInTheDocument();
  expect(screen.getByText(/future scans/i)).toBeInTheDocument();
});

it("renders timeline nodes and summary changes when multiple scans are available", () => {
  const items = [
    // timeline items come newest first
    createMockTimelineItem("s-2", "2026-08-15T10:00:00Z", 78, 18.5),
    createMockTimelineItem("s-1", "2026-08-01T10:00:00Z", 80, 20.0),
  ];

  render(<BodyAnalysisProgressStrip currentSessionId="s-2" initialItems={items} />);

  expect(screen.getByText("Progress over time")).toBeInTheDocument();
  expect(screen.getByText("18.5% BF")).toBeInTheDocument();
  expect(screen.getByText("20% BF")).toBeInTheDocument();
  expect(screen.getByText("78 kg")).toBeInTheDocument();
  expect(screen.getByText("80 kg")).toBeInTheDocument();

  // Summary delta: 18.5 - 20 = -1.5%, 78 - 80 = -2 kg
  expect(screen.getByText("-1.5 %")).toBeInTheDocument();
  expect(screen.getByText("-2 kg")).toBeInTheDocument();
});
