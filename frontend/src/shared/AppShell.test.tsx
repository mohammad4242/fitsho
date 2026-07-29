import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";

import "../i18n";
import { AppShell } from "./AppShell";

it("provides the four primary destinations in the mobile navigation", () => {
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <AppShell>
        <p>محتوای امروز</p>
      </AppShell>
    </MemoryRouter>,
  );

  expect(screen.getByRole("link", { name: "امروز" })).toHaveAttribute(
    "href",
    "/dashboard",
  );
  expect(screen.getByRole("link", { name: "برنامه" })).toHaveAttribute(
    "href",
    "/workout-plan",
  );
  expect(screen.getByRole("link", { name: "حرکات" })).toHaveAttribute(
    "href",
    "/exercises",
  );
  expect(screen.getByRole("link", { name: "پروفایل" })).toHaveAttribute(
    "href",
    "/profile",
  );
});
