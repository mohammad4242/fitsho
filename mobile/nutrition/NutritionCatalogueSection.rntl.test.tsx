import { fireEvent, render, screen, waitFor, within } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StyleSheet } from "react-native";
import type { ReactTestInstance } from "react-test-renderer";

jest.mock("@tanstack/react-query", () => ({ useQuery: jest.fn(), useQueryClient: jest.fn() }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("expo-image-picker", () => ({ launchImageLibraryAsync: jest.fn() }));
jest.mock("expo-file-system", () => ({
  File: class MockFile {
    readonly exists = true;
    readonly uri: string;

    constructor(uri: string) {
      this.uri = uri;
    }

    async arrayBuffer(): Promise<ArrayBuffer> {
      return new Uint8Array([1, 2, 3]).buffer;
    }
  },
}));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../platform/connectivity", () => ({
  connectivityMonitor: {
    getSnapshot: () => ({ status: "online" }),
    subscribe: jest.fn(() => jest.fn()),
  },
}));
jest.mock("./nutritionCatalogueApi", () => ({
  catalogueFoodImageExtension: (mimeType: string) => mimeType === "image/gif" ? "gif" : "jpg",
  catalogueFoodImageMimeTypeForAsset: (mimeType: string | null | undefined, uri: string) => {
    if (mimeType === "image/gif" || mimeType === "image/jpeg" || mimeType === "image/png" || mimeType === "image/webp") return mimeType;
    return uri.endsWith(".gif") ? "image/gif" : null;
  },
  createNutritionCatalogueApi: jest.fn(),
}));

import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createNutritionCatalogueApi } from "./nutritionCatalogueApi";
import { NutritionCatalogueSection } from "./NutritionCatalogueSection";

const mockUseQuery = jest.mocked(useQuery);
const mockUseQueryClient = jest.mocked(useQueryClient);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockCreateCatalogueApi = jest.mocked(createNutritionCatalogueApi);
const mockUseRouter = jest.mocked(useRouter);
const mockLaunchImageLibraryAsync = jest.mocked(ImagePicker.launchImageLibraryAsync);

const food = {
  allergen_metadata_verified: true,
  allergen_tags: ["legumes"],
  category: "legumes",
  id: "food-1",
  image_url: null,
  macros: {
    carbohydrate_g: "20",
    energy_kcal: "120",
    fibre_g: "4",
    protein_g: "8",
    total_fat_g: "2",
  },
  measurement_basis: "raw",
  name_en: "Lentils",
  name_fa: "عدس",
  nutrient_basis: { quantity: "100", unit: "g" },
  nutrients: [
    {
      confidence: "high",
      nutrient_code: "iron_mg",
      source_name: "USDA",
      source_reference: "fdc-1",
      unit: "mg",
      unit_form: "nutrient_mass",
      value_per_100g: 0.37,
    },
    {
      confidence: "high",
      nutrient_code: "fibre_g",
      source_name: "USDA",
      source_reference: "fdc-1",
      unit: "g",
      unit_form: "nutrient_mass",
      value_per_100g: 4,
    },
  ],
  portions: [{
    code: "piece",
    grams: "50",
    is_default: true,
    label_en: "1 piece",
    label_fa: "۱ عدد",
    quantity: "1",
    source_name: "USDA",
    source_reference: "fdc-1",
  }],
  slug: "lentils",
  source: {
    access_date: "2026-09-09",
    data_version: "v1",
    name: "USDA",
    reference: "https://fdc.nal.usda.gov/fdc-app.html#/food-details/1",
    source_food_id: "1",
  },
};

const adminFood = {
  ...food,
  price: {
    accepted_at: "2026-09-09T10:00:00Z",
    canonical_unit: "kg",
    observed_at: "2026-09-09T10:00:00Z",
    reference_price_irr: "5900000",
    reference_price_toman: null,
    reference_unit: "IRR_PER_KG",
    source: "automatic",
    status: "accepted",
  },
};

