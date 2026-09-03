import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import "../../i18n";
import { MealCataloguePage } from "./MealCataloguePage";
import * as api from "./api";
import type { MealCatalogueResponse } from "./api";

vi.mock("./api", () => ({
  getMealCatalogue: vi.fn(),
}));

const mockData: MealCatalogueResponse = {
  categories: ["breakfast", "lunch", "post_workout", "snack", "dinner"],
  items: [
    {
      id: "meal-1",
      name_fa: "املت گوجه‌فرنگی با نان",
      name_en: "Tomato omelette with bread",
      image_url: "/media/meals/omelette.jpg",
      category: "breakfast",
    },
    {
      id: "meal-2",
      name_fa: "چلو کباب فیله مرغ با گوجه",
      name_en: "Chicken kebab with rice and tomato",
      image_url: null,
      category: "lunch",
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

it("renders meal cards in the catalogue", async () => {
  vi.mocked(api.getMealCatalogue).mockResolvedValueOnce(mockData);

  render(<MealCataloguePage />);

  expect(screen.getByRole("status")).toHaveTextContent("در حال دریافت وعده‌ها…");

  const title = await screen.findByRole("heading", { level: 1, name: "کاتالوگ وعده‌های غذایی" });
  expect(title).toBeInTheDocument();

  const cards = screen.getAllByRole("listitem");
  expect(cards).toHaveLength(2);
  expect(within(cards[0]).getByText("املت گوجه‌فرنگی با نان")).toBeInTheDocument();
  expect(within(cards[0]).getByText("صبحانه")).toBeInTheDocument();
  expect(within(cards[1]).getByText("چلو کباب فیله مرغ با گوجه")).toBeInTheDocument();
  expect(within(cards[1]).getByText("ناهار")).toBeInTheDocument();

  // Verify no admin-specific controls are present
  expect(screen.queryByText("ویرایش وعده")).not.toBeInTheDocument();
  expect(screen.queryByText("افزودن وعده")).not.toBeInTheDocument();
  expect(screen.queryByText("بارگذاری تصویر")).not.toBeInTheDocument();
});

it("filters by category when a category chip is selected", async () => {
  const user = userEvent.setup();
  vi.mocked(api.getMealCatalogue).mockResolvedValue(mockData);

  render(<MealCataloguePage />);

  await screen.findByText("املت گوجه‌فرنگی با نان");

  const breakfastChip = screen.getByRole("tab", { name: "صبحانه" });
  await user.click(breakfastChip);

  expect(api.getMealCatalogue).toHaveBeenCalledWith("breakfast");
});

it("renders empty state when category has no items", async () => {
  vi.mocked(api.getMealCatalogue).mockResolvedValueOnce({
    categories: ["breakfast", "lunch", "dinner", "snack", "post_workout"],
    items: [],
  });

  render(<MealCataloguePage />);

  expect(await screen.findByText("در این دسته وعده‌ای یافت نشد.")).toBeInTheDocument();
});

it("renders error state and retries successfully", async () => {
  const user = userEvent.setup();
  vi.mocked(api.getMealCatalogue)
    .mockRejectedValueOnce(new Error("Network failure"))
    .mockResolvedValueOnce(mockData);

  render(<MealCataloguePage />);

  const retryButton = await screen.findByRole("button", { name: "تلاش دوباره" });
  expect(screen.getByText("کاتالوگ وعده‌ها دریافت نشد.")).toBeInTheDocument();

  await user.click(retryButton);

  expect(await screen.findByText("املت گوجه‌فرنگی با نان")).toBeInTheDocument();
});
