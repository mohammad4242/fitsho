import { act, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

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

it("keeps the default ring static and aqua-compatible", () => {
  render(<ProgressRing value={1200} max={2400} />);

  const ring = screen.getByRole("progressbar");
  expect(ring).not.toHaveClass("fitsho-progress-ring--mount-animated");
  expect(ring.style.getPropertyValue("--ring-color")).toBe("var(--fitsho-aqua)");
});

it("starts an opted-in ring at zero before the first animation frame", () => {
  let frame: FrameRequestCallback | undefined;
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    frame = callback;
    return 1;
  });
  vi.stubGlobal("cancelAnimationFrame", vi.fn());

  try {
    render(
      <ProgressRing
        animateOnMount
        color="var(--fitsho-blue)"
        value={1200}
        max={2400}
      />,
    );

    const ring = screen.getByRole("progressbar");
    expect(ring).toHaveClass("fitsho-progress-ring--mount-animated");
    expect(ring.style.getPropertyValue("--ring-progress")).toBe("0deg");
    expect(ring.style.getPropertyValue("--ring-color")).toBe("var(--fitsho-blue)");

    act(() => frame?.(0));
    expect(ring.style.getPropertyValue("--ring-progress")).toBe("180deg");
  } finally {
    vi.unstubAllGlobals();
  }
});
