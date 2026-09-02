import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";

import i18n from "../../i18n";
import { GhostOverlayGuide } from "./GhostOverlayGuide";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

it.each(["front", "side", "back"] as const)("renders the privacy cut and the loose %s silhouette", (view) => {
  const { container } = render(<GhostOverlayGuide view={view} />);

  expect(screen.getByLabelText(/privacy cut/i)).toBeInTheDocument();
  expect(screen.getByText(/keep your neck and shoulders below this line/i)).toBeInTheDocument();
  expect(container.querySelector(`.ghost-overlay__silhouette--${view}`)).not.toBeNull();
});

it.each(["front", "side", "back"] as const)("renders anatomical alignment landmarks for the %s guide", (view) => {
  const { container } = render(<GhostOverlayGuide view={view} />);
  const silhouette = container.querySelector(`.ghost-overlay__silhouette--${view}`);

  expect(silhouette?.querySelector(".ghost-overlay__silhouette-outline")).not.toBeNull();
  expect(silhouette?.querySelectorAll(".ghost-overlay__silhouette-detail")).toHaveLength(3);
  expect(silhouette?.querySelector(".ghost-overlay__silhouette-centerline")).not.toBeNull();
});

it.each(["front", "side", "back"] as const)("renders separate head and body contours for the %s guide", (view) => {
  const { container } = render(<GhostOverlayGuide view={view} />);
  const silhouette = container.querySelector(`.ghost-overlay__silhouette--${view}`);

  expect(silhouette?.querySelectorAll(".ghost-overlay__silhouette-fill")).toHaveLength(2);
  expect(silhouette?.querySelectorAll(".ghost-overlay__silhouette-outline")).toHaveLength(2);
});

it("marks the side guide with a distinct profile contour", () => {
  const { container } = render(<GhostOverlayGuide view="side" />);

  expect(container.querySelector(".ghost-overlay__silhouette--side .ghost-overlay__silhouette-profile")).not.toBeNull();
});
