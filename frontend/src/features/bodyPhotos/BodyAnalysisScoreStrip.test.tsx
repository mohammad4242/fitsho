import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";

import i18n from "../../i18n";
import { BodyAnalysisScoreStrip } from "./BodyAnalysisScoreStrip";
import type { BodyAnalysisExperienceIndicators } from "./types";

const indicators: BodyAnalysisExperienceIndicators = {
  upper_lower_balance: {
    status: "balanced",
    message_key: "body_analysis.indicators.upper_lower_balance",
    parameters: {},
    score_percent: 88,
  },
  visible_symmetry: {
    status: "no_clear_difference",
    message_key: "body_analysis.indicators.visible_symmetry",
    parameters: {},
    score_percent: 92,
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
    score_percent: 80,
  },
};

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

it("renders three ring cards with correct scores and titles", () => {
  render(<BodyAnalysisScoreStrip indicators={indicators} />);

  expect(screen.getAllByTestId("body-analysis-score-row")).toHaveLength(3);
  expect(screen.getByText("85%")).toBeInTheDocument();
  expect(screen.getByText("92%")).toBeInTheDocument();
  expect(screen.getByText("88%")).toBeInTheDocument();

  expect(screen.getByText("Muscle balance")).toBeInTheDocument();
  expect(screen.getByText(/vis(ible|ual) symmetry/i)).toBeInTheDocument();
  expect(screen.getByText("Upper / lower balance")).toBeInTheDocument();
});

it("displays dash when a score is null", () => {
  const nullIndicators: BodyAnalysisExperienceIndicators = {
    ...indicators,
    muscle_balance: { ...indicators.muscle_balance, score_percent: null },
    upper_lower_balance: { ...indicators.upper_lower_balance, score_percent: null },
  };

  render(<BodyAnalysisScoreStrip indicators={nullIndicators} />);

  const dashes = screen.getAllByText("—");
  expect(dashes.length).toBeGreaterThanOrEqual(2);
});
