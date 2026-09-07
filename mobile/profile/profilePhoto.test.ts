import { expect, it } from "vitest";

import { ApiError } from "@fitician/core";

import {
  PROFILE_PHOTO_MAX_BYTES,
  PROFILE_PHOTO_PICKER_OPTIONS,
  createProfilePhotoUploadJob,
  profilePhotoErrorMessage,
  profilePhotoMimeTypeForAsset,
  resolveProfilePhotoUrl,
} from "./profilePhoto";

it("builds a protected square-photo upload job with backend limits", () => {
  const job = createProfilePhotoUploadJob({
    bytes: Uint8Array.from([1, 2, 3]),
    height: 512,
    mimeType: "image/jpeg",
    width: 512,
  });

  expect(job).toMatchObject({
    allowedContentTypes: ["image/jpeg", "image/png", "image/webp"],
    maxBytes: PROFILE_PHOTO_MAX_BYTES,
    method: "PUT",
    operation: "photo",
    path: "/api/v1/profile/photo",
  });
  expect(job.parts).toEqual([
    expect.objectContaining({
      contentType: "image/jpeg",
      filename: "profile-photo.jpg",
      name: "file",
    }),
  ]);
});

it("rejects obvious client-side photo violations before upload", () => {
  expect(() => createProfilePhotoUploadJob({
    bytes: Uint8Array.from([1]),
    height: 512,
    mimeType: "image/jpeg",
    width: 640,
  })).toThrow("square");

  expect(profilePhotoMimeTypeForAsset("image/gif", "picked.gif")).toBeNull();
});

it("uses the system image picker without requesting broad media access", () => {
  expect(PROFILE_PHOTO_PICKER_OPTIONS).toMatchObject({
    allowsEditing: true,
    aspect: [1, 1],
    base64: false,
    exif: false,
    mediaTypes: ["images"],
  });
  expect(PROFILE_PHOTO_PICKER_OPTIONS).not.toHaveProperty("requestMediaLibraryPermissionsAsync");
});

it("resolves private profile URLs and keeps user-facing failures safe", () => {
  expect(resolveProfilePhotoUrl("/api/v1/profile/photo/user-1?v=1", "https://api.fitician.test")).toBe(
    "https://api.fitician.test/api/v1/profile/photo/user-1?v=1",
  );
  expect(resolveProfilePhotoUrl("https://cdn.fitician.test/photo.jpg", "https://api.fitician.test")).toBe(
    "https://cdn.fitician.test/photo.jpg",
  );
  expect(profilePhotoErrorMessage(new ApiError(422, "invalid", null, "invalid_geometry"))).toBe(
    "عکس باید مربعی باشد.",
  );
  expect(profilePhotoErrorMessage(new Error("permission denied"))).toBe(
    "دسترسی به تصویر داده نشد. می‌توانی بعداً دوباره تلاش کنی.",
  );
});
