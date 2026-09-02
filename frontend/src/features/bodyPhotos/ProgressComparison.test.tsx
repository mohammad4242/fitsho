import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";

import i18n from "../../i18n";
import { ProgressComparison } from "./ProgressComparison";
import type { BodyProgressComparison } from "./types";

const provenance = {
  previous: {
    source: "body_analysis_input_snapshot" as const,
    reference_id: "measurement-before",
    recorded_at: "2026-08-01T10:00:00Z",
    reason_code: "exact_analysis_input_snapshot" as const,
  },
  current: {
    source: "body_analysis_input_snapshot" as const,
    reference_id: "measurement-after",
    recorded_at: "2026-08-15T10:00:00Z",
    reason_code: "exact_analysis_input_snapshot" as const,
  },
};

const comparison: BodyProgressComparison = {
  id: "comparison-1",
  previous_session_id: "session-before",
  current_session_id: "session-after",
  previous_result_version_id: "version-before",
  current_result_version_id: "version-after",
  comparison_version: 1,
  schema_version: "2.0",
  normalized_result: {
    schema_version: "2.0",
    overall_confidence: 0.82,
    previous_session_id: "session-before",
    current_session_id: "session-after",
    previous_result_version_id: "version-before",
    current_result_version_id: "version-after",
    previous_session_date: "2026-08-01T10:00:00Z",
    current_session_date: "2026-08-15T10:00:00Z",
    interval_days: 14,
    measurement_deltas: [
      { measurement: "weight_kg", unit: "kg", previous: 80, current: 79, delta: -1, availability: "exact", provenance },
      { measurement: "shoulder_circumference_cm", unit: "cm", previous: 116, current: 118, delta: 2, availability: "exact", provenance },
      { measurement: "waist_circumference_cm", unit: "cm", previous: 84, current: 82, delta: -2, availability: "exact", provenance },
      { measurement: "hip_circumference_cm", unit: "cm", previous: 98, current: 98, delta: 0, availability: "exact", provenance },
    ],
    visual_transitions: [{
      body_area: "shoulders",
      state: "improved",
      previous_classification: "neutral",
      current_classification: "strength",
      change_confidence: 0.88,
      supporting_views: ["front", "back"],
      reason_codes: ["classification_changed"],
      provenance: {
        previous: {
          source: "normalized_result",
          reference_id: "version-before",
          recorded_at: "2026-08-01T10:01:00Z",
          reason_code: "effective_normalized_result",
        },
        current: {
          source: "normalized_result",
          reference_id: "version-after",
          recorded_at: "2026-08-15T10:01:00Z",
          reason_code: "effective_normalized_result",
        },
      },
    }],
    persistent_priorities: [{ body_area: "lats", provenance }],
    measurement_notice_code: "measurements_recorded_by_user",
    visual_observation_notice_code: "standardized_photo_observation_not_direct_measurement",
  },
  quality_snapshot: {},
  context_snapshot: { user_reported_measurement_changes: {} },
  created_at: "2026-08-15T10:02:00Z",
};

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

it("renders one compact measurement chart without repeated provenance", () => {
  render(<ProgressComparison comparison={comparison} />);

  expect(screen.getByRole("heading", { name: "Progress comparison" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Measurements" })).toBeInTheDocument();
  expect(screen.getByText("Waist circumference")).toBeInTheDocument();
  expect(screen.getByText(/84.*cm/i)).toBeInTheDocument();
  expect(screen.getByText(/82.*cm/i)).toBeInTheDocument();
  expect(screen.getAllByTestId("body-progress-measurement-row")).toHaveLength(4);
  expect(screen.queryByText(/Based on measurements recorded by you/i)).not.toBeInTheDocument();
});

it("renders only the biggest meaningful visual change", () => {
  render(<ProgressComparison comparison={comparison} />);

  expect(screen.getByRole("heading", { name: "Biggest change" })).toBeInTheDocument();
  expect(screen.getByText("Shoulders")).toBeInTheDocument();
  expect(screen.getByText(/had the biggest positive change/i)).toBeInTheDocument();
  expect(screen.queryByText(/Appears improved/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/Lats remain a primary priority/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/Visual observation from standardized photos/i)).not.toBeInTheDocument();
  expect(screen.queryByTestId("body-progress-visual-list")).not.toBeInTheDocument();
});
