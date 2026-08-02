import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const adminApi = vi.hoisted(() => ({ getAdminTrainingProgramTemplates: vi.fn() }));
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
  training_level: "intermediate" as const,
  fitness_goal: "build_muscle" as const,
  focus_tags: ["classic", "direct_targets"],
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
    training_level: "beginner" as const,
  },
  {
    ...template,
    id: "3",
    slug: "four-day-advanced-chest",
    name_fa: "تخصصی سینه چهارروزه پیشرفته",
    training_level: "advanced" as const,
  },
];

beforeEach(() => {
  adminApi.getAdminTrainingProgramTemplates.mockReset();
});

it("filters the library by day count and training level", async () => {
  adminApi.getAdminTrainingProgramTemplates.mockImplementation((days: number) => (
    days === 4 ? Promise.resolve({ items: templates }) : new Promise(() => {})
  ));
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <AdminTrainingTemplatesPage />
    </MemoryRouter>,
  );

  await user.click(screen.getByRole("tab", { name: "4 روزه" }));

  expect(await screen.findByText("تفکیک کلاسیک چهار روزه")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "متوسط" })).toBeInTheDocument();
  expect(screen.getAllByText("سینه + پشت بازو")).toHaveLength(3);
  expect(screen.getAllByText("پرس سینه دمبل")).toHaveLength(3);
  expect(screen.getAllByText("پلاور کابل")).toHaveLength(3);
  expect(screen.getAllByText("نیازمند ویدیو و بازبینی")).toHaveLength(3);
  expect(screen.getAllByRole("link", { name: "جزئیات حرکت: پرس سینه دمبل" })).toHaveLength(3);
  expect(screen.getAllByRole("link", { name: "جزئیات حرکت: پلاور کابل" })).toHaveLength(3);
  expect(screen.getAllByRole("link", { name: "ویرایش برنامه: تفکیک کلاسیک چهار روزه" })).toHaveLength(1);
  expect(screen.getByRole("link", { name: "افزودن برنامه جدید" })).toHaveAttribute(
    "href",
    "/admin/training-program-templates/new?days=4&level=beginner",
  );
  expect(screen.getAllByText("منطق برنامه")).toHaveLength(3);
  expect(screen.getAllByText("ترتیب حرکات")).toHaveLength(3);
  expect(adminApi.getAdminTrainingProgramTemplates).toHaveBeenCalledWith(4);

  await user.click(screen.getByRole("tab", { name: "پیشرفته" }));

  expect(await screen.findByText("تخصصی سینه چهارروزه پیشرفته")).toBeInTheDocument();
  expect(screen.queryByText("تفکیک کلاسیک چهار روزه")).not.toBeInTheDocument();
});
