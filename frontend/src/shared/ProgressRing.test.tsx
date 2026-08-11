import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { ProgressRing } from "./ProgressRing";

it("exposes the real value and target as an accessible progress indicator", () => {
  render(<ProgressRing value={1200} max={2400} label="Daily calories" />);

  const ring = screen.getByRole("progressbar", { name: "Daily calories" });
  expect(ring).toHaveAttribute("aria-valuenow", "1200");
  expect(ring).toHaveAttribute("aria-valuemax", "2400");
  expect(ring).toHaveTextContent("50%");
});

it("clamps the visual percentage without changing the reported real value", () => {
  render(<ProgressRing value={2800} max={2400} />);

  const ring = screen.getByRole("progressbar");
  expect(ring).toHaveAttribute("aria-valuenow", "2800");
  expect(ring).toHaveTextContent("100%");
});
