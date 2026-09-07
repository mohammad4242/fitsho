import type {
  BinaryDownload,
  BinaryDownloadRequest,
  TransportRequest,
} from "@fitician/core";
import type { components } from "@fitician/core";

import type { AuthenticatedNutritionRequest } from "./nutritionApi";

export type DailyCheckInInput = components["schemas"]["DailyCheckInInput"];
export type CatalogueConsumptionInput = components["schemas"]["CatalogueConsumptionInput"];
export type QuickApproximationInput = components["schemas"]["QuickApproximationInput"];
export type ConsumptionEntryEditInput = components["schemas"]["ConsumptionEntryEditInput"];
export type PlannedMealTrackingInput = components["schemas"]["PlannedMealTrackingInput"];
export type FreeMealTrackingInput = components["schemas"]["FreeMealTrackingInput"];
export type NutritionDailyTracking = components["schemas"]["NutritionDailyTrackingResponse"];
export type NutritionTrackingEntry = components["schemas"]["NutritionTrackingEntryResponse"];
export type NutritionRecentFood = components["schemas"]["NutritionRecentFoodResponse"];
export type NutritionAdherence = components["schemas"]["NutritionAdherenceResponse"];
export type NutritionAdaptivePreferences = components["schemas"]["NutritionAdaptivePreferencesResponse"];
export type TargetUpdateConfirmationInput = components["schemas"]["TargetUpdateConfirmationInput"];
export type NutritionTargetUpdate = components["schemas"]["NutritionTargetUpdateResponse"];
export type FoodPhotoItemCorrectionInput = components["schemas"]["FoodPhotoItemCorrectionInput"];
export type NutritionFoodPhotoEstimate = components["schemas"]["NutritionFoodPhotoEstimateResponse"];
export type NutritionFoodPhotoConfirmation = components["schemas"]["NutritionFoodPhotoConfirmationResponse"];
export type NutritionFoodPhotoMacroPreview = components["schemas"]["NutritionFoodPhotoMacroPreviewResponse"];
export type PrivateAccessGrant = components["schemas"]["PrivateAccessGrantResponse"];
export type NutritionLabDocument = components["schemas"]["NutritionLabDocumentResponse"];
export type NutritionLabUpload = components["schemas"]["NutritionLabUploadResponse"];
export type NutritionLabRequest = components["schemas"]["NutritionLabRequestResponse"];
export type SupplementAcknowledgementInput = components["schemas"]["SupplementAcknowledgementInput"];
export type NutritionSupplementCatalogue = components["schemas"]["NutritionSupplementCatalogueResponse"];
export type NutritionSupplementOrder = components["schemas"]["NutritionSupplementOrderResponse"];

export type AuthenticatedNutritionDownload = (
  request: BinaryDownloadRequest,
) => Promise<BinaryDownload>;

