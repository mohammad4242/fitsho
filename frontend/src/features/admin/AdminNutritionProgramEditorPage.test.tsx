import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const adminApi = vi.hoisted(() => ({
  createAdminNutritionProgram: vi.fn(),
  getAdminMealCatalogue: vi.fn(),
  getAdminNutritionProgram: vi.fn(),
  updateAdminNutritionProgram: vi.fn(),
}));
vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-08-12", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminNutritionProgramEditorPage } from "./AdminNutritionProgramEditorPage";

const categories = ["breakfast", "lunch", "post_workout", "snack", "dinner"] as const;
const meals = Object.fromEntries(categories.map((category) => [category, {
  id: `meal-${category}`,
  name_fa: `وعده ${category}`,
  name_en: `${category} meal`,
  category,
  verification_status: "verified",
  items: [],
  totals: {},
}]));

const program = {
  id: "program-1",
  slug: "economy-week",
  name_fa: "هفته اقتصادی",
  name_en: "Economy week",
  description_fa: "ساختار اقتصادی",
  description_en: "Economy structure",
  diet_style: "economy",
  budget_tier_hint: "economy" as const,
  post_workout_enabled: true,

  is_active: true,
  archived_at: null,
  created_at: "2026-08-12T10:00:00Z",
  updated_at: "2026-08-12T10:00:00Z",
  days: Array.from({ length: 7 }, (_, index) => ({
    id: `day-${index + 1}`,
    day_number: index + 1,
    post_workout_enabled: index === 0,
    slots: ["breakfast", "lunch", "snack", "dinner", ...(index === 0 ? ["post_workout"] : [])].map((category) => ({
      id: `slot-${index + 1}-${category}`,
      category,
      meal: meals[category],
    })),
  })),
};

beforeEach(() => {
  Object.values(adminApi).forEach((mock) => mock.mockReset());
  adminApi.getAdminNutritionProgram.mockResolvedValue(program);
  adminApi.getAdminMealCatalogue.mockImplementation((category: string) => Promise.resolve({
    items: [meals[category]],
    categories,
  }));
  adminApi.updateAdminNutritionProgram.mockResolvedValue(program);
  adminApi.createAdminNutritionProgram.mockResolvedValue(program);
});

it("renders seven days and saves global post-workout with per-day overrides", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/nutrition-programs/program-1/edit"]}>
      <Routes>
        <Route path="/admin/nutrition-programs/:programId/edit" element={<AdminNutritionProgramEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { name: "ویرایش برنامه غذایی" })).toBeInTheDocument();
  expect(screen.getAllByRole("group", { name: /روز / })).toHaveLength(7);
  const dailyPostWorkout = screen.getAllByLabelText(/وعده پس از تمرین برای روز/);
  expect(dailyPostWorkout[0]).toBeChecked();
  expect(dailyPostWorkout[1]).not.toBeChecked();

  await user.click(dailyPostWorkout[1]);
  await user.selectOptions(screen.getByLabelText(/انتخاب پس از تمرین روز 2/), "meal-post_workout");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(adminApi.updateAdminNutritionProgram).toHaveBeenCalledWith(
    "program-1",
    expect.objectContaining({
      diet_style: "economy",
      budget_tier_hint: "economy",
      post_workout_enabled: true,

      days: expect.arrayContaining([
        expect.objectContaining({
          day_number: 2,
          post_workout_enabled: true,
          slots: expect.arrayContaining([
            { category: "post_workout", meal_id: "meal-post_workout" },
          ]),
        }),
      ]),
    }),
  );
});

it("disables every daily override when global post-workout is disabled", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/nutrition-programs/program-1/edit"]}>
      <Routes>
        <Route path="/admin/nutrition-programs/:programId/edit" element={<AdminNutritionProgramEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );
  await screen.findByRole("heading", { name: "ویرایش برنامه غذایی" });

  await user.click(screen.getByLabelText("فعال‌سازی وعده پس از تمرین"));

  expect(screen.queryByLabelText("وعده پس از تمرین برای روز ۱")).not.toBeInTheDocument();
});
