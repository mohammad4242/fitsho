import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const adminApi = vi.hoisted(() => ({
  createAdminTrainingProgramTemplate: vi.fn(),
  deleteAdminTrainingProgramTemplate: vi.fn(),
  getAdminExercises: vi.fn(),
  getAdminTrainingProgramTemplate: vi.fn(),
  getAdminTrainingProgramTemplates: vi.fn(),
  updateAdminTrainingProgramTemplate: vi.fn(),
}));

vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-07-27", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminTrainingTemplateEditorPage } from "./AdminTrainingTemplateEditorPage";

beforeEach(() => {
  Object.values(adminApi).forEach((mock) => mock.mockReset());
  adminApi.getAdminExercises.mockResolvedValue({
    items: [{
      id: "exercise-1", slug: "dumbbell-bench-press", name_en: "Dumbbell Bench Press",
      name_fa: "پرس سینه دمبل", primary_muscle: "chest", secondary_muscles: ["triceps"],
      movement_pattern: "horizontal_push", needs_review: false, is_active: true,
    }], page: 1, page_size: 20, total: 1, total_pages: 1,
  });
});

it("creates a new program with shared content and multi-level eligibility", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/training-program-templates/new?days=4&level=intermediate"]}>
      <Routes>
        <Route path="/admin/training-program-templates/new" element={<AdminTrainingTemplateEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { name: "افزودن برنامه تمرینی" })).toBeInTheDocument();
  expect(screen.getByLabelText("تعداد روز تمرین")).toHaveValue("4");
  expect(screen.getByRole("checkbox", { name: "متوسط" })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "مبتدی" })).not.toBeChecked();
  await user.click(screen.getByRole("checkbox", { name: "مبتدی" }));
  expect(screen.getByRole("checkbox", { name: "مبتدی" })).toBeChecked();
  expect(screen.getByLabelText("برچسب‌های تمرکز (با کاما جدا کن)")).toHaveValue(
    "full_body, balanced",
  );
  expect(screen.getAllByText("روز 1")).toHaveLength(2);
  expect(screen.getByRole("button", { name: "باز کردن روز 1: روز 1" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("button", { name: "باز کردن روز 2: روز 2" })).toHaveAttribute("aria-expanded", "false");

  // Expand Day 1 and verify its fields and action appear
  await user.click(screen.getByRole("button", { name: "باز کردن روز 1: روز 1" }));
  expect(screen.getByRole("button", { name: "بستن روز 1: روز 1" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("button", { name: "افزودن حرکت" })).toBeInTheDocument();
});

it("supports first month as eligibility without creating separate content", async () => {
  render(
    <MemoryRouter initialEntries={["/admin/training-program-templates/new?days=2&level=first_month"]}>
      <Routes>
        <Route path="/admin/training-program-templates/new" element={<AdminTrainingTemplateEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByRole("checkbox", { name: "First Month" })).toBeChecked();
  expect(screen.getByRole("button", { name: "باز کردن روز 1: روز 1" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "باز کردن روز 2: روز 2" })).toBeInTheDocument();
});

it("searches the exercise library, links a movement, and toggles exercise-level accordion", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/training-program-templates/new?days=2&level=beginner"]}>
      <Routes>
        <Route path="/admin/training-program-templates/new" element={<AdminTrainingTemplateEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await screen.findByRole("heading", { name: "افزودن برنامه تمرینی" });
  await user.click(screen.getByRole("button", { name: "باز کردن روز 1: روز 1" }));
  await user.click(screen.getByRole("button", { name: "افزودن حرکت" }));
  await user.type(screen.getByPlaceholderText("جست‌وجو در کتابخانه حرکات"), "bench");
  await user.click(await screen.findByRole("button", { name: "انتخاب پرس سینه دمبل" }));

  // When added, slot is automatically expanded
  expect(screen.getByRole("button", { name: "بستن حرکت 1: پرس سینه دمبل" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("3 × 8–12 · RIR 2")).toBeInTheDocument();

  // Edit reps min and max inside expanded slot
  const repMinInput = screen.getByLabelText("حداقل تکرار");
  await user.clear(repMinInput);
  await user.type(repMinInput, "6");

  // Collapse the exercise accordion
  await user.click(screen.getByRole("button", { name: "بستن حرکت 1: پرس سینه دمبل" }));
  expect(screen.getByRole("button", { name: "باز کردن حرکت 1: پرس سینه دمبل" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByText("3 × 6–12 · RIR 2")).toBeInTheDocument();
  expect(screen.queryByLabelText("حداقل تکرار")).not.toBeInTheDocument();

  // Reopen the exercise accordion and verify values are preserved
  await user.click(screen.getByRole("button", { name: "باز کردن حرکت 1: پرس سینه دمبل" }));
  expect(screen.getByLabelText("حداقل تکرار")).toHaveValue(6);

  // Remove the slot
  await user.click(screen.getByRole("button", { name: "حذف پرس سینه دمبل" }));
  expect(screen.queryByText("پرس سینه دمبل")).not.toBeInTheDocument();
});

it("toggles day accordions independently and preserves uncommitted edits across collapse", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/training-program-templates/new?days=3&level=intermediate"]}>
      <Routes>
        <Route path="/admin/training-program-templates/new" element={<AdminTrainingTemplateEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await screen.findByRole("heading", { name: "افزودن برنامه تمرینی" });

  // Open Day 1 and edit its name and structure focus
  await user.click(screen.getByRole("button", { name: "باز کردن روز 1: روز 1" }));
  const day1NameInput = screen.getByLabelText("نام فارسی روز");
  await user.clear(day1NameInput);
  await user.type(day1NameInput, "سینه و پشت بازو");

  // Open Day 2 independently
  await user.click(screen.getByRole("button", { name: "باز کردن روز 2: روز 2" }));
  expect(screen.getByRole("button", { name: "بستن روز 1: سینه و پشت بازو" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("button", { name: "بستن روز 2: روز 2" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("button", { name: "باز کردن روز 3: روز 3" })).toHaveAttribute("aria-expanded", "false");

  // Collapse Day 1
  await user.click(screen.getByRole("button", { name: "بستن روز 1: سینه و پشت بازو" }));
  expect(screen.getByRole("button", { name: "باز کردن روز 1: سینه و پشت بازو" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("button", { name: "بستن روز 2: روز 2" })).toHaveAttribute("aria-expanded", "true");

  // Re-open Day 1 and verify the edited value is preserved
  await user.click(screen.getByRole("button", { name: "باز کردن روز 1: سینه و پشت بازو" }));
  expect(screen.getByDisplayValue("سینه و پشت بازو")).toBeInTheDocument();
});

it("deletes an existing shared template after confirmation", async () => {
  const user = userEvent.setup();
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  adminApi.getAdminTrainingProgramTemplate.mockResolvedValue({
    id: "template-17",
    slug: "shared-template",
    name_en: "Shared Template",
    name_fa: "الگوی مشترک",
    description_en: "One shared definition.",
    description_fa: "یک تعریف مشترک.",
    days_per_week: 2,
    supported_levels: ["beginner", "intermediate"],
    fitness_goal: "build_muscle",
    focus_tags: ["full_body"],
    intensity_methods: ["standard"],
    programming_rationale: [],
    source_name: "Fitsho admin library",
    source_url: "https://fitsho.local/admin-library",
    days: [],
  });
  adminApi.deleteAdminTrainingProgramTemplate.mockResolvedValue(undefined);

  render(
    <MemoryRouter initialEntries={["/admin/training-program-templates/template-17/edit"]}>
      <Routes>
        <Route path="/admin/training-program-templates/:templateId/edit" element={<AdminTrainingTemplateEditorPage />} />
        <Route path="/admin/training-program-templates" element={<p>کتابخانه برنامه‌ها</p>} />
      </Routes>
    </MemoryRouter>,
  );

  await user.click(await screen.findByRole("button", { name: "حذف برنامه" }));

  expect(confirm).toHaveBeenCalledWith("این برنامه و همه روزها و حرکت‌های آن حذف شود؟");
  expect(adminApi.deleteAdminTrainingProgramTemplate).toHaveBeenCalledWith("template-17");
  expect(await screen.findByText("کتابخانه برنامه‌ها")).toBeInTheDocument();
});

it("resolves library exercise name in accordion header and allows custom override", async () => {
  const user = userEvent.setup();
  adminApi.getAdminTrainingProgramTemplate.mockResolvedValue({
    id: "template-22",
    slug: "upper-lower",
    name_en: "Upper Lower Program",
    name_fa: "برنامه بالاتنه پایین‌تنه",
    description_en: "Reference split.",
    description_fa: "اسپلیت مرجع.",
    days_per_week: 2,
    supported_levels: ["intermediate"],
    fitness_goal: "build_muscle",
    focus_tags: ["upper_lower"],
    intensity_methods: ["standard"],
    programming_rationale: [],
    source_name: "Fitsho admin library",
    source_url: "https://fitsho.local/admin-library",
    days: [
      {
        id: "day-1",
        day_number: 1,
        title_en: "Upper Body",
        title_fa: "بالاتنه",
        structure_focus: "upper_body",
        direct_target_muscles: ["chest"],
        slots: Array.from({ length: 5 }, (_, i) => ({
          id: `slot-${i + 1}`,
          slot_order: i + 1,
          exercise_slug_hint: "dumbbell-bench-press",
          placeholder_name_en: null,
          placeholder_name_fa: null,
          target_muscles: ["chest"],
          movement_pattern: "horizontal_push",
          intensity_method: "standard",
          adaptation_priority: "core",
          superset_group: null,
          sets: 3,
          rep_min: 8,
          rep_max: 12,
          target_rir: 2,
          rest_seconds: 90,
          exercise: {
            id: "exercise-1",
            slug: "dumbbell-bench-press",
            name_en: "Dumbbell Bench Press",
            name_fa: "پرس سینه دمبل",
            needs_review: false,
          },
        })),
      },
      {
        id: "day-2",
        day_number: 2,
        title_en: "Lower Body",
        title_fa: "پایین‌تنه",
        structure_focus: "lower_body",
        direct_target_muscles: ["quadriceps"],
        slots: Array.from({ length: 5 }, (_, i) => ({
          id: `slot-2-${i + 1}`,
          slot_order: i + 1,
          exercise_slug_hint: "dumbbell-bench-press",
          placeholder_name_en: null,
          placeholder_name_fa: null,
          target_muscles: ["quadriceps"],
          movement_pattern: "squat",
          intensity_method: "standard",
          adaptation_priority: "core",
          superset_group: null,
          sets: 3,
          rep_min: 8,
          rep_max: 12,
          target_rir: 2,
          rest_seconds: 90,
          exercise: {
            id: "exercise-1",
            slug: "dumbbell-bench-press",
            name_en: "Dumbbell Bench Press",
            name_fa: "پرس سینه دمبل",
            needs_review: false,
          },
        })),
      },
    ],
  });
  adminApi.updateAdminTrainingProgramTemplate.mockResolvedValue({ id: "template-22" });

  render(
    <MemoryRouter initialEntries={["/admin/training-program-templates/template-22/edit"]}>
      <Routes>
        <Route path="/admin/training-program-templates/:templateId/edit" element={<AdminTrainingTemplateEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  // Open Day 1
  expect(await screen.findByRole("button", { name: "باز کردن روز 1: بالاتنه" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "باز کردن روز 1: بالاتنه" }));

  // Verify that slot headers resolve the library exercise name "پرس سینه دمبل", NOT "حرکت 1"
  expect(screen.getByRole("button", { name: "باز کردن حرکت 1: پرس سینه دمبل" })).toBeInTheDocument();

  // Expand slot 1
  await user.click(screen.getByRole("button", { name: "باز کردن حرکت 1: پرس سینه دمبل" }));

  // Verify that display_name_fa input has placeholder showing the library name and value is empty
  const displayNameFaInput = screen.getAllByLabelText("نام نمایشی فارسی")[0];
  expect(displayNameFaInput).toHaveAttribute("placeholder", "پرس سینه دمبل");
  expect(displayNameFaInput).toHaveValue("");

  // Enter a custom override
  await user.type(displayNameFaInput, "پرس سینه با دمبل سنگین");

  // Verify header updates to custom override
  expect(screen.getByRole("button", { name: "بستن حرکت 1: پرس سینه با دمبل سنگین" })).toBeInTheDocument();

  // Save the template and verify payload sends the custom override for slot 1 and null for others
  await user.click(screen.getByRole("button", { name: "ذخیره برنامه" }));
  expect(adminApi.updateAdminTrainingProgramTemplate).toHaveBeenCalledWith(
    "template-22",
    expect.objectContaining({
      days: expect.arrayContaining([
        expect.objectContaining({
          slots: expect.arrayContaining([
            expect.objectContaining({
              exercise_id: "exercise-1",
              display_name_fa: "پرس سینه با دمبل سنگین",
            }),
            expect.objectContaining({
              exercise_id: "exercise-1",
              display_name_fa: null,
            }),
          ]),
        }),
      ]),
    }),
  );
});
