import type { ImagePickerOptions } from "expo-image-picker";
import type { MultipartPart } from "@fitician/core";

import type { UploadJob } from "../upload/uploadManager";

export const FOOD_PHOTO_MAX_BYTES = 8 * 1024 * 1024;
export const LAB_DOCUMENT_MAX_BYTES = 12 * 1024 * 1024;
export const FOOD_PHOTO_MAX_PIXELS = 20_000_000;
export const LAB_DOCUMENT_MAX_PIXELS = 20_000_000;

export const FOOD_PHOTO_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export const LAB_DOCUMENT_MIME_TYPES = ["application/pdf", "image/jpeg", "image/png"] as const;

export type NutritionImageMimeType = (typeof FOOD_PHOTO_MIME_TYPES)[number];
export type NutritionLabMimeType = (typeof LAB_DOCUMENT_MIME_TYPES)[number];

export type NutritionImageAsset = {
  readonly bytes: Uint8Array;
  readonly filename: string;
  readonly height: number;
  readonly mimeType: string;
  readonly orientation?: number | null;
  readonly width: number;
};

export type NutritionLabAsset = {
  readonly bytes: Uint8Array;
  readonly filename: string;
  readonly height?: number | null;
  readonly mimeType: string;
  readonly orientation?: number | null;
  readonly width?: number | null;
};

export type FoodPhotoUploadInput = {
  readonly asset: NutritionImageAsset;
  readonly consent: boolean;
  readonly idempotencyKey?: string;
  readonly language?: "fa" | "en";
};

export type NutritionLabUploadMetadata = {
  readonly category?: string;
  readonly laboratoryName?: string;
  readonly requestId?: string;
  readonly testDate?: string;
  readonly userNote?: string;
};

export const FOOD_PHOTO_PICKER_OPTIONS: Pick<
  ImagePickerOptions,
  "allowsEditing" | "base64" | "exif" | "mediaTypes"
> = {
  allowsEditing: false,
  base64: false,
  exif: true,
  mediaTypes: ["images"],
};

function isSupportedMimeType(value: string, allowed: readonly string[]): boolean {
  return allowed.includes(value);
}

function extensionForMimeType(mimeType: string): string {
  switch (mimeType) {
    case "application/pdf":
      return "pdf";
    case "image/jpeg":
      return "jpg";
    case "image/png":
      return "png";
    case "image/webp":
      return "webp";
    default:
      throw new Error("Unsupported nutrition upload format");
  }
}

function validateOrientation(orientation: number | null | undefined): void {
  if (orientation === undefined || orientation === null) return;
  if (!Number.isInteger(orientation) || orientation < 1 || orientation > 8) {
    throw new Error("Nutrition upload has an invalid orientation");
  }
}

function validateDimensions(
  width: number | null | undefined,
  height: number | null | undefined,
  maxPixels: number,
  required: boolean,
): void {
  if (width === null || width === undefined || height === null || height === undefined) {
    if (required) throw new Error("Nutrition image dimensions are required");
    return;
  }
  if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
    throw new Error("Nutrition image dimensions are invalid");
  }
  if (width * height > maxPixels) {
    throw new Error("Nutrition image exceeds the pixel limit");
  }
}

function validateBytes(bytes: Uint8Array, maxBytes: number): void {
  if (bytes.length === 0) throw new Error("Nutrition upload is empty");
  if (bytes.length > maxBytes) throw new Error("Nutrition upload exceeds the size limit");
}

function validateFilename(filename: string): void {
  const hasControlCharacter = [...filename].some((character) => {
    const code = character.charCodeAt(0);
    return code <= 0x1f || code === 0x7f;
  });
  if (filename.trim().length === 0 || hasControlCharacter || filename.includes("/") || filename.includes("\\")) {
    throw new Error("Nutrition upload filename is invalid");
  }
}

function bytesAsText(bytes: Uint8Array): string {
  return new TextDecoder().decode(bytes);
}

function validatePdf(bytes: Uint8Array): void {
  const text = bytesAsText(bytes);
  if (!text.startsWith("%PDF-") || !text.slice(-1024).includes("%%EOF")) {
    throw new Error("Nutrition PDF document is invalid");
  }
  if (["/JavaScript", "/Launch", "/EmbeddedFile"].some((marker) => text.includes(marker))) {
    throw new Error("Nutrition PDF document contains unsafe content");
  }
}

function filePart(
  bytes: Uint8Array,
  mimeType: string,
  filename: string,
): MultipartPart {
  return { bytes, contentType: mimeType, filename, name: "file" };
}

