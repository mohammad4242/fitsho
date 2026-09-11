import type { components } from "@fitician/core";

import { formatNutritionNumber } from "./nutritionModel";
import type { NutritionFoodPhotoEstimate } from "./nutritionTrackingApi";

const checkInLabels: Readonly<Record<components["schemas"]["NutritionDailyCheckInStatus"], string>> = {
  mostly_on_plan: "بیشتر مطابق برنامه",
  not_recorded: "ثبت نشده",
  off_plan: "خارج از برنامه",
  on_plan: "مطابق برنامه",
};

const sourceLabels: Readonly<Record<components["schemas"]["NutritionConsumptionSource"], string>> = {
  catalogue_manual: "ثبت از فهرست غذا",
  free_meal: "وعده آزاد",
  photo_estimated_confirmed: "عکس تأییدشده",
  photo_estimated_edited: "عکس ویرایش‌شده",
  planned_adjusted: "وعده تنظیم‌شده",
  planned_confirmed: "وعده برنامه‌ریزی‌شده",
  professional_entry: "ثبت متخصص",
  quick_approximation: "برآورد سریع",
};

export function checkInStatusLabel(
  status: components["schemas"]["NutritionDailyCheckInStatus"],
): string {
  return checkInLabels[status];
}

export function trackingDataStatusLabel(
  status: components["schemas"]["NutritionDailyTrackingResponse"]["data_status"],
): string {
  return status === "sufficient" ? "داده کافی است" : "داده کافی نیست";
}

export function trackingSourceLabel(
  source: components["schemas"]["NutritionConsumptionSource"],
): string {
  return sourceLabels[source];
}

export function adherencePercentLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${formatNutritionNumber(Math.round(value))}٪`;
}

export function photoEstimatePresentation(estimate: NutritionFoodPhotoEstimate): {
  readonly canConfirm: boolean;
  readonly message: string;
  readonly title: string;
} {
  if (estimate.status === "queued") {
    return {
      canConfirm: false,
      message: "می‌توانی از برنامه استفاده کنی؛ نتیجه بعد از آماده شدن نمایش داده می‌شود.",
      title: "تحلیل عکس در صف است",
    };
  }
  if (estimate.status === "analyzing") {
    return {
      canConfirm: false,
      message: "تحلیل در پس‌زمینه انجام می‌شود؛ لازم نیست در این صفحه بمانی.",
      title: "عکس در حال تحلیل است",
    };
  }
  if (estimate.status === "failed") {
    return {
      canConfirm: false,
      message: "تحلیل انجام نشد؛ عکس را دوباره ارسال کن.",
      title: "تحلیل عکس ناموفق بود",
    };
  }
  if (estimate.status === "expired") {
    return {
      canConfirm: false,
      message: "مهلت این نتیجه تمام شده است؛ عکس را دوباره ارسال کن.",
      title: "مهلت تحلیل تمام شده است",
    };
  }
  if (estimate.status === "deleted") {
    return {
      canConfirm: false,
      message: "این برآورد دیگر در دسترس نیست.",
      title: "برآورد حذف شده است",
    };
  }
  if (estimate.status === "confirmed") {
    return {
      canConfirm: false,
      message: "این نتیجه قبلاً در پیگیری روزانه ثبت شده است.",
      title: "برآورد ثبت شده است",
    };
  }
  return {
    canConfirm: true,
    message: estimate.needs_user_confirmation
      ? "این نتیجه تخمینی است و قبل از ثبت باید آن را بررسی کنی."
      : "این نتیجه هنوز تخمینی است و تا تأیید تو نهایی نمی‌شود.",
    title: "برآورد عکس؛ نیازمند بررسی",
  };
}
