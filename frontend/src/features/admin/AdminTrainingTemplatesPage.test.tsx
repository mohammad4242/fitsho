import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const adminApi = vi.hoisted(() => ({
  deleteAdminTrainingTemplateSlot: vi.fn(),
  getAdminTrainingProgramTemplates: vi.fn(),
  getAdminTrainingProgramStructures: vi.fn(),
  updateAdminTrainingTemplateSlot: vi.fn(),
}));
vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-07-27", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminTrainingTemplatesPage } from "./AdminTrainingTemplatesPage";

const template = {
  id: "1",
  slug: "four-day-classic-body-part",
  name_en: "Four-Day Classic Body-Part Rotation",
  name_fa: "تفکیک کلاسیک چهار روزه",
  description_en: "A direct target split.",
  description_fa: "تقسیم با عضلات هدف مستقیم.",
  days_per_week: 4,
  supported_levels: ["beginner", "intermediate"] as const,
  fitness_goal: "build_muscle" as const,
  focus_tags: ["body_part_rotation", "balanced"],
  intensity_methods: ["standard" as const],
  source_name: "Fitsho original evidence-informed template",
  source_url: "https://pubmed.ncbi.nlm.nih.gov/38595233/",
  programming_rationale: [
    {
      title_en: "Exercise order",
      title_fa: "ترتیب حرکات",
      detail_en: "Main chest work comes first.",
      detail_fa: "حرکت اصلی سینه ابتدا می‌آید.",
    },
    {
      title_en: "Main movements",
      title_fa: "حرکت‌های اصلی",
      detail_en: "Compound work leads the session.",
      detail_fa: "حرکت‌های چندمفصلی ابتدای جلسه هستند.",
    },
    {
      title_en: "Working sets",
      title_fa: "ست‌های کاری",
      detail_en: "Three to four quality sets.",
      detail_fa: "سه تا چهار ست باکیفیت.",
    },
    {
      title_en: "Program focus",
      title_fa: "تمرکز برنامه",
      detail_en: "Direct target rotation.",
      detail_fa: "چرخش عضلات هدف مستقیم.",
    },
    {
      title_en: "Fatigue management",
      title_fa: "مدیریت خستگی",
      detail_en: "Isolation work closes the session.",
      detail_fa: "حرکات تک‌مفصلی پایان جلسه هستند.",
    },
  ],
  days: [{
    id: "day-1",
    day_number: 1,
    title_en: "Chest + Triceps",
    title_fa: "سینه + پشت بازو",
    direct_target_muscles: ["chest", "triceps"],
    slots: [
      {
        id: "slot-1", slot_order: 1, exercise_slug_hint: "dumbbell-bench-press",
        placeholder_name_en: null, placeholder_name_fa: null, target_muscles: ["chest"],
        movement_pattern: "horizontal_push", intensity_method: "standard" as const,
        sets: 4, rep_min: 8, rep_max: 12, target_rir: 2, rest_seconds: 90,
        exercise: { id: "exercise-1", slug: "dumbbell-bench-press", name_en: "Dumbbell Bench Press", name_fa: "پرس سینه دمبل", needs_review: false },
      },
      {
        id: "slot-2", slot_order: 2, exercise_slug_hint: "cable-pullover",
        placeholder_name_en: "Cable Pullover", placeholder_name_fa: "پلاور کابل", target_muscles: ["back"],
        movement_pattern: "vertical_pull", intensity_method: "standard" as const,
        sets: 3, rep_min: 10, rep_max: 15, target_rir: 2, rest_seconds: 60,
        exercise: { id: "exercise-2", slug: "cable-pullover", name_en: "Cable Pullover", name_fa: "پلاور کابل", needs_review: true },
      },
    ],
  }],
};

const templates = [
  template,
  {
    ...template,
    id: "2",
    slug: "four-day-beginner-foundation",
    name_fa: "پایه چهارروزه مبتدی",
    supported_levels: ["first_month"] as const,
  },
  {
    ...template,
    id: "3",
    slug: "four-day-advanced-chest",
    name_fa: "تخصصی سینه چهارروزه پیشرفته",
    supported_levels: ["advanced"] as const,
  },
];

