import { ApiError } from "@fitician/core";

import type { AccountDeletionStatus } from "./accountDeletionApi";

export interface AccountDeletionErrorMessage {
  readonly message: string;
  readonly requiresReauthentication: boolean;
}

export function isExactDeletionConfirmation(value: string): boolean {
  return value === "DELETE";
}

export function accountDeletionStatusLabel(status: AccountDeletionStatus): string {
  if (status === "none") return "درخواستی برای حذف ثبت نشده است";
  if (status === "pending") return "درخواست حذف در انتظار اجراست";
  if (status === "cancelled") return "درخواست حذف لغو شده است";
  return "حذف حساب تکمیل شده است";
}

export function accountDeletionError(error: unknown): AccountDeletionErrorMessage {
  const code = error instanceof ApiError ? error.code : null;
  const message = error instanceof Error ? error.message : "";
  if (code === "RECENT_AUTHENTICATION_REQUIRED" || message === "RECENT_AUTHENTICATION_REQUIRED") {
    return {
      message: "برای ادامه، یک‌بار خارج شو و دوباره وارد حساب شو.",
      requiresReauthentication: true,
    };
  }
  if (code === "INVALID_REAUTHENTICATION" || message === "INVALID_REAUTHENTICATION") {
    return {
      message: "رمز عبور درست نیست.",
      requiresReauthentication: false,
    };
  }
  if (code === "GRACE_PERIOD_EXPIRED" || message === "GRACE_PERIOD_EXPIRED") {
    return {
      message: "مهلت لغو این درخواست تمام شده است.",
      requiresReauthentication: false,
    };
  }
  if (error instanceof ApiError && error.status >= 500) {
    return {
      message: "حذف حساب فعلاً در دسترس نیست. بعداً دوباره تلاش کن.",
      requiresReauthentication: false,
    };
  }
  return {
    message: "درخواست انجام نشد. اتصال را بررسی کن و دوباره تلاش کن.",
    requiresReauthentication: false,
  };
}

export function formatDeletionDate(value: string | null): string {
  if (value === null) return "زمان نامشخص";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "زمان نامشخص";
  return date.toLocaleString("fa-IR");
}
