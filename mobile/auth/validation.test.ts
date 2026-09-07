import { expect, it } from "vitest";

import {
  normalizePhoneNumber,
  validateConfirmation,
  validateEmail,
  validateOtpCode,
  validatePassword,
  validatePhoneNumber,
} from "./validation";

it("validates the shared auth input boundaries", () => {
  expect(validateEmail("member@example.com")).toBeUndefined();
  expect(validateEmail("not-an-email")).toBe("ایمیل را درست وارد کنید.");
  expect(validatePassword("short")).toBe("رمز عبور باید حداقل ۸ نویسه باشد.");
  expect(validatePassword("long password")).toBeUndefined();
  expect(validateConfirmation("one", "two")).toBe("تکرار رمز عبور یکسان نیست.");
});

it("normalizes Persian digits before phone and OTP validation", () => {
  expect(normalizePhoneNumber("۰۹۱۲۳۴۵۶۷۸۹")).toBe("09123456789");
  expect(validatePhoneNumber("۰۹۱۲۳۴۵۶۷۸۹")).toBeUndefined();
  expect(validateOtpCode("۱۲۳۴۵۶")).toBeUndefined();
  expect(validateOtpCode("۱۲۳۴۵")).toBe("کد ورود باید ۶ رقم باشد.");
});
