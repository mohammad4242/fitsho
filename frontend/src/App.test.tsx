import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import type { ExerciseCategories, ExerciseDetail, PaginatedExercises } from "./features/exercises/types";
import { HYDRATED_ACCOUNT_KEY } from "./features/publicOnboarding/onboardingDraft";

const auth = vi.hoisted(() => ({
  value: {
    user: null as null | {
      id: string;
      email: string;
      created_at: string;
      is_admin: boolean;
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
      training_location: "gym";
      home_training_setup: null;
      session_duration_minutes: 60;
      physical_limitations: null;
      training_cautions: string[];
      plan_duration_weeks: 4;
      created_at: string;
      updated_at: string;
    },
    status: "idle" as "idle" | "loading" | "missing" | "mode_selected" | "ready" | "error",
    retryProfile: vi.fn(),
    createProfile: vi.fn(),
    updateProfile: vi.fn(),
  },
}));

const exerciseApi = vi.hoisted(() => ({
  getExerciseCategories: vi.fn(),
  getExercises: vi.fn(),
  getExercise: vi.fn(),
}));

const workoutApi = vi.hoisted(() => ({
  getActiveWorkoutPlan: vi.fn(),
  getWorkoutPlanHistory: vi.fn(),
  getWorkoutPlan: vi.fn(),
  generateWorkoutPlan: vi.fn(),
}));

const workoutReviewApi = vi.hoisted(() => ({
  verifyCoachAccess: vi.fn(),
  listWorkoutReviews: vi.fn(),
}));

const physicianApi = vi.hoisted(() => ({
  verifyPhysicianAccess: vi.fn(),
  listPhysicianReviews: vi.fn(),
}));

vi.mock("./features/auth/AuthContext", () => ({
  useAuth: () => auth.value,
}));

vi.mock("./features/profile/ProfileContext", () => ({
  useProfile: () => profile.value,
  useOptionalProfile: () => profile.value,
}));

vi.mock("./features/exercises/api", () => exerciseApi);
vi.mock("./features/workouts/api", () => workoutApi);
vi.mock("./features/workoutReviews/api", () => workoutReviewApi);
vi.mock("./features/nutrition/api", () => physicianApi);

import { AppRoutes } from "./App";

const exerciseCategories: ExerciseCategories = {
  body_regions: [
    { value: "upper_body", name_en: "Upper Body", name_fa: "بالاتنه" },
    { value: "lower_body", name_en: "Lower Body", name_fa: "پایین‌تنه" },
    { value: "core", name_en: "Core", name_fa: "میان‌تنه" },
  ],
  upper_body: [{ value: "chest", name_en: "Chest", name_fa: "سینه" }],
  lower_body: [],
  core: [],
};

const emptyExercisePage: PaginatedExercises = {
  items: [],
  page: 1,
  page_size: 12,
  total: 0,
  total_pages: 0,
};

const exerciseDetail: ExerciseDetail = {
  id: "018f0000-0000-7000-8000-000000000001",
  slug: "dumbbell-bench-press",
  name_en: "Dumbbell Bench Press",
  name_fa: "پرس سینه دمبل",
  body_region: "upper_body",
  primary_muscle: "chest",
  labels: [],
  secondary_muscles: ["triceps"],
  equipment: ["dumbbell", "bench"],
  difficulty: "intermediate",
  instructions_en: ["Press the dumbbells upward."],
  instructions_fa: ["دمبل‌ها را به بالا پرس کن."],
  safety_notes_en: ["Keep the shoulders supported."],
  safety_notes_fa: ["شانه‌ها را ثابت نگه دار."],
  media_path: "/exercises/upper-body/chest/dumbbell-bench-press.gif",
  media_type: "gif",
  media_source_url: null,
  media_license: "Project owner supplied and authorized",
  media_attribution: "Provided by Fitsho project owner",
};

