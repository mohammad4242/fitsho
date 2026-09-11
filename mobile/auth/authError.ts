import { ApiError } from "@fitician/core";

import { AppleSignInFlowError } from "./appleCredential";
import { GoogleSignInFlowError } from "./googleCredential";

export type AuthErrorContext = "apple" | "credentials" | "google" | "otp" | "recovery";

export function authErrorMessage(
  error: unknown,
  context: AuthErrorContext = "credentials",
): string {
  if (error instanceof GoogleSignInFlowError) return error.message;
  if (error instanceof AppleSignInFlowError) return error.message;
  if (error instanceof ApiError) {
    if (error.status === 401) {
      if (context === "otp") return "کد ورود معتبر نیست یا منقضی شده است.";
      if (context === "google") return "ورود با گوگل انجام نشد. دوباره تلاش کنید.";
      if (context === "apple") return "ورود با اپل انجام نشد. دوباره تلاش کنید.";
      return "ایمیل یا رمز عبور درست نیست.";
    }
    if (error.status === 409) {
      if (context === "apple") return "این حساب اپل به حساب دیگری متصل است.";
      if (context === "google") return "این حساب گوگل به حساب دیگری متصل است.";
      return "این ایمیل قبلاً ثبت شده است.";
    }
    if (error.status === 429) return "تعداد درخواست‌ها زیاد است. کمی بعد دوباره تلاش کنید.";
    if (error.status === 400) return "این درخواست معتبر نیست یا منقضی شده است.";
    if (error.status === 422) return "اطلاعات واردشده را بررسی کنید.";
    if (error.status >= 500) return "فیتیشن موقتاً در دسترس نیست. دوباره تلاش کنید.";
    return "احراز هویت انجام نشد. دوباره تلاش کنید.";
  }
  return "ارتباط با فیتیشن برقرار نشد. اتصال اینترنت را بررسی کنید.";
}
