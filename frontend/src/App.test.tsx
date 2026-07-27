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
    profile: null as null | {
      user_id: string;
      display_name: string;
      birth_date: string;
      sex: "male";
      height_cm: number;
      current_weight_kg: number;
      weight_measured_at: string;
      fitness_goal: "build_muscle";
      experience_level: "beginner";
      training_days_per_week: number;
      physical_limitations: null;
      created_at: string;
      updated_at: string;
    },
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
  profile.value.profile = null;
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
  profile.value.profile = {
    user_id: "1",
    display_name: "Mohammad",
    birth_date: "2000-05-14",
    sex: "male",
    height_cm: 178,
    current_weight_kg: 76.5,
    weight_measured_at: "2026-07-27T12:00:00Z",
    fitness_goal: "build_muscle",
    experience_level: "beginner",
    training_days_per_week: 3,
    physical_limitations: null,
    created_at: "2026-07-27T12:00:00Z",
    updated_at: "2026-07-27T12:00:00Z",
  };
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
  expect(
    screen.getByRole("link", { name: /ویرایش پروفایل/ }),
  ).toHaveAttribute("href", "/profile");
  await user.click(screen.getByRole("button", { name: "خروج" }));

  expect(auth.value.logout).toHaveBeenCalledOnce();
  expect(
    await screen.findByRole("heading", { name: "ادامهٔ مسیر از همین‌جا" }),
  ).toBeInTheDocument();
});

it("renders the protected profile route for a member with a profile", async () => {
  auth.value.user = {
    id: "1",
    email: "member@example.com",
    created_at: "2026-07-24T00:00:00Z",
  };
  profile.value.status = "ready";
  profile.value.profile = {
    user_id: "1",
    display_name: "Mohammad",
    birth_date: "2000-05-14",
    sex: "male",
    height_cm: 178,
    current_weight_kg: 76.5,
    weight_measured_at: "2026-07-27T12:00:00Z",
    fitness_goal: "build_muscle",
    experience_level: "beginner",
    training_days_per_week: 3,
    physical_limitations: null,
    created_at: "2026-07-27T12:00:00Z",
    updated_at: "2026-07-27T12:00:00Z",
  };

  render(
    <MemoryRouter initialEntries={["/profile"]}>
      <AppRoutes />
    </MemoryRouter>,
  );

  expect(
    await screen.findByRole("heading", { name: "پروفایل ورزشی" }),
  ).toBeInTheDocument();
});
