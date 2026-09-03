import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import "../../i18n";
import { ApiError } from "../../shared/apiClient";
import { MealCataloguePage } from "./MealCataloguePage";
import * as api from "./api";
import type { MealCatalogueResponse } from "./api";

const auth = vi.hoisted(() => ({ isAdmin: false }));
const adminApi = vi.hoisted(() => ({
  uploadAdminMealImage: vi.fn(),
  deleteAdminMeal: vi.fn(),
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "user-1", email: "user@example.com", is_admin: auth.isAdmin },
    logout: vi.fn(),
  }),
}));

vi.mock("../admin/api", () => adminApi);

vi.mock("./api", () => ({
  getMealCatalogue: vi.fn(),
}));

const mockData: MealCatalogueResponse = {
  categories: ["breakfast", "lunch", "post_workout", "snack", "dinner"],
  items: [
    {
      id: "meal-1",
      code: "BF01",
      name_fa: "املت گوجه‌فرنگی با نان",
      name_en: "Tomato omelette with bread",
      image_url: "/media/meals/omelette.jpg",
      category: "breakfast",
      verification_status: "verified",
      calculation_mode: "simple",
      items: [
        {
          food_id: "food-1",
          food_slug: "egg",
          food_name_fa: "تخم‌مرغ",
          food_name_en: "Egg",
          reference_grams: 100,
          min_grams: 50,
          max_grams: 150,
          is_required: true,
          functional_role: "primary_protein",
        },
      ],
    },
    {
      id: "meal-2",
      code: "LN01",
      name_fa: "چلو کباب فیله مرغ با گوجه",
      name_en: "Chicken kebab with rice and tomato",
      image_url: null,
      category: "lunch",
      verification_status: "draft",
      calculation_mode: "simple",
      items: [
        {
          food_id: "food-2",
          food_slug: "chicken-breast",
          food_name_fa: "فیله مرغ",
          food_name_en: "Chicken Breast",
          reference_grams: 150,
          min_grams: 100,
          max_grams: 250,
          is_required: true,
          functional_role: "primary_protein",
        },
      ],
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  auth.isAdmin = false;
});

it("renders rich meal cards with details disclosure for non-admin members", async () => {
  auth.isAdmin = false;
  vi.mocked(api.getMealCatalogue).mockResolvedValueOnce(mockData);

  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MealCataloguePage />
    </MemoryRouter>,
  );

  expect(screen.getByRole("status")).toHaveTextContent("در حال دریافت وعده‌ها…");

  const title = await screen.findByRole("heading", { level: 1, name: "کاتالوگ وعده‌های غذایی" });
  expect(title).toBeInTheDocument();

  const cards = document.querySelectorAll(".admin-meal-card");
  expect(cards).toHaveLength(2);
  expect(within(cards[0] as HTMLElement).getByText("املت گوجه‌فرنگی با نان")).toBeInTheDocument();
  expect(within(cards[0] as HTMLElement).getByText(/BF01/)).toBeInTheDocument();
  expect(within(cards[0] as HTMLElement).getByText("تأییدشده")).toBeInTheDocument();

  // Test disclosure opens and reveals ingredients
  const firstDetails = (cards[0] as HTMLElement).querySelector("details");
  expect(firstDetails).not.toHaveAttribute("open");

  await user.click(within(cards[0] as HTMLElement).getByText("املت گوجه‌فرنگی با نان"));
  expect(firstDetails).toHaveAttribute("open");
  expect(within(cards[0] as HTMLElement).getByText("تخم‌مرغ")).toBeInTheDocument();
  expect(within(cards[0] as HTMLElement).getByText("۵۰ تا ۱۵۰ گرم")).toBeInTheDocument();
  expect(within(cards[0] as HTMLElement).getByText("الزامی")).toBeInTheDocument();

  // Non-admin members must NOT see management controls
  expect(screen.queryByText("ویرایش وعده")).not.toBeInTheDocument();
  expect(screen.queryByText("افزودن وعده")).not.toBeInTheDocument();
  expect(screen.queryByText("بارگذاری تصویر")).not.toBeInTheDocument();
  expect(screen.queryByText("جایگزینی تصویر")).not.toBeInTheDocument();
  expect(screen.queryByText("حذف وعده")).not.toBeInTheDocument();
});

it("filters by category when a category chip is selected", async () => {
  vi.mocked(api.getMealCatalogue).mockResolvedValue(mockData);

  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MealCataloguePage />
    </MemoryRouter>,
  );

  await screen.findByText("املت گوجه‌فرنگی با نان");

  const breakfastChip = screen.getByRole("tab", { name: "صبحانه" });
  await user.click(breakfastChip);

  expect(api.getMealCatalogue).toHaveBeenCalledWith("breakfast", undefined);
});

it("shows admin actions, status filter, edit, upload image, and delete for administrators", async () => {
  auth.isAdmin = true;
  vi.mocked(api.getMealCatalogue).mockResolvedValue(mockData);

  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MealCataloguePage />
    </MemoryRouter>,
  );

  expect(await screen.findByText("املت گوجه‌فرنگی با نان")).toBeInTheDocument();

  // Admin add button
  const addLink = screen.getByRole("link", { name: "افزودن وعده" });
  expect(addLink).toHaveAttribute("href", "/admin/nutrition-meals/new?category=breakfast");

  // Status filter options
  const statusTablist = screen.getByRole("tablist", { name: "وضعیت" });
  expect(within(statusTablist).getByRole("tab", { name: "منتشرشده" })).toBeInTheDocument();
  expect(within(statusTablist).getByRole("tab", { name: "پیش‌نویس" })).toBeInTheDocument();
  expect(within(statusTablist).getByRole("tab", { name: "همه" })).toBeInTheDocument();

  // Open first meal disclosure
  await user.click(screen.getByText("املت گوجه‌فرنگی با نان"));

  // Admin controls in footer
  expect(screen.getByRole("link", { name: "ویرایش وعده: املت گوجه‌فرنگی با نان" })).toHaveAttribute(
    "href",
    "/admin/nutrition-meals/meal-1/edit",
  );
  expect(screen.getByRole("button", { name: "جایگزینی تصویر املت گوجه‌فرنگی با نان" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "حذف وعده: املت گوجه‌فرنگی با نان" })).toBeInTheDocument();
});