beforeEach(() => {
  adminApi.getAdminTrainingProgramTemplates.mockReset();
  adminApi.getAdminTrainingProgramTemplates.mockResolvedValue({ items: [] });
  adminApi.getAdminTrainingProgramStructures.mockReset();
  adminApi.getAdminTrainingProgramStructures.mockResolvedValue({ items: [] });
  adminApi.updateAdminTrainingTemplateSlot.mockReset();
  adminApi.deleteAdminTrainingTemplateSlot.mockReset();
});

it("uses family disclosure for longer weeks and resets dependent selections", async () => {
  const structures = {
    4: [
      {
        id: "4-upper-lower",
        slug: "4d-upper-lower-2x",
        name_en: "Upper / Lower ×2",
        name_fa: "بالاتنه / پایین‌تنه دو بار",
        days_per_week: 4,
        family: "upper_lower" as const,
        split_type: null,
      },
      {
        id: "4-split",
        slug: "4d-push-pull-quads-posterior",
        name_en: "Push / Pull / Quads / Posterior",
        name_fa: "پوش / پول / چهارسر / خلفی",
        days_per_week: 4,
        family: "split" as const,
        split_type: "body_part" as const,
      },
    ],
    5: [
      {
        id: "5-upper-lower",
        slug: "5d-upper-lower",
        name_en: "Upper / Lower",
        name_fa: "بالاتنه / پایین‌تنه",
        days_per_week: 5,
        family: "upper_lower" as const,
        split_type: null,
      },
      {
        id: "5-ppl",
        slug: "5d-ppl",
        name_en: "Push / Pull / Legs / Upper / Lower",
        name_fa: "پوش / پول / پا / بالاتنه / پایین‌تنه",
        days_per_week: 5,
        family: "split" as const,
        split_type: "ppl" as const,
      },
      {
        id: "5-body-part",
        slug: "5d-body-part-b",
        name_en: "5-Day Body-Part Split B",
        name_fa: "تقسیم عضله‌ای پنج‌روزه ب",
        days_per_week: 5,
        family: "split" as const,
        split_type: "body_part" as const,
      },
    ],
  };
  adminApi.getAdminTrainingProgramStructures.mockImplementation((days: number) => Promise.resolve({ items: structures[days as 4 | 5] ?? [] }));
  adminApi.getAdminTrainingProgramTemplates.mockResolvedValue({ items: templates });
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <AdminTrainingTemplatesPage />
    </MemoryRouter>,
  );

  await user.click(screen.getByRole("tab", { name: "5 روزه" }));
  expect(screen.queryByRole("button", { name: "Upper / Lower" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "بالاتنه / پایین‌تنه" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("button", { name: "Split" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByText("پوش / پول / پا / بالاتنه / پایین‌تنه")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Split" }));
  expect(screen.getByRole("button", { name: "Split" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("button", { name: "پوش / پول / پا / بالاتنه / پایین‌تنه" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "تقسیم عضله‌ای پنج‌روزه ب" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "بالاتنه / پایین‌تنه دو بار" })).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "پوش / پول / پا / بالاتنه / پایین‌تنه" }));
  expect(screen.getByRole("button", { name: "پوش / پول / پا / بالاتنه / پایین‌تنه" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("link", { name: "افزودن برنامه جدید" })).toHaveAttribute(
    "href",
    "/admin/training-program-templates/new?days=5&level=beginner&structure_id=5-ppl",
  );

  await user.click(screen.getByRole("tab", { name: "4 روزه" }));
  expect(screen.getByRole("button", { name: "بالاتنه / پایین‌تنه" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("button", { name: "Split" })).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("link", { name: "افزودن برنامه جدید" })).toHaveAttribute(
    "href",
    "/admin/training-program-templates/new?days=4&level=beginner",
  );

  await user.click(screen.getByRole("tab", { name: "همهٔ ساختارها" }));
  expect(screen.getByRole("tab", { name: "همهٔ ساختارها" })).toHaveAttribute("aria-selected", "true");
  expect(adminApi.getAdminTrainingProgramTemplates).toHaveBeenLastCalledWith(4, "all");
});

it("shows two- and three-day structures directly without family controls", async () => {
  adminApi.getAdminTrainingProgramStructures.mockImplementation((days: number) => Promise.resolve({
    items: [{
      id: `${days}-structure`,
      slug: `${days}d-structure`,
      name_en: `${days}-Day Structure`,
      name_fa: `ساختار ${days} روزه`,
      days_per_week: days,
      family: null,
      split_type: null,
    }],
  }));
  adminApi.getAdminTrainingProgramTemplates.mockResolvedValue({ items: [] });
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <AdminTrainingTemplatesPage />
    </MemoryRouter>,
  );

  await user.click(screen.getByRole("tab", { name: "3 روزه" }));
  expect(await screen.findByRole("tab", { name: "ساختار 3 روزه" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Upper / Lower" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Split" })).not.toBeInTheDocument();
});

it("removes day-count wording from titles for every supported day count", async () => {
  const cases = [
    { days: 2, raw: "تمام‌بدن دو روزه A/B", display: "تمام‌بدن A/B" },
    { days: 3, raw: "بالاتنه / پایین‌تنه / بالاتنه سه روزه", display: "بالاتنه / پایین‌تنه / بالاتنه" },
    { days: 4, raw: "چهارروزه؛ سه پایین‌تنه و یک بالاتنه", display: "سه پایین‌تنه و یک بالاتنه" },
    { days: 5, raw: "پنج‌روزه تخصص سینه", display: "تخصص سینه" },
    { days: 6, raw: "شش‌روزه پیشرفته عضله‌ای", display: "پیشرفته عضله‌ای" },
  ];
  adminApi.getAdminTrainingProgramStructures.mockResolvedValue({ items: [] });
  adminApi.getAdminTrainingProgramTemplates.mockImplementation((days: number) => {
    const item = cases.find((candidate) => candidate.days === days);
    return Promise.resolve({
      items: item === undefined ? [] : [{
        ...template,
        id: `title-${days}`,
        days_per_week: days,
        name_fa: item.raw,
        name_en: `${days}-Day Structure`,
      }],
    });
  });
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <AdminTrainingTemplatesPage />
    </MemoryRouter>,
  );

  for (const item of cases) {
    await user.click(screen.getByRole("tab", { name: `${item.days} روزه` }));
    expect(await screen.findByText(item.display)).toBeInTheDocument();
    expect(screen.queryByText(item.raw)).not.toBeInTheDocument();
  }
});

it("filters the library by day count and training level", async () => {
  adminApi.getAdminTrainingProgramTemplates.mockImplementation(
    (days: number, level: string) => {
      if (days !== 4) return new Promise(() => {});
      if (level === "all") return Promise.resolve({ items: templates });
      return Promise.resolve({
        items: templates.filter((item) => (
          item.supported_levels.some((supportedLevel) => supportedLevel === level)
        )),
      });
    },
  );
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <AdminTrainingTemplatesPage />
    </MemoryRouter>,
  );

  await user.click(screen.getByRole("tab", { name: "4 روزه" }));

  expect(await screen.findByText("تفکیک کلاسیک")).toBeInTheDocument();
  expect(screen.queryByText("تفکیک کلاسیک چهار روزه")).not.toBeInTheDocument();
  expect(within(screen.getAllByRole("article")[0]).getByText((content) => content.includes("روزه"))).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "متوسط" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "First Month" })).toBeInTheDocument();
  expect(screen.queryByText("سینه + پشت بازو")).not.toBeInTheDocument();
  expect(screen.queryByText("پرس سینه دمبل")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "باز کردن برنامه: تفکیک کلاسیک چهار روزه" })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  expect(screen.getAllByRole("link", { name: "ویرایش برنامه: تفکیک کلاسیک چهار روزه" })).toHaveLength(1);
  expect(screen.getByRole("link", { name: "افزودن برنامه جدید" })).toHaveAttribute(
    "href",
    "/admin/training-program-templates/new?days=4&level=beginner",
  );
  expect(adminApi.getAdminTrainingProgramTemplates).toHaveBeenCalledWith(4, "all");

  await user.click(screen.getByRole("tab", { name: "متوسط" }));
  const intermediateEditPath = screen.getByRole("link", {
    name: "ویرایش برنامه: تفکیک کلاسیک چهار روزه",
  }).getAttribute("href");
  expect(adminApi.getAdminTrainingProgramTemplates).toHaveBeenCalledWith(4, "intermediate");

  await user.click(screen.getByRole("tab", { name: "مبتدی" }));
  expect(screen.getByRole("link", {
    name: "ویرایش برنامه: تفکیک کلاسیک چهار روزه",
  })).toHaveAttribute("href", intermediateEditPath);
  expect(adminApi.getAdminTrainingProgramTemplates).toHaveBeenCalledWith(4, "beginner");

  await user.click(screen.getByRole("button", { name: "باز کردن برنامه: تفکیک کلاسیک چهار روزه" }));

  expect(screen.getByText("سینه + پشت بازو")).toBeInTheDocument();
  expect(screen.queryByText("پرس سینه دمبل")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "باز کردن روز 1: سینه + پشت بازو" })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  expect(screen.getByText("منطق برنامه")).toBeInTheDocument();
  expect(screen.getByText("ترتیب حرکات")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "باز کردن روز 1: سینه + پشت بازو" }));

  expect(screen.getByText("پرس سینه دمبل")).toBeInTheDocument();
  expect(screen.getByText("پلاور کابل")).toBeInTheDocument();
  expect(screen.getByText("نیازمند ویدیو و بازبینی")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "جزئیات حرکت: پرس سینه دمبل" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "جزئیات حرکت: پلاور کابل" })).toBeInTheDocument();

  await user.click(screen.getByRole("tab", { name: "پیشرفته" }));

  expect(await screen.findByText("تخصصی سینه پیشرفته")).toBeInTheDocument();
  expect(screen.queryByText("تفکیک کلاسیک چهار روزه")).not.toBeInTheDocument();

  await user.click(screen.getByRole("tab", { name: "First Month" }));

  expect(screen.getByRole("link", { name: "افزودن برنامه جدید" })).toHaveAttribute(
    "href",
    "/admin/training-program-templates/new?days=4&level=first_month",
  );
});

