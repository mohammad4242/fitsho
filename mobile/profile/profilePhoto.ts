import type { ImagePickerOptions } from "expo-image-picker";
import type { MultipartPart } from "@fitician/core";

import type { UploadJob } from "../upload/uploadManager";
import { resolveBackendResourceUrl } from "../config/backendResourceUrl";

export const PROFILE_PHOTO_MAX_BYTES = 5 * 1024 * 1024;
export const PROFILE_PHOTO_MIN_DIMENSION = 128;
export const PROFILE_PHOTO_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export type ProfilePhotoMimeType = (typeof PROFILE_PHOTO_MIME_TYPES)[number];

export const PROFILE_PHOTO_PICKER_OPTIONS: Pick<
  ImagePickerOptions,
  "allowsEditing" | "aspect" | "base64" | "exif" | "mediaTypes"
> = {
  allowsEditing: true,
  aspect: [1, 1],
  base64: false,
  exif: false,
  mediaTypes: ["images"],
};

export type ProfilePhotoUploadAsset = {
  readonly bytes: Uint8Array;
  readonly height: number;
  readonly mimeType: ProfilePhotoMimeType;
  readonly width: number;
};

export type ProfilePhotoResponse = {
  readonly id: string;
  readonly profile_photo_url: string;
  readonly mime_type: ProfilePhotoMimeType;
  readonly byte_size: number;
  readonly width: number;
  readonly height: number;
  readonly updated_at: string;
};

export function createProfilePhotoUploadJob(asset: ProfilePhotoUploadAsset): UploadJob {
  if (asset.bytes.length === 0) throw new Error("Profile photo is empty");
  if (asset.bytes.length > PROFILE_PHOTO_MAX_BYTES) {
    throw new Error("Profile photo exceeds the size limit");
  }
  if (asset.width !== asset.height) throw new Error("Profile photo must be square");
  if (asset.width < PROFILE_PHOTO_MIN_DIMENSION) {
    throw new Error("Profile photo is too small");
  }

  const extension = asset.mimeType === "image/jpeg"
    ? "jpg"
    : asset.mimeType === "image/png"
      ? "png"
      : "webp";
  const part: MultipartPart = {
    bytes: asset.bytes,
    contentType: asset.mimeType,
    filename: `profile-photo.${extension}`,
    name: "file",
  };
  return {
    allowedContentTypes: [...PROFILE_PHOTO_MIME_TYPES],
    maxBytes: PROFILE_PHOTO_MAX_BYTES,
    method: "PUT",
    operation: "photo",
    parts: [part],
    path: "/api/v1/profile/photo",
  };
}

export function profilePhotoMimeTypeForAsset(
  mimeType: string | null | undefined,
  uri: string,
): ProfilePhotoMimeType | null {
  if (isProfilePhotoMimeType(mimeType)) return mimeType;
  const extension = uri.split(/[?#]/u)[0]?.split(".").pop()?.toLowerCase();
  if (extension === "jpg" || extension === "jpeg") return "image/jpeg";
  if (extension === "png") return "image/png";
  if (extension === "webp") return "image/webp";
  return null;
}

export function isProfilePhotoMimeType(value: string | null | undefined): value is ProfilePhotoMimeType {
  return PROFILE_PHOTO_MIME_TYPES.includes(value as ProfilePhotoMimeType);
}

export function resolveProfilePhotoUrl(path: string, apiBaseUrl: string): string {
  return resolveBackendResourceUrl(path, apiBaseUrl);
}

export function profilePhotoErrorMessage(error: unknown): string {
  const code = error instanceof Error && "code" in error
    ? String((error as Error & { code?: unknown }).code)
    : "";
  if (code === "invalid_geometry" || (error instanceof Error && error.message.includes("square"))) {
    return "عکس باید مربعی باشد.";
  }
  if (code === "invalid_file_size" || code === "image_too_large") {
    return "حجم یا ابعاد عکس مجاز نیست.";
  }
  if (code === "unsupported_format" || (error instanceof Error && error.message.includes("format"))) {
    return "فرمت عکس پشتیبانی نمی‌شود.";
  }
  if (code === "OFFLINE_UPLOAD_NOT_QUEUEABLE") {
    return "برای تغییر عکس به اینترنت وصل شو.";
  }
  if (error instanceof Error && /permission|denied/i.test(error.message)) {
    return "دسترسی به تصویر داده نشد. می‌توانی بعداً دوباره تلاش کنی.";
  }
  return "ذخیره عکس انجام نشد. دوباره تلاش کن.";
}
