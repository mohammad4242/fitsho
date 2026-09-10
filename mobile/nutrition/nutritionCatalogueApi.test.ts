import { expect, it } from "vitest";

import type { MultipartUploadRequest, TransportRequest } from "@fitician/core";

import { createNutritionCatalogueApi, type FoodCatalogueWriteInput } from "./nutritionCatalogueApi";

it("uses member-only food and meal catalogue read endpoints", async () => {
  const requests: TransportRequest[] = [];
  const api = createNutritionCatalogueApi(async <TResponse>(request: TransportRequest) => {
    requests.push(request);
    return {} as TResponse;
  });

  await api.getFoodCatalogue({ category: "grain", page: 2, pageSize: 12, query: "rice" });
  await api.getMealCatalogue("breakfast");

  expect(requests).toEqual([
    {
      method: "GET",
      path: "/api/v1/nutrition/food-catalogue?q=rice&category=grain&page=2&page_size=12",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/meal-catalogue?category=breakfast",
    },
  ]);
});

it("uses bounded defaults and never sends admin catalogue filters", async () => {
  const requests: TransportRequest[] = [];
  const api = createNutritionCatalogueApi(async <TResponse>(request: TransportRequest) => {
    requests.push(request);
    return {} as TResponse;
  });

  await api.getFoodCatalogue();
  await api.getMealCatalogue();

  expect(requests).toEqual([
    {
      method: "GET",
      path: "/api/v1/nutrition/food-catalogue?page=1&page_size=24",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/meal-catalogue",
    },
  ]);
  expect(requests.every((request) => !request.path.includes("/admin/"))).toBe(true);
});

it("uses the member and admin food catalogue routes and all admin mutations", async () => {
  const requests: TransportRequest[] = [];
  const uploads: MultipartUploadRequest[] = [];
  const api = createNutritionCatalogueApi(
    async <TResponse,>(request: TransportRequest) => {
      requests.push(request);
      return {} as TResponse;
    },
    async <TResponse,>(request: MultipartUploadRequest) => {
      uploads.push(request);
      return { image_url: "/media/food-catalogue/lentils.png" } as TResponse;
    },
  );
  const foodPayload: FoodCatalogueWriteInput = {
    slug: "lentils",
    name_fa: "عدس",
    name_en: "Lentils",
    category: "legumes",
    source_name: "USDA",
    source_reference: "https://fdc.nal.usda.gov/food/1",
    verification_status: "verified",
    measurement_basis: "as_purchased",
    canonical_quantity: 100,
    canonical_unit: "g",
    edible_portion: 1,
    data_version: "admin-verified-v1",
    source_food_id: null,
    source_access_date: "2026-09-10",
    aliases: [],
    dietary_patterns: ["omnivore", "vegetarian", "vegan"],
    roles: ["flexible"],
    nutrients: [],
  };

  await api.getFoodCatalogue({ category: "legumes", page: 2, pageSize: 24, query: "عدس" });
  await api.getAdminFoodCatalogue({ category: "legumes", page: 2, pageSize: 24, query: "عدس" });
  await api.saveCatalogueFood(foodPayload);
  await api.deleteCatalogueFood("lentils");
  await api.researchFoodPrice("lentils", true);
  await api.saveFoodPriceOverride("lentils", {
    canonical_unit: "TOMAN_PER_KG",
    reason: "تأیید قیمت هفتگی",
    reference_price_toman: "125000",
  });
  await api.uploadCatalogueFoodImage("lentils", {
    bytes: Uint8Array.from([0xff, 0xd8, 0xff]),
    filename: "lentils.jpg",
    mimeType: "image/jpeg",
  });

  expect(requests).toEqual([
    {
      method: "GET",
      path: "/api/v1/nutrition/food-catalogue?q=%D8%B9%D8%AF%D8%B3&category=legumes&page=2&page_size=24",
    },
    {
      method: "GET",
      path: "/api/v1/nutrition/admin/food-catalogue?q=%D8%B9%D8%AF%D8%B3&category=legumes&page=2&page_size=24",
    },
    {
      body: foodPayload,
      method: "POST",
      path: "/api/v1/nutrition/admin/foods",
    },
    {
      method: "DELETE",
      path: "/api/v1/nutrition/admin/foods/lentils",
    },
    {
      method: "POST",
      path: "/api/v1/nutrition/admin/foods/lentils/price-research?apply=true",
    },
    {
      body: {
        canonical_unit: "TOMAN_PER_KG",
        reason: "تأیید قیمت هفتگی",
        reference_price_toman: "125000",
      },
      method: "POST",
      path: "/api/v1/nutrition/admin/foods/lentils/price-override",
    },
  ]);
  expect(uploads).toEqual([
    {
      method: "POST",
      parts: [{
        bytes: Uint8Array.from([0xff, 0xd8, 0xff]),
        contentType: "image/jpeg",
        filename: "lentils.jpg",
        name: "file",
      }],
      path: "/api/v1/nutrition/admin/foods/lentils/image",
    },
  ]);
});
