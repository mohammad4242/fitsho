import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import i18n from "../../i18n";
import { BodyTimeline } from "./BodyTimeline";
import type { BodyProgressTimelineItem } from "./types";

const photos = (prefix: string) => (["front", "side", "back"] as const).map((view) => ({
  id: `${prefix}-${view}`,
  view,
  mime_type: "image/jpeg",
  byte_size: 100,
  width: 800,
  height: 1200,
  content_url: `/${prefix}-${view}.jpg`,
  created_at: "2026-08-15T10:00:00Z",
  updated_at: "2026-08-15T10:00:00Z",
}));

const comparison = {
  id: "comparison-1",
  previous_session_id: "session-before",
  current_session_id: "session-current",
  previous_result_version_id: "version-before",
  current_result_version_id: "version-current",
  comparison_version: 1,
  schema_version: "2.0" as const,
  normalized_result: {
    schema_version: "2.0" as const,
    overall_confidence: 0.8,
    previous_session_id: "session-before",
    current_session_id: "session-current",
    previous_result_version_id: "version-before",
    current_result_version_id: "version-current",
    previous_session_date: "2026-08-01T10:00:00Z",
    current_session_date: "2026-08-15T10:00:00Z",
    interval_days: 14,
    measurement_deltas: [
      { measurement: "weight_kg" as const, unit: "kg" as const, previous: 80, current: 79, delta: -1, availability: "exact" as const, provenance: { previous: { source: "body_analysis_input_snapshot" as const, reference_id: "m1", recorded_at: "2026-08-01T10:00:00Z", reason_code: "exact_analysis_input_snapshot" as const }, current: { source: "body_analysis_input_snapshot" as const, reference_id: "m2", recorded_at: "2026-08-15T10:00:00Z", reason_code: "exact_analysis_input_snapshot" as const } } },
      { measurement: "shoulder_circumference_cm" as const, unit: "cm" as const, previous: 116, current: 118, delta: 2, availability: "exact" as const, provenance: { previous: { source: "body_analysis_input_snapshot" as const, reference_id: "m1", recorded_at: "2026-08-01T10:00:00Z", reason_code: "exact_analysis_input_snapshot" as const }, current: { source: "body_analysis_input_snapshot" as const, reference_id: "m2", recorded_at: "2026-08-15T10:00:00Z", reason_code: "exact_analysis_input_snapshot" as const } } },
      { measurement: "waist_circumference_cm" as const, unit: "cm" as const, previous: 84, current: 82, delta: -2, availability: "exact" as const, provenance: { previous: { source: "body_analysis_input_snapshot" as const, reference_id: "m1", recorded_at: "2026-08-01T10:00:00Z", reason_code: "exact_analysis_input_snapshot" as const }, current: { source: "body_analysis_input_snapshot" as const, reference_id: "m2", recorded_at: "2026-08-15T10:00:00Z", reason_code: "exact_analysis_input_snapshot" as const } } },
      { measurement: "hip_circumference_cm" as const, unit: "cm" as const, previous: 98, current: 98, delta: 0, availability: "exact" as const, provenance: { previous: { source: "body_analysis_input_snapshot" as const, reference_id: "m1", recorded_at: "2026-08-01T10:00:00Z", reason_code: "exact_analysis_input_snapshot" as const }, current: { source: "body_analysis_input_snapshot" as const, reference_id: "m2", recorded_at: "2026-08-15T10:00:00Z", reason_code: "exact_analysis_input_snapshot" as const } } },
    ],
    visual_transitions: [{
      body_area: "shoulders" as const,
      state: "improved" as const,
      previous_classification: "neutral" as const,
      current_classification: "strength" as const,
      change_confidence: 0.8,
      supporting_views: ["front", "back"] as const,
      reason_codes: ["classification_changed"] as const,
      provenance: { previous: { source: "normalized_result" as const, reference_id: "v1", recorded_at: "2026-08-01T10:01:00Z", reason_code: "effective_normalized_result" as const }, current: { source: "normalized_result" as const, reference_id: "v2", recorded_at: "2026-08-15T10:01:00Z", reason_code: "effective_normalized_result" as const } },
    }],
    persistent_priorities: [],
    measurement_notice_code: "measurements_recorded_by_user" as const,
    visual_observation_notice_code: "standardized_photo_observation_not_direct_measurement" as const,
  },
  quality_snapshot: {},
  context_snapshot: { user_reported_measurement_changes: {} },
  created_at: "2026-08-15T10:02:00Z",
  previous_session_date: "2026-08-01T10:00:00Z",
  current_session_date: "2026-08-15T10:00:00Z",
  interval_days: 14,
  before_photos: photos("before"),
  after_photos: photos("after"),
};

