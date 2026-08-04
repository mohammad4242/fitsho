import { ApiError, request } from "../../shared/apiClient";
import type {
  ProductMode,
  Profile,
  ProfileInput,
  ProfilePatch,
  ProfileStatusResponse,
} from "./types";

const profilePath = "/api/v1/profile";

export function getProfileStatus(): Promise<ProfileStatusResponse> {
  return request<ProfileStatusResponse>(`${profilePath}/status`);
}

export function selectProductMode(productMode: ProductMode): Promise<ProfileStatusResponse> {
  return request<ProfileStatusResponse>(`${profilePath}/mode`, {
    method: "POST",
    body: JSON.stringify({ product_mode: productMode }),
  });
}

export async function getProfile(): Promise<Profile | null> {
  try {
    return await request<Profile>(profilePath);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export function createProfile(input: ProfileInput): Promise<Profile> {
  return request<Profile>(profilePath, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateProfile(patch: ProfilePatch): Promise<Profile> {
  return request<Profile>(profilePath, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}
