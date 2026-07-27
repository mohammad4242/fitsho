import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  value: {
    user: null as null | {
      id: string;
      email: string;
      created_at: string;
    },
    loading: false,
    startupError: false,
    retryStartup: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  },
}));

const profile = vi.hoisted(() => ({
  value: {
    profile: null,
    status: "idle" as "idle" | "loading" | "missing" | "ready" | "error",
    retryProfile: vi.fn(),
    createProfile: vi.fn(),
    updateProfile: vi.fn(),
  },
}));

vi.mock("./features/auth/AuthContext", () => ({
  useAuth: () => auth.value,
}));

vi.mock("./features/profile/ProfileContext", () => ({
  useProfile: () => profile.value,
}));

import { AppRoutes } from "./App";

beforeEach(() => {
  auth.value.user = null;
  auth.value.loading = false;
  auth.value.startupError = false;
  auth.value.retryStartup.mockReset();
  auth.value.login.mockReset();
  auth.value.register.mockReset();
  auth.value.logout.mockReset();
  profile.value.status = "idle";
  profile.value.retryProfile.mockReset();
});

it("shows a retry action when the initial session check is unavailable", async () => {
  auth.value.startupError = true;
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <AppRoutes />
    </MemoryRouter>,
  );

  expect(screen.getByRole("alert")).toHaveTextContent(
    "ارتباط با سرور برقرار نشد",
  );
  await user.click(screen.getByRole("button", { name: "تلاش دوباره" }));

  expect(auth.value.retryStartup).toHaveBeenCalledOnce();
});

it("redirects a guest away from the protected dashboard", async () => {
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <AppRoutes />
    </MemoryRouter>,
  );

  expect(
    await screen.findByRole("heading", { name: "ادامهٔ مسیر از همین‌جا" }),
  ).toBeInTheDocument();
});

it("shows the real account and logs the user out", async () => {
  auth.value.user = {
    id: "1",
    email: "member@example.com",
    created_at: "2026-07-24T00:00:00Z",
  };
  profile.value.status = "ready";
  auth.value.logout.mockImplementation(async () => {
    auth.value.user = null;
  });
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <AppRoutes />
    </MemoryRouter>,
  );

  expect(screen.getByText("member@example.com")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "خروج" }));

  expect(auth.value.logout).toHaveBeenCalledOnce();
  expect(
    await screen.findByRole("heading", { name: "ادامهٔ مسیر از همین‌جا" }),
  ).toBeInTheDocument();
});