const meal = {
  calculation_mode: "simple",
  category: "breakfast",
  code: "breakfast-1",
  id: "meal-1",
  image_url: null,
  items: [{
    food_id: "food-1",
    food_name_en: "Egg",
    food_name_fa: "تخم‌مرغ",
    food_slug: "egg",
    functional_role: "protein",
    is_required: true,
    max_grams: 100,
    min_grams: 50,
    reference_grams: 75,
  }],
  name_en: "Vegetable omelette",
  name_fa: "املت سبزیجات",
  verification_status: "verified",
};

function pageFor(page = 1, pageSize = 24) {
  return { categories: ["legumes", "grains"], items: [food], page, page_size: pageSize, total: pageSize === 1 ? 3 : 1 };
}

function adminPageFor(page = 1, pageSize = 24) {
  return { categories: ["legumes", "grains"], items: [adminFood], page, page_size: pageSize, total: pageSize === 1 ? 3 : 1 };
}

function queryResult<T>(data: T, overrides: { readonly isError?: boolean; readonly isFetching?: boolean; readonly isPending?: boolean; readonly isStale?: boolean } = {}) {
  return {
    data,
    error: null,
    isError: overrides.isError ?? false,
    isFetching: overrides.isFetching ?? false,
    isPending: overrides.isPending ?? false,
    isStale: overrides.isStale ?? false,
    refetch: jest.fn(),
  } as never;
}

function renderCatalogue(initialMode: "foods" | "meals" = "foods") {
  return render(
    <SafeAreaProvider initialMetrics={{ frame: { height: 800, width: 400, x: 0, y: 0 }, insets: { bottom: 0, left: 0, right: 0, top: 0 } }}>
      <NutritionCatalogueSection initialMode={initialMode} />
    </SafeAreaProvider>,
  );
}

type QueryOptions = { readonly queryKey: readonly unknown[]; readonly queryFn: () => Promise<unknown> };

function latestQuery(feature: "food-catalogue" | "meal-catalogue"): QueryOptions {
  const matches = mockUseQuery.mock.calls
    .map(([options]) => options as unknown as QueryOptions)
    .filter((options) => options.queryKey[1] === feature);
  const latest = matches[matches.length - 1];
  if (latest === undefined) throw new Error(`No ${feature} query found`);
  return latest;
}

let catalogueApi: {
  deleteCatalogueFood: jest.Mock<(slug: string) => Promise<unknown>>;
  getAdminFoodCatalogue: jest.Mock<(input?: unknown) => Promise<unknown>>;
  getFoodCatalogue: jest.Mock<(input?: unknown) => Promise<unknown>>;
  getMealCatalogue: jest.Mock<(category?: unknown) => Promise<unknown>>;
  researchFoodPrice: jest.Mock<(slug: string, apply?: boolean) => Promise<unknown>>;
  saveCatalogueFood: jest.Mock<(input: unknown) => Promise<unknown>>;
  saveFoodPriceOverride: jest.Mock<(slug: string, input: unknown) => Promise<unknown>>;
  uploadCatalogueFoodImage: jest.Mock<(slug: string, asset: unknown) => Promise<unknown>>;
};
let queryClient: { invalidateQueries: jest.Mock<(...args: never[]) => Promise<unknown>>; setQueryData: jest.Mock<(...args: never[]) => unknown> };
let isAdmin = false;
let routerPush: jest.Mock<(path: string) => unknown>;

