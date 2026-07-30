import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import type { Profile } from "./types";

const context = vi.hoisted(() => ({
  profile: null as Profile | null,
  updateProfile: vi.fn(),
  logout: vi.fn(),
}));

vi.mock("./ProfileContext", () => ({
  useProfile: () => ({
    profile: context.profile,
    status: "ready",
    retryProfile: vi.fn(),
    createProfile: vi.fn(),
    updateProfile: context.updateProfile,
  }),
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: "018f0000-0000-7000-8000-000000000001",
      email: "member@example.com",
      created_at: "2026-07-24T00:00:00Z",
    },
    loading: false,
    startupError: false,
    retryStartup: vi.fn(),
    register: vi.fn(),
    login: vi.fn(),
    logout: context.logout,
  }),
}));

import { ProfilePage } from "./ProfilePage";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";

const savedProfile: Profile = {
  user_id: "018f0000-0000-7000-8000-000000000001",
  display_name: "Mohammad",
  birth_date: "2000-05-14",
  sex: "male",
  height_cm: 178,
  current_weight_kg: 76.5,
  weight_measured_at: "2026-07-27T12:00:00Z",
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  training_days_per_week: 3,
  training_location: "home",
  home_training_setup: "dumbbells_available",
  session_duration_minutes: 75,
  physical_limitations: "Knee pain",
  training_cautions: ["knee"],
  plan_duration_weeks: 6,
  created_at: "2026-07-27T12:00:00Z",
  updated_at: "2026-07-27T12:00:00Z",
};

function Destination() {
  const location = useLocation();
  return <h1>{`destination:${location.pathname}`}</h1>;
}

function renderProfilePage(initialEntry = "/profile") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/profile" element={<ProfilePage />} />
        <Route
          path="/dashboard"
          element={
            <>
              <AuthenticatedHeader />
              <Destination />
            </>
          }
        />
        <Route path="/login" element={<Destination />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(async () => {
  vi.clearAllMocks();
  context.profile = savedProfile;
  await i18n.changeLanguage("fa");
});

it("renders every saved profile value in editable controls", () => {
  renderProfilePage();

  expect(screen.getByLabelText("نام نمایشی")).toHaveValue("Mohammad");
  expect(screen.getByLabelText("تاریخ تولد")).toHaveValue("2000-05-14");
  expect(screen.getByLabelText("جنسیت")).toHaveValue("male");
  expect(screen.getByLabelText("قد (سانتی‌متر)")).toHaveValue(178);
  expect(screen.getByLabelText("وزن فعلی (کیلوگرم)")).toHaveValue(76.5);
  expect(screen.getByLabelText("هدف ورزشی")).toHaveValue("build_muscle");
  expect(screen.getByLabelText("سطح تجربه")).toHaveValue("beginner");
  expect(screen.getByLabelText("روزهای تمرین در هفته")).toHaveValue(3);
  expect(screen.getByLabelText("کجا تمرین می‌کنی؟")).toHaveValue("home");
  expect(
    screen.getByLabelText("برای تمرین در خانه چه امکاناتی داری؟"),
  ).toHaveValue("dumbbells_available");
  expect(screen.getByLabelText("معمولاً برای هر جلسه چقدر زمان داری؟")).toHaveValue(
    "75",
  );
  expect(screen.getByLabelText("محدودیت‌های جسمی (اختیاری)")).toHaveValue(
    "Knee pain",
  );
});

it("uses the supplied training still in the profile header", () => {
  renderProfilePage();

  const background = screen.getByTestId("member-header-image");
  expect(background).toHaveAttribute(
    "src",
    expect.stringContaining("auth-training-accent"),
  );
  expect(background.parentElement).toHaveClass("member-page-background");
});

it("shows the latest measured weight and localized measurement time", () => {
  renderProfilePage();
  const locale = "fa-IR";
  const expectedWeight = new Intl.NumberFormat(locale, {
    maximumFractionDigits: 2,
  }).format(savedProfile.current_weight_kg);
  const expectedDate = new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(savedProfile.weight_measured_at));

  expect(screen.getByText(`${expectedWeight} کیلوگرم`)).toBeInTheDocument();
  expect(screen.getByText(`ثبت‌شده در ${expectedDate}`)).toBeInTheDocument();
});

it("skips profile update when no values changed", async () => {
  const user = userEvent.setup();
  renderProfilePage();

  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(context.updateProfile).not.toHaveBeenCalled();
  expect(screen.getByRole("status")).toHaveTextContent("تغییری برای ذخیره نیست");
});

it("sends only a changed display name", async () => {
  context.updateProfile.mockResolvedValue({
    ...savedProfile,
    display_name: "New Name",
  });
  const user = userEvent.setup();
  renderProfilePage();

  await user.clear(screen.getByLabelText("نام نمایشی"));
  await user.type(screen.getByLabelText("نام نمایشی"), "New Name");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  await waitFor(() =>
    expect(context.updateProfile).toHaveBeenCalledWith({
      display_name: "New Name",
    }),
  );
});

