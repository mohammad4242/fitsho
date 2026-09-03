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
    insight_key: "body_analysis.insights.balanced",
    insight_parameters: { area: "chest" },
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
  expect(screen.getByRole("img", { name: `${label} front body artwork` })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Shoulders — Priority area" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
});

it("starts unselected, switches artwork, and selects an overlay region by pointer", async () => {
  const user = userEvent.setup();
  render(<BodyAreaMap sex="male" regions={regions} />);

  expect(screen.queryByRole("heading", { name: "Chest" })).not.toBeInTheDocument();
  const frontImage = screen.getByRole("img", { name: "Male front body artwork" });
  expect(frontImage).toHaveAttribute("src", expect.stringContaining("male-front.jpg"));

  await user.click(screen.getByRole("button", { name: "Chest — Balanced in these views" }));
  const chestRegion = screen.getByRole("button", { name: "Chest — Balanced in these views" });
  expect(chestRegion).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(chestRegion).toHaveClass("body-area-map__hit-region");
  expect(chestRegion).not.toHaveClass("is-selected");
  const visualMask = document.querySelector(".body-area-map__visual-mask");
  expect(visualMask).toHaveAttribute("aria-hidden", "true");
  expect(visualMask).toHaveAttribute("data-area", "chest");
  expect(visualMask).toHaveAttribute("data-mask-file", "male-front/chest.svg");
  expect(visualMask).toHaveAttribute("src", expect.stringContaining("male-front.jpg"));
  expect(screen.getByRole("heading", { name: "Chest" })).toBeInTheDocument();
  expect(screen.getByText(/chest is balanced/i)).toBeInTheDocument();

  await user.click(screen.getByRole("tab", { name: "Back view" }));
  expect(screen.getByRole("group", { name: "Male back body map" })).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "Male back body artwork" })).toHaveAttribute(
    "src",
    expect.stringContaining("male-back.jpg"),
  );
  expect(screen.queryByRole("heading", { name: "Chest" })).not.toBeInTheDocument();

  const backRegion = screen.getByRole("button", { name: "Back — Not assessable" });
  backRegion.focus();
  await user.keyboard("{Enter}");

  expect(backRegion).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("heading", { name: "Back" })).toBeInTheDocument();
  expect(screen.getByText(/this area could not be assessed clearly/i)).toBeInTheDocument();
  expect(document.querySelector(".body-area-map__regions")).not.toBeInTheDocument();
});

it("supports Space-key selection and shows the direct balanced insight", async () => {
  const user = userEvent.setup();
  render(<BodyAreaMap sex="neutral" regions={regions} />);

  const chest = screen.getByRole("button", { name: "Chest — Balanced in these views" });
  chest.focus();
  await user.keyboard(" ");

  expect(chest).toHaveAttribute("data-classification", "balanced");
  expect(chest).toHaveAttribute("aria-pressed", "true");
  expect(chest).not.toHaveClass("is-selected");
  expect(screen.getByText(/chest is balanced/i)).toBeInTheDocument();
});

it.each([
  ["male", "front", "chest", "Chest — Balanced in these views", "male-front/chest.svg"],
  ["male", "back", "back", "Back — Not assessable", "male-back/back.svg"],
  ["female", "front", "chest", "Chest — Balanced in these views", "female-front/chest.svg"],
  ["female", "back", "back", "Back — Not assessable", "female-back/back.svg"],
] as const)("uses a precise visual mask for the %s %s artwork", async (sex, view, area, label, maskFile) => {
  const user = userEvent.setup();
  render(<BodyAreaMap sex={sex} regions={regions} />);

  if (view === "back") {
    await user.click(screen.getByRole("tab", { name: "Back view" }));
  }

  const hitRegion = screen.getByRole("button", { name: label });
  await user.click(hitRegion);

  const visualMask = document.querySelector(".body-area-map__visual-mask");
  expect(visualMask).toHaveAttribute("data-area", area);
  expect(visualMask).toHaveAttribute("data-mask-file", maskFile);
  expect(visualMask).toHaveAttribute(
    "src",
    expect.stringContaining(`${sex}-${view}.jpg`),
  );
  expect(hitRegion).not.toHaveClass("is-selected");
});
