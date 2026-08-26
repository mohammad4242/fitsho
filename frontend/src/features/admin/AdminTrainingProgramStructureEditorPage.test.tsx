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
