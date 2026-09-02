import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
      image_url: "/media/food-catalogue/chicken.png",
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
          nutrient_code: "fibre_g",
          value_per_100g: 0,
          unit: "g",
          unit_form: "nutrient_mass",
          source_name: "USDA FoodData Central",
          source_reference: "https://fdc.nal.usda.gov/",
          confidence: "high",
        },
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
          nutrient_code: "copper_mg",
          value_per_100g: 0.3,
          unit: "mg",
          unit_form: "nutrient_mass",
          source_name: "Iranian bread nutrient review",
          source_reference: "https://doi.org/10.1186/s41043-022-00327-9",
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
  vi.mocked(api.deleteCatalogueFood).mockResolvedValue(undefined);
  vi.mocked(api.uploadCatalogueFoodImage).mockResolvedValue({ image_url: "/media/food-catalogue/replacement.png" });
});

it("shows nutrient data and never shows catalogue price information to a member", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "کاتالوگ مواد غذایی" })).toBeVisible();
  expect(screen.getByRole("list", { name: "مواد غذایی" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "سینه مرغ" })).toBeVisible();
  expect(screen.getByRole("img", { name: "سینه مرغ" })).toHaveAttribute(
    "src",
    "/media/food-catalogue/chicken.png",
  );
  expect(screen.queryByText("فیبر")).not.toBeInTheDocument();
  expect(screen.getByText("کالری")).toBeVisible();
  expect(screen.getByText("پروتئین")).toBeVisible();
  expect(screen.getByText("کربوهیدرات")).toBeVisible();
  expect(screen.getByText("چربی")).toBeVisible();
  expect(screen.queryByText("یافت نشد")).not.toBeInTheDocument();
  expect(screen.getByText("۱۱٫۳ گرم")).toBeVisible();
  expect(screen.queryByRole("button", { name: "افزودن ماده غذایی" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "جایگزینی تصویر سینه مرغ" })).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "جزئیات بیشتر" }));
  expect(screen.getByRole("dialog", { name: "جزئیات سینه مرغ" })).toBeVisible();
  expect(screen.getByText("فیبر")).toBeVisible();
  expect(screen.getByText("آهن")).toBeVisible();
  expect(screen.getByText("مس")).toBeVisible();
  expect(screen.getByText("ویتامین C")).toBeVisible();
  expect(screen.getByText(/USDA FoodData Central/)).toBeVisible();
  expect(screen.getByText("در ۱ عدد")).toBeVisible();
  expect(screen.getByText(/۱ عدد ≈ ۵۰ گرم/)).toBeVisible();
  const ironCard = screen.getByText("آهن").closest("article");
  expect(ironCard).not.toBeNull();
  expect(within(ironCard!).getByText("۰٫۲ mg")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "۱۰۰ گرم" }));
  expect(screen.getByText("۰٫۴ mg")).toBeVisible();
});

it("filters with horizontal category chips while preserving the search query", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  const allChip = await screen.findByRole("button", { name: "همه گروه‌ها" });
  expect(allChip).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "مرغ و ماکیان" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  await user.type(screen.getByLabelText("جست‌وجوی ماده غذایی"), "مرغ");
  await user.click(screen.getByRole("button", { name: "جست‌وجو" }));
  await user.click(screen.getByRole("button", { name: "مرغ و ماکیان" }));

  await waitFor(() => expect(api.getFoodCatalogue).toHaveBeenLastCalledWith({
    query: "مرغ",
    category: "poultry",
    page: 1,
    pageSize: 24,
  }));
});

it("shows price and price controls only to an admin", async () => {
  auth.isAdmin = true;
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  await screen.findByRole("heading", { name: "کاتالوگ مواد غذایی" });
  expect(screen.getByRole("button", { name: "افزودن ماده غذایی" })).toBeVisible();
  expect(screen.getByRole("button", { name: "ویرایش قیمت سینه مرغ" })).toBeVisible();
  expect(screen.getByRole("button", { name: "جایگزینی تصویر سینه مرغ" })).toBeVisible();
  expect(screen.getByRole("button", { name: "حذف سینه مرغ" })).toBeVisible();
  expect(screen.getByText("یافت نشد")).toBeVisible();
});