beforeEach(() => {
  isAdmin = false;
  routerPush = jest.fn<(path: string) => unknown>();
  queryClient = {
    invalidateQueries: jest.fn<() => Promise<unknown>>().mockResolvedValue(undefined),
    setQueryData: jest.fn<(...args: never[]) => unknown>(),
  };
  catalogueApi = {
    deleteCatalogueFood: jest.fn<(slug: string) => Promise<unknown>>().mockResolvedValue(undefined),
    getAdminFoodCatalogue: jest.fn<(input?: unknown) => Promise<unknown>>().mockResolvedValue(adminPageFor()),
    getFoodCatalogue: jest.fn<(input?: unknown) => Promise<unknown>>().mockResolvedValue(pageFor()),
    getMealCatalogue: jest.fn<(category?: unknown) => Promise<unknown>>().mockResolvedValue({ categories: ["breakfast"], items: [meal] }),
    researchFoodPrice: jest.fn<(slug: string, apply?: boolean) => Promise<unknown>>().mockResolvedValue({
      candidate_reference_price_toman: "1234",
      canonical_unit: "TOMAN_PER_KG",
      food_name_fa: "عدس",
      food_slug: "lentils",
      quotes: [],
      status: "success",
    }),
    saveCatalogueFood: jest.fn<(input: unknown) => Promise<unknown>>().mockResolvedValue(food),
    saveFoodPriceOverride: jest.fn<(slug: string, input: unknown) => Promise<unknown>>().mockResolvedValue({}),
    uploadCatalogueFoodImage: jest.fn<(slug: string, asset: unknown) => Promise<unknown>>().mockResolvedValue({ image_url: "/media/lentils.gif" }),
  };
  mockCreateCatalogueApi.mockReturnValue(catalogueApi as never);
  mockUseMobileAuth.mockReturnValue({
    request: jest.fn(),
    upload: jest.fn(),
    user: { is_admin: isAdmin },
  } as never);
  mockUseRouter.mockReturnValue({ push: routerPush } as never);
  mockUseQueryClient.mockReturnValue(queryClient as never);
  mockLaunchImageLibraryAsync.mockReset();
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "meal-catalogue") {
      return queryResult({ categories: ["breakfast"], items: [meal] });
    }
    const filters = key[2] as { readonly page?: number; readonly pageSize?: number; readonly scope?: string };
    return queryResult(filters.scope === "admin"
      ? adminPageFor(filters.page ?? 1, filters.pageSize ?? 24)
      : pageFor(filters.page ?? 1, filters.pageSize ?? 24));
  });
});

test("dedicated food screen has a concise web-like header and attached search control", () => {
  renderCatalogue();

  expect(screen.getByRole("header", { name: "کاتالوگ مواد غذایی" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "تغذیه" })).toBeTruthy();
  expect(screen.queryByText("مواد غذایی تأییدشده را جست‌وجو کن و جزئیات هر مورد را ببین.")).toBeNull();
  expect(screen.getByPlaceholderText("مثلاً عدس یا سینه مرغ")).toBeTruthy();
  expect(screen.getByRole("button", { name: "جست‌وجو" })).toBeTruthy();
  expect(StyleSheet.flatten(screen.getByTestId("food-search-row").props.style)).toMatchObject({ flexDirection: "row" });

  fireEvent.press(screen.getByRole("button", { name: "تغذیه" }));
  expect(routerPush).toHaveBeenCalledWith("/member/nutrition");
});

test("typing alone does not commit a query and submit resets page", async () => {
  renderCatalogue();
  const input = screen.getByPlaceholderText("مثلاً عدس یا سینه مرغ");
  fireEvent.changeText(input, " عدس ");

  expect(catalogueApi.getFoodCatalogue).not.toHaveBeenCalled();
  expect(latestQuery("food-catalogue").queryKey[2]).toMatchObject({ page: 1, query: "" });

  fireEvent.press(screen.getByRole("button", { name: "جست‌وجو" }));
  const query = latestQuery("food-catalogue");
  expect(query.queryKey[2]).toMatchObject({ page: 1, query: "عدس", scope: "member" });
  await query.queryFn();
  expect(catalogueApi.getFoodCatalogue).toHaveBeenLastCalledWith({ category: undefined, page: 1, pageSize: 24, query: "عدس" });
});

test("keyboard search action commits the trimmed query", async () => {
  renderCatalogue();
  const input = screen.getByPlaceholderText("مثلاً عدس یا سینه مرغ");
  fireEvent.changeText(input, " مرغ ");
  fireEvent(input, "submitEditing");

  expect(latestQuery("food-catalogue").queryKey[2]).toMatchObject({ page: 1, query: "مرغ" });
  await latestQuery("food-catalogue").queryFn();
  expect(catalogueApi.getFoodCatalogue).toHaveBeenLastCalledWith({ category: undefined, page: 1, pageSize: 24, query: "مرغ" });
});