it("sends only a changed current weight", async () => {
  context.updateProfile.mockResolvedValue({
    ...savedProfile,
    current_weight_kg: 75.25,
    weight_measured_at: "2026-07-28T12:00:00Z",
  });
  const user = userEvent.setup();
  renderProfilePage();

  await user.clear(screen.getByLabelText("وزن فعلی (کیلوگرم)"));
  await user.type(screen.getByLabelText("وزن فعلی (کیلوگرم)"), "75.25");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  await waitFor(() =>
    expect(context.updateProfile).toHaveBeenCalledWith({
      current_weight_kg: 75.25,
    }),
  );
});

it("sends null when physical limitations are cleared", async () => {
  context.updateProfile.mockResolvedValue({
    ...savedProfile,
    physical_limitations: null,
  });
  const user = userEvent.setup();
  renderProfilePage();

  await user.clear(screen.getByLabelText("محدودیت‌های جسمی (اختیاری)"));
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  await waitFor(() =>
    expect(context.updateProfile).toHaveBeenCalledWith({
      physical_limitations: null,
    }),
  );
});

it("clears home setup and serializes the workout preference edit", async () => {
  context.updateProfile.mockResolvedValue({
    ...savedProfile,
    training_location: "gym",
    home_training_setup: null,
    session_duration_minutes: 90,
  });
  const user = userEvent.setup();
  renderProfilePage();

  await user.selectOptions(screen.getByLabelText("کجا تمرین می‌کنی؟"), "gym");
  expect(
    screen.queryByLabelText("برای تمرین در خانه چه امکاناتی داری؟"),
  ).not.toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("معمولاً برای هر جلسه چقدر زمان داری؟"), "90");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  await waitFor(() =>
    expect(context.updateProfile).toHaveBeenCalledWith({
      training_location: "gym",
      home_training_setup: null,
      session_duration_minutes: 90,
    }),
  );
});

it("focuses the first invalid edit and skips profile update", async () => {
  const user = userEvent.setup();
  renderProfilePage();

  await user.clear(screen.getByLabelText("نام نمایشی"));
  await user.clear(screen.getByLabelText("قد (سانتی‌متر)"));
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(screen.getByLabelText("نام نمایشی")).toHaveFocus();
  expect(context.updateProfile).not.toHaveBeenCalled();
});

it("shows success from the returned profile and resets the patch baseline", async () => {
  context.updateProfile.mockResolvedValue({
    ...savedProfile,
    display_name: "New Name",
  });
  const user = userEvent.setup();
  renderProfilePage();

  await user.clear(screen.getByLabelText("نام نمایشی"));
  await user.type(screen.getByLabelText("نام نمایشی"), "New Name");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(await screen.findByRole("status")).toHaveTextContent(
    "پروفایل New Name ذخیره شد",
  );
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));
  expect(context.updateProfile).toHaveBeenCalledOnce();
});

it("keeps edited values and shows an alert when profile update fails", async () => {
  context.updateProfile.mockRejectedValue(new Error("offline"));
  const user = userEvent.setup();
  renderProfilePage();

  await user.clear(screen.getByLabelText("نام نمایشی"));
  await user.type(screen.getByLabelText("نام نمایشی"), "Offline Name");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "تغییرات ذخیره نشد",
  );
  expect(screen.getByLabelText("نام نمایشی")).toHaveValue("Offline Name");
});

it("navigates from the profile header to dashboard", async () => {
  const user = userEvent.setup();
  renderProfilePage();

  await user.click(screen.getByRole("link", { name: "امروز" }));

  expect(
    screen.getByRole("heading", { name: "destination:/dashboard" }),
  ).toBeInTheDocument();
});

it("navigates from the dashboard header to profile", async () => {
  const user = userEvent.setup();
  renderProfilePage("/dashboard");

  await user.click(screen.getByRole("link", { name: "پروفایل" }));

  expect(
    screen.getByRole("heading", { name: "پروفایل ورزشی" }),
  ).toBeInTheDocument();
});

it("logs out and replaces the current route with login", async () => {
  context.logout.mockResolvedValue(undefined);
  const user = userEvent.setup();
  renderProfilePage();

  await user.click(screen.getByRole("button", { name: "خروج" }));

  expect(context.logout).toHaveBeenCalledOnce();
  expect(
    await screen.findByRole("heading", { name: "destination:/login" }),
  ).toBeInTheDocument();
});

it("disables logout while the request is pending", async () => {
  context.logout.mockReturnValue(new Promise(() => undefined));
  const user = userEvent.setup();
  renderProfilePage();

  await user.click(screen.getByRole("button", { name: "خروج" }));

  expect(
    await screen.findByRole("button", { name: "در حال خروج…" }),
  ).toBeDisabled();
});

it("keeps the authenticated page and shows an alert when logout fails", async () => {
  context.logout.mockRejectedValue(new Error("offline"));
  const user = userEvent.setup();
  renderProfilePage();

  await user.click(screen.getByRole("button", { name: "خروج" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "درخواست انجام نشد",
  );
  expect(screen.getByRole("heading", { name: "پروفایل ورزشی" })).toBeInTheDocument();
});
