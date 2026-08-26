import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const exercisesApi = vi.hoisted(() => ({
  getExerciseCategories: vi.fn(),
}));

const adminApi = vi.hoisted(() => ({
  createAdminTrainingProgramTemplate: vi.fn(),
  deleteAdminTrainingProgramTemplate: vi.fn(),
  getAdminExercises: vi.fn(),
  getAdminTrainingProgramStructures: vi.fn(),
  getAdminTrainingProgramTemplate: vi.fn(),
  getAdminTrainingProgramTemplates: vi.fn(),
  updateAdminTrainingProgramTemplate: vi.fn(),
}));

vi.mock("../exercises/api", () => exercisesApi);
vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-07-27", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminTrainingTemplateEditorPage } from "./AdminTrainingTemplateEditorPage";

const mockCategories = {
  body_regions: [
    { value: "upper_body", name_en: "Upper Body", name_fa: "بالاتنه" },
    { value: "lower_body", name_en: "Lower Body", name_fa: "پایین‌تنه" },
    { value: "core", name_en: "Core", name_fa: "میان‌تنه" },
  ],
  upper_body: [
    { value: "chest", name_en: "Chest", name_fa: "سینه" },
    { value: "back", name_en: "Back", name_fa: "پشت" },
  ],
  lower_body: [
    { value: "quadriceps", name_en: "Quadriceps", name_fa: "چهارسر" },
  ],
  core: [
    { value: "abs", name_en: "Abs", name_fa: "شکم" },
  ],
  muscle_focuses: {
    chest: [
      { value: "upper_chest", name_en: "Upper Chest", name_fa: "بالاسینه" },
      { value: "mid_chest", name_en: "Mid Chest", name_fa: "میانسینه" },
    ],
    quadriceps: [],
  },
};

const mockBenchPress = {
  id: "exercise-1",
  slug: "dumbbell-bench-press",
  name_en: "Dumbbell Bench Press",
  name_fa: "پرس سینه دمبل",
  primary_muscle: "chest",
  secondary_muscles: ["triceps"],
  movement_pattern: "horizontal_push",
  needs_review: false,
  is_active: true,
  equipment: ["dumbbell", "bench"],
};

const mockLatPulldown = {
  id: "exercise-2",
  slug: "lat-pulldown",
  name_en: "Lat Pulldown",
  name_fa: "زیربغل سیم‌کش",
  primary_muscle: "back",
  secondary_muscles: ["biceps"],
  movement_pattern: "vertical_pull",
  needs_review: false,
  is_active: true,
  equipment: ["cable"],
};