test("category chips are horizontal, start with all groups, and preserve submitted search", async () => {
  renderCatalogue();

  const chipScroll = screen.getByTestId("food-category-scroll");
  expect(chipScroll.props.horizontal).toBe(true);
  expect(chipScroll.props.showsHorizontalScrollIndicator).toBe(false);
  expect(screen.getByRole("button", { name: "همه گروه‌ها" }).props.accessibilityState).toMatchObject({ selected: true });

  fireEvent.changeText(screen.getByPlaceholderText("مثلاً عدس یا سینه مرغ"), "عدس");
  fireEvent.press(screen.getByRole("button", { name: "جست‌وجو" }));
  fireEvent.press(screen.getByRole("button", { name: "غلات" }));

  const query = latestQuery("food-catalogue");
  expect(query.queryKey[2]).toMatchObject({ category: "grains", page: 1, query: "عدس" });
  await query.queryFn();
  expect(catalogueApi.getFoodCatalogue).toHaveBeenLastCalledWith({ category: "grains", page: 1, pageSize: 24, query: "عدس" });
  expect(screen.getByRole("button", { name: "غلات" }).props.accessibilityState).toMatchObject({ selected: true });
});

test("member uses member data and never renders price or admin controls", async () => {
  renderCatalogue();
  await latestQuery("food-catalogue").queryFn();

  expect(catalogueApi.getFoodCatalogue).toHaveBeenCalled();
  expect(catalogueApi.getAdminFoodCatalogue).not.toHaveBeenCalled();
  expect(screen.queryByText("قیمت این هفته")).toBeNull();
  expect(screen.queryByRole("button", { name: "افزودن ماده غذایی" })).toBeNull();
  expect(screen.queryByRole("button", { name: "ویرایش قیمت" })).toBeNull();
  expect(screen.queryByRole("button", { name: "استعلام قیمت" })).toBeNull();
  expect(screen.queryByRole("button", { name: "حذف" })).toBeNull();
  expect(screen.queryByRole("button", { name: "بارگذاری تصویر" })).toBeNull();
});

test("admin uses admin data and renders the full food action set", async () => {
  isAdmin = true;
  mockUseMobileAuth.mockReturnValue({ request: jest.fn(), upload: jest.fn(), user: { is_admin: true } } as never);
  renderCatalogue();
  await latestQuery("food-catalogue").queryFn();

  expect(latestQuery("food-catalogue").queryKey[2]).toMatchObject({ scope: "admin" });
  expect(catalogueApi.getAdminFoodCatalogue).toHaveBeenCalled();
  expect(catalogueApi.getFoodCatalogue).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "+ افزودن ماده غذایی" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "ویرایش قیمت" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "بارگذاری تصویر" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "استعلام قیمت" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "حذف" })).toBeTruthy();
  expect(screen.getByText("قیمت این هفته")).toBeTruthy();
  expect(screen.getByText("۵۹۰٬۰۰۰ تومان")).toBeTruthy();
  expect(screen.getByText(/تومان برای هر کیلوگرم/)).toBeTruthy();
  expect(screen.getByText(/به‌روزرسانی خودکار بازار/)).toBeTruthy();
});

test("food cards keep calories separate and expose exactly three macro cells", () => {
  renderCatalogue();
  const card = screen.getByTestId("food-card-food-1");
  const macroStrip = within(card).getByTestId("food-macro-strip-food-1");

  expect(within(card).getByText("کالری")).toBeTruthy();
  expect(within(card).getByText("۶۰ kcal")).toBeTruthy();
  expect(within(macroStrip).getByText("پروتئین")).toBeTruthy();
  expect(within(macroStrip).getByText("کربوهیدرات")).toBeTruthy();
  expect(within(macroStrip).getByText("چربی")).toBeTruthy();
  expect(within(macroStrip).queryByText("کالری")).toBeNull();
  expect(within(macroStrip).queryByText("فیبر")).toBeNull();
  expect(within(card).getByText("در ۱ عدد")).toBeTruthy();
});

