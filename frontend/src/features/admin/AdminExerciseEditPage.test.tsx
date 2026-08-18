import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const adminApi = vi.hoisted(() => ({
  getAdminExercise: vi.fn(),
  updateAdminExercise: vi.fn(),
}));

vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-07-27", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminExerciseEditPage } from "./AdminExerciseEditPage";

const exercise = {
  id: "exercise-id",
  slug: "incline-push-up",
  name_en: "Incline Push Up",
  name_fa: "شنا سوئدی شیب‌دار",
  content_type: "exercise",
  body_region: "upper_body",
  primary_muscle: "chest",
  muscle_focus: "mid_chest",
  secondary_muscles: ["triceps"],
  equipment: ["bodyweight", "bench"],
  difficulty: "beginner",
  movement_pattern: "horizontal_push",
  exercise_type: "compound",
  caution_tags: ["shoulder_internal_rotation"],
  body_position: "supported",
  stability_demand: "high",
  skill_demand: "moderate",
  impact_level: "low",
  axial_loading_level: "none",
  fatigue_cost: 4,
  setup_cost: 2,
  laterality: "unilateral",
  substitution_group: "horizontal_push",
  range_of_motion_profile: ["supported", "shortened"],
  labels: [],
  needs_review: false,
  is_programmable: true,
  instructions_en: ["Brace", "Lower", "Press"],
  instructions_fa: ["محکم", "پایین", "فشار"],
  safety_notes_en: ["Keep aligned"],
  safety_notes_fa: ["هم‌راستا بمانید"],
  media_path: "/exercises/exercise-placeholder.svg",
  media_type: "placeholder",
  media_source_url: null,
  media_license: null,
  media_attribution: null,
  is_active: true,
  created_at: "2026-07-27T12:00:00Z",
  updated_at: "2026-07-27T12:00:00Z",
};

beforeEach(() => {
  adminApi.getAdminExercise.mockReset();
  adminApi.updateAdminExercise.mockReset();
  adminApi.getAdminExercise.mockResolvedValue(exercise);
  adminApi.updateAdminExercise.mockResolvedValue(exercise);
});

async function openSection(user: ReturnType<typeof userEvent.setup>, title: string) {
  await user.click(await screen.findByRole("button", { name: title }));
}

it("opens one edit section at a time from a collapsed default", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/exercises/exercise-id/edit"]}>
      <Routes>
        <Route path="/admin/exercises/:exerciseId/edit" element={<AdminExerciseEditPage />} />
        <Route path="/exercises" element={<p>LIST PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );

  const identity = await screen.findByRole("button", { name: "هویت حرکت" });
  const target = screen.getByRole("button", { name: "هدف و تجهیزات" });
  expect(identity).toHaveAttribute("aria-expanded", "false");
  expect(target).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByLabelText("نام انگلیسی")).not.toBeInTheDocument();

  await user.click(identity);
  expect(identity).toHaveAttribute("aria-expanded", "true");
  expect(identity).toHaveTextContent("⌃");
  expect(screen.getByLabelText("نام انگلیسی")).toBeInTheDocument();

  await user.click(target);
  expect(identity).toHaveAttribute("aria-expanded", "false");
  expect(identity).toHaveTextContent("⌄");
  expect(target).toHaveAttribute("aria-expanded", "true");
  expect(screen.queryByLabelText("نام انگلیسی")).not.toBeInTheDocument();
  expect(screen.getByLabelText("ناحیه بدن")).toBeInTheDocument();
});