beforeEach(() => {
  sessionStorage.clear();
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
  exerciseApi.getExerciseCategories.mockReset();
  exerciseApi.getExercises.mockReset();
  exerciseApi.getExercise.mockReset();
  workoutApi.getActiveWorkoutPlan.mockReset();
  workoutApi.getWorkoutPlanHistory.mockReset();
  workoutApi.getWorkoutPlan.mockReset();
  workoutApi.generateWorkoutPlan.mockReset();
  workoutReviewApi.verifyCoachAccess.mockReset();
  workoutReviewApi.verifyCoachAccess.mockRejectedValue(new Error("not a coach"));
  workoutReviewApi.listWorkoutReviews.mockReset();
  workoutReviewApi.listWorkoutReviews.mockResolvedValue([]);
  physicianApi.verifyPhysicianAccess.mockReset();
  physicianApi.verifyPhysicianAccess.mockRejectedValue(new Error("not a physician"));
  physicianApi.listPhysicianReviews.mockReset();
  physicianApi.listPhysicianReviews.mockResolvedValue([]);
  exerciseApi.getExerciseCategories.mockResolvedValue(exerciseCategories);
  exerciseApi.getExercises.mockResolvedValue(emptyExercisePage);
  exerciseApi.getExercise.mockResolvedValue(exerciseDetail);
  workoutApi.getActiveWorkoutPlan.mockImplementation(() => new Promise(() => {}));
  workoutApi.getWorkoutPlanHistory.mockResolvedValue([]);
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

it("keeps password recovery routes in the guest auth shell", async () => {
  renderRoute("/forgot-password");
  expect(
    await screen.findByRole("heading", { name: "بازیابی رمز عبور" }),
  ).toBeInTheDocument();

  renderRoute("/reset-password?token=raw-token");
  expect(
    await screen.findByRole("heading", { name: "انتخاب رمز عبور جدید" }),
  ).toBeInTheDocument();
});

it("shows an accessible loading state while a route chunk loads", async () => {
  renderRoute("/");

  expect(screen.getByRole("status")).toHaveTextContent("در حال آماده‌سازی فیتشو…");
  expect(await screen.findByRole("heading", { name: "هر بدن، برنامه خودش را می‌خواهد." })).toBeInTheDocument();
});

it("shows the public landing to a guest at the root route", () => {
  renderRoute("/");

  expect(screen.getAllByRole("link", { name: "برنامه من را بساز" })[0]).toHaveAttribute("href", "/get-started");
});

it("redirects a signed-in root visitor to Today", async () => {
  setReadyMember();
  renderRoute("/");

  expect(await screen.findByRole("heading", { name: "سلام، Mohammad" })).toBeInTheDocument();
});

it("opens the dashboard after sign-in and keeps profile completion in the account menu", async () => {
  const user = userEvent.setup();
  auth.value.user = member;
  profile.value.status = "mode_selected";
  profile.value.profile = null;
  renderRoute("/dashboard");

  expect(await screen.findByRole("heading", { name: "سلام، دوست" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "بیشتر در چه زمینه‌ای به کمک نیاز داری؟" })).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "باز کردن منوی حساب" }));

  const accountMenu = screen.getByRole("navigation", { name: "منوی حساب" });
  expect(accountMenu.closest("header")).toHaveClass("dashboard-header--menu-open");
  const productGroup = within(accountMenu).getByRole("group", { name: "محصول" });
  const accountGroup = within(accountMenu).getByRole("group", { name: "حساب" });
  const socialGroup = within(accountMenu).getByRole("group", { name: "شبکه‌های اجتماعی" });
  expect(accountMenu.querySelector('[href="/onboarding"]')).toHaveTextContent("تکمیل پروفایل");
  expect(within(productGroup).getByRole("link", { name: "حرکات" })).toHaveAttribute("href", "/exercises");
  expect(within(accountGroup).getByRole("link", { name: "تکمیل پروفایل" })).toHaveAttribute("href", "/onboarding");
  expect(within(socialGroup).getAllByRole("link")).toHaveLength(4);
  expect(screen.getByRole("button", { name: /مقالات روز دنیا/ })).toBeDisabled();
});