const items = [
  {
    session: {
      id: "session-current",
      cycle_id: null,
      purpose: "progress_check" as const,
      state: "review_pending" as const,
      submitted_at: "2026-08-15T10:00:00Z",
      created_at: "2026-08-15T10:00:00Z",
      updated_at: "2026-08-15T10:00:00Z",
    },
    photos: photos("after"),
    analysis: null,
    snapshot: {
      captured_at: "2026-08-15T10:00:00Z",
      confirmed_at: "2026-08-15T09:59:00Z",
      profile_updated_at: "2026-08-14T10:00:00Z",
      measurement_id: "m2",
      measurement_measured_at: "2026-08-15T09:58:00Z",
      sex: "male" as const,
      height_cm: 180,
      weight_kg: 79,
      shoulder_circumference_cm: 118,
      waist_circumference_cm: 82,
      hip_circumference_cm: 98,
      selected_goal: "build_muscle" as const,
    },
    comparison,
    review_state: {
      coach: { role: "coach" as const, decision: "approved" as const, reviewed_at: "2026-08-15T12:00:00Z", reviewed_result_version: 1 },
      doctor: { role: "doctor" as const, decision: null, reviewed_at: null, reviewed_result_version: null },
      fully_reviewed: false,
    },
  },
  {
    session: {
      id: "session-incomplete",
      cycle_id: null,
      purpose: "progress_check" as const,
      state: "uploading" as const,
      submitted_at: null,
      created_at: "2026-08-14T10:00:00Z",
      updated_at: "2026-08-14T10:00:00Z",
    },
    photos: photos("draft").slice(0, 1),
    analysis: null,
    snapshot: null,
    comparison: null,
    review_state: {
      coach: { role: "coach" as const, decision: null, reviewed_at: null, reviewed_result_version: null },
      doctor: { role: "doctor" as const, decision: null, reviewed_at: null, reviewed_result_version: null },
      fully_reviewed: false,
    },
  },
] satisfies BodyProgressTimelineItem[];

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

it("renders the longitudinal scan timeline and deterministic comparison entry", () => {
  render(<MemoryRouter><BodyTimeline items={items} onDelete={vi.fn()} /></MemoryRouter>);

  expect(screen.getByRole("heading", { name: "My body over time" })).toBeInTheDocument();
  expect(screen.getByText(/14 days/i)).toBeInTheDocument();
  expect(screen.getAllByText(/Based on measurements recorded by you/i).length).toBeGreaterThan(0);
  expect(screen.getByRole("link", { name: "View analysis" })).toHaveAttribute(
    "href",
    "/body-progress/session-current",
  );
  expect(screen.getByLabelText("Coach review Approved")).toBeInTheDocument();
  expect(screen.getByLabelText("Doctor review Pending")).toBeInTheDocument();
});

it("keeps incomplete sessions resumable and deletable", async () => {
  const onDelete = vi.fn();
  render(<MemoryRouter><BodyTimeline items={items} onDelete={onDelete} /></MemoryRouter>);

  expect(screen.getByRole("link", { name: "Continue upload" })).toHaveAttribute(
    "href",
    "/body-progress/new?sessionId=session-incomplete",
  );
  screen.getByRole("button", { name: "Delete upload" }).click();
  expect(onDelete).toHaveBeenCalledWith(items[1]?.session, expect.any(HTMLButtonElement));
});
