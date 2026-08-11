import { expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { applyDesignSystem } from "./designSystem";

it("marks the document root as the Fitsho application", () => {
  const documentElement = document.createElement("html");

  applyDesignSystem(documentElement);

  expect(documentElement).toHaveClass("fitsho-app");
  expect(documentElement).toHaveAttribute("data-fitsho-theme", "dark");
});

it("defines the interactive authenticated surface tokens", () => {
  const tokens = readFileSync(resolve(process.cwd(), "src/styles/tokens.css"), "utf8");

  expect(tokens).toContain("--fitsho-surface-interactive");
  expect(tokens).toContain("--fitsho-shadow-focus");
  expect(tokens).toContain("--fitsho-radius-xl");
});
