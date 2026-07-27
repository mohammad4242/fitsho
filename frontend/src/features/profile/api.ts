import { ApiError, request } from "../../shared/apiClient";
import type { Profile, ProfileInput, ProfilePatch } from "./types";

const profilePath = "/api/v1/profile";

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
