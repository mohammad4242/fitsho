import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const adminApi = vi.hoisted(() => ({
  createAdminTrainingProgramStructure: vi.fn(),
  getAdminTrainingProgramStructure: vi.fn(),
  updateAdminTrainingProgramStructure: vi.fn(),
}));
vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-07-27", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminTrainingProgramStructureEditorPage } from "./AdminTrainingProgramStructureEditorPage";

beforeEach(() => {
  adminApi.createAdminTrainingProgramStructure.mockReset().mockResolvedValue({ id: "structure-new" });
  adminApi.getAdminTrainingProgramStructure.mockReset();
  adminApi.updateAdminTrainingProgramStructure.mockReset();
});

it("creates a five-day body-part split with ordered database days", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/training-program-structures/new"]}>
      <Routes>
        <Route path="/admin/training-program-structures/new" element={<AdminTrainingProgramStructureEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(screen.getByRole("heading", { name: "افزودن ساختار تمرینی" })).toBeInTheDocument();
  expect(screen.queryByLabelText("خانواده ساختار")).not.toBeInTheDocument();

  await user.selectOptions(screen.getByLabelText("تعداد روز تمرین"), "5");
  await user.selectOptions(screen.getByLabelText("خانواده ساختار"), "split");
  await user.selectOptions(screen.getByLabelText("نوع تقسیم Split"), "body_part");
  await user.type(screen.getByLabelText("نام فارسی ساختار"), "تقسیم عضله‌ای پنج‌روزه ب");
  await user.type(screen.getByLabelText("نام انگلیسی ساختار"), "5-Day Body-Part Split B");
  await user.type(screen.getByLabelText("شناسه یکتا"), "5d-body-part-b");
  await user.click(screen.getByRole("button", { name: "ذخیره ساختار" }));

  expect(adminApi.createAdminTrainingProgramStructure).toHaveBeenCalledWith(expect.objectContaining({
    days_per_week: 5,
    family: "split",
    split_type: "body_part",
    days: expect.arrayContaining([
      expect.objectContaining({ day_number: 1 }),
      expect.objectContaining({ day_number: 5 }),
    ]),
  }));
});

it("loads the current family on edit and preserves an upper-lower update", async () => {
  adminApi.getAdminTrainingProgramStructure.mockResolvedValue({
    id: "structure-6-upper-lower",
    slug: "six-day-upper-lower",
    name_en: "6-Day Upper / Lower",
    name_fa: "بالاتنه / پایین‌تنه شش‌روزه",
    days_per_week: 6,
    family: "upper_lower",
    split_type: null,
    description_en: null,
    description_fa: null,
    is_active: true,
    structure_days: Array.from({ length: 6 }, (_, index) => ({
      id: `day-${index + 1}`,
      day_number: index + 1,
      label_en: `Day ${index + 1}`,
      label_fa: `روز ${index + 1}`,
      day_type: "upper_lower",
    })),
  });
  adminApi.updateAdminTrainingProgramStructure.mockResolvedValue({ id: "structure-6-upper-lower" });
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/training-program-structures/structure-6-upper-lower/edit"]}>
      <Routes>
        <Route path="/admin/training-program-structures/:structureId/edit" element={<AdminTrainingProgramStructureEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByLabelText("خانواده ساختار")).toHaveValue("upper_lower");
  expect(screen.queryByLabelText("نوع تقسیم Split")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "ذخیره ساختار" }));

  expect(adminApi.updateAdminTrainingProgramStructure).toHaveBeenCalledWith(
    "structure-6-upper-lower",
    expect.objectContaining({
      days_per_week: 6,
      family: "upper_lower",
      split_type: null,
      days: expect.arrayContaining([
        expect.objectContaining({ day_number: 1 }),
        expect.objectContaining({ day_number: 6 }),
      ]),
    }),
  );
});
