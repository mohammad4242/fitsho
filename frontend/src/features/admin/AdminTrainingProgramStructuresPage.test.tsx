import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const adminApi = vi.hoisted(() => ({
  activateAdminTrainingProgramStructure: vi.fn(),
  deactivateAdminTrainingProgramStructure: vi.fn(),
  getAdminTrainingProgramStructures: vi.fn(),
}));
vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-07-27", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminTrainingProgramStructuresPage } from "./AdminTrainingProgramStructuresPage";

const structure = {
  id: "structure-1",
  slug: "5d-body-part-b",
  name_en: "5-Day Body-Part Split B",
  name_fa: "تقسیم عضله‌ای پنج‌روزه ب",
  days_per_week: 5,
  family: "split" as const,
  split_type: "body_part" as const,
  description_en: "A body-part split.",
  description_fa: "تقسیم عضلات بدن.",
  is_active: true,
  structure_days: [
    { id: "day-1", day_number: 1, label_en: "Chest + Triceps", label_fa: "سینه + پشت بازو", day_type: null },
    { id: "day-2", day_number: 2, label_en: "Back + Biceps", label_fa: "پشت + جلو بازو", day_type: null },
    { id: "day-3", day_number: 3, label_en: "Quads", label_fa: "چهارسر", day_type: null },
    { id: "day-4", day_number: 4, label_en: "Shoulders + Traps", label_fa: "سرشانه + کول", day_type: null },
    { id: "day-5", day_number: 5, label_en: "Hamstrings", label_fa: "همسترینگ", day_type: null },
  ],
};

beforeEach(() => {
  adminApi.getAdminTrainingProgramStructures.mockReset().mockResolvedValue({ items: [structure] });
  adminApi.activateAdminTrainingProgramStructure.mockReset().mockResolvedValue(structure);
  adminApi.deactivateAdminTrainingProgramStructure.mockReset().mockResolvedValue({ ...structure, is_active: false });
});

it("lists database structures and toggles activation without deleting them", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <AdminTrainingProgramStructuresPage />
    </MemoryRouter>,
  );

  expect(await screen.findByText("تقسیم عضله‌ای پنج‌روزه ب")).toBeInTheDocument();
  expect(screen.getByText("فعال")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "افزودن ساختار" })).toHaveAttribute(
    "href",
    "/admin/training-program-structures/new",
  );
  expect(screen.getByRole("link", { name: "ویرایش: تقسیم عضله‌ای پنج‌روزه ب" })).toHaveAttribute(
    "href",
    "/admin/training-program-structures/structure-1/edit",
  );

  await user.click(screen.getByRole("button", { name: "غیرفعال کردن: تقسیم عضله‌ای پنج‌روزه ب" }));
  await waitFor(() => expect(adminApi.deactivateAdminTrainingProgramStructure).toHaveBeenCalledWith("structure-1"));
  expect(screen.getByText("غیرفعال")).toBeInTheDocument();
});
