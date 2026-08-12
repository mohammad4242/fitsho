import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const adminApi = vi.hoisted(() => ({
  getAdminMealCatalogue: vi.fn(),
  uploadAdminMealImage: vi.fn(),
}));
vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-08-11", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminMealCataloguePage } from "./AdminMealCataloguePage";

beforeEach(() => {
  adminApi.getAdminMealCatalogue.mockReset();
  adminApi.getAdminMealCatalogue.mockImplementation((category: string) => Promise.resolve({
    categories: ["breakfast", "lunch", "post_workout", "snack", "dinner"],
    items: category === "breakfast" ? [{
      id: "meal-1",
      code: "BF02",
      name_fa: "تخم‌مرغ نیمرو با نان و گوجه خردشده",
      name_en: "Fried eggs with bread and chopped tomato",
      image_url: null,
      category: "breakfast",
      verification_status: "draft",
      totals: { energy_kcal: 420 },
      items: [{
        food_id: "food-1", food_slug: "egg", food_name_fa: "تخم‌مرغ", food_name_en: "Egg",
        reference_grams: 100, min_grams: 50, max_grams: 200, is_required: true,
        functional_role: "protein",
      }],
    }] : [],
  }));
});

it("shows all five categories and meals linked for editing", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><AdminMealCataloguePage /></MemoryRouter>);

  expect(await screen.findByText("تخم‌مرغ نیمرو با نان و گوجه خردشده")).toBeInTheDocument();
  expect(screen.getByText(/BF02/)).toBeInTheDocument();
  expect(screen.getAllByRole("tab")).toHaveLength(5);
  expect(screen.getByRole("tab", { name: "صبحانه" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("۵۰ تا ۲۰۰ گرم")).toBeInTheDocument();
  expect(screen.getByText("الزامی")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "تصویر پیش‌فرض تخم‌مرغ نیمرو با نان و گوجه خردشده" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "ویرایش وعده: تخم‌مرغ نیمرو با نان و گوجه خردشده" })).toHaveAttribute(
    "href", "/admin/nutrition-meals/meal-1/edit",
  );
  expect(screen.getByRole("link", { name: "افزودن وعده" })).toHaveAttribute(
    "href", "/admin/nutrition-meals/new?category=breakfast",
  );

  await user.click(screen.getByRole("tab", { name: "ناهار" }));
  expect(adminApi.getAdminMealCatalogue).toHaveBeenLastCalledWith("lunch");
});

it("shows meal thumbnails and replaces an uploaded image", async () => {
  const user = userEvent.setup();
  adminApi.getAdminMealCatalogue.mockResolvedValue({
    categories: ["breakfast", "lunch", "post_workout", "snack", "dinner"],
    items: [{
      id: "meal-1", code: "BF02", name_fa: "املت", name_en: "Omelette",
      image_url: "/media/meal-catalogue/omelette.png", category: "breakfast",
      verification_status: "verified", totals: {}, items: [],
    }],
  });
  adminApi.uploadAdminMealImage.mockResolvedValue({
    image_url: "/media/meal-catalogue/replacement.png",
  });
  render(<MemoryRouter><AdminMealCataloguePage /></MemoryRouter>);

  expect(await screen.findByRole("img", { name: "املت" })).toHaveAttribute(
    "src", "/media/meal-catalogue/omelette.png",
  );
  await user.click(screen.getByRole("button", { name: "جایگزینی تصویر املت" }));
  const file = new File(["image"], "replacement.png", { type: "image/png" });
  await user.upload(screen.getByLabelText("تصویر وعده"), file);
  await user.click(screen.getByRole("button", { name: "ذخیره تصویر" }));

  expect(adminApi.uploadAdminMealImage).toHaveBeenCalledWith("meal-1", file);
  expect(await screen.findByRole("img", { name: "املت" })).toHaveAttribute(
    "src", "/media/meal-catalogue/replacement.png",
  );
});
