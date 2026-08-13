import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { AuthShell } from "./AuthShell";

it("shows only account navigation and form content", () => {
  render(
    <AuthShell>
      <p>account form</p>
    </AuthShell>,
  );

  expect(screen.getByRole("main")).toHaveClass("auth-shell", "fitsho-page");
  expect(screen.getByRole("link", { name: "فیتشو" })).toHaveAttribute("href", "/");
  expect(screen.getByRole("button", { name: "English" })).toBeVisible();
  expect(screen.getByText("account form")).toBeVisible();
  expect(screen.queryByTestId("auth-training-accent")).not.toBeInTheDocument();
  expect(document.querySelector(".brand-panel")).not.toBeInTheDocument();
});
