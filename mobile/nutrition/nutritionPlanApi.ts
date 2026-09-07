import { ApiError, type BinaryDownload, type BinaryDownloadRequest, type TransportRequest } from "@fitician/core";
import type { components } from "@fitician/core";

import type { AuthenticatedNutritionRequest } from "./nutritionApi";

export type WeeklyPlan = components["schemas"]["WeeklyPlanResponse"];
export type WeeklyPlanDay = components["schemas"]["WeeklyPlanDayResponse"];
export type WeeklyPlanMeal = components["schemas"]["WeeklyPlanMealResponse"];
export type WeeklyPlanFood = components["schemas"]["WeeklyPlanFoodResponse"];
export type WeeklyPlanNutrient = components["schemas"]["WeeklyPlanNutrientResponse"];
export type WeeklyPlanGeneration = components["schemas"]["WeeklyPlanGenerationResponse"];
export type WeeklyPlanHistoryItem = components["schemas"]["WeeklyPlanHistoryItemResponse"];
export type PlanBundleSelectionInput = components["schemas"]["PlanBundleSelectInput"];
export type PlanBundleSelectResponse = components["schemas"]["PlanBundleSelectResponse"];

export type AuthenticatedNutritionDownload = (
  request: BinaryDownloadRequest,
) => Promise<BinaryDownload>;

export interface NutritionPlanApi {
  downloadPdf(planId: string): Promise<BinaryDownload>;
  generate(): Promise<WeeklyPlanGeneration>;
  get(planId: string): Promise<WeeklyPlan>;
  getActive(): Promise<WeeklyPlan | null>;
  getHistory(): Promise<WeeklyPlanHistoryItem[]>;
  getLatest(): Promise<WeeklyPlan | null>;
  getLatestBundle(): Promise<WeeklyPlanGeneration | null>;
  selectBundle(bundleId: string, input: PlanBundleSelectionInput): Promise<PlanBundleSelectResponse>;
}

const nutritionPlansPath = "/api/v1/nutrition/plans";
const nutritionBundlesPath = "/api/v1/nutrition/plan-bundles";

function jsonBody(value: object): TransportRequest["body"] {
  return value as TransportRequest["body"];
}

async function optional<TResponse>(
  request: AuthenticatedNutritionRequest,
  path: string,
): Promise<TResponse | null> {
  try {
    return await request<TResponse>({ method: "GET", path });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function createNutritionPlanApi(
  request: AuthenticatedNutritionRequest,
  download: AuthenticatedNutritionDownload,
): NutritionPlanApi {
  return {
    downloadPdf(planId) {
      return download({
        method: "GET",
        path: `${nutritionPlansPath}/${encodeURIComponent(planId)}/pdf`,
        responseType: "binary",
      });
    },

    generate() {
      return request<WeeklyPlanGeneration>({ method: "POST", path: nutritionPlansPath });
    },

    get(planId) {
      return request<WeeklyPlan>({
        method: "GET",
        path: `${nutritionPlansPath}/${encodeURIComponent(planId)}`,
      });
    },

    getActive() {
      return optional<WeeklyPlan>(request, `${nutritionPlansPath}/active`);
    },

    getHistory() {
      return request<WeeklyPlanHistoryItem[]>({
        method: "GET",
        path: `${nutritionPlansPath}/history`,
      });
    },

    getLatest() {
      return optional<WeeklyPlan>(request, `${nutritionPlansPath}/latest`);
    },

    getLatestBundle() {
      return optional<WeeklyPlanGeneration>(request, `${nutritionBundlesPath}/latest`);
    },

    selectBundle(bundleId, input) {
      return request<PlanBundleSelectResponse>({
        body: jsonBody(input),
        method: "POST",
        path: `${nutritionBundlesPath}/${encodeURIComponent(bundleId)}/select`,
      });
    },
  };
}