it("never shows the delete action to a member", async () => {
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  await screen.findByRole("heading", { name: "کاتالوگ مواد غذایی" });

  expect(screen.queryByRole("button", { name: "حذف سینه مرغ" })).not.toBeInTheDocument();
});

it("opens a confirmation dialog with the food name and preservation warning", async () => {
  const user = userEvent.setup();
  auth.isAdmin = true;
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "حذف سینه مرغ" }));

  expect(screen.getByRole("dialog", { name: "حذف ماده غذایی؟" })).toBeVisible();
  expect(screen.getByText("«سینه مرغ» از کاتالوگ فعال حذف شود؟")).toBeVisible();
  expect(screen.getByText(/سوابق تاریخی آن حذف نخواهند شد/)).toBeVisible();
});

it("closes the delete confirmation without calling the API when cancelled", async () => {
  const user = userEvent.setup();
  auth.isAdmin = true;
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "حذف سینه مرغ" }));
  await user.click(screen.getByRole("button", { name: "انصراف" }));

  expect(api.deleteCatalogueFood).not.toHaveBeenCalled();
  expect(screen.queryByRole("dialog", { name: "حذف ماده غذایی؟" })).not.toBeInTheDocument();
});

it("deletes the food after confirmation and refetches the catalogue", async () => {
  const user = userEvent.setup();
  auth.isAdmin = true;
  const adminItem = { ...response.items[0], price: { status: "not_found" as const } };
  const adminResponse: api.AdminFoodCatalogueResponse = { ...response, items: [adminItem] };
  vi.mocked(api.getAdminFoodCatalogue)
    .mockResolvedValueOnce(adminResponse)
    .mockResolvedValueOnce({ ...adminResponse, items: [], total: 0 });
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "حذف سینه مرغ" }));
  await user.click(screen.getByRole("button", { name: "حذف ماده غذایی" }));

  await waitFor(() => expect(api.deleteCatalogueFood).toHaveBeenCalledWith("chicken-breast"));
  await waitFor(() => expect(api.getAdminFoodCatalogue).toHaveBeenCalledTimes(2));
  expect(screen.queryByRole("heading", { name: "سینه مرغ" })).not.toBeInTheDocument();
});

it("keeps the dialog and food visible when deletion fails", async () => {
  const user = userEvent.setup();
  auth.isAdmin = true;
  vi.mocked(api.deleteCatalogueFood).mockRejectedValueOnce(new Error("delete failed"));
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "حذف سینه مرغ" }));
  await user.click(screen.getByRole("button", { name: "حذف ماده غذایی" }));

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("حذف ماده غذایی انجام نشد."));
  expect(screen.getByRole("dialog", { name: "حذف ماده غذایی؟" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "سینه مرغ" })).toBeVisible();
});

it("disables the confirmation action while deletion is pending", async () => {
  const user = userEvent.setup();
  auth.isAdmin = true;
  let resolveDelete: (() => void) | undefined;
  vi.mocked(api.deleteCatalogueFood).mockReturnValueOnce(
    new Promise<void>((resolve) => {
      resolveDelete = resolve;
    }),
  );
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "حذف سینه مرغ" }));
  await user.click(screen.getByRole("button", { name: "حذف ماده غذایی" }));
  await waitFor(() => expect(api.deleteCatalogueFood).toHaveBeenCalledTimes(1));

  const confirmButton = screen.getByRole("button", { name: "در حال حذف…" });
  expect(confirmButton).toBeDisabled();
  expect(api.deleteCatalogueFood).toHaveBeenCalledTimes(1);

  resolveDelete?.();
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "حذف ماده غذایی؟" })).not.toBeInTheDocument());
});