export interface NutritionTrackingApi {
  addCatalogueFood(input: CatalogueConsumptionInput): Promise<NutritionTrackingEntry>;
  addQuickApproximation(input: QuickApproximationInput): Promise<NutritionTrackingEntry>;
  acknowledgeSupplementOrder(
    orderId: string,
    input?: SupplementAcknowledgementInput,
  ): Promise<NutritionSupplementOrder>;
  adjustPlannedMeal(mealId: string, input: PlannedMealTrackingInput): Promise<NutritionDailyTracking>;
  confirmFreeMealPhotoPreview(estimateId: string): Promise<NutritionFoodPhotoMacroPreview>;
  confirmPhoto(
    estimateId: string,
    input: components["schemas"]["FoodPhotoConfirmInput"],
  ): Promise<NutritionFoodPhotoConfirmation[]>;
  confirmTarget(input: TargetUpdateConfirmationInput): Promise<NutritionTargetUpdate>;
  correctPhotoItem(
    estimateId: string,
    itemId: string,
    input: FoodPhotoItemCorrectionInput,
  ): Promise<NutritionFoodPhotoEstimate>;
  deleteLabDocument(documentId: string): Promise<void>;
  deletePhotoEstimate(estimateId: string): Promise<void>;
  downloadLabDocument(documentId: string, token: string): Promise<BinaryDownload>;
  downloadPhoto(estimateId: string, token: string): Promise<BinaryDownload>;
  editEntry(entryId: string, input: ConsumptionEntryEditInput): Promise<NutritionTrackingEntry>;
  getAdaptivePreferences(): Promise<NutritionAdaptivePreferences>;
  getAdherence(start: string, end: string): Promise<NutritionAdherence>;
  getDailyTracking(entryDate: string): Promise<NutritionDailyTracking>;
  getLabDocuments(): Promise<NutritionLabDocument[]>;
  getLabRequests(): Promise<NutritionLabRequest[]>;
  getRecentFoods(limit?: number): Promise<NutritionRecentFood[]>;
  getSupplementCatalogue(): Promise<NutritionSupplementCatalogue[]>;
  getSupplementOrders(): Promise<NutritionSupplementOrder[]>;
  getTrackingHistory(start: string, end: string): Promise<NutritionDailyTracking[]>;
  grantLabAccess(documentId: string): Promise<PrivateAccessGrant>;
  grantPhotoAccess(estimateId: string): Promise<PrivateAccessGrant>;
  removeEntry(entryId: string): Promise<void>;
  saveDailyCheckIn(input: DailyCheckInInput): Promise<NutritionDailyTracking>;
  saveFreeMeal(
    mealId: string,
    input: FreeMealTrackingInput,
  ): Promise<NutritionDailyTracking>;
}

const nutritionPath = "/api/v1/nutrition";

function jsonBody(value: object): TransportRequest["body"] {
  return value as TransportRequest["body"];
}

function resourcePath(resource: string, id: string): string {
  return `${nutritionPath}/${resource}/${encodeURIComponent(id)}`;
}

function privateFilePath(resource: string, id: string, token: string): string {
  if (token.trim().length === 0) throw new Error("A private media access token is required");
  return `${resourcePath(resource, id)}/file?token=${encodeURIComponent(token)}`;
}

