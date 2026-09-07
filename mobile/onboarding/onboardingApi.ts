import { ApiError, type TransportRequest } from "@fitician/core";
import type { NutritionEstimate, NutritionProfile, NutritionProfileInput, SafetyDecision, SafetyEvaluation, SafetyProfileInput, StructuredExercise, StructuredExerciseInput } from "@fitician/core/nutrition";
import type { ProductMode, Profile, ProfileInput, ProfileStatusResponse, SharedProfile, SharedProfileInput } from "@fitician/core/profile";

export type AuthenticatedRequest = <TResponse>(request: TransportRequest) => Promise<TResponse>;

export interface OnboardingApi {
  createNutritionEstimate(): Promise<NutritionEstimate>;
  createProfile(input: ProfileInput): Promise<Profile>;
  evaluateSafetyProfile(input: SafetyProfileInput): Promise<SafetyEvaluation>;
  getNutritionProfile(): Promise<NutritionProfile | null>;
  getProfileStatus(): Promise<ProfileStatusResponse>;
  getSafetyDecision(): Promise<SafetyDecision | null>;
  getSharedProfile(): Promise<SharedProfile | null>;
  getStructuredExercise(): Promise<StructuredExercise | null>;
  saveNutritionProfile(input: NutritionProfileInput): Promise<NutritionProfile>;
  saveSafetyProfile(input: SafetyProfileInput): Promise<SafetyDecision>;
  saveSharedProfile(input: SharedProfileInput): Promise<SharedProfile>;
  saveStructuredExercise(input: StructuredExerciseInput): Promise<StructuredExercise>;
  selectProductMode(mode: ProductMode): Promise<ProfileStatusResponse>;
}

const profilePath = "/api/v1/profile";
const nutritionPath = "/api/v1/nutrition";

function jsonBody(value: object): TransportRequest["body"] {
  return value as TransportRequest["body"];
}

async function optional<TResponse>(
  request: AuthenticatedRequest,
  path: string,
): Promise<TResponse | null> {
  try {
    return await request<TResponse>({ method: "GET", path });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function createOnboardingApi(request: AuthenticatedRequest): OnboardingApi {
  return {
    createNutritionEstimate: () => request<NutritionEstimate>({
      method: "POST",
      path: `${nutritionPath}/estimates`,
    }),
    createProfile: (input) => request<Profile>({
      body: jsonBody(input),
      method: "POST",
      path: profilePath,
    }),
    evaluateSafetyProfile: (input) => request<SafetyEvaluation>({
      body: jsonBody(input),
      method: "POST",
      path: `${nutritionPath}/safety/evaluate`,
    }),
    getNutritionProfile: () => optional<NutritionProfile>(request, `${nutritionPath}/profile`),
    getProfileStatus: () => request<ProfileStatusResponse>({
      method: "GET",
      path: `${profilePath}/status`,
    }),
    getSafetyDecision: () => optional<SafetyDecision>(request, `${nutritionPath}/safety`),
    getSharedProfile: () => optional<SharedProfile>(request, `${profilePath}/shared`),
    getStructuredExercise: () => optional<StructuredExercise>(request, `${nutritionPath}/structured-exercise`),
    saveNutritionProfile: (input) => request<NutritionProfile>({
      body: jsonBody(input),
      method: "PUT",
      path: `${nutritionPath}/profile`,
    }),
    saveSafetyProfile: (input) => request<SafetyDecision>({
      body: jsonBody(input),
      method: "PUT",
      path: `${nutritionPath}/safety`,
    }),
    saveSharedProfile: (input) => request<SharedProfile>({
      body: jsonBody(input),
      method: "PUT",
      path: `${profilePath}/shared`,
    }),
    saveStructuredExercise: (input) => request<StructuredExercise>({
      body: jsonBody(input),
      method: "PUT",
      path: `${nutritionPath}/structured-exercise`,
    }),
    selectProductMode: (mode) => request<ProfileStatusResponse>({
      body: { product_mode: mode },
      method: "POST",
      path: `${profilePath}/mode`,
    }),
  };
}
