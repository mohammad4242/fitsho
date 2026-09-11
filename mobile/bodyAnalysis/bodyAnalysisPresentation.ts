import type {
  BodyAnalysisExperienceGoal,
  BodyAnalysisExperienceIndicator,
  BodyAnalysisExperienceRegion,
  BodyAnalysisExperienceV4,
  BodyArea,
  BodyProgressTimelineItem,
} from "@fitician/core/body-photos";

import type { FiticianIconName } from "../ui/icons";
import { bodyAnalysisCopy } from "./bodyAnalysisCopy";

export type BodyIndicatorTone = "aqua" | "amber" | "blue";

export type BodyIndicatorPresentation = {
  readonly caption: string;
  readonly icon: FiticianIconName;
  readonly id: "muscle_balance" | "visible_symmetry" | "upper_lower_balance";
  readonly score: number | null;
  readonly subtitle: string;
  readonly title: string;
  readonly tone: BodyIndicatorTone;
};

export type BodyAnalysisExperienceCopy = {
  readonly firstLook: string;
  readonly firstLookTitle: string;
  readonly route: string;
};

export type BodyProgressLandingSummary = {
  readonly incomplete: readonly BodyProgressTimelineItem[];
  readonly latestAnalysis: BodyProgressTimelineItem | null;
  readonly submitted: readonly BodyProgressTimelineItem[];
};

export function buildBodyProgressLandingSummary(
  items: readonly BodyProgressTimelineItem[],
): BodyProgressLandingSummary {
  const incomplete = items.filter((item) => item.session.submitted_at === null);
  const submitted = items.filter((item) => item.session.submitted_at !== null);
  return {
    incomplete,
    latestAnalysis: submitted[0] ?? null,
    submitted,
  };
}

export function buildBodyIndicatorSummary(
  experience: BodyAnalysisExperienceV4,
): readonly BodyIndicatorPresentation[] {
  const indicators = experience.indicators;
  const muscleBalance = indicators.muscle_balance ?? indicators.body_shape;
  const muscleBalanceScore = normalizeScore(muscleBalance?.score_percent);
  return [
    indicator(
      "muscle_balance",
      "تناسب عضلات",
      muscleBalanceScore !== null && muscleBalanceScore >= 80
        ? bodyAnalysisCopy.indicators.states.balanced
        : "",
      muscleBalance,
      "training",
      "aqua",
      bodyAnalysisCopy.indicators.muscleBalance.message,
    ),
    indicator(
      "visible_symmetry",
      "تقارن بصری",
      indicatorCaption(indicators.visible_symmetry, "هماهنگی و تقارن مطلوب"),
      indicators.visible_symmetry,
      "bodyAnalysis",
      "blue",
      "هماهنگی و تقارن مطلوب",
    ),
    indicator(
      "upper_lower_balance",
      "تناسب بالاتنه و پایین‌تنه",
      indicatorCaption(indicators.upper_lower_balance, "توازن ساختاری بدن"),
      indicators.upper_lower_balance,
      "target",
      "amber",
      "توازن بالا و پایین‌تنه",
    ),
  ];
}

export function buildBodyAnalysisExperienceCopy(
  experience: BodyAnalysisExperienceV4,
): BodyAnalysisExperienceCopy {
  const areaLabel = (area: string) => bodyAreaLabel(area);
  return {
    firstLook: translateExperienceMessage(
      experience.first_impression.message_key,
      experience.first_impression.parameters,
      areaLabel,
    ),
    firstLookTitle: "نگاه اول",
    route: buildRouteMessage(experience, areaLabel),
  };
}

export function bodyAreaLabel(area: string): string {
  const labels: Partial<Record<BodyArea, string>> = {
    arms: "بازوها",
    back: "پشت",
    calves: "ساق",
    chest: "سینه",
    forearms: "ساعد",
    glutes: "باسن",
    hamstrings: "پشت پا",
    lats: "زیربغل",
    quads: "چهارسر ران",
    shoulders: "سرشانه",
    symmetry: "تقارن قابل‌مشاهده",
    visible_alignment_or_posture: "راستای قابل‌مشاهده بدن",
    waist_midsection: "کمر و میان‌تنه",
  };
  return labels[area as BodyArea] ?? "ناحیه بدن";
}

export function bodyRegionClassificationLabel(
  classification: BodyAnalysisExperienceRegion["display_classification"],
): string {
  const labels: Record<BodyAnalysisExperienceRegion["display_classification"], string> = {
    stronger: "نقطهٔ قوت ظاهری",
    balanced: "متعادل در این نماها",
    room_to_grow: "جا برای رشد",
    primary_priority: "ناحیهٔ اولویت‌دار",
    not_assessable: "قابل ارزیابی نیست",
  };
  return labels[classification];
}

