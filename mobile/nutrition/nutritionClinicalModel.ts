import type { components } from "@fitician/core";

const labStatusLabels: Readonly<Record<string, string>> = {
  cancelled: "لغوشده",
  pending_review: "در انتظار بررسی پزشک",
  reviewed: "بررسی‌شده",
  uploaded: "بارگذاری‌شده",
};

const labRequestStatusLabels: Readonly<Record<string, string>> = {
  cancelled: "لغوشده",
  requested: "درخواست‌شده",
  reviewed: "بررسی‌شده",
  uploaded: "بارگذاری‌شده",
};

const supplementStatusLabels: Readonly<Record<components["schemas"]["NutritionSupplementOrderStatus"], string>> = {
  active: "فعال",
  cancelled: "لغوشده",
  completed: "تکمیل‌شده",
  discontinued: "متوقف‌شده",
  draft: "پیش‌نویس",
  prescribed: "تجویزشده",
};

export function labReviewStatusLabel(status: string): string {
  return labStatusLabels[status] ?? status;
}

export function labRequestStatusLabel(status: string): string {
  return labRequestStatusLabels[status] ?? status;
}

export function supplementStatusLabel(
  status: components["schemas"]["NutritionSupplementOrderStatus"],
): string {
  return supplementStatusLabels[status];
}

export function supplementSafetyPresentation(
  exposure: components["schemas"]["NutritionSupplementExposureResponse"],
): {
  readonly blocked: boolean;
  readonly message: string;
  readonly title: string;
} {
  if (exposure.hard_blocks.length > 0) {
    return {
      blocked: true,
      message: "این مکمل به‌دلیل هشدار ایمنی فعلاً قابل تأیید نیست.",
      title: "نیازمند بررسی ایمنی",
    };
  }
  return {
    blocked: false,
    message: "هشدار مسدودکننده‌ای برای این سفارش ثبت نشده است.",
    title: "بررسی ایمنی انجام شده است",
  };
}
