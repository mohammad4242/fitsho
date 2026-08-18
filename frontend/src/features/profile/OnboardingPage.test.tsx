import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
  useNavigationType,
} from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import type { SafetyProfileInput } from "../nutrition/types";
import {
  PENDING_NUTRITION_BASICS_KEY,
  type OnboardingDraft,
  type PreAccountNutritionBasics,
} from "../publicOnboarding/onboardingDraft";
import type { Profile } from "./types";

const profileContext = vi.hoisted(() => ({
  status: "mode_selected" as "missing" | "mode_selected",
  productMode: "training" as "training" | "nutrition" | "both" | null,
  createProfile: vi.fn(),
  selectProductMode: vi.fn(),
  retryProfile: vi.fn(),
  updateProfile: vi.fn(),
}));

const authContext = vi.hoisted(() => ({
  logout: vi.fn(),
}));

const nutritionFlow = vi.hoisted(() => ({ props: null as unknown }));

vi.mock("./ProfileContext", () => ({
  useProfile: () => ({
    profile: null,
    ...profileContext,
  }),
  useOptionalProfile: () => ({ status: "ready" }),
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => authContext,
}));

vi.mock("../nutrition/NutritionOnboardingFlow", () => ({
  NutritionOnboardingFlow: (props: unknown) => {
    nutritionFlow.props = props;
    return <h1>Nutrition flow</h1>;
  },
}));

import { OnboardingPage } from "./OnboardingPage";

const createdProfile: Profile = {
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
  training_location: "gym",
  home_training_setup: null,
  session_duration_minutes: 60,
  training_intensity: "moderate",
  physical_limitations: null,
  training_cautions: [],
  plan_duration_weeks: 4,
  created_at: "2026-07-27T12:00:00Z",
  updated_at: "2026-07-27T12:00:00Z",
};

function Destination() {
  const location = useLocation();
  const navigationType = useNavigationType();
  return <h1>{`${navigationType}:${location.pathname}`}</h1>;
}

