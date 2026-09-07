import type { components, TransportRequest } from "@fitician/core";

import type { AuthenticatedNutritionRequest } from "./nutritionApi";

export type FoodCatalogueItem = components["schemas"]["FoodCatalogueItemResponse"];
export type FoodCataloguePage = components["schemas"]["FoodCataloguePageResponse"];
export type FoodCataloguePortion = components["schemas"]["FoodCataloguePortionResponse"];
export type MealCatalogueCategory = components["schemas"]["MealCategory"];
export type MealCatalogueItem = components["schemas"]["SharedCatalogueMealResponse"];
export type MealCataloguePage = components["schemas"]["SharedCatalogueMealPageResponse"];

export type FoodCatalogueQuery = {
  readonly category?: string;
  readonly page?: number;
  readonly pageSize?: number;
  readonly query?: string;
};

export interface NutritionCatalogueApi {
  getFoodCatalogue(input?: FoodCatalogueQuery): Promise<FoodCataloguePage>;
  getMealCatalogue(category?: MealCatalogueCategory): Promise<MealCataloguePage>;
}

const nutritionPath = "/api/v1/nutrition";

export function createNutritionCatalogueApi(
  request: AuthenticatedNutritionRequest,
): NutritionCatalogueApi {
  return {
    getFoodCatalogue: (input = {}) => {
      const parameters = new URLSearchParams();
      if (input.query) parameters.set("q", input.query);
      if (input.category) parameters.set("category", input.category);
      parameters.set("page", String(input.page ?? 1));
      parameters.set("page_size", String(input.pageSize ?? 24));
      return request<FoodCataloguePage>({
        method: "GET",
        path: `${nutritionPath}/food-catalogue?${parameters.toString()}`,
      });
    },

    getMealCatalogue: (category) => {
      const parameters = new URLSearchParams();
      if (category) parameters.set("category", category);
      const query = parameters.toString();
      return request<MealCataloguePage>({
        method: "GET",
        path: `${nutritionPath}/meal-catalogue${query ? `?${query}` : ""}`,
      });
    },
  } satisfies NutritionCatalogueApi;
}

export type NutritionCatalogueRequest = TransportRequest;
