import { ApiError } from "@fitician/core";

export const BODY_PHOTO_COUNTDOWN_SECONDS = 5 as const;
export const BODY_PHOTO_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export type BodyPhotoMimeType = (typeof BODY_PHOTO_MIME_TYPES)[number];
export type BodyPhotoCaptureSource = "camera" | "library";

export type BodyPhotoCapturedAsset = {
  readonly height: number;
  readonly mimeType: BodyPhotoMimeType;
  readonly privacyCropApplied: true;
  readonly source: BodyPhotoCaptureSource;
  readonly uri: string;
  readonly width: number;
};

export function advanceBodyPhotoCountdown(current: number | null): number | null {
  if (current === null || current <= 0) return null;
  return current - 1;
}

export function filePathToUri(path: string): string {
  if (path.startsWith("file://")) return path;
  return `file://${path}`;
}

export function bodyPhotoMimeTypeForAsset(
  mimeType: string | null | undefined,
  uri: string,
): BodyPhotoMimeType | null {
  if (isBodyPhotoMimeType(mimeType)) return mimeType;
  const extension = uri.split(/[?#]/u)[0]?.split(".").pop()?.toLowerCase();
  if (extension === "jpg" || extension === "jpeg") return "image/jpeg";
  if (extension === "png") return "image/png";
  if (extension === "webp") return "image/webp";
  return null;
}

export function isBodyPhotoMimeType(value: string | null | undefined): value is BodyPhotoMimeType {
  return BODY_PHOTO_MIME_TYPES.includes(value as BodyPhotoMimeType);
}

export function bodyPhotoCaptureErrorMessage(error: unknown): string {
  const name = typeof error === "object" && error !== null && "name" in error
    ? String(error.name)
    : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "دسترسی به دوربین داده نشد. از انتخاب عکس استفاده کن یا دوباره تلاش کن.";
  }
  if (name === "PhotoCaptureError") {
    return "ثبت عکس انجام نشد. دوباره تلاش کن.";
  }
  return "دوربین در دسترس نیست. از انتخاب عکس استفاده کن یا دوباره تلاش کن.";
}

export function bodyPhotoPrivacyProcessingErrorMessage(): string {
  return "پردازش امن عکس انجام نشد. عکس دیگری انتخاب کن یا دوباره تلاش کن.";
}

export function bodyPhotoUploadErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) {
    return "ارسال عکس از مسیر امن فیتیچیان انجام نشد. دوباره تلاش کن.";
  }
  if (error instanceof ApiError && error.status === 409) {
    return "وضعیت این نشست تغییر کرده است. نشست را دوباره باز کن.";
  }
  if (error instanceof ApiError && error.status >= 500) {
    return "سرویس ثبت عکس موقتاً در دسترس نیست. دوباره تلاش کن.";
  }
  if (error instanceof Error && /unavailable|empty|upload|configured|file/i.test(error.message)) {
    return "فایل عکس آماده ارسال نیست. دوباره عکس را انتخاب کن.";
  }
  return "ثبت این تصویر انجام نشد. عکس‌های ثبت‌شده حفظ شدند؛ دوباره تلاش کن.";
}