function renderOnboarding() {
  return render(
    <MemoryRouter initialEntries={["/onboarding"]}>
      <Routes>
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/dashboard" element={<Destination />} />
        <Route path="/body-progress/new" element={<Destination />} />
        <Route path="/" element={<Destination />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function completePersonalStep(
  user: UserEvent,
  displayName = "Mohammad",
) {
  await user.type(screen.getByLabelText("نام نمایشی"), displayName);
  await user.type(screen.getByLabelText("تاریخ تولد"), "2000-05-14");
  await user.selectOptions(screen.getByLabelText("جنسیت"), "male");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
}

async function completeBodyStep(user: UserEvent) {
  await user.type(screen.getByLabelText("قد (سانتی‌متر)"), "178");
  await user.type(screen.getByLabelText("وزن فعلی (کیلوگرم)"), "76.5");
  await user.selectOptions(screen.getByLabelText("هدف ورزشی"), "build_muscle");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
}

async function reachExperienceStep(
  user: UserEvent,
  displayName = "Mohammad",
) {
  await completePersonalStep(user, displayName);
  await completeBodyStep(user);
}

async function completeExperienceFields(user: UserEvent) {
  await user.selectOptions(screen.getByLabelText("سطح تجربه"), "beginner");
  await user.type(screen.getByLabelText("روزهای تمرین در هفته"), "3");
  await user.selectOptions(screen.getByLabelText("کجا تمرین می‌کنی؟"), "gym");
  await user.selectOptions(screen.getByLabelText("معمولاً برای هر جلسه چقدر زمان داری؟"), "60");
  await user.selectOptions(screen.getByLabelText("شدت معمول تمرین"), "moderate");
  await user.click(screen.getByLabelText("ندارم"));
}

beforeEach(async () => {
  vi.clearAllMocks();
  sessionStorage.clear();
  nutritionFlow.props = null;
  authContext.logout.mockResolvedValue(undefined);
  profileContext.status = "mode_selected";
  profileContext.productMode = "training";
  await i18n.changeLanguage("fa");
});

it("resumes pending nutrition safety data after registration", () => {
  const safety: SafetyProfileInput = {
    conditions: [{ code: "type_2_diabetes_non_insulin", details: null }],
    medications: [],
    dangerous_food_reaction_history: false,
    pregnant: true,
    breastfeeding: false,
    eating_disorder_diagnosed: false,
    eating_disorder_active_symptoms: false,
    emergency_or_danger_symptoms: false,
    complex_medication_food_interaction: false,
    physician_dietary_restrictions: null,
    other_relevant_condition: null,
  };
  const nutritionBasics: PreAccountNutritionBasics = {
    daily_activity_level: "moderate",
    individual_monthly_food_budget_irr: 8_000_000,
    budget_style: "flexible",
    plan_style: "balanced",
    allergies: [],
    intolerances: [],
    dietary_pattern: "omnivore",
  };
  sessionStorage.setItem(
    PENDING_NUTRITION_BASICS_KEY,
    JSON.stringify({ safety, nutritionBasics }),
  );
  profileContext.productMode = "nutrition";

  renderOnboarding();

  expect(screen.getByRole("heading", { name: "Nutrition flow" })).toBeInTheDocument();
  const props = nutritionFlow.props as {
    initialDraft?: OnboardingDraft;
    initialNutritionBasics?: PreAccountNutritionBasics;
  };
  expect(props.initialDraft).toMatchObject({ mode: "nutrition", safety });
  expect(props.initialNutritionBasics).toEqual(nutritionBasics);
});

it("logs out from onboarding and returns to the public landing", async () => {
  const user = userEvent.setup();
  renderOnboarding();

  await user.click(screen.getByRole("button", { name: "خروج" }));

  expect(authContext.logout).toHaveBeenCalledOnce();
  expect(await screen.findByRole("heading", { name: "REPLACE:/" })).toBeInTheDocument();
});

it("shows unselected product modes first and saves the chosen mode", async () => {
  profileContext.status = "missing";
  profileContext.productMode = null;
  profileContext.selectProductMode.mockResolvedValue({
    user_id: createdProfile.user_id,
    product_mode: "both",
    completion_state: "shared_profile_incomplete",
  });
  const user = userEvent.setup();
  renderOnboarding();

  expect(screen.getByRole("heading", { name: "بیشتر در چه زمینه‌ای به کمک نیاز داری؟" })).toBeInTheDocument();
  expect(screen.getByText("پیشنهاد فیتشو")).toBeInTheDocument();
  await user.click(screen.getByText("تمرین و تغذیه").closest("button")!);

  expect(profileContext.selectProductMode).toHaveBeenCalledWith("both");
});

it("announces the first of three onboarding steps", () => {
  renderOnboarding();

  expect(screen.getByRole("heading", { name: "پروفایل ورزشی‌ات را بساز" })).toHaveClass("fitsho-display");
  expect(screen.getByText("مرحله ۱ از ۳")).toBeInTheDocument();
  const progress = screen.getByRole("list", { name: "مراحل ساخت پروفایل" });
  expect(progress).toBeInTheDocument();
  expect(within(progress).getByText("مشخصات فردی").closest("li")).toHaveAttribute(
    "aria-current",
    "step",
  );
});

it("shows personal field errors and stays on step one", async () => {
  const user = userEvent.setup();
  renderOnboarding();

  await user.click(screen.getByRole("button", { name: "ادامه" }));

  expect(screen.getAllByText("این فیلد الزامی است.")).toHaveLength(3);
  expect(screen.getByText("مرحله ۱ از ۳")).toBeInTheDocument();
  expect(screen.getByLabelText("نام نمایشی")).toHaveFocus();
});

it("advances after valid personal values", async () => {
  const user = userEvent.setup();
  renderOnboarding();

  await completePersonalStep(user);

  expect(screen.getByText("مرحله ۲ از ۳")).toBeInTheDocument();
  expect(screen.getByLabelText("قد (سانتی‌متر)")).toBeInTheDocument();
});

it("keeps invalid body values on step two and focuses height first", async () => {
  const user = userEvent.setup();
  renderOnboarding();
  await completePersonalStep(user);

  await user.type(screen.getByLabelText("قد (سانتی‌متر)"), "99");
  await user.type(screen.getByLabelText("وزن فعلی (کیلوگرم)"), "19");
  await user.selectOptions(screen.getByLabelText("هدف ورزشی"), "build_muscle");
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  expect(screen.getByText("قد باید بین ۱۲۰ تا ۲۳۰ سانتی‌متر باشد.")).toBeInTheDocument();
  expect(screen.getByText("وزن باید بین ۳۵ تا ۳۰۰ کیلوگرم باشد.")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByLabelText("قد (سانتی‌متر)")).toHaveFocus());
  expect(screen.getByText("مرحله ۲ از ۳")).toBeInTheDocument();
});

it("requires a fitness goal before leaving step two", async () => {
  const user = userEvent.setup();
  renderOnboarding();
  await completePersonalStep(user);

  await user.type(screen.getByLabelText("قد (سانتی‌متر)"), "178");
  await user.type(screen.getByLabelText("وزن فعلی (کیلوگرم)"), "76.5");
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  expect(screen.getByText("مرحله ۲ از ۳")).toBeInTheDocument();
  expect(screen.getByLabelText("هدف ورزشی")).toHaveFocus();
});

it("advances after valid body and goal values", async () => {
  const user = userEvent.setup();
  renderOnboarding();
  await completePersonalStep(user);

  await completeBodyStep(user);

  expect(screen.getByText("مرحله ۳ از ۳")).toBeInTheDocument();
  expect(screen.getByLabelText("سطح تجربه")).toBeInTheDocument();
});

it("shows home setup only for home training and clears it after switching to gym", async () => {
  profileContext.createProfile.mockResolvedValue(createdProfile);
  const user = userEvent.setup();
  renderOnboarding();
  await reachExperienceStep(user);
  await user.selectOptions(screen.getByLabelText("سطح تجربه"), "beginner");
  await user.type(screen.getByLabelText("روزهای تمرین در هفته"), "3");

  expect(
    screen.queryByLabelText("برای تمرین در خانه چه امکاناتی داری؟"),
  ).not.toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("کجا تمرین می‌کنی؟"), "home");
  await user.selectOptions(
    screen.getByLabelText("برای تمرین در خانه چه امکاناتی داری؟"),
    "dumbbells_available",
  );
  await user.selectOptions(screen.getByLabelText("معمولاً برای هر جلسه چقدر زمان داری؟"), "60");
  await user.selectOptions(screen.getByLabelText("شدت معمول تمرین"), "moderate");
  await user.click(screen.getByLabelText("ندارم"));
  await user.selectOptions(screen.getByLabelText("کجا تمرین می‌کنی؟"), "gym");

  expect(
    screen.queryByLabelText("برای تمرین در خانه چه امکاناتی داری؟"),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "ساخت پروفایل" }));
  await waitFor(() => expect(profileContext.createProfile).toHaveBeenCalledOnce());
  expect(profileContext.createProfile).toHaveBeenCalledWith(
    expect.objectContaining({ training_location: "gym", home_training_setup: null }),
  );
});