it("loads structured programming metadata and saves an edited exercise", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/exercises/exercise-id/edit"]}>
      <Routes>
        <Route path="/admin/exercises/:exerciseId/edit" element={<AdminExerciseEditPage />} />
        <Route path="/exercises" element={<p>LIST PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );

  await openSection(user, "اطلاعات برنامه‌سازی");
  expect(await screen.findByLabelText("الگوی حرکت")).toHaveValue("horizontal_push");
  expect(screen.getByLabelText("نوع حرکت")).toHaveValue("compound");
  await openSection(user, "هدف و تجهیزات");
  expect(screen.getByLabelText("بخش هدف عضله")).toHaveValue("mid_chest");
  await openSection(user, "اطلاعات برنامه‌سازی");
  expect(screen.getByLabelText("فشار داخلی شانه")).toBeChecked();
  expect(screen.getByLabelText("قابل استفاده برای تولید برنامه")).toBeChecked();

  await openSection(user, "هویت حرکت");
  await user.clear(screen.getByLabelText("نام انگلیسی"));
  await user.type(screen.getByLabelText("نام انگلیسی"), "Advanced Incline Push Up");
  await user.clear(screen.getByLabelText("نام فارسی"));
  await user.type(screen.getByLabelText("نام فارسی"), "شنا شیب‌دار پیشرفته");
  await user.selectOptions(screen.getByLabelText("سطح سختی"), "advanced");
  await openSection(user, "هدف و تجهیزات");
  await user.click(screen.getByLabelText("دمبل"));
  await openSection(user, "آموزش و ایمنی");
  await user.clear(screen.getByLabelText("مرحله انگلیسی ۱"));
  await user.type(screen.getByLabelText("مرحله انگلیسی ۱"), "Set the bench securely");
  await user.clear(screen.getByLabelText("نکته فارسی ۱"));
  await user.type(screen.getByLabelText("نکته فارسی ۱"), "شانه‌ها را ثابت نگه دارید");

  await openSection(user, "اطلاعات برنامه‌سازی");
  await user.selectOptions(screen.getByLabelText("الگوی حرکت"), "vertical_push");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(adminApi.updateAdminExercise).toHaveBeenCalledWith(
    "exercise-id",
    expect.objectContaining({
      name_en: "Advanced Incline Push Up",
      name_fa: "شنا شیب‌دار پیشرفته",
      equipment: ["bodyweight", "bench", "dumbbell"],
      difficulty: "advanced",
      instructions_en: ["Set the bench securely", "Lower", "Press"],
      safety_notes_fa: ["شانه‌ها را ثابت نگه دارید"],
      movement_pattern: "vertical_push",
      is_programmable: true,
    }),
    null,
    [],
  );
  expect(await screen.findByText("LIST PAGE")).toBeInTheDocument();
});

it("edits all persisted exercise programming metadata fields", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/exercises/exercise-id/edit"]}>
      <Routes>
        <Route path="/admin/exercises/:exerciseId/edit" element={<AdminExerciseEditPage />} />
        <Route path="/exercises" element={<p>LIST PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );

  await openSection(user, "اطلاعات برنامه‌سازی");
  await user.selectOptions(screen.getByLabelText("وضعیت بدن"), "lying");
  await user.selectOptions(screen.getByLabelText("نیاز به ثبات"), "low");
  await user.selectOptions(screen.getByLabelText("نیاز به مهارت"), "low");
  await user.selectOptions(screen.getByLabelText("سطح ضربه"), "moderate");
  await user.selectOptions(screen.getByLabelText("سطح بار محوری"), "moderate");
  await user.clear(screen.getByLabelText("هزینه خستگی"));
  await user.type(screen.getByLabelText("هزینه خستگی"), "2");
  await user.clear(screen.getByLabelText("هزینه آماده‌سازی"));
  await user.type(screen.getByLabelText("هزینه آماده‌سازی"), "3");
  await user.selectOptions(screen.getByLabelText("طرفیت حرکت"), "bilateral");
  await user.clear(screen.getByLabelText("گروه جایگزینی"));
  await user.type(screen.getByLabelText("گروه جایگزینی"), "squat");
  await user.clear(screen.getByLabelText("الگوی دامنه حرکت"));
  await user.type(screen.getByLabelText("الگوی دامنه حرکت"), "deep_knee_flexion, supported");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(adminApi.updateAdminExercise).toHaveBeenCalledWith(
    "exercise-id",
    expect.objectContaining({
      body_position: "lying",
      stability_demand: "low",
      skill_demand: "low",
      impact_level: "moderate",
      axial_loading_level: "moderate",
      fatigue_cost: 2,
      setup_cost: 3,
      laterality: "bilateral",
      substitution_group: "squat",
      range_of_motion_profile: ["deep_knee_flexion", "supported"],
    }),
    null,
    [],
  );
});

it("saves a name-only edit when safety notes are empty", async () => {
  const user = userEvent.setup();
  adminApi.getAdminExercise.mockResolvedValue({
    ...exercise,
    safety_notes_en: [],
    safety_notes_fa: [],
  });
  render(
    <MemoryRouter initialEntries={["/admin/exercises/exercise-id/edit"]}>
      <Routes>
        <Route path="/admin/exercises/:exerciseId/edit" element={<AdminExerciseEditPage />} />
        <Route path="/exercises" element={<p>LIST PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );

  await openSection(user, "هویت حرکت");
  await user.clear(screen.getByLabelText("نام انگلیسی"));
  await user.type(screen.getByLabelText("نام انگلیسی"), "Renamed Incline Push Up");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(adminApi.updateAdminExercise).toHaveBeenCalledWith(
    "exercise-id",
    expect.objectContaining({
      name_en: "Renamed Incline Push Up",
      safety_notes_en: [],
      safety_notes_fa: [],
    }),
    null,
    [],
  );
  expect(await screen.findByText("LIST PAGE")).toBeInTheDocument();
});

it("switches an existing catalogue item to guide without uploading media", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/exercises/exercise-id/edit"]}>
      <Routes>
        <Route path="/admin/exercises/:exerciseId/edit" element={<AdminExerciseEditPage />} />
        <Route path="/exercises" element={<p>LIST PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );

  await openSection(user, "هویت حرکت");
  await user.click(await screen.findByLabelText("راهنما"));
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(adminApi.updateAdminExercise).toHaveBeenCalledWith(
    "exercise-id",
    expect.objectContaining({ content_type: "guide" }),
    null,
    [],
  );
});