it("edits one exercise instance and keeps the accordion open", async () => {
  adminApi.getAdminTrainingProgramTemplates.mockResolvedValue({ items: templates });
  const updatedTemplate = {
    ...template,
    days: [{
      ...template.days[0],
      slots: [{
        ...template.days[0].slots[0],
        sets: 5,
        rep_min: 6,
        rep_max: 10,
        target_rir: 1,
        exercise: { ...template.days[0].slots[0].exercise, name_fa: "پرس سینه جایگزین" },
      }, template.days[0].slots[1]],
    }],
  };
  adminApi.updateAdminTrainingTemplateSlot.mockResolvedValue(updatedTemplate);
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <AdminTrainingTemplatesPage />
    </MemoryRouter>,
  );

  await user.click(screen.getByRole("tab", { name: "4 روزه" }));
  await user.click(await screen.findByRole("button", { name: "باز کردن برنامه: تفکیک کلاسیک چهار روزه" }));
  await user.click(screen.getByRole("button", { name: "باز کردن روز 1: سینه + پشت بازو" }));
  await user.click(screen.getByRole("button", { name: "ویرایش حرکت: پرس سینه دمبل" }));

  expect(screen.getByRole("dialog", { name: "ویرایش حرکت: پرس سینه دمبل" })).toBeInTheDocument();
  await user.clear(screen.getByRole("spinbutton", { name: "ست" }));
  await user.type(screen.getByRole("spinbutton", { name: "ست" }), "5");
  await user.click(screen.getByRole("button", { name: "ذخیره حرکت" }));

  expect(adminApi.updateAdminTrainingTemplateSlot).toHaveBeenCalledWith(
    "1",
    "day-1",
    "slot-1",
    expect.objectContaining({ sets: 5, rep_min: 8, rep_max: 12, target_rir: 2 }),
  );
  expect(await screen.findByText("پرس سینه جایگزین")).toBeInTheDocument();
  expect(screen.getByText("تغییر حرکت ذخیره شد.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "بستن روز 1: سینه + پشت بازو" })).toBeInTheDocument();
});

it("cancels an exercise edit without saving", async () => {
  adminApi.getAdminTrainingProgramTemplates.mockResolvedValue({ items: templates });
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <AdminTrainingTemplatesPage />
    </MemoryRouter>,
  );

  await user.click(screen.getByRole("tab", { name: "4 روزه" }));
  await user.click(await screen.findByRole("button", { name: "باز کردن برنامه: تفکیک کلاسیک چهار روزه" }));
  await user.click(screen.getByRole("button", { name: "باز کردن روز 1: سینه + پشت بازو" }));
  await user.click(screen.getByRole("button", { name: "ویرایش حرکت: پرس سینه دمبل" }));
  await user.click(screen.getByRole("button", { name: "انصراف" }));

  expect(screen.queryByRole("dialog", { name: "ویرایش حرکت: پرس سینه دمبل" })).not.toBeInTheDocument();
  expect(adminApi.updateAdminTrainingTemplateSlot).not.toHaveBeenCalled();
});
