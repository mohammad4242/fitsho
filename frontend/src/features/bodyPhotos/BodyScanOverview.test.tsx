import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it } from "vitest";

import i18n from "../../i18n";
import { BodyScanOverview } from "./BodyScanOverview";
import type { BodyAnalysisExperienceV4 } from "./types";

const mockExperience = (sex: "male" | "female" = "male"): BodyAnalysisExperienceV4 => ({
  schema_version: "4.0",
  presentation_version: "body-analysis-experience-v2",
  assessment_status: "complete",
  input_snapshot: {
    captured_at: "2026-08-03T10:00:00Z",
    confirmed_at: "2026-08-03T10:00:00Z",
    profile_updated_at: "2026-08-03T09:00:00Z",
    measurement_id: "m-1",
    measurement_measured_at: "2026-08-03T09:00:00Z",
    sex,
    height_cm: 180,
    weight_kg: 80,
    shoulder_circumference_cm: 120,
    waist_circumference_cm: 85,
    hip_circumference_cm: 100,
    selected_goal: "build_muscle",
  },
  body_composition: {
    bmi: 24.7,
    estimated_body_fat_percent: 18.5,
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
    upper_lower_balance: { status: "balanced", message_key: "k", parameters: {}, score_percent: 90 },
    visible_symmetry: { status: "balanced", message_key: "k", parameters: {}, score_percent: 90 },
    muscle_balance: { status: "available", message_key: "k", parameters: {}, score_percent: 88 },
    body_shape: { status: "available", message_key: "k", parameters: {}, score_percent: 85 },
  },
  regions: [],
  review_notice_code: "approved",
});

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

it("renders male hero image for male user and female for female user", () => {
  const { rerender } = render(
    <BodyScanOverview
      experience={mockExperience("male")}
      summaryMessage="Looking balanced."
      routeMessage="Continue current direction."
    />,
  );

  const img = screen.getByRole("img", { name: /fitsho physique scan visual/i });
  expect(img).toHaveAttribute("src", expect.stringContaining("male-hero.png"));

  rerender(
    <BodyScanOverview
      experience={mockExperience("female")}
      summaryMessage="Looking balanced."
      routeMessage="Continue current direction."
    />,
  );

  expect(img).toHaveAttribute("src", expect.stringContaining("female-hero.png"));
});

it("toggles view buttons and shows view labels", async () => {
  const user = userEvent.setup();
  render(
    <BodyScanOverview
      experience={mockExperience("male")}
      summaryMessage="Looking balanced."
      routeMessage="Continue current direction."
    />,
  );

  const front = screen.getByRole("button", { name: /^front$/i });
  const side = screen.getByRole("button", { name: /^side$/i });
  const back = screen.getByRole("button", { name: /^back$/i });

  expect(front).toHaveAttribute("aria-pressed", "true");
  await user.click(side);
  expect(side).toHaveAttribute("aria-pressed", "true");
  await user.click(back);
  expect(back).toHaveAttribute("aria-pressed", "true");
});

it("toggles info notes for body fat and BMI", async () => {
  const user = userEvent.setup();
  render(
    <BodyScanOverview
      experience={mockExperience("male")}
      summaryMessage="Looking balanced."
      routeMessage="Continue current direction."
    />,
  );

  const infoBtns = screen.getAllByRole("button", { name: /اطلاعات/i });
  expect(infoBtns).toHaveLength(2);

  await user.click(infoBtns[0]);
  expect(screen.getByText(/Relative Fat Mass/i)).toBeInTheDocument();

  await user.click(infoBtns[1]);
  expect(screen.getByText(/Body Mass Index from height and weight/i)).toBeInTheDocument();
});