test("default portion scales all card values and details can switch to 100 grams", () => {
  renderCatalogue();
  const card = screen.getByTestId("food-card-food-1");

  expect(within(card).getByText("۱۰ گرم")).toBeTruthy();
  expect(within(card).getByText("۴ گرم")).toBeTruthy();
  expect(within(card).getByText("۱ گرم")).toBeTruthy();
  expect(within(card).getByRole("button", { name: "جزئیات بیشتر" })).toBeTruthy();

  fireEvent.press(within(card).getByRole("button", { name: "جزئیات بیشتر" }));
  expect(screen.getByText("در ۱ عدد · ۱ عدد ≈ ۵۰ گرم")).toBeTruthy();
  expect(screen.getByText("۰٫۲ mg")).toBeTruthy();
  expect(screen.getByText("همه مواد مغذی")).toBeTruthy();

  fireEvent.press(screen.getByRole("button", { name: "۱۰۰ گرم" }));
  expect(screen.getByText("در هر ۱۰۰ گرم")).toBeTruthy();
  expect(screen.getByText("۰٫۴ mg")).toBeTruthy();
  expect(screen.getByText("۴ g")).toBeTruthy();
});

test("food image stays inside a bounded physical card layout", () => {
  renderCatalogue();
  const card = screen.getByTestId("food-card-food-1");
  const image = within(card).getByLabelText("تصویر عدس موجود نیست");

  expect(StyleSheet.flatten(card.props.style)).toMatchObject({ direction: "ltr", overflow: "hidden" });
  expect(StyleSheet.flatten(image.props.style)).toMatchObject({ flexShrink: 0 });
  expect(isDescendant(card, image)).toBe(true);
});

test("pagination exposes previous and next controls and follows page state", () => {
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "meal-catalogue") return queryResult({ categories: ["breakfast"], items: [meal] });
    const filters = key[2] as { readonly page?: number; readonly scope?: string };
    return queryResult(filters.scope === "admin" ? adminPageFor(filters.page ?? 1, 1) : pageFor(filters.page ?? 1, 1));
  });
  renderCatalogue();
  fireEvent.press(screen.getByRole("button", { name: "بعدی" }));

  const nextQuery = latestQuery("food-catalogue");
  expect(nextQuery.queryKey[2]).toMatchObject({ page: 2 });
  expect(screen.getByText("۲ / ۳")).toBeTruthy();
  expect(screen.getByRole("button", { name: "قبلی" }).props.accessibilityState).toMatchObject({ disabled: false });

  fireEvent.press(screen.getByRole("button", { name: "قبلی" }));
  expect(latestQuery("food-catalogue").queryKey[2]).toMatchObject({ page: 1 });
  expect(screen.getByRole("button", { name: "قبلی" }).props.accessibilityState).toMatchObject({ disabled: true });
});

test("price research has independent pending and immediate success state", async () => {
  isAdmin = true;
  mockUseMobileAuth.mockReturnValue({ request: jest.fn(), upload: jest.fn(), user: { is_admin: true } } as never);
  let resolveResearch: ((value: unknown) => void) | undefined;
  catalogueApi.researchFoodPrice.mockReturnValue(new Promise((resolve) => { resolveResearch = resolve; }));
  renderCatalogue();

  fireEvent.press(screen.getByRole("button", { name: "استعلام قیمت" }));
  expect(screen.getAllByText("در حال استعلام…").length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: "در حال استعلام…" }).props.accessibilityState).toMatchObject({ disabled: true });
  expect(catalogueApi.researchFoodPrice).toHaveBeenCalledWith("lentils", true);

  resolveResearch?.({
    candidate_reference_price_toman: "1234",
    canonical_unit: "TOMAN_PER_KG",
    food_name_fa: "عدس",
    food_slug: "lentils",
    status: "success",
  });
  await waitFor(() => expect(screen.getByText("۱٬۲۳۴ تومان")).toBeTruthy());
  expect(screen.queryByText("در حال استعلام…")).toBeNull();
});