it("moves back one page when the deleted food was the only item on a later page", async () => {
  const user = userEvent.setup();
  auth.isAdmin = true;
  const adminItem = { ...response.items[0], price: { status: "not_found" as const } };
  const pageOne: api.AdminFoodCatalogueResponse = { ...response, page: 1, page_size: 1, total: 3, items: [adminItem] };
  const pageTwo: api.AdminFoodCatalogueResponse = { ...pageOne, page: 2 };
  const pageThree: api.AdminFoodCatalogueResponse = { ...pageOne, page: 3 };
  vi.mocked(api.getAdminFoodCatalogue)
    .mockReset()
    .mockResolvedValueOnce(pageOne)
    .mockResolvedValueOnce(pageTwo)
    .mockResolvedValueOnce(pageThree)
    .mockResolvedValueOnce({ ...pageTwo, total: 2 });
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  await screen.findByRole("heading", { name: "سینه مرغ" });
  await user.click(screen.getByRole("button", { name: "بعدی" }));
  await waitFor(() => expect(api.getAdminFoodCatalogue).toHaveBeenCalledTimes(2));
  await user.click(screen.getByRole("button", { name: "بعدی" }));
  await waitFor(() => expect(api.getAdminFoodCatalogue).toHaveBeenCalledTimes(3));
  await user.click(screen.getByRole("button", { name: "حذف سینه مرغ" }));
  await user.click(screen.getByRole("button", { name: "حذف ماده غذایی" }));

  await waitFor(() => expect(api.getAdminFoodCatalogue).toHaveBeenLastCalledWith({
    query: "",
    category: "",
    page: 2,
    pageSize: 24,
  }));
});

it("shows a stable fallback for missing and broken food images", async () => {
  vi.mocked(api.getFoodCatalogue).mockResolvedValueOnce({
    ...response,
    items: [{ ...response.items[0], image_url: null }],
  });
  const { unmount } = render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  expect(await screen.findByRole("img", { name: "تصویر پیش‌فرض سینه مرغ" })).toBeVisible();
  unmount();

  vi.mocked(api.getFoodCatalogue).mockResolvedValueOnce(response);
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);
  const image = await screen.findByRole("img", { name: "سینه مرغ" });
  fireEvent.error(image);
  expect(await screen.findByRole("img", { name: "تصویر پیش‌فرض سینه مرغ" })).toBeVisible();
});

