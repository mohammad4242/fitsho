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
import type { Profile } from "./types";

const profileContext = vi.hoisted(() => ({
  createProfile: vi.fn(),
  retryProfile: vi.fn(),
  updateProfile: vi.fn(),
}));

vi.mock("./ProfileContext", () => ({
  useProfile: () => ({
    profile: null,
    status: "missing",
    ...profileContext,
  }),
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
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  training_days_per_week: 3,
  physical_limitations: null,
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
}

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage("fa");
});

it("announces the first of three onboarding steps", () => {
  renderOnboarding();

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

  expect(screen.getByText("قد باید بین ۱۰۰ تا ۲۵۰ سانتی‌متر باشد.")).toBeInTheDocument();
  expect(screen.getByText("وزن باید بین ۲۰ تا ۵۰۰ کیلوگرم باشد.")).toBeInTheDocument();
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

  expect(screen.getByText("روزهای تمرین باید بین ۱ تا ۷ باشد.")).toBeInTheDocument();
  expect(screen.getByText("محدودیت‌ها حداکثر ۱۰۰۰ نویسه است.")).toBeInTheDocument();
  expect(profileContext.createProfile).not.toHaveBeenCalled();
});

it("submits one normalized typed profile payload", async () => {
  profileContext.createProfile.mockResolvedValue(createdProfile);
  const user = userEvent.setup();
  renderOnboarding();
  await reachExperienceStep(user, "  Mohammad  ");
  await completeExperienceFields(user);
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
    fitness_goal: "build_muscle",
    experience_level: "beginner",
    training_days_per_week: 3,
    physical_limitations: "knee pain",
  });
});

it("replaces onboarding with dashboard after successful creation", async () => {
  profileContext.createProfile.mockResolvedValue(createdProfile);
  const user = userEvent.setup();
  renderOnboarding();
  await reachExperienceStep(user);
  await completeExperienceFields(user);

  await user.click(screen.getByRole("button", { name: "ساخت پروفایل" }));

  expect(
    await screen.findByRole("heading", { name: "REPLACE:/dashboard" }),
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
  await i18n.changeLanguage("en");
  renderOnboarding();

  expect(screen.getByRole("heading", { name: "Build your fitness profile" })).toBeInTheDocument();
  expect(screen.getByText("Step 1 of 3")).toBeInTheDocument();
  expect(screen.getByLabelText("Display name")).toBeInTheDocument();
});
