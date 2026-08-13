import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import "../i18n";

const logout = vi.fn(async () => undefined);
const auth = vi.hoisted(() => ({ isAdmin: false }));

vi.mock("../features/auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "member@example.com", created_at: "2026-08-11", is_admin: auth.isAdmin },
    logout,
  }),
}));

vi.mock("../features/profile/ProfileContext", () => ({
  useProfile: () => ({
    profile: { display_name: "محمد" },
    productMode: "both",
    status: "ready",
  }),
}));

vi.mock("../features/nutrition/api", () => ({ verifyPhysicianAccess: vi.fn(async () => { throw new Error("denied"); }) }));
vi.mock("../features/workoutReviews/api", () => ({ verifyCoachAccess: vi.fn(async () => { throw new Error("denied"); }) }));

import { MorePage } from "./MorePage";

it("signs out from the separated account action", async () => {
  auth.isAdmin = false;
  const user = userEvent.setup();
  render(<MemoryRouter><MorePage /></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "خروج از حساب" }));

  expect(logout).toHaveBeenCalledOnce();
});

it("shows the training program library in the mobile admin workspace", () => {
  auth.isAdmin = true;

  render(<MemoryRouter><MorePage /></MemoryRouter>);

  expect(screen.getByRole("link", { name: /کتابخانه برنامه‌های تمرینی/ })).toHaveAttribute(
    "href",
    "/admin/training-program-templates",
  );
});

it("shows the nutrition program catalogue in the mobile admin workspace", () => {
  auth.isAdmin = true;

  render(<MemoryRouter><MorePage /></MemoryRouter>);

  expect(screen.getByRole("link", { name: /کاتالوگ برنامه‌های غذایی/ })).toHaveAttribute(
    "href",
    "/admin/nutrition-programs",
  );
});

it("does not show a separate exercise administration workspace", () => {
  auth.isAdmin = true;

  render(<MemoryRouter><MorePage /></MemoryRouter>);

  expect(screen.queryByRole("link", { name: /مدیریت حرکات/ })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /کتابخانه حرکات/ })).toHaveAttribute("href", "/exercises");
});