test("price research failure remains on the card", async () => {
  isAdmin = true;
  mockUseMobileAuth.mockReturnValue({ request: jest.fn(), upload: jest.fn(), user: { is_admin: true } } as never);
  catalogueApi.researchFoodPrice.mockResolvedValue({
    food_name_fa: "عدس",
    food_slug: "lentils",
    message: "برای این ماده مظنه معتبر پیدا نشد.",
    status: "no_quotes",
  });
  renderCatalogue();
  fireEvent.press(screen.getByRole("button", { name: "استعلام قیمت" }));
  await waitFor(() => expect(screen.getByText("برای این ماده مظنه معتبر پیدا نشد.")).toBeTruthy());
  expect(screen.getByTestId("food-price-ticket-lentils")).toBeTruthy();
});

test("admin add food sheet sends the web payload with five primary nutrients", async () => {
  isAdmin = true;
  mockUseMobileAuth.mockReturnValue({ request: jest.fn(), upload: jest.fn(), user: { is_admin: true } } as never);
  renderCatalogue();
  fireEvent.press(screen.getByRole("button", { name: "+ افزودن ماده غذایی" }));

  expect(screen.getByRole("header", { name: "ماده غذایی تأییدشده" })).toBeTruthy();
  expect(screen.getByText("برای انتشار، مشخصات و پنج مقدار اصلی باید کامل باشند.")).toBeTruthy();
  const values: Record<string, string> = {
    "شناسه انگلیسی": "lentils-new",
    "نام فارسی": "عدس سبز",
    "نام انگلیسی": "Green lentils",
    "گروه غذایی": "legumes",
    "نام منبع": "USDA",
    "لینک منبع": "fdc-2",
    "کالری (kcal)": "116",
    "پروتئین (g)": "9",
    "کربوهیدرات (g)": "20",
    "چربی (g)": "1",
    "فیبر (g)": "8",
  };
  for (const [label, value] of Object.entries(values)) fireEvent.changeText(screen.getByLabelText(label), value);

  fireEvent.press(screen.getByRole("button", { name: "افزودن به کاتالوگ" }));
  await waitFor(() => expect(catalogueApi.saveCatalogueFood).toHaveBeenCalled());
  expect(catalogueApi.saveCatalogueFood).toHaveBeenCalledWith(expect.objectContaining({
    canonical_quantity: 100,
    canonical_unit: "g",
    data_version: "admin-verified-v1",
    dietary_patterns: ["omnivore", "vegetarian", "vegan"],
    edible_portion: 1,
    measurement_basis: "as_purchased",
    roles: ["flexible"],
    source_access_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/u),
    source_food_id: null,
    verification_status: "verified",
  }));
  const payload = catalogueApi.saveCatalogueFood.mock.calls[0]?.[0] as { nutrients: Array<{ nutrient_code: string; value_per_100g: number }> };
  expect(payload.nutrients).toEqual(expect.arrayContaining([
    expect.objectContaining({ nutrient_code: "energy_kcal", value_per_100g: 116 }),
    expect.objectContaining({ nutrient_code: "protein_g", value_per_100g: 9 }),
    expect.objectContaining({ nutrient_code: "carbohydrate_g", value_per_100g: 20 }),
    expect.objectContaining({ nutrient_code: "total_fat_g", value_per_100g: 1 }),
    expect.objectContaining({ nutrient_code: "fibre_g", value_per_100g: 8 }),
  ]));
  expect(queryClient.invalidateQueries).toHaveBeenCalled();
});