it("returns to step two with entered values preserved", async () => {
  const user = userEvent.setup();
  renderOnboarding();
  await reachExperienceStep(user);

  await user.click(screen.getByRole("button", { name: "بازگشت" }));

  expect(screen.getByLabelText("قد (سانتی‌متر)")).toHaveValue(178);
  expect(screen.getByLabelText("وزن فعلی (کیلوگرم)")).toHaveValue(76.5);
  expect(screen.getByLabelText("هدف ورزشی")).toHaveValue("build_muscle");
});

it("blocks invalid training days and long limitations", async () => {
  const user = userEvent.setup();
  renderOnboarding();
  await reachExperienceStep(user);

  await user.selectOptions(screen.getByLabelText("سطح تجربه"), "beginner");
  await user.type(screen.getByLabelText("روزهای تمرین در هفته"), "8");
  fireEvent.change(screen.getByLabelText("محدودیت‌های جسمی (اختیاری)"), {
    target: { value: "x".repeat(1001) },
  });
  await user.click(screen.getByRole("button", { name: "ساخت پروفایل" }));

  expect(screen.getByText("روزهای تمرین باید بین ۲ تا ۶ باشد.")).toBeInTheDocument();
  expect(screen.getByText("محدودیت‌ها حداکثر ۱۰۰۰ نویسه است.")).toBeInTheDocument();
  expect(profileContext.createProfile).not.toHaveBeenCalled();
});