it("lets an admin replace a food image and reloads the catalogue", async () => {
  const user = userEvent.setup();
  auth.isAdmin = true;
  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);
  await user.click(await screen.findByRole("button", { name: "جایگزینی تصویر سینه مرغ" }));
  const file = new File(["replacement"], "replacement.png", { type: "image/png" });

  await user.upload(screen.getByLabelText("تصویر غذا"), file);
  await user.click(screen.getByRole("button", { name: "ذخیره تصویر" }));

  await waitFor(() => expect(api.uploadCatalogueFoodImage).toHaveBeenCalledWith("chicken-breast", file));
  await waitFor(() => expect(api.getAdminFoodCatalogue).toHaveBeenCalledTimes(2));
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

const successfulPriceResearch: api.SingleFoodPriceResearchResponse = {
  food_slug: "chicken-breast",
  food_name_fa: "سینه مرغ",
  status: "success",
  candidate_reference_price_toman: "385000",
  canonical_unit: "TOMAN_PER_KG",
  quotes: [
    {
      source_name: "دیجی‌کالا",
      source_url: "https://digikala.com/product/1",
      source_domain: "digikala.com",
      product_title: "سینه مرغ ۱ کیلوگرمی",
      normal_price_toman: "385000",
      promotional_price_toman: null,
      package_quantity: "1",
      package_unit: "kg",
      match_accepted: true,
    },
  ],
};

it("runs admin food price inquiry in the background without opening a dialog", async () => {
  const user = userEvent.setup();
  auth.isAdmin = true;
  vi.mocked(api.getAdminFoodCatalogue).mockResolvedValue({
    ...response,
    items: [{
      ...response.items[0],
      price: {
        status: "not_found",
      },
    }],
  });
  let resolveResearch: ((value: api.SingleFoodPriceResearchResponse) => void) | undefined;
  vi.mocked(api.researchFoodPrice).mockReturnValueOnce(
    new Promise<api.SingleFoodPriceResearchResponse>((resolve) => {
      resolveResearch = (value) => resolve(value);
    }),
  );

  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  const inquireButton = await screen.findByRole("button", { name: "استعلام قیمت سینه مرغ" });
  await user.click(inquireButton);

  await waitFor(() => expect(api.researchFoodPrice).toHaveBeenCalledWith("chicken-breast", true));
  expect(screen.getByText("در حال استعلام…")).toBeVisible();
  expect(screen.getByRole("button", { name: "در حال استعلام قیمت سینه مرغ" })).toBeDisabled();
  expect(screen.queryByRole("dialog", { name: "ویرایش قیمت سینه مرغ" })).not.toBeInTheDocument();

  resolveResearch?.(successfulPriceResearch);
  await waitFor(() => expect(screen.queryByText("در حال استعلام…")).not.toBeInTheDocument());
});

it("shows the applied price from a successful background inquiry", async () => {
  const user = userEvent.setup();
  auth.isAdmin = true;
  vi.mocked(api.getAdminFoodCatalogue).mockResolvedValue({
    ...response,
    items: [{
      ...response.items[0],
      price: {
        status: "not_found",
      },
    }],
  });
  vi.mocked(api.researchFoodPrice).mockResolvedValue(successfulPriceResearch);

  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  const inquireButton = await screen.findByRole("button", { name: "استعلام قیمت سینه مرغ" });
  await user.click(inquireButton);

  expect(await screen.findByText("۳۸۵٬۰۰۰ تومان")).toBeVisible();
  expect(api.researchFoodPrice).toHaveBeenCalledWith("chicken-breast", true);
  expect(api.saveFoodPriceOverride).not.toHaveBeenCalled();
  expect(api.getAdminFoodCatalogue).toHaveBeenCalledTimes(1);
});

it("shows the backend failure reason and keeps the old price state", async () => {
  const user = userEvent.setup();
  auth.isAdmin = true;
  vi.mocked(api.getAdminFoodCatalogue).mockResolvedValue({
    ...response,
    items: [{ ...response.items[0], price: { status: "not_found" } }],
  });
  vi.mocked(api.researchFoodPrice).mockResolvedValue({
    ...successfulPriceResearch,
    status: "failed",
    candidate_reference_price_toman: null,
    canonical_unit: null,
    quotes: [],
    message: "Agent Service در دسترس نیست",
  });

  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "استعلام قیمت سینه مرغ" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Agent Service در دسترس نیست");
  expect(screen.getByText("یافت نشد")).toBeVisible();
  expect(screen.getByRole("button", { name: "استعلام قیمت سینه مرغ" })).toBeEnabled();
});

it("shows a connection error when background price inquiry rejects", async () => {
  const user = userEvent.setup();
  auth.isAdmin = true;
  vi.mocked(api.getAdminFoodCatalogue).mockResolvedValue({
    ...response,
    items: [{ ...response.items[0], price: { status: "not_found" } }],
  });
  vi.mocked(api.researchFoodPrice).mockRejectedValueOnce(new Error("اتصال به سرویس برقرار نشد"));

  render(<MemoryRouter><FoodCataloguePage /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "استعلام قیمت سینه مرغ" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("اتصال به سرویس برقرار نشد");
  expect(screen.getByText("یافت نشد")).toBeVisible();
  expect(screen.getByRole("button", { name: "استعلام قیمت سینه مرغ" })).toBeEnabled();
});