test("admin image sheet accepts GIF and uploads bytes as file multipart asset", async () => {
  isAdmin = true;
  mockUseMobileAuth.mockReturnValue({ request: jest.fn(), upload: jest.fn(), user: { is_admin: true } } as never);
  mockLaunchImageLibraryAsync.mockResolvedValue({
    canceled: false,
    assets: [{ fileName: "lentils.gif", mimeType: "image/gif", uri: "file:///lentils.gif" }],
  } as never);
  renderCatalogue();
  fireEvent.press(screen.getByRole("button", { name: "بارگذاری تصویر" }));
  expect(screen.getByRole("header", { name: "بارگذاری تصویر غذا" })).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "انتخاب تصویر" }));
  await waitFor(() => expect(screen.getByText("lentils.gif")).toBeTruthy());
  fireEvent.press(screen.getByRole("button", { name: "ذخیره تصویر" }));

  await waitFor(() => expect(catalogueApi.uploadCatalogueFoodImage).toHaveBeenCalled());
  expect(catalogueApi.uploadCatalogueFoodImage).toHaveBeenCalledWith("lentils", expect.objectContaining({
    filename: "lentils.gif",
    mimeType: "image/gif",
    bytes: expect.any(Uint8Array),
  }));
  expect(queryClient.invalidateQueries).toHaveBeenCalled();
});

test("price override sheet validates and saves price, unit, and reason", async () => {
  isAdmin = true;
  mockUseMobileAuth.mockReturnValue({ request: jest.fn(), upload: jest.fn(), user: { is_admin: true } } as never);
  renderCatalogue();
  fireEvent.press(screen.getByRole("button", { name: "ویرایش قیمت" }));
  expect(screen.getByRole("header", { name: "ویرایش قیمت" })).toBeTruthy();
  fireEvent.changeText(screen.getByLabelText("قیمت"), "150000");
  fireEvent.changeText(screen.getByLabelText("دلیل"), "قیمت فروشگاه امروز");
  fireEvent.press(screen.getByRole("button", { name: "تومان/لیتر" }));
  fireEvent.press(screen.getByRole("button", { name: "ذخیره قیمت" }));

  await waitFor(() => expect(catalogueApi.saveFoodPriceOverride).toHaveBeenCalled());
  expect(catalogueApi.saveFoodPriceOverride).toHaveBeenCalledWith("lentils", {
    canonical_unit: "TOMAN_PER_LITER",
    reason: "قیمت فروشگاه امروز",
    reference_price_toman: "150000",
  });
  expect(queryClient.invalidateQueries).toHaveBeenCalled();
});

test("delete requires confirmation, keeps errors open, and refreshes after success", async () => {
  isAdmin = true;
  mockUseMobileAuth.mockReturnValue({ request: jest.fn(), upload: jest.fn(), user: { is_admin: true } } as never);
  catalogueApi.deleteCatalogueFood.mockRejectedValueOnce(new Error("delete failed"));
  renderCatalogue();

  fireEvent.press(screen.getByRole("button", { name: "حذف" }));
  expect(screen.getByRole("header", { name: "حذف ماده غذایی؟" })).toBeTruthy();
  expect(screen.getByText("«عدس» از کاتالوگ فعال حذف شود؟")).toBeTruthy();
  expect(screen.getByText("این ماده دیگر در کاتالوگ و برنامه‌های غذایی جدید استفاده نمی‌شود، اما اطلاعات و سوابق تاریخی آن حذف نخواهند شد.")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "انصراف" }));
  expect(catalogueApi.deleteCatalogueFood).not.toHaveBeenCalled();

  fireEvent.press(screen.getByRole("button", { name: "حذف" }));
  fireEvent.press(screen.getByRole("button", { name: "حذف ماده غذایی" }));
  await waitFor(() => expect(screen.getByText("حذف ماده غذایی انجام نشد.")).toBeTruthy());
  expect(screen.getByRole("header", { name: "حذف ماده غذایی؟" })).toBeTruthy();

  catalogueApi.deleteCatalogueFood.mockResolvedValueOnce(undefined);
  fireEvent.press(screen.getByRole("button", { name: "حذف ماده غذایی" }));
  await waitFor(() => expect(queryClient.invalidateQueries).toHaveBeenCalled());
  expect(screen.queryByRole("header", { name: "حذف ماده غذایی؟" })).toBeNull();
});

