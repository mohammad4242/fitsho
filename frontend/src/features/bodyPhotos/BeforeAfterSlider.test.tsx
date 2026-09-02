import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it } from "vitest";

import i18n from "../../i18n";
import { BeforeAfterSlider } from "./BeforeAfterSlider";
import type { BodyPhoto } from "./types";

function photos(prefix: string): BodyPhoto[] {
  return (["front", "side", "back"] as const).map((view) => ({
    id: `${prefix}-${view}`,
    view,
    mime_type: "image/jpeg",
    byte_size: 100,
    width: 800,
    height: 1200,
    content_url: `/${prefix}-${view}.jpg`,
    created_at: "2026-08-01T10:00:00Z",
    updated_at: "2026-08-01T10:00:00Z",
  }));
}

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

it("shows protected front photos by default with dates and a keyboard slider", async () => {
  const user = userEvent.setup();
  render(
    <BeforeAfterSlider
      afterPhotos={photos("after")}
      beforePhotos={photos("before")}
      currentDate="August 15, 2026"
      previousDate="August 1, 2026"
    />,
  );

  expect(screen.getByRole("tab", { name: "Front" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("img", { name: "Before — Front" })).toHaveAttribute("src", "/before-front.jpg");
  expect(screen.getByRole("img", { name: "After — Front" })).toHaveAttribute("src", "/after-front.jpg");
  expect(screen.getByText("August 1, 2026")).toBeInTheDocument();
  expect(screen.getByText("August 15, 2026")).toBeInTheDocument();

  const slider = screen.getByRole("slider", { name: "Before and after position" });
  expect(slider).toHaveValue("50");
  slider.focus();
  await user.keyboard("{ArrowRight}");
  expect(slider).toHaveValue("51");
});

it("switches the protected pair across all recorded views", async () => {
  const user = userEvent.setup();
  render(
    <BeforeAfterSlider
      afterPhotos={photos("after")}
      beforePhotos={photos("before")}
      currentDate="August 15, 2026"
      previousDate="August 1, 2026"
    />,
  );

  await user.click(screen.getByRole("tab", { name: "Side" }));

  expect(screen.getByRole("tab", { name: "Side" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("img", { name: "Before — Side" })).toHaveAttribute("src", "/before-side.jpg");
  expect(screen.getByRole("img", { name: "After — Side" })).toHaveAttribute("src", "/after-side.jpg");
});
