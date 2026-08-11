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
import type { ProductMode, Profile, SharedProfile } from "./types";

const context = vi.hoisted(() => ({
  profile: null as Profile | null,
  productMode: "both" as ProductMode,
  updateProfile: vi.fn(),
}));

const profileApi = vi.hoisted(() => ({
  getSharedProfile: vi.fn(),
  saveSharedProfile: vi.fn(),
}));

vi.mock("./api", () => profileApi);
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ user: { email: "member@example.com" } }) }));

vi.mock("../nutrition/NutritionOnboardingFlow", () => ({
  NutritionOnboardingFlow: ({ onBack }: { onBack?: () => void }) => (
    <section aria-label="اطلاعات تغذیه‌ای">
      <h2>اطلاعات تغذیه‌ای</h2>
      <p>فرم یکپارچه تغذیه</p>
      <button type="button" onClick={onBack}>بازگشت</button>
    </section>
  ),
}));

vi.mock("./ProfileContext", () => ({
  useProfile: () => ({
    profile: context.profile,
    productMode: context.productMode,
    status: "ready",
    retryProfile: vi.fn(),
    createProfile: vi.fn(),
    updateProfile: context.updateProfile,
  }),
  useOptionalProfile: () => ({
    status: "ready",
  }),
}));

import { ProfilePage } from "./ProfilePage";

const savedProfile: Profile = {
  user_id: "018f0000-0000-7000-8000-000000000001",
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
  training_location: "home",
  home_training_setup: "dumbbells_available",
  session_duration_minutes: 75,
  physical_limitations: "Knee pain",
  training_cautions: ["knee"],
  plan_duration_weeks: 6,
  created_at: "2026-07-27T12:00:00Z",
  updated_at: "2026-07-27T12:00:00Z",
};

const savedSharedProfile: SharedProfile = {
  user_id: savedProfile.user_id,
  product_mode: "nutrition",
  display_name: savedProfile.display_name,
  birth_date: savedProfile.birth_date,
  sex: savedProfile.sex,
  height_cm: savedProfile.height_cm,
  current_weight_kg: savedProfile.current_weight_kg,
  fitness_goal: savedProfile.fitness_goal,
  weight_measured_at: savedProfile.weight_measured_at,
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
        <Route path="/dashboard" element={<Destination />} />
        <Route path="/login" element={<Destination />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function openTrainingPage(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "بعدی" }));
  expect(screen.getByRole("heading", { name: "اطلاعات تمرینی" })).toBeInTheDocument();
}

beforeEach(async () => {
  vi.clearAllMocks();
  context.profile = savedProfile;
  context.productMode = "both";
  profileApi.getSharedProfile.mockResolvedValue(savedSharedProfile);
  profileApi.saveSharedProfile.mockResolvedValue(savedSharedProfile);
  await i18n.changeLanguage("fa");
});

it("shows signed-in profile information as three ordered full pages", async () => {
  const user = userEvent.setup();
  renderProfilePage();

  expect(screen.getByRole("heading", { name: "اطلاعات شخصی" })).toBeInTheDocument();
  expect(screen.getByRole("form", { name: "اطلاعات شخصی" })).toBeInTheDocument();
  expect(screen.getByText("مرحله ۱ از ۳")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "بعدی" }));
  expect(screen.getByRole("heading", { name: "اطلاعات تمرینی" })).toBeInTheDocument();
  expect(screen.getByText("مرحله ۲ از ۳")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "بعدی" }));
  expect(screen.getByRole("heading", { name: "اطلاعات تغذیه‌ای" })).toBeInTheDocument();
  expect(screen.getByText("مرحله ۳ از ۳")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "بازگشت" }));
  expect(screen.getByRole("heading", { name: "اطلاعات تمرینی" })).toBeInTheDocument();
});

