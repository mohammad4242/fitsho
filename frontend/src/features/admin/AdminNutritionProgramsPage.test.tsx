import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const adminApi = vi.hoisted(() => ({
  archiveAdminNutritionProgram: vi.fn(),
  getAdminNutritionPrograms: vi.fn(),
  restoreAdminNutritionProgram: vi.fn(),
}));
vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-08-12", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminNutritionProgramsPage } from "./AdminNutritionProgramsPage";

const program = {
  id: "program-1",
  code: "IRN01",
  slug: "iranian-week",
  name_fa: "هفته ایرانی متعادل",
  name_en: "Balanced Iranian week",
  description_fa: "ساختار هفت‌روزه",
  description_en: "Seven-day structure",
  diet_style: "balanced_iranian",
  post_workout_enabled: true,
  is_active: true,
  archived_at: null,
  created_at: "2026-08-12T10:00:00Z",
  updated_at: "2026-08-12T10:00:00Z",
  days: Array.from({ length: 7 }, (_, index) => ({
    id: `day-${index + 1}`,
    day_number: index + 1,
    post_workout_enabled: index === 0,
    slots: index === 6 ? [{ id: "free-slot", kind: "free_meal", category: "lunch", meal: null }] : [{
      id: `slot-${index + 1}`,
      kind: "catalogue_meal",
      category: "breakfast",
      meal: {
        id: "meal-1", code: "BF01", name_fa: "املت", name_en: "Omelette",
        image_url: "/media/meal-catalogue/omelette.png", category: "breakfast",
      },
    }],
  })),
};

beforeEach(() => {
  Object.values(adminApi).forEach((mock) => mock.mockReset());
  adminApi.getAdminNutritionPrograms.mockResolvedValue({
    items: [program],
    diet_styles: ["economy", "balanced_iranian", "high_protein_gym", "quick_easy", "premium_varied"],
  });
  adminApi.archiveAdminNutritionProgram.mockResolvedValue(undefined);
  adminApi.restoreAdminNutritionProgram.mockResolvedValue(program);
});

it("filters weekly programs by diet style and archives them", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter initialEntries={["/admin/nutrition-programs"]}><AdminNutritionProgramsPage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "کاتالوگ برنامه‌های غذایی" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "کاتالوگ برنامه‌های غذایی" })).toHaveAttribute("href", "/admin/nutrition-programs");
  expect(screen.queryByRole("img", { name: "املت" })).not.toBeInTheDocument();
  expect(screen.queryByText("وعده آزاد")).not.toBeInTheDocument();
  expect(screen.queryByText(/روز /)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "باز کردن برنامه: هفته ایرانی متعادل" })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  expect(screen.getByRole("link", { name: "ویرایش هفته ایرانی متعادل" })).toHaveAttribute(
    "href", "/admin/nutrition-programs/program-1/edit",
  );

  await user.click(screen.getByRole("button", { name: "باز کردن برنامه: هفته ایرانی متعادل" }));

  expect(screen.getAllByText(/روز /)).toHaveLength(7);
  expect(screen.queryByRole("img", { name: "املت" })).not.toBeInTheDocument();
  expect(screen.queryByText("وعده آزاد")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "باز کردن روز 1" })).toHaveAttribute("aria-expanded", "false");

  await user.click(screen.getByRole("button", { name: "باز کردن روز 1" }));

  expect(screen.getByRole("img", { name: "املت" })).toHaveAttribute(
    "src", "/media/meal-catalogue/omelette.png",
  );
  expect(screen.getByText(/BF01 — املت/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "باز کردن روز 7" }));
  expect(screen.getByText("وعده آزاد")).toBeInTheDocument();

  await user.click(screen.getByRole("tab", { name: "اقتصادی" }));
  expect(adminApi.getAdminNutritionPrograms).toHaveBeenLastCalledWith({
    dietStyle: "economy",
    lifecycle: "active",
  });

  await user.click(screen.getByRole("button", { name: "آرشیو هفته ایرانی متعادل" }));
  expect(adminApi.archiveAdminNutritionProgram).toHaveBeenCalledWith("program-1");
});

it("shows archived programs and restores them", async () => {
  const user = userEvent.setup();
  adminApi.getAdminNutritionPrograms.mockResolvedValue({
    items: [{ ...program, is_active: false, archived_at: "2026-08-12T11:00:00Z" }],
    diet_styles: ["economy", "balanced_iranian", "high_protein_gym", "quick_easy", "premium_varied"],
  });
  render(<MemoryRouter initialEntries={["/admin/nutrition-programs"]}><AdminNutritionProgramsPage /></MemoryRouter>);

  await user.click(await screen.findByRole("tab", { name: "آرشیوشده" }));
  await user.click(await screen.findByRole("button", { name: "بازیابی هفته ایرانی متعادل" }));

  expect(adminApi.restoreAdminNutritionProgram).toHaveBeenCalledWith("program-1");
});