export function bodyRegionInsight(region: BodyAnalysisExperienceRegion): string {
  const area = bodyAreaLabel(region.area);
  if (region.display_classification === "stronger") {
    return `${area} خوب جلو افتاده و فعلاً جزو اولویت‌های اصلیت نیست.`;
  }
  if (region.display_classification === "room_to_grow") {
    return `${area} بد نیست، ولی نسبت به قسمت‌های قوی‌تر بدنت جا برای رشد داره.`;
  }
  if (region.display_classification === "primary_priority") {
    return `${area} نسبت به بقیه بدنت عقب‌تره و بهتره فعلاً بیشتر روش کار کنی.`;
  }
  if (region.display_classification === "not_assessable") {
    return "این قسمت توی عکس‌ها به اندازهٔ کافی واضح نیست؛ روش نظر قطعی نمی‌دم.";
  }
  return `${area} نسبت به بقیه بدنت متعادله؛ فعلاً مشکل واضحی اینجا دیده نمی‌شه.`;
}

function indicator(
  id: BodyIndicatorPresentation["id"],
  title: string,
  caption: string,
  source: BodyAnalysisExperienceIndicator | undefined,
  icon: FiticianIconName,
  tone: BodyIndicatorTone,
  subtitle: string,
): BodyIndicatorPresentation {
  return {
    caption,
    icon,
    id,
    score: normalizeScore(source?.score_percent),
    subtitle,
    title,
    tone,
  };
}

function indicatorCaption(
  source: BodyAnalysisExperienceIndicator | undefined,
  fallback: string,
): string {
  if (source?.status === "balanced" || source?.status === "no_clear_difference") {
    return source.status === "balanced"
      ? bodyAnalysisCopy.indicators.states.balanced
      : bodyAnalysisCopy.indicators.states.no_clear_difference;
  }
  if (source?.status === "needs_improvement") {
    return "نیازمند بهبود";
  }
  if (source?.status === "asymmetrical") {
    return bodyAnalysisCopy.indicators.states.clear_visible_difference;
  }
  return fallback;
}

function translateExperienceMessage(
  messageKey: string,
  parameters: Record<string, unknown>,
  areaLabel: (area: string) => string,
): string {
  const areas = Array.isArray(parameters.areas)
    ? parameters.areas
      .filter((area): area is string => typeof area === "string")
      .map(areaLabel)
      .join("، ")
    : "این ناحیه‌ها";
  if (messageKey === "body_analysis.first_impression.primary_priority") {
    return `${areas} نسبت به بقیه بدنت عقب‌ترن.`;
  }
  if (messageKey === "body_analysis.first_impression.room_to_grow") {
    return `${areas} نسبت به قسمت‌های قوی‌تر بدنت جا برای رشد دارن.`;
  }
  if (messageKey === "body_analysis.first_impression.visible_strengths") {
    return `${areas} فعلاً خوب جلو افتادن.`;
  }
  if (messageKey === "body_analysis.first_impression.balanced") {
    return "فعلاً تفاوت واضحی بین ناحیه‌های بدنت دیده نمی‌شه.";
  }
  return "این نتیجه هنوز در دسترس نیست.";
}

function buildRouteMessage(
  experience: BodyAnalysisExperienceV4,
  areaLabel: (area: string) => string,
): string {
  const reason = experience.direction.reason_codes[0];
  if (reason === "low_body_mass_gain_priority") {
    return "با وزن فعلیت، اول بهتره یه مقدار وزن و حجم بگیری؛ بعد روی جزئیات عضلات کار کنیم.";
  }
  if (reason === "high_body_mass_reduction_priority") {
    return "با وزن و اندازه‌های فعلیت، اولویت اولت بهتره کاهش وزن باشه؛ بعد عضلات عقب‌تر رو هدف می‌گیریم.";
  }

  const goal = goalLabel(experience.direction.goal);
  if (reason === "legacy_goal_requires_confirmation") {
    return `مسیر فعلیت برای ${goal} ذخیره شده؛ قبل از ساخت برنامهٔ بعدی تأییدش می‌کنیم.`;
  }
  const focusAreas = experience.regions
    .filter((region) => (
      region.display_classification === "primary_priority"
      || region.display_classification === "room_to_grow"
    ))
    .slice(0, 3)
    .map((region) => areaLabel(region.area));
  if (focusAreas.length === 0) {
    return `مسیر فعلیت برای ${goal} منطقیه؛ فعلاً همین مسیر رو ادامه می‌دیم.`;
  }
  return `مسیر فعلیت برای ${goal} منطقیه؛ تمرکز اصلی رو می‌ذاریم روی ${focusAreas.join("، ")}.`;
}

function goalLabel(goal: BodyAnalysisExperienceGoal | null): string {
  const labels: Record<BodyAnalysisExperienceGoal, string> = {
    lose_weight: "کاهش وزن",
    gain_weight: "افزایش وزن",
    fat_loss: "کاهش چربی",
    build_muscle: "عضله‌سازی",
    body_recomposition: "بازترکیب بدنی",
    strength: "قدرت",
    improve_fitness: "بهبود آمادگی",
    maintain_weight: "حفظ وزن",
  };
  return goal === null ? "در دسترس نیست" : labels[goal];
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
