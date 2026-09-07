import { expect, it } from "vitest";

import { ApiError } from "@fitician/core";

import { authErrorMessage } from "./authError";

it("maps expected authentication failures to Persian user-safe messages", () => {
  expect(authErrorMessage(new ApiError(401, "Invalid email or password"))).toBe(
    "ایمیل یا رمز عبور درست نیست.",
  );
  expect(authErrorMessage(new ApiError(409, "Email is already registered"))).toBe(
    "این ایمیل قبلاً ثبت شده است.",
  );
  expect(authErrorMessage(new ApiError(429, "Too many requests"))).toBe(
    "تعداد درخواست‌ها زیاد است. کمی بعد دوباره تلاش کنید.",
  );
  expect(authErrorMessage(new ApiError(401, "Invalid or expired OTP"), "otp")).toBe(
    "کد ورود معتبر نیست یا منقضی شده است.",
  );
});

it("does not expose raw server or network errors", () => {
  expect(authErrorMessage(new Error("database password leaked"))).toBe(
    "ارتباط با فیتیشن برقرار نشد. اتصال اینترنت را بررسی کنید.",
  );
  expect(authErrorMessage(new ApiError(500, "internal details"))).toBe(
    "فیتیشن موقتاً در دسترس نیست. دوباره تلاش کنید.",
  );
});
