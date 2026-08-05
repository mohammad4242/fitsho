import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Profile } from "./types";

const contexts = vi.hoisted(() => ({
  auth: {
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
  profile: {
    profile: null as Profile | null,
    status: "idle" as "idle" | "loading" | "missing" | "ready" | "error",
    productMode: null,
    retryProfile: vi.fn(),
    createProfile: vi.fn(),
    updateProfile: vi.fn(),
    selectProductMode: vi.fn(),
  },
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => contexts.auth,
}));

vi.mock("./ProfileContext", () => ({
  useProfile: () => contexts.profile,
  useOptionalProfile: () => contexts.profile,
}));

import { AppRoutes } from "../../App";

const member = {
  id: "1",
  email: "member@example.com",
  created_at: "2026-07-24T00:00:00Z",
};

const readyProfile: Profile = {
  user_id: "1",
  display_name: "Mohammad",
  birth_date: "2000-05-14",
  sex: "male",
  height_cm: 178,
  current_weight_kg: 76.5,
  weight_measured_at: "2026-07-27T12:00:00Z",
  shoulder_circumference_cm: null,
  waist_circumference_cm: null,
  hip_circumference_cm: null,
  circumferences_measured_at: null,
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  training_days_per_week: 3,
  training_location: "gym",
  home_training_setup: null,
  session_duration_minutes: 60,
  physical_limitations: null,
  training_cautions: [],
  plan_duration_weeks: 4,
  created_at: "2026-07-27T12:00:00Z",
  updated_at: "2026-07-27T12:00:00Z",
};

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  contexts.auth.user = null;
  contexts.auth.loading = false;
  contexts.auth.startupError = false;
  contexts.profile.profile = null;
  contexts.profile.status = "idle";
  contexts.profile.retryProfile.mockReset();
});

describe("profile route matrix", () => {
  it.each(["/dashboard", "/onboarding"])(
    "redirects a guest from %s to login",
    async (path) => {
      renderRoute(path);

      expect(
        await screen.findByRole("heading", { name: "ادامهٔ مسیر از همین‌جا" }),
      ).toBeInTheDocument();
    },
  );

  it.each(["/dashboard", "/login"])(
    "redirects a member without a profile from %s to onboarding",
    async (path) => {
      contexts.auth.user = member;
      contexts.profile.status = "missing";
      renderRoute(path);

      expect(
        await screen.findByRole("heading", { name: "بیشتر در چه زمینه‌ای به کمک نیاز داری؟" }),
      ).toBeInTheDocument();
    },
  );

  it("shows onboarding to a member without a profile", async () => {
    contexts.auth.user = member;
    contexts.profile.status = "missing";
    renderRoute("/onboarding");

    expect(
      await screen.findByRole("heading", { name: "بیشتر در چه زمینه‌ای به کمک نیاز داری؟" }),
    ).toBeInTheDocument();
    expect(screen.getByText("پیشنهاد فیتشو")).toBeInTheDocument();
  });

  it.each(["/onboarding", "/login"])(
    "redirects a member with a profile from %s to the dashboard",
    async (path) => {
      contexts.auth.user = member;
      contexts.profile.status = "ready";
      contexts.profile.profile = readyProfile;
      renderRoute(path);

      expect(
        await screen.findByRole("heading", { name: "سلام، Mohammad" }),
      ).toBeInTheDocument();
    },
  );

  it("waits for the profile before choosing a route", () => {
    contexts.auth.user = member;
    contexts.profile.status = "loading";
    renderRoute("/dashboard");

    expect(screen.getByText("در حال آماده‌سازی فیتشو…")).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "حسابت آماده است" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "پروفایل ورزشی‌ات را بساز" }),
    ).not.toBeInTheDocument();
  });

  it("offers profile retry without redirecting after a startup error", async () => {
    contexts.auth.user = member;
    contexts.profile.status = "error";
    const user = userEvent.setup();
    renderRoute("/dashboard");

    expect(screen.getByRole("alert")).toHaveTextContent(
      "ارتباط با سرور برقرار نشد",
    );
    await user.click(screen.getByRole("button", { name: "تلاش دوباره" }));

    expect(contexts.profile.retryProfile).toHaveBeenCalledOnce();
    expect(
      screen.queryByRole("heading", { name: "پروفایل ورزشی‌ات را بساز" }),
    ).not.toBeInTheDocument();
  });
});
