import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";

import i18n from "../../i18n";
import { GhostOverlayGuide } from "./GhostOverlayGuide";
import { resolveGhostOverlayVariant } from "./ghostOverlayAssets";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

it.each([
  ["male", "front", "photo_2026-09-02_13-27-40.jpg"],
  ["male", "side", "photo_2026-09-02_13-27-41 (2).jpg"],
  ["male", "back", "photo_2026-09-02_13-27-39.jpg"],
  ["female", "front", "photo_2026-09-02_13-54-09.jpg"],
  ["female", "side", "photo_2026-09-02_13-27-41.jpg"],
  ["female", "back", "photo_2026-09-02_13-27-42.jpg"],
] as const)("renders the prepared %s %s ghost asset", (sex, view, fileName) => {
  const { container } = render(<GhostOverlayGuide sex={sex} view={view} />);
  const image = container.querySelector(".ghost-overlay__asset");

  expect(screen.getByLabelText(/privacy cut/i)).toBeInTheDocument();
  expect(screen.getByText(/keep your neck and shoulders below this line/i)).toBeInTheDocument();
  expect(image).toHaveAttribute("src", expect.stringContaining(fileName.replace(" ", "%20")));
  expect(image).toHaveAttribute("alt", "");
  expect(container.querySelector("svg")).toBeNull();
});

it.each([undefined, null, "other", "prefer_not_to_say"] as const)(
  "uses the prepared neutral fallback for %s sex",
  (sex) => {
    const { container } = render(<GhostOverlayGuide sex={sex} view="side" />);

    expect(resolveGhostOverlayVariant(sex)).toBe("neutral");
    expect(container.querySelector(".ghost-overlay__asset")).toHaveAttribute(
      "src",
      expect.stringContaining("photo_2026-09-02_13-27-41%20(2).jpg"),
    );
  },
);

it("applies a uniform centered scale to the Ghost asset frame", () => {
  const { container } = render(<GhostOverlayGuide sex="female" view="front" scale={0.95} />);
  const frame = container.querySelector<HTMLElement>(".ghost-overlay__asset-frame");

  expect(frame).not.toBeNull();
  expect(frame).toHaveStyle({ transform: "scale(0.95)" });
});
