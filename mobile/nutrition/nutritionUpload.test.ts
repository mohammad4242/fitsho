import { expect, it } from "vitest";

import {
  FOOD_PHOTO_MAX_BYTES,
  FOOD_PHOTO_MAX_PIXELS,
  FOOD_PHOTO_PICKER_OPTIONS,
  LAB_DOCUMENT_MAX_BYTES,
  LAB_DOCUMENT_MAX_PIXELS,
  createFoodPhotoUploadJob,
  createLabDocumentUploadJob,
  labMimeTypeForAsset,
  nutritionMimeTypeForAsset,
} from "./nutritionUpload";

const validImage = {
  bytes: Uint8Array.from([1, 2, 3]),
  filename: "meal.png",
  height: 2000,
  mimeType: "image/png" as const,
  orientation: 6,
  width: 2000,
};

it("builds a consented, bounded, idempotent food-photo job", () => {
  const job = createFoodPhotoUploadJob({
    asset: validImage,
    consent: true,
    idempotencyKey: "photo-key-1",
    language: "fa",
  });

  expect(job).toMatchObject({
    allowedContentTypes: ["image/jpeg", "image/png", "image/webp"],
    idempotencyKey: "photo-key-1",
    maxBytes: FOOD_PHOTO_MAX_BYTES,
    method: "POST",
    operation: "photo",
    path: "/api/v1/nutrition/tracking/photo-estimates?language=fa",
  });
  expect(job.headers).toEqual({
    "Accept-Language": "fa",
    "Idempotency-Key": "photo-key-1",
    "X-Fitsho-Food-Photo-Consent": "true",
  });
  expect(job.parts).toEqual([
    expect.objectContaining({
      contentType: "image/png",
      filename: "food-photo.png",
      name: "file",
    }),
  ]);
});

it("rejects food-photo consent, dimensions, orientation, MIME, and size violations", () => {
  expect(() => createFoodPhotoUploadJob({ asset: validImage, consent: false })).toThrow(/consent/i);
  expect(() => createFoodPhotoUploadJob({
    asset: { ...validImage, height: 5000, width: 5000 },
    consent: true,
  })).toThrow(/pixel/i);
  expect(() => createFoodPhotoUploadJob({
    asset: { ...validImage, orientation: 9 },
    consent: true,
  })).toThrow(/orientation/i);
  expect(() => createFoodPhotoUploadJob({
    asset: { ...validImage, mimeType: "image/gif" },
    consent: true,
  })).toThrow(/format|MIME|content/i);
  expect(() => createFoodPhotoUploadJob({
    asset: { ...validImage, bytes: new Uint8Array(FOOD_PHOTO_MAX_BYTES + 1) },
    consent: true,
  })).toThrow(/size|large/i);
});

it("builds a member lab upload with validated metadata parts", () => {
  const pdf = Uint8Array.from(new TextEncoder().encode("%PDF-1.7\n1 0 obj\n%%EOF"));
  const job = createLabDocumentUploadJob({
    asset: {
      bytes: pdf,
      filename: "blood-report.pdf",
      mimeType: "application/pdf",
    },
    idempotencyKey: "lab-key-1",
    metadata: {
      category: "bloodwork",
      laboratoryName: "آزمایشگاه مرکزی",
      requestId: "request-1",
      testDate: "2026-09-06",
      userNote: "ناشتا بودم",
    },
  });

  expect(job).toMatchObject({
    allowedContentTypes: ["application/pdf", "image/jpeg", "image/png"],
    idempotencyKey: "lab-key-1",
    maxBytes: LAB_DOCUMENT_MAX_BYTES,
    method: "POST",
    operation: "medical",
    path: "/api/v1/nutrition/labs",
  });
  expect(job.parts).toEqual([
    expect.objectContaining({ contentType: "application/pdf", filename: "lab-document.pdf", name: "file" }),
    { name: "test_date", value: "2026-09-06" },
    { name: "laboratory_name", value: "آزمایشگاه مرکزی" },
    { name: "user_note", value: "ناشتا بودم" },
    { name: "category", value: "bloodwork" },
    { name: "request_id", value: "request-1" },
  ]);
});

it("rejects unsafe or incomplete laboratory files before upload", () => {
  expect(() => createLabDocumentUploadJob({
    asset: {
      bytes: Uint8Array.from(new TextEncoder().encode("not a pdf")),
      filename: "report.pdf",
      mimeType: "application/pdf",
    },
  })).toThrow(/PDF|document|invalid/i);
  expect(() => createLabDocumentUploadJob({
    asset: {
      bytes: Uint8Array.from(new TextEncoder().encode("%PDF-1.7\n/JavaScript\n%%EOF")),
      filename: "report.pdf",
      mimeType: "application/pdf",
    },
  })).toThrow(/PDF|unsafe|invalid/i);
  expect(() => createLabDocumentUploadJob({
    asset: {
      bytes: Uint8Array.from([1, 2, 3]),
      filename: "report.exe",
      mimeType: "application/octet-stream",
    },
  })).toThrow(/format|MIME|content/i);
  expect(() => createLabDocumentUploadJob({
    asset: {
      bytes: new Uint8Array(LAB_DOCUMENT_MAX_BYTES + 1),
      filename: "report.pdf",
      mimeType: "application/pdf",
    },
  })).toThrow(/size|large/i);
  expect(() => createLabDocumentUploadJob({
    asset: {
      bytes: Uint8Array.from([1, 2, 3]),
      filename: "report.png",
      height: 5000,
      mimeType: "image/png",
      width: 5000,
    },
  })).toThrow(/pixel/i);
});

it("uses camera/gallery image selection without broad media permission requests", () => {
  expect(FOOD_PHOTO_PICKER_OPTIONS).toMatchObject({
    allowsEditing: false,
    base64: false,
    exif: true,
    mediaTypes: ["images"],
  });
  expect(FOOD_PHOTO_PICKER_OPTIONS).not.toHaveProperty("requestMediaLibraryPermissionsAsync");
});

it("infers only supported nutrition upload MIME types from picker assets", () => {
  expect(nutritionMimeTypeForAsset(undefined, "picked.JPG")).toBe("image/jpeg");
  expect(nutritionMimeTypeForAsset("image/webp", "picked.bin")).toBe("image/webp");
  expect(nutritionMimeTypeForAsset("image/gif", "picked.gif")).toBeNull();
  expect(labMimeTypeForAsset(undefined, "report.PDF")).toBe("application/pdf");
  expect(labMimeTypeForAsset(undefined, "report.jpg")).toBe("image/jpeg");
  expect(labMimeTypeForAsset("image/webp", "report.webp")).toBeNull();
});

it("keeps backend pixel limits explicit for both protected upload types", () => {
  expect(FOOD_PHOTO_MAX_PIXELS).toBe(20_000_000);
  expect(LAB_DOCUMENT_MAX_PIXELS).toBe(20_000_000);
});