export function createNutritionTrackingApi(
  request: AuthenticatedNutritionRequest,
  download: AuthenticatedNutritionDownload,
): NutritionTrackingApi {
  return {
    addCatalogueFood(input) {
      return request<NutritionTrackingEntry>({
        body: jsonBody(input),
        method: "POST",
        path: `${nutritionPath}/tracking/entries/catalogue`,
      });
    },

    addQuickApproximation(input) {
      return request<NutritionTrackingEntry>({
        body: jsonBody(input),
        method: "POST",
        path: `${nutritionPath}/tracking/entries/quick`,
      });
    },

    acknowledgeSupplementOrder(orderId, input = {}) {
      return request<NutritionSupplementOrder>({
        body: jsonBody(input),
        method: "POST",
        path: `${resourcePath("supplement-orders", orderId)}/acknowledge`,
      });
    },

    adjustPlannedMeal(mealId, input) {
      return request<NutritionDailyTracking>({
        body: jsonBody(input),
        method: "PUT",
        path: `${resourcePath("tracking/planned-meals", mealId)}`,
      });
    },

    confirmFreeMealPhotoPreview(estimateId) {
      return request<NutritionFoodPhotoMacroPreview>({
        method: "POST",
        path: `${resourcePath("tracking/photo-estimates", estimateId)}/free-meal-preview`,
      });
    },

    confirmPhoto(estimateId, input) {
      return request<NutritionFoodPhotoConfirmation[]>({
        body: jsonBody(input),
        method: "POST",
        path: `${resourcePath("tracking/photo-estimates", estimateId)}/confirm`,
      });
    },

    confirmTarget(input) {
      return request<NutritionTargetUpdate>({
        body: jsonBody(input),
        method: "POST",
        path: `${nutritionPath}/targets/confirm-update`,
      });
    },

    correctPhotoItem(estimateId, itemId, input) {
      return request<NutritionFoodPhotoEstimate>({
        body: jsonBody(input),
        method: "PATCH",
        path: `${resourcePath("tracking/photo-estimates", estimateId)}/items/${encodeURIComponent(itemId)}`,
      });
    },

    deleteLabDocument(documentId) {
      return request<void>({
        method: "DELETE",
        path: resourcePath("labs", documentId),
      });
    },

    deletePhotoEstimate(estimateId) {
      return request<void>({
        method: "DELETE",
        path: resourcePath("tracking/photo-estimates", estimateId),
      });
    },

    downloadLabDocument(documentId, token) {
      return download({
        method: "GET",
        path: privateFilePath("labs", documentId, token),
        responseType: "binary",
      });
    },

    downloadPhoto(estimateId, token) {
      return download({
        method: "GET",
        path: privateFilePath("tracking/photo-estimates", estimateId, token),
        responseType: "binary",
      });
    },

    editEntry(entryId, input) {
      return request<NutritionTrackingEntry>({
        body: jsonBody(input),
        method: "PUT",
        path: resourcePath("tracking/entries", entryId),
      });
    },

    getAdaptivePreferences() {
      return request<NutritionAdaptivePreferences>({
        method: "GET",
        path: `${nutritionPath}/adaptive-preferences`,
      });
    },

    getAdherence(start, end) {
      const parameters = new URLSearchParams({ start, end });
      return request<NutritionAdherence>({
        method: "GET",
        path: `${nutritionPath}/adherence?${parameters.toString()}`,
      });
    },

    getDailyTracking(entryDate) {
      return request<NutritionDailyTracking>({
        method: "GET",
        path: `${nutritionPath}/tracking/days/${encodeURIComponent(entryDate)}`,
      });
    },

    getLabDocuments() {
      return request<NutritionLabDocument[]>({
        method: "GET",
        path: `${nutritionPath}/labs`,
      });
    },

    getLabRequests() {
      return request<NutritionLabRequest[]>({
        method: "GET",
        path: `${nutritionPath}/lab-requests`,
      });
    },

    getRecentFoods(limit) {
      const query = limit === undefined ? "" : `?limit=${encodeURIComponent(String(limit))}`;
      return request<NutritionRecentFood[]>({
        method: "GET",
        path: `${nutritionPath}/tracking/recent-foods${query}`,
      });
    },

    getSupplementCatalogue() {
      return request<NutritionSupplementCatalogue[]>({
        method: "GET",
        path: `${nutritionPath}/supplements/catalogue`,
      });
    },

    getSupplementOrders() {
      return request<NutritionSupplementOrder[]>({
        method: "GET",
        path: `${nutritionPath}/supplement-orders`,
      });
    },

    getTrackingHistory(start, end) {
      const parameters = new URLSearchParams({ start, end });
      return request<NutritionDailyTracking[]>({
        method: "GET",
        path: `${nutritionPath}/tracking/history?${parameters.toString()}`,
      });
    },

    grantLabAccess(documentId) {
      return request<PrivateAccessGrant>({
        method: "POST",
        path: `${resourcePath("labs", documentId)}/access-grant`,
      });
    },

    grantPhotoAccess(estimateId) {
      return request<PrivateAccessGrant>({
        method: "POST",
        path: `${resourcePath("tracking/photo-estimates", estimateId)}/access-grant`,
      });
    },

    removeEntry(entryId) {
      return request<void>({
        method: "DELETE",
        path: resourcePath("tracking/entries", entryId),
      });
    },

    saveDailyCheckIn(input) {
      return request<NutritionDailyTracking>({
        body: jsonBody(input),
        method: "PUT",
        path: `${nutritionPath}/tracking/check-in`,
      });
    },

    saveFreeMeal(mealId, input) {
      return request<NutritionDailyTracking>({
        body: jsonBody(input),
        method: "PUT",
        path: resourcePath("tracking/free-meals", mealId),
      });
    },
  } satisfies NutritionTrackingApi;
}
