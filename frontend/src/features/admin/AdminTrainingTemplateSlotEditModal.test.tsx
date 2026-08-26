import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

const exercisesApi = vi.hoisted(() => ({ getExerciseCategories: vi.fn() }));
const adminApi = vi.hoisted(() => ({
  deleteAdminTrainingTemplateSlot: vi.fn(),
  getAdminExercises: vi.fn(),
  updateAdminTrainingTemplateSlot: vi.fn(),
}));

vi.mock("../exercises/api", () => exercisesApi);
vi.mock("./api", () => adminApi);

import { AdminTrainingTemplateSlotEditModal } from "./AdminTrainingTemplateSlotEditModal";
import type { AdminTrainingProgramTemplate, AdminTrainingTemplateSlot } from "./types";

const slot: AdminTrainingTemplateSlot = {
  id: "slot-1",
  slot_order: 1,
  exercise_slug_hint: "old-press",
  placeholder_name_en: null,
  placeholder_name_fa: null,
  target_muscles: ["chest"],
  movement_pattern: "horizontal_push",
  intensity_method: "standard",
  adaptation_priority: "core",
  superset_group: null,
  superset_exercise_id: null,
  sets: 3,
  rep_min: 8,
  rep_max: 12,
  target_rir: 2,
  rest_seconds: 90,
  exercise: {
    id: "old-exercise",
    slug: "old-press",
    name_en: "Old Press",
    name_fa: "پرس قبلی",
    needs_review: false,
  },
  superset_exercise: null,
};

const replacement = {
  id: "new-exercise",
  slug: "new-press",
  name_en: "New Press",
  name_fa: "پرس جایگزین",
  primary_muscle: "chest",
  secondary_muscles: ["triceps"],
  movement_pattern: "horizontal_push",
  needs_review: false,
};

const categories = {
  body_regions: [
    { value: "upper_body", name_en: "Upper Body", name_fa: "بالاتنه" },
    { value: "lower_body", name_en: "Lower Body", name_fa: "پایین‌تنه" },
    { value: "core", name_en: "Core", name_fa: "میان‌تنه" },
  ],
  upper_body: [{ value: "chest", name_en: "Chest", name_fa: "سینه" }],
  lower_body: [],
  core: [],
  muscle_focuses: { chest: [] },
};

beforeEach(() => {
  vi.clearAllMocks();
  exercisesApi.getExerciseCategories.mockResolvedValue(categories);
  adminApi.getAdminExercises.mockResolvedValue({ items: [replacement], total: 1 });
  adminApi.updateAdminTrainingTemplateSlot.mockResolvedValue({} as AdminTrainingProgramTemplate);
});

it("replaces the slot through the existing exercise library picker", async () => {
  const user = userEvent.setup();
  render(
    <AdminTrainingTemplateSlotEditModal
      dayId="day-1"
      onClose={vi.fn()}
      onSaved={vi.fn()}
      slot={slot}
      templateId="template-1"
    />,
  );

  await user.click(screen.getByRole("button", { name: "تغییر حرکت از کتابخانه" }));
  await user.click(await screen.findByRole("button", { name: /بالاتنه/ }));
  await user.click(await screen.findByRole("button", { name: /سینه/ }));
  await user.click(await screen.findByRole("button", { name: /انتخاب پرس جایگزین/ }));
  await user.click(screen.getByRole("button", { name: "ذخیره حرکت" }));

  expect(adminApi.updateAdminTrainingTemplateSlot).toHaveBeenCalledWith(
    "template-1",
    "day-1",
    "slot-1",
    expect.objectContaining({
      exercise_id: "new-exercise",
      movement_pattern: "horizontal_push",
      target_muscles: ["chest", "triceps"],
    }),
  );
});
