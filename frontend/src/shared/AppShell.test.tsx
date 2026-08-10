import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import "../i18n";
import * as profileContextModule from "../features/profile/ProfileContext";
import { AppShell } from "./AppShell";

afterEach(() => vi.restoreAllMocks());

it("moves secondary combined-mode destinations behind More", async () => {
  const user = userEvent.setup();

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
  expect(screen.getByRole("link", { name: "تغذیه" })).toHaveAttribute(
    "href",
    "/nutrition-estimate",
  );
  expect(screen.queryByRole("link", { name: "کاتالوگ مواد غذایی" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "پروفایل" })).not.toBeInTheDocument();

  const moreButton = screen.getByRole("button", { name: "بیشتر" });
  expect(moreButton).toHaveAttribute("aria-expanded", "false");
  await user.click(moreButton);

  expect(moreButton).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("link", { name: "کاتالوگ مواد غذایی" })).toHaveAttribute(
    "href",
    "/food-catalogue",
  );
  expect(screen.getByRole("link", { name: "پروفایل" })).toHaveAttribute(
    "href",
    "/profile",
  );
});

it.each([
  ["nutrition", ["امروز", "تغذیه", "کاتالوگ مواد غذایی", "پروفایل"], "برنامه"],
] as const)("shows direct links without More for %s mode", (productMode, visibleLabels, hiddenLabel) => {
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
  expect(screen.queryByRole("link", { name: hiddenLabel })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "بیشتر" })).not.toBeInTheDocument();
});

it("keeps body progress in the compact More menu for training members", async () => {
  const user = userEvent.setup();
  vi.spyOn(profileContextModule, "useOptionalProfile").mockReturnValue({
    profile: null,
    status: "ready",
    productMode: "training",
    retryProfile: vi.fn(),
    createProfile: vi.fn(async () => { throw new Error("not used"); }),
    selectProductMode: vi.fn(async () => { throw new Error("not used"); }),
    updateProfile: vi.fn(async () => { throw new Error("not used"); }),
  });

  render(<MemoryRouter initialEntries={["/dashboard"]}><AppShell><p>محتوا</p></AppShell></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "بیشتر" }));
  expect(screen.getByRole("link", { name: "پیشرفت بدن" })).toHaveAttribute("href", "/body-progress");
  expect(screen.getByRole("link", { name: "پروفایل" })).toHaveAttribute("href", "/profile");
});
