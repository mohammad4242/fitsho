import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import * as api from "./api";
import { FoodCataloguePage } from "./FoodCataloguePage";

const auth = vi.hoisted(() => ({ isAdmin: false }));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: "user-1",
      email: "member@example.com",
      created_at: "2026-08-09T00:00:00Z",
      is_admin: auth.isAdmin,
    },
  }),
}));
vi.mock("./api");

const response: api.FoodCatalogueResponse = {
  page: 1,
  page_size: 24,
  total: 1,
  categories: ["poultry"],
  items: [
    {
      id: "food-1",
      slug: "chicken-breast",
      name_fa: "سینه مرغ",
      name_en: "Chicken breast",
      category: "poultry",
      measurement_basis: "raw",
      nutrient_basis: { quantity: "100.0000", unit: "g" },
      macros: {
        energy_kcal: "120.00000000",
        protein_g: "22.50000000",
        carbohydrate_g: "0.00000000",
        total_fat_g: "2.62000000",
        fibre_g: "0.00000000",
      },
      nutrients: [
        {
          nutrient_code: "iron_mg",
          value_per_100g: 0.37,
          unit: "mg",
          unit_form: "nutrient_mass",
          source_name: "USDA FoodData Central",
          source_reference: "https://fdc.nal.usda.gov/",
          confidence: "high",
        },
        {
          nutrient_code: "vitamin_c_mg",
          value_per_100g: 12,
          unit: "mg",
          unit_form: "nutrient_mass",
          source_name: "USDA FoodData Central",
          source_reference: "https://fdc.nal.usda.gov/",
          confidence: "high",
        },
      ],
      portions: [
        {
          code: "piece",
          quantity: "1.0000",
          label_fa: "۱ عدد",
          label_en: "1 piece",
          grams: "50.0000",
          is_default: true,
          source_name: "USDA FoodData Central SR Legacy",
          source_reference: "https://fdc.nal.usda.gov/download-datasets/",
        },
      ],
      source: {
        name: "USDA FoodData Central",
        reference: "https://fdc.nal.usda.gov/",
        source_food_id: "171077",
        data_version: "2025",
        access_date: "2026-08-09",
      },
    },
  ],
};

beforeEach(async () => {
  vi.clearAllMocks();
  auth.isAdmin = false;
  await i18n.changeLanguage("fa");
  vi.mocked(api.getFoodCatalogue).mockResolvedValue(response);
  vi.mocked(api.getAdminFoodCatalogue).mockResolvedValue({ ...response, items: [{ ...response.items[0], price: { status: "not_found" } }] });
});

it("shows nutrient data and never shows catalogue price information to a member", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "کاتالوگ مواد غذایی" })).toBeVisible();
  expect(screen.getByRole("list", { name: "مواد غذایی" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "سینه مرغ" })).toBeVisible();
  expect(screen.queryByText("یافت نشد")).not.toBeInTheDocument();
  expect(screen.getByText("۱۱٫۳ گرم")).toBeVisible();
  expect(screen.queryByRole("button", { name: "افزودن ماده غذایی" })).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "جزئیات بیشتر" }));
  expect(screen.getByRole("dialog", { name: "جزئیات سینه مرغ" })).toBeVisible();
  expect(screen.getByText("آهن")).toBeVisible();
  expect(screen.getByText("ویتامین C")).toBeVisible();
  expect(screen.getByText(/USDA FoodData Central/)).toBeVisible();
  expect(screen.getByText("در ۱ عدد")).toBeVisible();
  expect(screen.getByText(/۱ عدد ≈ ۵۰ گرم/)).toBeVisible();
  expect(screen.getByText("۰٫۲ mg")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "۱۰۰ گرم" }));
  expect(screen.getByText("۰٫۴ mg")).toBeVisible();
});

it("shows price and price controls only to an admin", async () => {
  auth.isAdmin = true;
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  await screen.findByRole("heading", { name: "کاتالوگ مواد غذایی" });
  expect(screen.getByRole("button", { name: "افزودن ماده غذایی" })).toBeVisible();
  expect(screen.getByRole("button", { name: "ویرایش قیمت سینه مرغ" })).toBeVisible();
  expect(screen.getByText("یافت نشد")).toBeVisible();
});

it("uses English copy and left-to-right flow", async () => {
  const user = userEvent.setup();
  await i18n.changeLanguage("en");
  const { container } = render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "Food catalogue" })).toBeVisible();
  expect(screen.queryByText("Not found")).not.toBeInTheDocument();
  expect(container.querySelector("main")).toHaveAttribute("dir", "ltr");
  expect(container.querySelector("main")).toHaveClass("fitsho-page");
  await user.click(screen.getByRole("button", { name: "More details" }));
  expect(screen.getByText("Vitamin C")).toBeVisible();
});

it("shows accepted catalogue prices to an admin only", async () => {
  await i18n.changeLanguage("en");
  auth.isAdmin = true;
  vi.mocked(api.getAdminFoodCatalogue).mockResolvedValue({
    ...response,
    items: [{
      ...response.items[0],
      price: {
        status: "accepted",
        reference_price_irr: "5900000.00000000",
        reference_unit: "IRR_PER_KG",
        observed_at: "2026-08-09T12:00:00Z",
        accepted_at: "2026-08-09T12:05:00Z",
        source: "automatic",
      },
    }],
  });
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  expect(await screen.findByText("590,000 Toman")).toBeVisible();
  expect(screen.getByText(/Automatic market update/)).toBeVisible();
  expect(screen.getByText(/8\/9\/26/)).toBeVisible();
  expect(screen.getByText("Toman per kilogram")).toBeVisible();
});
