import { expect, it } from "vitest";

import { applyDesignSystem } from "./designSystem";

it("marks the document root as the Fitsho application", () => {
  const documentElement = document.createElement("html");

  applyDesignSystem(documentElement);

  expect(documentElement).toHaveClass("fitsho-app");
  expect(documentElement).toHaveAttribute("data-fitsho-theme", "dark");
});
