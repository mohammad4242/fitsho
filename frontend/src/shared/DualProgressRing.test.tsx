import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { DualProgressRing } from "./DualProgressRing";

it("exposes primary and secondary combined progress as an accessible progressbar", () => {
  render(
    <DualProgressRing
      primaryValue={1600}
      secondaryValue={800}
      total={2400}
      label="TDEE breakdown"
    />,
  );

  const ring = screen.getByRole("progressbar", { name: "TDEE breakdown" });
  expect(ring).toHaveAttribute("aria-valuenow", "2400");
  expect(ring).toHaveAttribute("aria-valuemax", "2400");
  expect(ring).toHaveTextContent("100%");
  expect(ring.style.getPropertyValue("--ring-deg-1")).toBe("240.0deg");
  expect(ring.style.getPropertyValue("--ring-deg-2")).toBe("360.0deg");
});

it("handles partial progress and custom labels correctly", () => {
  render(
    <DualProgressRing
      primaryValue={800}
      secondaryValue={400}
      total={2400}
    />,
  );

  const ring = screen.getByRole("progressbar");
  expect(ring).toHaveAttribute("aria-valuenow", "1200");
  expect(ring).toHaveAttribute("aria-valuemax", "2400");
  expect(ring).toHaveTextContent("50%");
  expect(ring.style.getPropertyValue("--ring-deg-1")).toBe("120.0deg");
  expect(ring.style.getPropertyValue("--ring-deg-2")).toBe("180.0deg");
});
