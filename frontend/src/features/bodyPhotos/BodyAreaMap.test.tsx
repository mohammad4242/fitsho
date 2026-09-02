import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it } from "vitest";

import i18n from "../../i18n";
import { BodyAreaMap } from "./BodyAreaMap";
import type { BodyAnalysisExperienceRegion } from "./types";

const regions: BodyAnalysisExperienceRegion[] = [
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
  {
    area: "back",
    display_classification: "not_assessable",
    insight_key: "body_analysis.insights.not_assessable",
    insight_parameters: { area: "back" },
    supporting_views: ["back"],
  },
];

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

it.each([
  ["male", "Male"],
  ["female", "Female"],
  ["neutral", "Neutral"],
] as const)("selects the %s artwork without changing region semantics", (sex, label) => {
  render(<BodyAreaMap sex={sex} regions={regions} />);

  expect(screen.getByRole("group", { name: `${label} front body map` })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Shoulders — Priority area" })).toBeInTheDocument();
});

it("switches front and back views and lets keyboard users select an SVG region", async () => {
  const user = userEvent.setup();
  render(<BodyAreaMap sex="male" regions={regions} />);

  await user.click(screen.getByRole("button", { name: /SVG region: Chest.*balanced/i }));
  expect(screen.getByRole("button", { name: "Chest — Balanced in these views" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  await user.click(screen.getByRole("tab", { name: "Back view" }));
  expect(screen.getByRole("group", { name: "Male back body map" })).toBeInTheDocument();

  const backRegion = screen.getByRole("button", { name: "Back — Not assessable" });
  backRegion.focus();
  await user.keyboard("{Enter}");

  expect(backRegion).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("heading", { name: "Back" })).toBeInTheDocument();
  expect(screen.getByText(/this area could not be assessed clearly/i)).toBeInTheDocument();
});

it("shows classification text as well as visual state", () => {
  render(<BodyAreaMap sex="neutral" regions={regions} />);

  const priority = screen.getByRole("button", { name: "Shoulders — Priority area" });
  expect(priority).toHaveTextContent("Priority area");
  expect(priority).toHaveAttribute("data-classification", "primary_priority");
});
