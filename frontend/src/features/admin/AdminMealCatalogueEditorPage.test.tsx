import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const adminApi = vi.hoisted(() => ({
  createAdminMeal: vi.fn(),
  getAdminFoodCatalogue: vi.fn(),
  getAdminMeal: vi.fn(),
  updateAdminMeal: vi.fn(),
  previewAdminPreparedRecipe: vi.fn(),
}));
vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-08-11", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminMealCatalogueEditorPage } from "./AdminMealCatalogueEditorPage";

beforeEach(() => {
  Object.values(adminApi).forEach((mock) => mock.mockReset());
  adminApi.getAdminFoodCatalogue.mockResolvedValue({
    items: [{
      id: "food-1", slug: "egg", name_fa: "تخم‌مرغ", name_en: "Egg", image_url: null,
      category: "eggs", measurement_basis: "raw", nutrient_basis: { quantity: "100", unit: "g" },
      portions: [], macros: { energy_kcal: "143", protein_g: "12.56", carbohydrate_g: "0.72", total_fat_g: "9.51", fibre_g: "0" },
      nutrients: [], source: { name: "USDA", reference: "https://example.test", source_food_id: "1", data_version: "v1", access_date: "2026-08-11" },
      price: { status: "accepted", reference_price_irr: "1000", reference_unit: "IRR_PER_KG" },
    }], page: 1, page_size: 20, total: 1, categories: ["eggs"],
  });
  adminApi.previewAdminPreparedRecipe.mockResolvedValue({
    final_cooked_yield_grams: 250,
    nutrients_per_100g: { energy_kcal: 150, protein_g: 12, iron_mg: 2.5 },
    estimated_cost_irr_per_100g: 40000,
    price_reference_ids: ["price-1"],
  });
});

it("switches to Prepared Recipe and recalculates a bounded recipe preview", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/nutrition-meals/new?category=lunch"]}>
      <Routes>
        <Route path="/admin/nutrition-meals/new" element={<AdminMealCatalogueEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await user.click(screen.getByLabelText("محاسبه به‌صورت غذای پخته"));

  expect(screen.getByRole("heading", { name: "دستور پخت آماده" })).toBeInTheDocument();
  expect(screen.getByLabelText("وزن نهایی غذای پخته (گرم)")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "افزودن ماده اولیه دستور پخت" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "افزودن محدودیت نسبت" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "ثبت شکاف داده" })).toBeInTheDocument();

  await user.type(screen.getByLabelText("نام منبع دستور پخت"), "Test kitchen");
  await user.type(screen.getByLabelText("پیوند منبع دستور پخت"), "https://example.test/recipe");

  await user.click(screen.getByRole("button", { name: "افزودن ماده اولیه دستور پخت" }));
  await user.type(screen.getByPlaceholderText("جست‌وجو در کاتالوگ مواد غذایی"), "تخم");
  await user.click(await screen.findByRole("button", { name: "انتخاب تخم‌مرغ" }));
  await user.clear(screen.getByLabelText("وزن نهایی غذای پخته (گرم)"));
  await user.type(screen.getByLabelText("وزن نهایی غذای پخته (گرم)"), "250");

  expect(await screen.findByText("150 kcal / 100 g")).toBeInTheDocument();
  expect(screen.getByText("iron_mg: 2.5")).toBeInTheDocument();
  expect(adminApi.previewAdminPreparedRecipe).toHaveBeenCalled();
});

it("shows a missing Food Catalogue ingredient as a visible data gap", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/nutrition-meals/new?category=lunch"]}>
      <Routes>
        <Route path="/admin/nutrition-meals/new" element={<AdminMealCatalogueEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await user.click(screen.getByLabelText("محاسبه به‌صورت غذای پخته"));
  await user.click(screen.getByRole("button", { name: "ثبت شکاف داده" }));
  await user.type(screen.getByLabelText("نام فارسی ماده موجودنیست"), "پیاز مخصوص");
  await user.type(screen.getByLabelText("نام انگلیسی ماده موجودنیست"), "Special onion");

  expect(screen.getByText("پیاز مخصوص در کاتالوگ مواد غذایی وجود ندارد")).toBeInTheDocument();
});

it("adds a food-catalogue ingredient and captures bounded planner inputs", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/nutrition-meals/new?category=post_workout"]}>
      <Routes>
        <Route path="/admin/nutrition-meals/new" element={<AdminMealCatalogueEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { name: "افزودن وعده غذایی" })).toBeInTheDocument();
  expect(screen.getByLabelText("کد وعده")).toBeEnabled();
  expect(screen.getByLabelText("دسته وعده")).toHaveValue("post_workout");
  await user.click(screen.getByRole("button", { name: "افزودن ماده غذایی" }));
  await user.type(screen.getByPlaceholderText("جست‌وجو در کاتالوگ مواد غذایی"), "تخم");
  await user.click(await screen.findByRole("button", { name: "انتخاب تخم‌مرغ" }));

  expect(screen.getByText("تخم‌مرغ")).toBeInTheDocument();
  expect(screen.getByLabelText("مقدار مرجع تخم‌مرغ")).toHaveValue(100);
  expect(screen.getByLabelText("حداقل گرم تخم‌مرغ")).toHaveValue(50);
  expect(screen.getByLabelText("حداکثر گرم تخم‌مرغ")).toHaveValue(200);
  expect(screen.getByLabelText("نقش تخم‌مرغ")).toHaveValue("protein");
  expect(screen.getByLabelText("تخم‌مرغ الزامی است")).toBeChecked();
});

it("shows an existing meal code as immutable while editing", async () => {
  adminApi.getAdminMeal.mockResolvedValue({
    id: "meal-1",
    code: "BF02",
    name_fa: "نیمرو با نان",
    name_en: "Fried eggs with bread",
    category: "breakfast",
    verification_status: "verified",
    totals: {},
    items: [],
  });
  render(
    <MemoryRouter initialEntries={["/admin/nutrition-meals/meal-1/edit"]}>
      <Routes>
        <Route
          path="/admin/nutrition-meals/:mealId/edit"
          element={<AdminMealCatalogueEditorPage />}
        />
      </Routes>
    </MemoryRouter>,
  );

  const code = await screen.findByLabelText("کد وعده");
  expect(code).toHaveValue("BF02");
  expect(code).toBeDisabled();
});