function foodPhotoPart(asset: NutritionImageAsset, mimeType: NutritionImageMimeType): MultipartPart {
  return filePart(asset.bytes, mimeType, `food-photo.${extensionForMimeType(mimeType)}`);
}

export function nutritionMimeTypeForAsset(
  mimeType: string | null | undefined,
  uri: string,
): NutritionImageMimeType | null {
  if (mimeType && isSupportedMimeType(mimeType, FOOD_PHOTO_MIME_TYPES)) {
    return mimeType as NutritionImageMimeType;
  }
  const extension = uri.split(/[?#]/u)[0]?.split(".").pop()?.toLowerCase();
  if (extension === "jpg" || extension === "jpeg") return "image/jpeg";
  if (extension === "png") return "image/png";
  if (extension === "webp") return "image/webp";
  return null;
}

export function labMimeTypeForAsset(
  mimeType: string | null | undefined,
  uri: string,
): NutritionLabMimeType | null {
  if (mimeType && isSupportedMimeType(mimeType, LAB_DOCUMENT_MIME_TYPES)) {
    return mimeType as NutritionLabMimeType;
  }
  const extension = uri.split(/[?#]/u)[0]?.split(".").pop()?.toLowerCase();
  if (extension === "pdf") return "application/pdf";
  if (extension === "jpg" || extension === "jpeg") return "image/jpeg";
  if (extension === "png") return "image/png";
  return null;
}

export function createFoodPhotoUploadJob(input: FoodPhotoUploadInput): UploadJob {
  const { asset, consent, idempotencyKey, language = "fa" } = input;
  if (!consent) throw new Error("Food-photo consent is required");
  validateBytes(asset.bytes, FOOD_PHOTO_MAX_BYTES);
  validateFilename(asset.filename);
  if (!isSupportedMimeType(asset.mimeType, FOOD_PHOTO_MIME_TYPES)) {
    throw new Error("Unsupported food-photo format");
  }
  validateDimensions(asset.width, asset.height, FOOD_PHOTO_MAX_PIXELS, true);
  validateOrientation(asset.orientation);
  const mimeType = asset.mimeType as NutritionImageMimeType;
  const headers: Record<string, string> = {
    "Accept-Language": language,
    "X-Fitsho-Food-Photo-Consent": "true",
  };
  if (idempotencyKey !== undefined) headers["Idempotency-Key"] = idempotencyKey;
  return {
    allowedContentTypes: [...FOOD_PHOTO_MIME_TYPES],
    headers,
    idempotencyKey,
    maxBytes: FOOD_PHOTO_MAX_BYTES,
    method: "POST",
    operation: "photo",
    parts: [foodPhotoPart(asset, mimeType)],
    path: `/api/v1/nutrition/tracking/photo-estimates?language=${language}`,
  };
}

export function createLabDocumentUploadJob(input: {
  readonly asset: NutritionLabAsset;
  readonly idempotencyKey?: string;
  readonly metadata?: NutritionLabUploadMetadata;
}): UploadJob {
  const { asset, idempotencyKey, metadata = {} } = input;
  validateBytes(asset.bytes, LAB_DOCUMENT_MAX_BYTES);
  validateFilename(asset.filename);
  if (!isSupportedMimeType(asset.mimeType, LAB_DOCUMENT_MIME_TYPES)) {
    throw new Error("Unsupported laboratory document format");
  }
  validateDimensions(asset.width, asset.height, LAB_DOCUMENT_MAX_PIXELS, false);
  validateOrientation(asset.orientation);
  if (asset.mimeType === "application/pdf") validatePdf(asset.bytes);

  const parts: MultipartPart[] = [
    filePart(asset.bytes, asset.mimeType, `lab-document.${extensionForMimeType(asset.mimeType)}`),
  ];
  const metadataParts: readonly [string, string | undefined][] = [
    ["test_date", metadata.testDate],
    ["laboratory_name", metadata.laboratoryName],
    ["user_note", metadata.userNote],
    ["category", metadata.category],
    ["request_id", metadata.requestId],
  ];
  for (const [name, value] of metadataParts) {
    if (value !== undefined && value.length > 0) parts.push({ name, value });
  }

  return {
    allowedContentTypes: [...LAB_DOCUMENT_MIME_TYPES],
    idempotencyKey,
    maxBytes: LAB_DOCUMENT_MAX_BYTES,
    method: "POST",
    operation: "medical",
    parts,
    path: "/api/v1/nutrition/labs",
  };
}