it("keeps the desktop account navigation to four primary destinations", async () => {
  auth.value.user = member;
  profile.value.status = "ready";
  renderRoute("/dashboard");

  const navigation = await screen.findByRole("navigation", { name: "ناوبری حساب" });
  expect(within(navigation).getAllByRole("link")).toHaveLength(4);
});

it("keeps a newly hydrated member on the dashboard while profile status refreshes", async () => {
  sessionStorage.setItem(HYDRATED_ACCOUNT_KEY, "true");
  auth.value.user = member;
  profile.value.status = "missing";
  profile.value.profile = null;
  renderRoute("/dashboard");

  expect(await screen.findByRole("heading", { name: "سلام، دوست" })).toBeInTheDocument();
});

it("logs a signed-in user out from Today", async () => {
  auth.value.user = {
    id: "1",
    email: "member@example.com",
    created_at: "2026-07-24T00:00:00Z",
    is_admin: false,
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
    training_location: "gym",
    home_training_setup: null,
    session_duration_minutes: 60,
    physical_limitations: null,
  training_cautions: [],
  plan_duration_weeks: 4,
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

  expect(screen.getByRole("heading", { name: "تمرین امروز" })).toBeInTheDocument();
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
    is_admin: false,
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
    training_location: "gym",
    home_training_setup: null,
    session_duration_minutes: 60,
    physical_limitations: null,
  training_cautions: [],
  plan_duration_weeks: 4,
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

it("redirects the legacy nutrition profile route into the unified profile flow", async () => {
  setReadyMember();
  renderRoute("/nutrition-profile");

  expect(await screen.findByRole("heading", { name: "اطلاعات شخصی" })).toBeInTheDocument();
});

it.each(["/exercises", "/exercises/dumbbell-bench-press", "/workout-plan"])(
  "redirects a guest from %s to login",
  async (path) => {
    renderRoute(path);

    expect(
      await screen.findByRole("heading", { name: "ادامهٔ مسیر از همین‌جا" }),
    ).toBeInTheDocument();
  },
);

it.each(["/exercises", "/exercises/dumbbell-bench-press", "/workout-plan"])(
  "redirects a member without a profile from %s to onboarding",
  async (path) => {
    auth.value.user = member;
    profile.value.status = "missing";
    renderRoute(path);

    expect(
      await screen.findByRole("heading", {
        name: "بیشتر در چه زمینه‌ای به کمک نیاز داری؟",
      }),
    ).toBeInTheDocument();
  },
);

it("renders the catalog route for a ready member", async () => {
  setReadyMember();
  renderRoute("/exercises");

  expect(
    await screen.findByRole("heading", { name: "کتابخانه حرکات" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("navigation", { name: "ناوبری اصلی" }).querySelector('[href="/workout-plan"]'),
  ).toHaveAttribute(
    "aria-current",
    "page",
  );
});

it("renders detail with active exercise navigation for a ready member", async () => {
  setReadyMember();
  renderRoute("/exercises/dumbbell-bench-press");

  expect(
    await screen.findByRole("heading", { name: "پرس سینه دمبل" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("navigation", { name: "ناوبری اصلی" }).querySelector('[href="/workout-plan"]'),
  ).toHaveAttribute(
    "aria-current",
    "page",
  );
});

it("links the dashboard body analysis shortcut to the existing flow", async () => {
  setReadyMember();
  renderRoute("/dashboard");

  expect(
    screen.getByRole("navigation", { name: "دسترسی سریع" }).querySelector('[href="/body-progress"]'),
  ).toHaveAttribute("href", "/body-progress");
});

it("hides admin navigation from regular members", async () => {
  setReadyMember();
  renderRoute("/dashboard");

  expect(screen.queryByRole("link", { name: "مدیریت حرکات" })).not.toBeInTheDocument();
});

it("shows the nutrition program catalogue in the administrator account menu", async () => {
  auth.value.user = { ...member, is_admin: true };
  profile.value.status = "ready";
  const user = userEvent.setup();
  renderRoute("/dashboard");

  await user.click(screen.getByRole("button", { name: "باز کردن منوی حساب" }));

  const accountMenu = screen.getByRole("navigation", { name: "منوی حساب" });
  const adminGroup = within(accountMenu).getByRole("group", { name: "مدیریت" });
  expect(
    within(adminGroup).getByRole("link", { name: "کاتالوگ برنامه‌های غذایی" }),
  ).toHaveAttribute("href", "/admin/nutrition-programs");
});

it("shows the workout review workspace in the account menu for coaches", async () => {
  workoutReviewApi.verifyCoachAccess.mockResolvedValue({ authorized: true });
  setReadyMember();
  const user = userEvent.setup();
  renderRoute("/dashboard");

  await user.click(screen.getByRole("button", { name: "باز کردن منوی حساب" }));

  const coachLinks = await screen.findAllByRole("link", { name: "پنل مربی" });
  expect(coachLinks).not.toHaveLength(0);
  expect(coachLinks[0]).toHaveAttribute("href", "/coach/workouts");
});

it("shows the physician workspace only for physicians", async () => {
  physicianApi.verifyPhysicianAccess.mockResolvedValue({ authorized: true });
  setReadyMember();
  const user = userEvent.setup();
  renderRoute("/dashboard");

  await user.click(screen.getByRole("button", { name: "باز کردن منوی حساب" }));

  const physicianLinks = await screen.findAllByRole("link", { name: "پنل پزشک" });
  expect(physicianLinks).not.toHaveLength(0);
  expect(physicianLinks[0]).toHaveAttribute("href", "/physician/nutrition");
});

it("redirects a guest away from the admin route", async () => {
  renderRoute("/admin/exercises");

  expect(
    await screen.findByRole("heading", { name: "ادامهٔ مسیر از همین‌جا" }),
  ).toBeInTheDocument();
});

it("redirects a non-admin away from the admin route", async () => {
  setReadyMember();
  renderRoute("/admin/exercises");

  expect(await screen.findByRole("heading", { name: "سلام، Mohammad" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "مدیریت حرکات" })).not.toBeInTheDocument();
});

it("opens the authenticated More hub", async () => {
  setReadyMember();
  renderRoute("/more");

  expect(await screen.findByRole("heading", { name: "بیشتر" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "پروفایل" })).toHaveAttribute("href", "/profile");
});

it("redirects the obsolete admin exercise browser to the shared library", async () => {
  auth.value.user = { ...member, is_admin: true };
  profile.value.status = "missing";
  renderRoute("/admin/exercises");

  expect(
    await screen.findByRole("heading", { name: "کتابخانه حرکات" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "مدیریت حرکات" })).not.toBeInTheDocument();
});

it("lets an admin open the nutrition program catalogue route", async () => {
  auth.value.user = { ...member, is_admin: true };
  profile.value.status = "missing";
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({
      items: [],
      diet_styles: ["economy", "balanced_iranian", "high_protein_gym", "quick_easy", "premium_varied"],
    }), { status: 200, headers: { "Content-Type": "application/json" } }),
  );

  renderRoute("/admin/nutrition-programs");

  expect(
    await screen.findByRole("heading", { name: "کاتالوگ برنامه‌های غذایی" }),
  ).toBeInTheDocument();
  fetchMock.mockRestore();
});

const member = {
  id: "1",
  email: "member@example.com",
  created_at: "2026-07-24T00:00:00Z",
  is_admin: false,
};

function setReadyMember() {
  auth.value.user = member;
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
    training_location: "gym",
    home_training_setup: null,
    session_duration_minutes: 60,
    physical_limitations: null,
  training_cautions: [],
  plan_duration_weeks: 4,
    created_at: "2026-07-27T12:00:00Z",
    updated_at: "2026-07-27T12:00:00Z",
  };
}

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}
