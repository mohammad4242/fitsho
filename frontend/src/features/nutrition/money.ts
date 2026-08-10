const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

export function formatTomanInput(value: string): string {
  const latin = value.replace(/[۰-۹]/g, (digit) => String(PERSIAN_DIGITS.indexOf(digit)));
  const digits = latin.replaceAll(/\D/g, "").replace(/^0+(?=\d)/, "");
  return digits ? Number(digits).toLocaleString("en-US", { useGrouping: true }) : "";
}

export function tomanToIrr(value: string): number {
  const normalized = formatTomanInput(value).replaceAll(",", "");
  return normalized ? Number(normalized) * 10 : 0;
}

export function irrToToman(value: number): string {
  return formatTomanInput(String(Math.floor(value / 10)));
}
