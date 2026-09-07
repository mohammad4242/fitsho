import { ApiError, type TransportRequest } from "@fitician/core";
import type { components } from "@fitician/core";

export type NutritionProfile = components["schemas"]["NutritionProfileResponse"];
export type NutritionProfileInput = components["schemas"]["NutritionProfileInput"];
export type SafetyProfileInput = components["schemas"]["SafetyProfileInput"];
export type SafetyDecision = components["schemas"]["SafetyDecisionResponse"];
export type SafetyEvaluation = components["schemas"]["SafetyEvaluationResponse"];
export type StructuredExercise = components["schemas"]["StructuredExerciseResponse"];
export type StructuredExerciseInput = components["schemas"]["StructuredExerciseInput"];
export type NutritionEstimate = components["schemas"]["NutritionEstimateResponse"];
export type PhysicianReviewRequirement = components["schemas"]["PhysicianReviewRequirementResponse"];

export type AuthenticatedNutritionRequest = <TResponse>(
  request: TransportRequest,
) => Promise<TResponse>;

export interface NutritionApi {
  evaluateSafety(input: SafetyProfileInput): Promise<SafetyEvaluation>;
  generateEstimate(): Promise<NutritionEstimate>;
  getCurrentEstimate(): Promise<NutritionEstimate | null>;
  getNutritionProfile(): Promise<NutritionProfile | null>;
  getReviewRequirement(): Promise<PhysicianReviewRequirement | null>;
  getSafety(): Promise<SafetyDecision | null>;
  getStructuredExercise(): Promise<StructuredExercise | null>;
  saveNutritionProfile(input: NutritionProfileInput): Promise<NutritionProfile>;
  saveSafety(input: SafetyProfileInput): Promise<SafetyDecision>;
  saveStructuredExercise(input: StructuredExerciseInput): Promise<StructuredExercise>;
}

const nutritionPath = "/api/v1/nutrition";

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

export function createNutritionApi(request: AuthenticatedNutritionRequest): NutritionApi {
  return {
    evaluateSafety: (input) => request<SafetyEvaluation>({
      body: jsonBody(input),
      method: "POST",
      path: `${nutritionPath}/safety/evaluate`,
    }),
    generateEstimate: () => request<NutritionEstimate>({
      method: "POST",
      path: `${nutritionPath}/estimates`,
    }),
    getCurrentEstimate: () => optional<NutritionEstimate>(
      request,
      `${nutritionPath}/estimates/current`,
    ),
    getNutritionProfile: () => optional<NutritionProfile>(request, `${nutritionPath}/profile`),
    getReviewRequirement: () => optional<PhysicianReviewRequirement>(
      request,
      `${nutritionPath}/review-requirement`,
    ),
    getSafety: () => optional<SafetyDecision>(request, `${nutritionPath}/safety`),
    getStructuredExercise: () => optional<StructuredExercise>(
      request,
      `${nutritionPath}/structured-exercise`,
    ),
    saveNutritionProfile: (input) => request<NutritionProfile>({
      body: jsonBody(input),
      method: "PUT",
      path: `${nutritionPath}/profile`,
    }),
    saveSafety: (input) => request<SafetyDecision>({
      body: jsonBody(input),
      method: "PUT",
      path: `${nutritionPath}/safety`,
    }),
    saveStructuredExercise: (input) => request<StructuredExercise>({
      body: jsonBody(input),
      method: "PUT",
      path: `${nutritionPath}/structured-exercise`,
    }),
  };
}
