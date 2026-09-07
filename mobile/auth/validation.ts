const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩";

export function normalizePhoneNumber(value: string): string {
  return Array.from(value, (character) => {
    const persianIndex = PERSIAN_DIGITS.indexOf(character);
    if (persianIndex >= 0) return String(persianIndex);
    const arabicIndex = ARABIC_DIGITS.indexOf(character);
    return arabicIndex >= 0 ? String(arabicIndex) : character;
  }).join("").replace(/[\s()-]/g, "");
}

export function validateEmail(value: string): string | undefined {
  const email = value.trim();
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
    ? undefined
    : "ایمیل را درست وارد کنید.";
}

export function validatePassword(value: string): string | undefined {
  return value.length >= 8 ? undefined : "رمز عبور باید حداقل ۸ نویسه باشد.";
}

export function validateConfirmation(value: string, original: string): string | undefined {
  return value === original ? undefined : "تکرار رمز عبور یکسان نیست.";
}

export function validatePhoneNumber(value: string): string | undefined {
  const phone = normalizePhoneNumber(value);
  return /^(?:0\d{10}|\+98\d{10}|98\d{10})$/.test(phone)
    ? undefined
    : "شماره موبایل را درست وارد کنید.";
}

export function validateOtpCode(value: string): string | undefined {
  return /^\d{6}$/.test(normalizePhoneNumber(value))
    ? undefined
    : "کد ورود باید ۶ رقم باشد.";
}
