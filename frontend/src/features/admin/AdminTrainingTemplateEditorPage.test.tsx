import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const adminApi = vi.hoisted(() => ({
  createAdminTrainingProgramTemplate: vi.fn(),
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

it("creates a new program with the selected day and level defaults", async () => {
  render(
    <MemoryRouter initialEntries={["/admin/training-program-templates/new?days=4&level=intermediate"]}>
      <Routes>
        <Route path="/admin/training-program-templates/new" element={<AdminTrainingTemplateEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { name: "افزودن برنامه تمرینی" })).toBeInTheDocument();
  expect(screen.getByLabelText("تعداد روز تمرین")).toHaveValue("4");
  expect(screen.getByLabelText("سطح تمرین")).toHaveValue("intermediate");
  expect(screen.getAllByText("روز 1")).toHaveLength(1);
  expect(screen.getAllByRole("button", { name: "افزودن حرکت" })).toHaveLength(4);
});

it("searches the exercise library, links a movement, and removes a slot", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/training-program-templates/new?days=2&level=beginner"]}>
      <Routes>
        <Route path="/admin/training-program-templates/new" element={<AdminTrainingTemplateEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await screen.findByRole("heading", { name: "افزودن برنامه تمرینی" });
  await user.click(screen.getAllByRole("button", { name: "افزودن حرکت" })[0]);
  await user.type(screen.getByPlaceholderText("جست‌وجو در کتابخانه حرکات"), "bench");
  await user.click(await screen.findByRole("button", { name: "انتخاب پرس سینه دمبل" }));

  expect(screen.getByText("پرس سینه دمبل")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "حذف پرس سینه دمبل" }));
  expect(screen.queryByText("پرس سینه دمبل")).not.toBeInTheDocument();
});
