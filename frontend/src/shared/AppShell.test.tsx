import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import "../i18n";
import * as profileContextModule from "../features/profile/ProfileContext";
import { AppShell } from "./AppShell";

vi.mock("./AuthenticatedHeader", () => ({
  AuthenticatedHeader: () => <header>member header</header>,
}));

afterEach(() => vi.restoreAllMocks());

it("shows the five primary combined-mode destinations", () => {
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <AppShell>
        <p>محتوای امروز</p>
      </AppShell>
    </MemoryRouter>,
  );

  expect(screen.getByRole("banner")).toHaveTextContent("member header");
  expect(screen.getByRole("link", { name: "امروز" })).toHaveAttribute(
    "href",
    "/dashboard",
  );
  const workoutLink = screen.getByRole("link", { name: "تمرین" });
  expect(workoutLink).toHaveAttribute(
    "href",
    "/workout-plan",
  );
  expect(workoutLink.querySelector("svg")).toHaveClass("app-shell__nav-icon--workout");
  expect(screen.getByRole("link", { name: "تغذیه" })).toHaveAttribute(
    "href",
    "/nutrition-estimate",
  );
  expect(screen.getByRole("link", { name: "Body Analysis" })).toHaveAttribute(
    "href",
    "/body-progress",
  );
  expect(screen.getByRole("link", { name: "بیشتر" })).toHaveAttribute("href", "/more");
});

it.each([
  ["nutrition", ["امروز", "تغذیه", "بیشتر"], ["تمرین", "Body Analysis"]],
  ["training", ["امروز", "تمرین", "Body Analysis", "بیشتر"], ["تغذیه"]],
] as const)("shows capability-aware links for %s mode", (productMode, visibleLabels, hiddenLabels) => {
  vi.spyOn(profileContextModule, "useOptionalProfile").mockReturnValue({
    profile: null,
    status: "ready",
    productMode,
    retryProfile: vi.fn(),
    createProfile: vi.fn(async () => { throw new Error("not used"); }),
    selectProductMode: vi.fn(async () => { throw new Error("not used"); }),
    updateProfile: vi.fn(async () => { throw new Error("not used"); }),
  });

  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <AppShell>
        <p>محتوای امروز</p>
      </AppShell>
    </MemoryRouter>,
  );

  for (const label of visibleLabels) {
    expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
  }
  for (const label of hiddenLabels) {
    expect(screen.queryByRole("link", { name: label })).not.toBeInTheDocument();
  }
});

it.each([
  ["/exercises", "تمرین"],
  ["/nutrition-tracking", "تغذیه"],
  ["/food-catalogue", "تغذیه"],
  ["/profile", "بیشتر"],
] as const)("keeps the related primary destination active on %s", (pathname, label) => {
  render(
    <MemoryRouter initialEntries={[pathname]}>
      <AppShell><p>content</p></AppShell>
    </MemoryRouter>,
  );

  expect(screen.getByRole("link", { name: label })).toHaveAttribute("aria-current", "page");
});