it("allows administrator to upload and replace a meal image", async () => {
  auth.isAdmin = true;
  vi.mocked(api.getMealCatalogue).mockResolvedValue(mockData);
  adminApi.uploadAdminMealImage.mockResolvedValueOnce({
    image_url: "/media/meals/new-omelette.jpg",
  });

  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MealCataloguePage />
    </MemoryRouter>,
  );

  await screen.findByText("املت گوجه‌فرنگی با نان");
  await user.click(screen.getByText("املت گوجه‌فرنگی با نان"));

  const replaceBtn = screen.getByRole("button", { name: "جایگزینی تصویر املت گوجه‌فرنگی با نان" });
  await user.click(replaceBtn);

  const dialog = screen.getByRole("dialog", { name: "تصویر وعده املت گوجه‌فرنگی با نان" });
  expect(dialog).toBeInTheDocument();

  const file = new File(["dummy"], "new-omelette.jpg", { type: "image/jpeg" });
  const fileInput = within(dialog).getByLabelText("تصویر وعده");
  await user.upload(fileInput, file);

  const saveBtn = screen.getByRole("button", { name: "ذخیره تصویر" });
  await user.click(saveBtn);

  expect(adminApi.uploadAdminMealImage).toHaveBeenCalledWith("meal-1", file);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("allows administrator to delete an unreferenced meal through confirmation dialog", async () => {
  auth.isAdmin = true;
  vi.mocked(api.getMealCatalogue).mockResolvedValue(mockData);
  adminApi.deleteAdminMeal.mockResolvedValueOnce(undefined);

  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MealCataloguePage />
    </MemoryRouter>,
  );

  await screen.findByText("املت گوجه‌فرنگی با نان");
  await user.click(screen.getByText("املت گوجه‌فرنگی با نان"));

  const deleteBtn = screen.getByRole("button", { name: "حذف وعده: املت گوجه‌فرنگی با نان" });
  await user.click(deleteBtn);

  // Dialog opened
  expect(screen.getByRole("dialog", { name: "تأیید حذف وعده غذایی" })).toBeInTheDocument();
  expect(screen.getByText(/آیا از حذف وعده «املت گوجه‌فرنگی با نان» اطمینان دارید؟/)).toBeInTheDocument();

  const confirmBtn = screen.getByRole("button", { name: "حذف قطعی" });
  await user.click(confirmBtn);

  expect(adminApi.deleteAdminMeal).toHaveBeenCalledWith("meal-1");
  // Meal 1 should be removed from the view
  expect(screen.queryByText("املت گوجه‌فرنگی با نان")).not.toBeInTheDocument();
  expect(screen.getByText("چلو کباب فیله مرغ با گوجه")).toBeInTheDocument();
});

it("displays conflict error when deleting a referenced meal (409 Conflict)", async () => {
  auth.isAdmin = true;
  vi.mocked(api.getMealCatalogue).mockResolvedValue(mockData);
  adminApi.deleteAdminMeal.mockRejectedValueOnce(
    new ApiError(409, "Meal is referenced", null, "meal_referenced"),
  );

  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MealCataloguePage />
    </MemoryRouter>,
  );

  await screen.findByText("املت گوجه‌فرنگی با نان");
  await user.click(screen.getByText("املت گوجه‌فرنگی با نان"));

  await user.click(screen.getByRole("button", { name: "حذف وعده: املت گوجه‌فرنگی با نان" }));

  const confirmBtn = screen.getByRole("button", { name: "حذف قطعی" });
  await user.click(confirmBtn);

  expect(adminApi.deleteAdminMeal).toHaveBeenCalledWith("meal-1");
  // Displays domain conflict message
  expect(
    screen.getByText("این وعده در برنامه‌ها یا پلن‌های هفتگی استفاده شده و قابل حذف نیست."),
  ).toBeInTheDocument();
  // Meal 1 is NOT removed
  expect(screen.getByText("املت گوجه‌فرنگی با نان")).toBeInTheDocument();
});

it("renders empty state when category has no items", async () => {
  vi.mocked(api.getMealCatalogue).mockResolvedValueOnce({
    categories: ["breakfast", "lunch", "dinner", "snack", "post_workout"],
    items: [],
  });

  render(
    <MemoryRouter>
      <MealCataloguePage />
    </MemoryRouter>,
  );

  expect(await screen.findByText("در این دسته وعده‌ای ثبت نشده است.")).toBeInTheDocument();
});

it("renders error state and retries successfully", async () => {
  const user = userEvent.setup();
  vi.mocked(api.getMealCatalogue)
    .mockRejectedValueOnce(new Error("Network failure"))
    .mockResolvedValueOnce(mockData);

  render(
    <MemoryRouter>
      <MealCataloguePage />
    </MemoryRouter>,
  );

  const retryButton = await screen.findByRole("button", { name: "تلاش دوباره" });
  expect(screen.getByText("کاتالوگ وعده‌ها دریافت نشد.")).toBeInTheDocument();

  await user.click(retryButton);

  expect(await screen.findByText("املت گوجه‌فرنگی با نان")).toBeInTheDocument();
});
