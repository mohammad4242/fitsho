import { ApiError, type TransportRequest } from "@fitician/core";
import type { NutritionProfile, NutritionProfileInput } from "@fitician/core/nutrition";
import type {
  Profile,
  ProfilePatch,
  SharedProfile,
  SharedProfileInput,
} from "@fitician/core/profile";

export type AuthenticatedProfileRequest = <TResponse>(request: TransportRequest) => Promise<TResponse>;

export interface ProfileApi {
  getNutritionProfile(): Promise<NutritionProfile | null>;
  getProfile(): Promise<Profile | null>;
  getSharedProfile(): Promise<SharedProfile | null>;
  saveNutritionProfile(input: NutritionProfileInput): Promise<NutritionProfile>;
  saveSharedProfile(input: SharedProfileInput): Promise<SharedProfile>;
  updateProfile(patch: ProfilePatch): Promise<Profile>;
}

const profilePath = "/api/v1/profile";
const nutritionPath = "/api/v1/nutrition";

function jsonBody(value: object): TransportRequest["body"] {
  return value as TransportRequest["body"];
}

async function optional<TResponse>(
  request: AuthenticatedProfileRequest,
  path: string,
): Promise<TResponse | null> {
  try {
    return await request<TResponse>({ method: "GET", path });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function createProfileApi(request: AuthenticatedProfileRequest): ProfileApi {
  return {
    getNutritionProfile: () => optional<NutritionProfile>(request, `${nutritionPath}/profile`),
    getProfile: () => optional<Profile>(request, profilePath),
    getSharedProfile: () => optional<SharedProfile>(request, `${profilePath}/shared`),
    saveNutritionProfile: (input) => request<NutritionProfile>({
      body: jsonBody(input),
      method: "PUT",
      path: `${nutritionPath}/profile`,
    }),
    saveSharedProfile: (input) => request<SharedProfile>({
      body: jsonBody(input),
      method: "PUT",
      path: `${profilePath}/shared`,
    }),
    updateProfile: (patch) => request<Profile>({
      body: jsonBody(patch),
      method: "PATCH",
      path: profilePath,
    }),
  };
}