it("submits one normalized typed profile payload", async () => {
  profileContext.createProfile.mockResolvedValue(createdProfile);
  const user = userEvent.setup();
  renderOnboarding();
  await reachExperienceStep(user, "  Mohammad  ");
  await completeExperienceFields(user);
  await user.click(screen.getByLabelText("احتیاط برای زانو"));
  await user.selectOptions(screen.getByLabelText("مدت این برنامه چقدر باشد؟"), "6");
  await user.type(
    screen.getByLabelText("محدودیت‌های جسمی (اختیاری)"),
    "  knee pain  ",
  );

  await user.click(screen.getByRole("button", { name: "ساخت پروفایل" }));

  await waitFor(() => expect(profileContext.createProfile).toHaveBeenCalledOnce());
  expect(profileContext.createProfile).toHaveBeenCalledWith({
    display_name: "Mohammad",
    birth_date: "2000-05-14",
    sex: "male",
    height_cm: 178,
    current_weight_kg: 76.5,
    shoulder_circumference_cm: null,
    waist_circumference_cm: null,
    hip_circumference_cm: null,
    fitness_goal: "build_muscle",
    experience_level: "beginner",
    training_age_months: null,
    training_days_per_week: 3,
    preferred_weekdays: null,
    priority_muscles: null,
    training_location: "gym",
    home_training_setup: null,
    session_duration_minutes: 60,
    training_intensity: "moderate",
    physical_limitations: "knee pain",
    training_cautions: ["knee"],
    plan_duration_weeks: 6,
  });
});

it("offers the optional photo flow after successful profile creation", async () => {
  profileContext.createProfile.mockResolvedValue(createdProfile);
  const user = userEvent.setup();
  renderOnboarding();
  await reachExperienceStep(user);
  await completeExperienceFields(user);

  await user.click(screen.getByRole("button", { name: "ساخت پروفایل" }));

  expect(
    await screen.findByRole("heading", { name: "REPLACE:/body-progress/new" }),
  ).toBeInTheDocument();
});

it("keeps entered values and shows an alert when creation fails", async () => {
  profileContext.createProfile.mockRejectedValue(new Error("offline"));
  const user = userEvent.setup();
  renderOnboarding();
  await reachExperienceStep(user, "Mohammad");
  await completeExperienceFields(user);
  await user.type(
    screen.getByLabelText("محدودیت‌های جسمی (اختیاری)"),
    "knee pain",
  );

  await user.click(screen.getByRole("button", { name: "ساخت پروفایل" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "درخواست انجام نشد",
  );
  expect(screen.getByLabelText("روزهای تمرین در هفته")).toHaveValue(3);
  expect(screen.getByLabelText("محدودیت‌های جسمی (اختیاری)")).toHaveValue(
    "knee pain",
  );
  await user.click(screen.getByRole("button", { name: "بازگشت" }));
  await user.click(screen.getByRole("button", { name: "بازگشت" }));
  expect(screen.getByLabelText("نام نمایشی")).toHaveValue("Mohammad");
});

it("disables back and submit controls while creation is pending", async () => {
  profileContext.createProfile.mockReturnValue(new Promise(() => undefined));
  const user = userEvent.setup();
  renderOnboarding();
  await reachExperienceStep(user);
  await completeExperienceFields(user);

  await user.click(screen.getByRole("button", { name: "ساخت پروفایل" }));

  expect(await screen.findByRole("button", { name: "در حال ذخیره…" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "بازگشت" })).toBeDisabled();
});

it("renders the onboarding structure in English", async () => {
  const user = userEvent.setup();
  renderOnboarding();
  await reachExperienceStep(user);
  await i18n.changeLanguage("en");

  expect(screen.getByRole("heading", { name: "Build your fitness profile" })).toBeInTheDocument();
  expect(screen.getByText("Step 3 of 3")).toBeInTheDocument();
  expect(screen.getByLabelText("Where do you train?")).toBeInTheDocument();
  expect(
    screen.getByLabelText("How much time do you usually have for each workout?"),
  ).toBeInTheDocument();
});

it("requires a deliberate training-caution choice", async () => {
  const user = userEvent.setup();
  renderOnboarding();
  await reachExperienceStep(user);
  await user.selectOptions(screen.getByLabelText("سطح تجربه"), "beginner");
  await user.type(screen.getByLabelText("روزهای تمرین در هفته"), "3");
  await user.selectOptions(screen.getByLabelText("کجا تمرین می‌کنی؟"), "gym");
  await user.selectOptions(
    screen.getByLabelText("معمولاً برای هر جلسه چقدر زمان داری؟"),
    "60",
  );
  await user.selectOptions(screen.getByLabelText("شدت معمول تمرین"), "moderate");

  await user.click(screen.getByRole("button", { name: "ساخت پروفایل" }));

  expect(screen.getByText("این فیلد الزامی است.")).toBeInTheDocument();
  expect(profileContext.createProfile).not.toHaveBeenCalled();
});