beforeEach(() => {
  Object.values(exercisesApi).forEach((mock) => mock.mockReset());
  Object.values(adminApi).forEach((mock) => mock.mockReset());

  exercisesApi.getExerciseCategories.mockResolvedValue(mockCategories);
  adminApi.getAdminExercises.mockResolvedValue({
    items: [mockBenchPress, mockLatPulldown],
    page: 1,
    page_size: 50,
    total: 2,
    total_pages: 1,
  });
  adminApi.getAdminTrainingProgramStructures.mockResolvedValue({ items: [] });
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

it("browses exercise library hierarchy and adds a movement", async () => {
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
  screen.debug();
  await user.click((await screen.findAllByRole("button", { name: /انتخاب از کتابخانه/ }))[0]);

  // Modal opens with Category hierarchy
  expect(await screen.findByRole("dialog", { name: "انتخاب از کتابخانه حرکات" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /بالاتنه/ })).toBeInTheDocument();

  // Browse: Region (بالاتنه) -> Muscle (سینه) -> Focus (بالاسینه) -> Exercise
  await user.click(screen.getByRole("button", { name: /بالاتنه/ }));
  await user.click(await screen.findByRole("button", { name: /سینه/ }));
  await user.click(await screen.findByRole("button", { name: /بالاسینه/ }));

  // Exercise list
  const exerciseButton = await screen.findByRole("button", { name: /پرس سینه دمبل/ });
  await user.click(exerciseButton);

  // Modal closes, slot is added and expanded
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "بستن حرکت 1: پرس سینه دمبل" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("3 × 8–12 · RIR 2")).toBeInTheDocument();

  // Remove the slot
  await user.click(screen.getByRole("button", { name: "حذف پرس سینه دمبل" }));
  expect(screen.queryByText("پرس سینه دمبل")).not.toBeInTheDocument();
});

it("searches the exercise library by English or Persian name, links a movement, and toggles accordion", async () => {
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
  screen.debug();
  await user.click((await screen.findAllByRole("button", { name: /انتخاب از کتابخانه/ }))[0]);

  // Type in search bar
  const searchInput = await screen.findByPlaceholderText("جست‌وجو با نام فارسی یا انگلیسی…");
  await user.type(searchInput, "bench");

  await waitFor(() => {
    expect(adminApi.getAdminExercises).toHaveBeenCalledWith(
      expect.objectContaining({ search: "bench" }),
    );
  });

  await user.click(await screen.findByRole("button", { name: /پرس سینه دمبل/ }));

  // Slot is automatically expanded
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
});

it("replaces an existing exercise in a slot while preserving workout-specific parameters", async () => {
  const user = userEvent.setup();
  adminApi.getAdminTrainingProgramTemplate.mockResolvedValue({
    id: "template-50",
    slug: "custom-split",
    name_en: "Custom Split",
    name_fa: "اسپلیت اختصاصی",
    description_en: "A template.",
    description_fa: "یک الگو.",
    days_per_week: 2,
    supported_levels: ["beginner"],
    fitness_goal: "build_muscle",
    focus_tags: ["full_body"],
    intensity_methods: ["standard"],
    programming_rationale: [],
    source_name: "Admin",
    source_url: "https://fitsho.local",
    days: [
      {
        id: "day-1",
        day_number: 1,
        title_en: "Upper",
        title_fa: "بالاتنه",
        structure_focus: "upper_body",
        direct_target_muscles: ["chest"],
        slots: [
          {
            id: "slot-1",
            slot_order: 1,
            exercise_slug_hint: "dumbbell-bench-press",
            placeholder_name_en: null,
            placeholder_name_fa: null,
            target_muscles: ["chest"],
            movement_pattern: "horizontal_push",
            intensity_method: "standard",
            adaptation_priority: "core",
            superset_group: null,
            sets: 4,
            rep_min: 10,
            rep_max: 15,
            target_rir: 1,
            rest_seconds: 120,
            exercise: mockBenchPress,
          },
        ],
      },
      {
        id: "day-2",
        day_number: 2,
        title_en: "Lower",
        title_fa: "پایین‌تنه",
        structure_focus: "lower_body",
        direct_target_muscles: ["quadriceps"],
        slots: [],
      },
    ],
  });

  render(
    <MemoryRouter initialEntries={["/admin/training-program-templates/template-50/edit"]}>
      <Routes>
        <Route path="/admin/training-program-templates/:templateId/edit" element={<AdminTrainingTemplateEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  // Open Day 1
  await user.click(await screen.findByRole("button", { name: "باز کردن روز 1: بالاتنه" }));

  // Open slot 1 accordion
  await user.click(screen.getByRole("button", { name: "باز کردن حرکت 1: پرس سینه دمبل" }));
  expect(screen.getByDisplayValue("4")).toBeInTheDocument(); // sets = 4

  // Click "انتخاب از کتابخانه حرکات" inside slot panel
  const chooseFromLibraryBtn = screen.getByRole("button", { name: "انتخاب از کتابخانه حرکات" });
  await user.click(chooseFromLibraryBtn);

  // Modal opens -> Select "زیربغل سیم‌کش"
  expect(await screen.findByRole("dialog", { name: "انتخاب از کتابخانه حرکات" })).toBeInTheDocument();
  const searchInput = screen.getByPlaceholderText("جست‌وجو با نام فارسی یا انگلیسی…");
  await user.type(searchInput, "lat");

  await waitFor(() => {
    expect(adminApi.getAdminExercises).toHaveBeenCalledWith(
      expect.objectContaining({ search: "lat" }),
    );
  });

  await user.click(await screen.findByRole("button", { name: /زیربغل سیم‌کش/ }));

  // Verify header is updated to the new exercise name and prescription is retained
  expect(screen.getByRole("button", { name: "بستن حرکت 1: زیربغل سیم‌کش" })).toBeInTheDocument();
  expect(screen.getByText("4 × 10–15 · RIR 1")).toBeInTheDocument();

  // Verify inputs still retain sets=4, rest=120
  expect(screen.getByLabelText("ست")).toHaveValue(4);
  expect(screen.getByLabelText("استراحت (ثانیه)")).toHaveValue(120);
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
          exercise: mockBenchPress,
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
          exercise: mockBenchPress,
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

it.each([320, 360, 390, 430])(
  "renders days and exercise slots cleanly without error on %ipx mobile width",
  async (width) => {
    window.innerWidth = width;
    window.dispatchEvent(new Event("resize"));

    adminApi.getAdminTrainingProgramTemplate.mockResolvedValue({
      id: "template-mobile",
      slug: "mobile-template",
      name_en: "Mobile Template",
      name_fa: "الگوی موبایل",
      description_en: "Mobile view test.",
      description_fa: "تست نمایش موبایل.",
      days_per_week: 2,
      supported_levels: ["beginner"],
      fitness_goal: "build_muscle",
      focus_tags: ["full_body"],
      intensity_methods: ["standard"],
      programming_rationale: [],
      source_name: "Fitsho admin library",
      source_url: "https://fitsho.local/admin-library",
      days: [
        {
          title_en: "Day 1",
          title_fa: "روز ۱",
          structure_focus: "chest_and_triceps",
          direct_target_muscles: ["chest", "triceps"],
          slots: [
            {
              exercise: mockBenchPress,
              placeholder_name_en: null,
              placeholder_name_fa: null,
              target_muscles: ["chest"],
              movement_pattern: "horizontal_push",
              intensity_method: "standard",
              adaptation_priority: "core",
              superset_group: null,
              sets: 4,
              rep_min: 8,
              rep_max: 12,
              target_rir: 2,
              rest_seconds: 90,
            },
          ],
        },
      ],
    });

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/admin/training-program-templates/template-mobile/edit"]}>
        <Routes>
          <Route
            path="/admin/training-program-templates/:templateId/edit"
            element={<AdminTrainingTemplateEditorPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("روزها و حرکت‌ها")).toBeInTheDocument();

    const dayTrigger = screen.getByRole("button", { name: /روز ۱/ });
    await user.click(dayTrigger);

    const slotTrigger = screen.getByRole("button", { name: /پرس سینه دمبل/ });
    await user.click(slotTrigger);

    expect(screen.getByLabelText("نام فارسی روز")).toHaveValue("روز ۱");
    expect(screen.getByRole("radio", { name: "استاندارد" })).toBeChecked();
    expect(screen.getByText("انتخاب از کتابخانه حرکات")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "حذف پرس سینه دمبل" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "افزودن حرکت" })).toBeInTheDocument();
  },
);
