import { expect, it } from "vitest";

import { ApiError } from "@fitician/core";

import {
  accountDeletionError,
  accountDeletionStatusLabel,
  isExactDeletionConfirmation,
} from "./accountDeletionModel";

it("requires the exact destructive confirmation phrase", () => {
  expect(isExactDeletionConfirmation("DELETE")).toBe(true);
  expect(isExactDeletionConfirmation(" delete ")).toBe(false);
  expect(isExactDeletionConfirmation("CANCEL")).toBe(false);
});

it("maps deletion states and reauthentication without exposing server details", () => {
  expect(accountDeletionStatusLabel("pending")).toBe("درخواست حذف در انتظار اجراست");
  expect(accountDeletionError(new ApiError(403, "RECENT_AUTHENTICATION_REQUIRED"))).toEqual({
    message: "برای ادامه، یک‌بار خارج شو و دوباره وارد حساب شو.",
    requiresReauthentication: true,
  });
  expect(accountDeletionError(new ApiError(500, "internal stack trace"))).toEqual({
    message: "حذف حساب فعلاً در دسترس نیست. بعداً دوباره تلاش کن.",
    requiresReauthentication: false,
  });
});
