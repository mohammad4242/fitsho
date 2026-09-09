export function formatPersianNumber(value: number, options: Intl.NumberFormatOptions = {}): string {
  return new Intl.NumberFormat("fa-IR", options).format(value);
}
