import { expect, it } from "vitest";

import type { TransportRequest } from "@fitician/core";

import { createNutritionCatalogueApi } from "./nutritionCatalogueApi";

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
