import type { BodyAnalysisExperienceMessage, BodyAnalysisExperienceRegion } from "./types";

type Translate = (key: string, options?: Record<string, unknown>) => string;

const experienceTranslationKeys: Record<string, string> = {
  "body_analysis.first_impression.primary_priority": "bodyAnalysis.firstImpression.primaryPriority",
  "body_analysis.first_impression.room_to_grow": "bodyAnalysis.firstImpression.roomToGrow",
  "body_analysis.first_impression.visible_strengths": "bodyAnalysis.firstImpression.visibleStrengths",
  "body_analysis.first_impression.balanced": "bodyAnalysis.firstImpression.balanced",
  "body_analysis.indicators.upper_lower_balance": "bodyAnalysis.indicators.upperLowerBalance.message",
  "body_analysis.indicators.visible_symmetry": "bodyAnalysis.indicators.visibleSymmetry.message",
  "body_analysis.indicators.body_shape": "bodyAnalysis.indicators.bodyShape.message",
  "body_analysis.insights.stronger": "bodyAnalysis.insights.stronger",
  "body_analysis.insights.balanced": "bodyAnalysis.insights.balanced",
  "body_analysis.insights.room_to_grow": "bodyAnalysis.insights.roomToGrow",
  "body_analysis.insights.primary_priority": "bodyAnalysis.insights.primaryPriority",
  "body_analysis.insights.not_assessable": "bodyAnalysis.insights.notAssessable",
};

export function translateExperienceMessage(
  t: Translate,
  message: BodyAnalysisExperienceMessage,
  areaLabel: (area: string) => string,
): string {
  const translationKey = experienceTranslationKeys[message.message_key];
  if (translationKey === undefined) return t("bodyAnalysis.unavailable");
  return t(translationKey, translateParameters(message.parameters, areaLabel));
}

export function translateExperienceInsight(
  t: Translate,
  region: BodyAnalysisExperienceRegion,
  areaLabel: (area: string) => string,
): string | null {
  if (region.insight_key === null) return null;
  const translationKey = experienceTranslationKeys[region.insight_key];
  if (translationKey === undefined) return null;
  return t(translationKey, translateParameters({ ...region.insight_parameters, area: region.area }, areaLabel));
}

function translateParameters(
  parameters: Record<string, unknown>,
  areaLabel: (area: string) => string,
): Record<string, unknown> {
  return Object.fromEntries(Object.entries(parameters).map(([key, value]) => {
    if (key === "areas" && Array.isArray(value)) {
      return [key, value.map((area) => areaLabel(String(area))).join(", ")];
    }
    if (key === "area" && typeof value === "string") {
      return [key, areaLabel(value)];
    }
    return [key, value];
  }));
}
