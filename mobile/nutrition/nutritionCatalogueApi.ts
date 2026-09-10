import type {
  components,
  MultipartUploadRequest,
  TransportRequest,
} from "@fitician/core";

import type { AuthenticatedNutritionRequest } from "./nutritionApi";

export type FoodCatalogueNutrient = components["schemas"]["CatalogueNutrientInput"];
export type FoodCatalogueItem = components["schemas"]["FoodCatalogueItemResponse"];
export type FoodCataloguePage = components["schemas"]["FoodCataloguePageResponse"];
export type AdminFoodCatalogueItem = components["schemas"]["AdminFoodCatalogueItemResponse"];
export type AdminFoodCataloguePage = components["schemas"]["AdminFoodCataloguePageResponse"];
export type FoodCataloguePortion = components["schemas"]["FoodCataloguePortionResponse"];
export type FoodCataloguePrice = components["schemas"]["FoodCataloguePriceResponse"];
export type FoodCatalogueImageResponse = components["schemas"]["FoodCatalogueImageResponse"];
export type CatalogueFoodResponse = components["schemas"]["CatalogueFoodResponse"];
export type FoodPriceOverrideInput = components["schemas"]["FoodPriceOverrideInput"];
export type SingleFoodPriceResearchQuote = components["schemas"]["SingleFoodPriceResearchQuoteResponse"];
export type SingleFoodPriceResearchResponse = components["schemas"]["SingleFoodPriceResearchResponse"];

export type FoodCatalogueWriteInput = Omit<
  components["schemas"]["CatalogueFoodWrite"],
  "allergen_metadata_verified"
> & {
  readonly allergen_metadata_verified?: boolean;
};

export const CATALOGUE_FOOD_IMAGE_MIME_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
] as const;

export type CatalogueFoodImageMimeType = (typeof CATALOGUE_FOOD_IMAGE_MIME_TYPES)[number];

export type CatalogueFoodImageAsset = {
  readonly bytes: Uint8Array;
  readonly filename: string;
  readonly mimeType: CatalogueFoodImageMimeType;
};

export function catalogueFoodImageMimeTypeForAsset(
  mimeType: string | null | undefined,
  uri: string,
): CatalogueFoodImageMimeType | null {
  if (isCatalogueFoodImageMimeType(mimeType)) return mimeType;
  const extension = uri.split(/[?#]/u)[0]?.split(".").pop()?.toLowerCase();
  if (extension === "jpg" || extension === "jpeg") return "image/jpeg";
  if (extension === "png") return "image/png";
  if (extension === "webp") return "image/webp";
  if (extension === "gif") return "image/gif";
  return null;
}

export function isCatalogueFoodImageMimeType(value: string | null | undefined): value is CatalogueFoodImageMimeType {
  return CATALOGUE_FOOD_IMAGE_MIME_TYPES.includes(value as CatalogueFoodImageMimeType);
}

export function catalogueFoodImageExtension(mimeType: CatalogueFoodImageMimeType): string {
  switch (mimeType) {
    case "image/gif":
      return "gif";
    case "image/jpeg":
      return "jpg";
    case "image/png":
      return "png";
    case "image/webp":
      return "webp";
  }
}

export type MealCatalogueCategory = components["schemas"]["MealCategory"];
export type MealCatalogueItem = components["schemas"]["SharedCatalogueMealResponse"];
export type MealCataloguePage = components["schemas"]["SharedCatalogueMealPageResponse"];

export type FoodCatalogueQuery = {
  readonly category?: string;
  readonly page?: number;
  readonly pageSize?: number;
  readonly query?: string;
};

export type AuthenticatedNutritionUpload = <TResponse>(
  request: MultipartUploadRequest,
) => Promise<TResponse>;

export interface NutritionCatalogueApi {
  getFoodCatalogue(input?: FoodCatalogueQuery): Promise<FoodCataloguePage>;
  getAdminFoodCatalogue(input?: FoodCatalogueQuery): Promise<AdminFoodCataloguePage>;
  saveCatalogueFood(input: FoodCatalogueWriteInput): Promise<CatalogueFoodResponse>;
  deleteCatalogueFood(slug: string): Promise<void>;
  researchFoodPrice(slug: string, apply?: boolean): Promise<SingleFoodPriceResearchResponse>;
  saveFoodPriceOverride(
    slug: string,
    input: FoodPriceOverrideInput,
  ): Promise<components["schemas"]["FoodPriceOverrideResponse"]>;
  uploadCatalogueFoodImage(
    slug: string,
    asset: CatalogueFoodImageAsset,
  ): Promise<FoodCatalogueImageResponse>;
  getMealCatalogue(category?: MealCatalogueCategory): Promise<MealCataloguePage>;
}

const nutritionPath = "/api/v1/nutrition";

function jsonBody(value: object): TransportRequest["body"] {
  return value as TransportRequest["body"];
}

function foodPath(slug: string): string {
  return `${nutritionPath}/admin/foods/${encodeURIComponent(slug)}`;
}

function cataloguePath<TResponse>(
  request: AuthenticatedNutritionRequest,
  path: string,
  input: FoodCatalogueQuery = {},
): Promise<TResponse> {
  const parameters = new URLSearchParams();
  if (input.query) parameters.set("q", input.query);
  if (input.category) parameters.set("category", input.category);
  parameters.set("page", String(input.page ?? 1));
  parameters.set("page_size", String(input.pageSize ?? 24));
  return request<TResponse>({
    method: "GET",
    path: `${nutritionPath}/${path}?${parameters.toString()}`,
  });
}

export function createNutritionCatalogueApi(
  request: AuthenticatedNutritionRequest,
  upload?: AuthenticatedNutritionUpload,
): NutritionCatalogueApi {
  return {
    getFoodCatalogue: (input = {}) => cataloguePath<FoodCataloguePage>(request, "food-catalogue", input),

    getAdminFoodCatalogue: (input = {}) => cataloguePath<AdminFoodCataloguePage>(
      request,
      "admin/food-catalogue",
      input,
    ),

    saveCatalogueFood: (input) => request<CatalogueFoodResponse>({
      body: jsonBody(input),
      method: "POST",
      path: `${nutritionPath}/admin/foods`,
    }),

    deleteCatalogueFood: (slug) => request<void>({
      method: "DELETE",
      path: foodPath(slug),
    }),

    researchFoodPrice: (slug, apply = false) => request<SingleFoodPriceResearchResponse>({
      method: "POST",
      path: `${foodPath(slug)}/price-research${apply ? "?apply=true" : ""}`,
    }),

    saveFoodPriceOverride: (slug, input) => request<components["schemas"]["FoodPriceOverrideResponse"]>({
      body: jsonBody(input),
      method: "POST",
      path: `${foodPath(slug)}/price-override`,
    }),

    uploadCatalogueFoodImage: (slug, asset) => {
      if (upload === undefined) {
        return Promise.reject(new Error("Catalogue food image uploads are not configured"));
      }
      return upload<FoodCatalogueImageResponse>({
        method: "POST",
        parts: [{
          bytes: asset.bytes,
          contentType: asset.mimeType,
          filename: asset.filename,
          name: "file",
        }],
        path: `${foodPath(slug)}/image`,
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