it("leads with a compact real-data account summary and edit action", () => {
  renderProfilePage();

  const summary = screen.getByRole("region", { name: "خلاصه پروفایل" });
  expect(summary).toHaveTextContent("Mohammad");
  expect(summary).toHaveTextContent("۱۷۸");
  expect(summary).toHaveTextContent("۷۶٫۵");
  expect(screen.getByRole("link", { name: "ویرایش پروفایل" })).toHaveAttribute("href", "#profile-editor");
});

it("returns from the first profile page to the dashboard", async () => {
  const user = userEvent.setup();
  renderProfilePage();

  await user.click(screen.getByRole("button", { name: "بازگشت" }));

  expect(screen.getByRole("heading", { name: "destination:/dashboard" })).toBeInTheDocument();
});

it("keeps training optional for nutrition-only members and continues to nutrition", async () => {
  context.profile = null;
  context.productMode = "nutrition";
  const user = userEvent.setup();
  renderProfilePage();

  expect(await screen.findByRole("heading", { name: "اطلاعات شخصی" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "بعدی" }));

  expect(screen.getByRole("heading", { name: "اطلاعات تمرینی" })).toBeInTheDocument();
  expect(screen.getByText("این بخش برای مسیر تغذیه اختیاری است.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "بعدی" }));

  expect(screen.getByRole("heading", { name: "اطلاعات تغذیه‌ای" })).toBeInTheDocument();
});

it("uses English labels and left-to-right layout for every signed-in profile page", async () => {
  await i18n.changeLanguage("en");
  const user = userEvent.setup();
  renderProfilePage();

  const heading = screen.getByRole("heading", { name: "Personal information" });
  expect(heading.closest(".profile-page-shell")).toHaveAttribute("dir", "ltr");
  expect(screen.getByText("Step 1 of 3")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByRole("heading", { name: "Training information" })).toBeInTheDocument();
  expect(screen.getByText("Step 2 of 3")).toBeInTheDocument();
});

it("renders every saved profile value in its editable profile page", async () => {
  const user = userEvent.setup();
  renderProfilePage();

  expect(screen.getByLabelText("نام نمایشی")).toHaveValue("Mohammad");
  expect(screen.getByLabelText("تاریخ تولد")).toHaveValue("2000-05-14");
  expect(screen.getByLabelText("جنسیت")).toHaveValue("male");
  expect(screen.getByLabelText("قد (سانتی‌متر)")).toHaveValue(178);
  expect(screen.getByLabelText("وزن فعلی (کیلوگرم)")).toHaveValue(76.5);
  expect(screen.getByLabelText("هدف ورزشی")).toHaveValue("build_muscle");

  await openTrainingPage(user);
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

  expect(screen.getAllByText(`${expectedWeight} کیلوگرم`)).toHaveLength(2);
  expect(screen.getByText(`ثبت‌شده در ${expectedDate}`)).toBeInTheDocument();
});

it("offers optional body-photo progress from the profile without blocking edits", () => {
  renderProfilePage();

  expect(screen.getByRole("link", { name: "شروع جلسه عکس" })).toHaveAttribute(
    "href",
    "/body-progress",
  );
  expect(screen.getByText(/اختیاری — برای برنامه تمرینی دقیق‌تر/)).toBeInTheDocument();
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

it("saves only fields from the active profile page", async () => {
  context.updateProfile.mockResolvedValue({ ...savedProfile, display_name: "New Name" });
  const user = userEvent.setup();
  renderProfilePage();

  await openTrainingPage(user);
  await user.selectOptions(screen.getByLabelText("کجا تمرین می‌کنی؟"), "gym");
  await user.click(screen.getByRole("button", { name: "بازگشت" }));
  await user.clear(screen.getByLabelText("نام نمایشی"));
  await user.type(screen.getByLabelText("نام نمایشی"), "New Name");
  await user.click(screen.getByRole("button", { name: "بعدی" }));

  await waitFor(() => expect(context.updateProfile).toHaveBeenCalledWith({ display_name: "New Name" }));
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

  await openTrainingPage(user);
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

  await openTrainingPage(user);
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
