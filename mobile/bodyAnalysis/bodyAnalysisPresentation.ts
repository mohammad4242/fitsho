import type {
  BodyAnalysisExperienceIndicator,
  BodyAnalysisExperienceV4,
} from "@fitician/core/body-photos";

import type { FiticianIconName } from "../ui/icons";

export type BodyIndicatorTone = "aqua" | "amber" | "blue";

export type BodyIndicatorPresentation = {
  readonly caption: string;
  readonly icon: FiticianIconName;
  readonly id: "muscle_balance" | "visible_symmetry" | "upper_lower_balance";
  readonly score: number | null;
  readonly title: string;
  readonly tone: BodyIndicatorTone;
};

export function buildBodyIndicatorSummary(
  experience: BodyAnalysisExperienceV4,
): readonly BodyIndicatorPresentation[] {
  const indicators = experience.indicators;
  return [
    indicator(
      "muscle_balance",
      "تعادل عضلانی",
      "توسعه متوازن عضلات",
      indicators.muscle_balance ?? indicators.body_shape,
      "training",
      "aqua",
    ),
    indicator(
      "visible_symmetry",
      "تقارن ظاهری",
      indicatorCaption(indicators.visible_symmetry, "هماهنگی و تقارن مطلوب"),
      indicators.visible_symmetry,
      "bodyAnalysis",
      "blue",
    ),
    indicator(
      "upper_lower_balance",
      "توازن بالاتنه و پایین‌تنه",
      indicatorCaption(indicators.upper_lower_balance, "توازن ساختاری بدن"),
      indicators.upper_lower_balance,
      "target",
      "amber",
    ),
  ];
}

function indicator(
  id: BodyIndicatorPresentation["id"],
  title: string,
  caption: string,
  source: BodyAnalysisExperienceIndicator | undefined,
  icon: FiticianIconName,
  tone: BodyIndicatorTone,
): BodyIndicatorPresentation {
  return {
    caption,
    icon,
    id,
    score: normalizeScore(source?.score_percent),
    title,
    tone,
  };
}

function indicatorCaption(
  source: BodyAnalysisExperienceIndicator | undefined,
  fallback: string,
): string {
  if (source?.status === "balanced" || source?.status === "no_clear_difference") {
    return "در محدوده‌ی متعادل";
  }
  if (source?.status === "needs_improvement" || source?.status === "asymmetrical") {
    return "نیازمند توجه بیشتر";
  }
  return fallback;
}

function normalizeScore(value: number | null | undefined): number | null {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  return Math.min(100, Math.max(0, value));
}

export function bodyMetricProgress(value: number | null, minimum: number, maximum: number): number {
  if (value === null || !Number.isFinite(value) || maximum <= minimum) return 0;
  return Math.min(1, Math.max(0, (value - minimum) / (maximum - minimum)));
}

export function bodyBmiLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "ثبت نشده";
  if (value < 18.5) return "کمتر از محدوده نرمال";
  if (value < 25) return "محدوده نرمال";
  if (value < 30) return "بالاتر از محدوده نرمال";
  return "بالاتر از محدوده معمول";
}