it("shows and allows editing a cross-region secondary muscle", async () => {
  const user = userEvent.setup();
  adminApi.getAdminExercise.mockResolvedValue({
    ...exercise,
    secondary_muscles: ["triceps", "calves"],
  });
  render(
    <MemoryRouter initialEntries={["/admin/exercises/exercise-id/edit"]}>
      <Routes>
        <Route path="/admin/exercises/:exerciseId/edit" element={<AdminExerciseEditPage />} />
        <Route path="/exercises" element={<p>LIST PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );

  await openSection(user, "هدف و تجهیزات");
  const calves = await screen.findByLabelText("عضله فرعی: ساق");
  expect(calves).toBeChecked();
  await user.click(calves);
  expect(calves).not.toBeChecked();
  await user.click(calves);

  await openSection(user, "هویت حرکت");
  await user.clear(screen.getByLabelText("نام انگلیسی"));
  await user.type(screen.getByLabelText("نام انگلیسی"), "Renamed Legacy Exercise");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(adminApi.updateAdminExercise).toHaveBeenCalledWith(
    "exercise-id",
    expect.objectContaining({
      name_en: "Renamed Legacy Exercise",
      secondary_muscles: ["triceps", "calves"],
    }),
    null,
    [],
  );
});

it("allows editing muscle focus on a review exercise", async () => {
  const user = userEvent.setup();
  adminApi.getAdminExercise.mockResolvedValue({
    ...exercise,
    needs_review: true,
  });
  render(
    <MemoryRouter initialEntries={["/admin/exercises/exercise-id/edit"]}>
      <Routes>
        <Route path="/admin/exercises/:exerciseId/edit" element={<AdminExerciseEditPage />} />
        <Route path="/exercises" element={<p>LIST PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );

  await openSection(user, "هدف و تجهیزات");
  const focus = await screen.findByLabelText("بخش هدف عضله");
  expect(focus).not.toBeDisabled();
  await user.selectOptions(focus, "upper_chest");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(adminApi.updateAdminExercise).toHaveBeenCalledWith(
    "exercise-id",
    expect.objectContaining({ muscle_focus: "upper_chest" }),
    null,
    [],
  );
});

it("allows editing the primary muscle on a review exercise", async () => {
  const user = userEvent.setup();
  adminApi.getAdminExercise.mockResolvedValue({
    ...exercise,
    needs_review: true,
  });
  render(
    <MemoryRouter initialEntries={["/admin/exercises/exercise-id/edit"]}>
      <Routes>
        <Route path="/admin/exercises/:exerciseId/edit" element={<AdminExerciseEditPage />} />
        <Route path="/exercises" element={<p>LIST PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );

  await openSection(user, "هدف و تجهیزات");
  const primaryMuscle = await screen.findByLabelText("عضله اصلی");
  expect(primaryMuscle).not.toBeDisabled();
  await user.selectOptions(primaryMuscle, "back");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(adminApi.updateAdminExercise).toHaveBeenCalledWith(
    "exercise-id",
    expect.objectContaining({ primary_muscle: "back", muscle_focus: null }),
    null,
    [],
  );
});

it("allows editing the body region and primary muscle on a review exercise", async () => {
  const user = userEvent.setup();
  adminApi.getAdminExercise.mockResolvedValue({
    ...exercise,
    needs_review: true,
  });
  render(
    <MemoryRouter initialEntries={["/admin/exercises/exercise-id/edit"]}>
      <Routes>
        <Route path="/admin/exercises/:exerciseId/edit" element={<AdminExerciseEditPage />} />
        <Route path="/exercises" element={<p>LIST PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );

  await openSection(user, "هدف و تجهیزات");
  const bodyRegion = await screen.findByLabelText("ناحیه بدن");
  expect(bodyRegion).not.toBeDisabled();
  await user.selectOptions(bodyRegion, "lower_body");
  expect(screen.getByLabelText("عضله اصلی")).toHaveValue("");
  await user.selectOptions(screen.getByLabelText("عضله اصلی"), "quadriceps");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(adminApi.updateAdminExercise).toHaveBeenCalledWith(
    "exercise-id",
    expect.objectContaining({
      body_region: "lower_body",
      primary_muscle: "quadriceps",
      muscle_focus: null,
    }),
    null,
    [],
  );
});