test("deleting the only item on a later page moves to the previous page", async () => {
  isAdmin = true;
  mockUseMobileAuth.mockReturnValue({ request: jest.fn(), upload: jest.fn(), user: { is_admin: true } } as never);
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "meal-catalogue") return queryResult({ categories: ["breakfast"], items: [meal] });
    const filters = key[2] as { readonly page?: number; readonly scope?: string };
    return queryResult(filters.scope === "admin" ? adminPageFor(filters.page ?? 1, 1) : pageFor(filters.page ?? 1, 1));
  });
  renderCatalogue();

  fireEvent.press(screen.getByRole("button", { name: "بعدی" }));
  expect(latestQuery("food-catalogue").queryKey[2]).toMatchObject({ page: 2 });
  fireEvent.press(screen.getByRole("button", { name: "حذف" }));
  fireEvent.press(screen.getByRole("button", { name: "حذف ماده غذایی" }));

  await waitFor(() => expect(latestQuery("food-catalogue").queryKey[2]).toMatchObject({ page: 1 }));
});

test("dedicated meal mode still renders and expands the meal catalogue", () => {
  renderCatalogue("meals");

  expect(screen.getByText("ترکیب‌های کنترل‌شده تغذیه")).toBeTruthy();
  expect(screen.getByRole("header", { name: "کاتالوگ وعده‌های غذایی" })).toBeTruthy();
  expect(screen.getByText("دسته‌بندی وعده‌ها:")).toBeTruthy();
  for (const category of ["همه", "صبحانه", "ناهار", "پس از تمرین", "میان‌وعده", "شام"]) {
    expect(screen.getByRole("button", { name: category })).toBeTruthy();
  }
  expect(screen.getByRole("button", { name: "همه" }).props.accessibilityState).toMatchObject({ selected: true });

  const card = screen.getByTestId("meal-card-meal-1");
  const summary = screen.getByTestId("meal-card-meal-1-summary");
  expect(within(card).getByText("املت سبزیجات")).toBeTruthy();
  expect(screen.queryByText("تخم‌مرغ")).toBeNull();
  fireEvent.press(summary);
  expect(within(card).getByText("تخم‌مرغ")).toBeTruthy();
  fireEvent.press(summary);
  expect(within(card).queryByText("۵۰ تا ۱۰۰ گرم")).toBeNull();
});

test("meal mode preserves server verification statuses", () => {
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "meal-catalogue") {
      return queryResult({
        categories: ["breakfast", "lunch", "dinner"],
        items: [
          meal,
          { ...meal, code: "DR01", id: "meal-draft", name_fa: "وعده پیش‌نویس", verification_status: "draft" },
          { ...meal, code: "RT01", id: "meal-retired", name_fa: "وعده بازنشسته", verification_status: "retired" },
        ],
      });
    }
    return queryResult(pageFor());
  });
  renderCatalogue("meals");
  expect(screen.getByText("تأییدشده")).toBeTruthy();
  expect(screen.getByText("پیش‌نویس")).toBeTruthy();
  expect(screen.getByText("بازنشسته")).toBeTruthy();
});

test("meal mode requests the unfiltered catalogue", async () => {
  renderCatalogue("meals");
  const mealQuery = latestQuery("meal-catalogue");
  expect(mealQuery.queryKey).toEqual(["nutrition", "meal-catalogue", null]);
  await mealQuery.queryFn();
  expect(catalogueApi.getMealCatalogue).toHaveBeenCalledWith(undefined);
});

test("meal mode renders cached data without a food stale warning", () => {
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "meal-catalogue") return queryResult({ categories: ["breakfast"], items: [meal] }, { isFetching: true, isStale: true });
    return queryResult(pageFor());
  });
  renderCatalogue("meals");
  expect(screen.getByText("املت سبزیجات")).toBeTruthy();
  expect(screen.queryByText("نتایج کاتالوگ تازه‌سازی نشده‌اند.")).toBeNull();
});

function isDescendant(parent: ReactTestInstance, node: ReactTestInstance): boolean {
  let current = node.parent;
  while (current !== null) {
    if (current === parent) return true;
    current = current.parent;
  }
  return false;
}
