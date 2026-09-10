import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import type { NutritionEstimate } from "./nutritionApi";
import { createNutritionTrackingApi } from "./nutritionTrackingApi";
import { nutritionKeys } from "../data/queryKeys";
import { useMobileAuth } from "../auth/MobileAuthProvider";
import type { ConnectivityStatus } from "../platform/connectivity";
import { Button, Card, MetricRing, Notice, Skeleton } from "../ui/components";
import { getMobileViewState } from "../ui/requestState";
import { LTR_TEXT, RTL_TEXT } from "../ui/rtl";
import { fiticianTokens } from "../ui/tokens";
import { NutritionDualMetricRing } from "./NutritionDualMetricRing";
import { NutritionAnimatedNumber } from "./NutritionAnimatedNumber";
import { formatNutritionNumber } from "./nutritionModel";

type NutritionSummaryCardProps =
  | {
    readonly connectivityStatus: ConnectivityStatus;
    readonly estimate: NutritionEstimate | null | undefined;
    readonly onRefresh?: () => void;
  }
  | {
    readonly error: boolean;
    readonly loading: boolean;
    readonly summary: {
      readonly carbohydrate: number | null;
      readonly consumedCalories: number | null;
      readonly estimatedDailyExpenditureCalories: number | null;
      readonly fat: number | null;
      readonly progress: number;
      readonly protein: number | null;
      readonly status: string;
      readonly targetCalories: number | null;
    };
  };

export function NutritionSummaryCard(props: NutritionSummaryCardProps) {
  if ("estimate" in props) {
    return <NutritionEstimateSummaryCard {...props} />;
  }
  return <LegacyNutritionSummaryCard {...props} />;
}

function NutritionEstimateSummaryCard({
  connectivityStatus,
  estimate,
  onRefresh,
}: {
  readonly connectivityStatus: ConnectivityStatus;
  readonly estimate: NutritionEstimate | null | undefined;
  readonly onRefresh?: () => void;
}) {
  const auth = useMobileAuth();
  const entryDate = useMemo(todayIsoDate, []);
  const api = useMemo(
    () => createNutritionTrackingApi(auth.request, auth.download),
    [auth.download, auth.request],
  );
  const dailyQuery = useQuery({
    enabled: estimate !== undefined && estimate !== null,
    queryFn: () => api.getDailyTracking(entryDate),
    queryKey: nutritionKeys.tracking(entryDate),
  });
  const dailyState = getMobileViewState(dailyQuery, { connectivityStatus });
  const daily = dailyState.status === "loading" ? null : "data" in dailyState ? dailyState.data : null;

  if (estimate === undefined) return <Skeleton height={252} />;
  if (estimate === null) return null;

  const target = (code: string) => estimate.targets[code];
  const goalCalories = firstNumericTarget(target("goal_calories"), "preferred");
  const tdee = firstNumericTarget(target("tdee"), "preferred", "minimum");
  const bmr = firstNumericTarget(target("bmr"), "preferred", "minimum");
  const additionalCalories = tdee === null || bmr === null ? null : Math.max(0, tdee - bmr);
  const tracked = daily?.actual_totals;
  const hasTrackedData = tracked !== undefined && (
    daily?.data_status === "sufficient"
    || (daily?.entries.length ?? 0) > 0
    || Object.values(tracked).some((value) => value > 0)
  );
  const macros = [
    { code: "protein_g", label: "پروتئین", target: target("protein") },
    { code: "carbohydrate_g", label: "کربوهیدرات", target: target("carbohydrate") ?? target("carbohydrates") },
    { code: "total_fat_g", label: "چربی", target: target("total_fat") ?? target("fat") },
  ] as const;

  return (
    <View style={summaryStyles.section}>
      <Card accessibilityLabel="خلاصه هدف‌ها" style={summaryStyles.card}>
        <View style={summaryStyles.targetArea}>
          <View style={summaryStyles.energyItem}>
            <View style={summaryStyles.targetCopy}>
              <Text style={summaryStyles.targetLabel}>کالری هدف</Text>
              {goalCalories === null ? (
                <Text style={summaryStyles.calorieValue}>تعیین نشده</Text>
              ) : (
                <NutritionAnimatedNumber style={summaryStyles.calorieValue} value={goalCalories} />
              )}
              <Text style={summaryStyles.unit}>
                {hasTrackedData
                  ? `دریافت امروز ${formatWebNumber(tracked?.energy_kcal ?? 0)} کیلوکالری`
                  : "کیلوکالری روزانه"}
              </Text>
            </View>
            {goalCalories !== null ? (
              <MetricRing
                animateOnFocus
                label="پیشرفت کالری هدف"
                progress={1}
                size={82}
                valueLabel="۱۰۰٪"
              />
            ) : null}
          </View>

          {tdee !== null ? (
            <View style={[summaryStyles.energyItem, summaryStyles.tdeeItem]}>
              <View style={summaryStyles.targetCopy}>
                <Text style={summaryStyles.targetLabel}>TDEE (کل مصرف روزانه)</Text>
                <NutritionAnimatedNumber style={summaryStyles.tdeeValue} value={tdee} />
                <View accessibilityLabel="تفکیک BMR و کالری اضافه در TDEE" style={summaryStyles.breakdownLegend}>
                  <View style={summaryStyles.breakdownItem}>
                    <Text style={summaryStyles.bmrDot}>●</Text>
                    {bmr === null ? (
                      <Text style={summaryStyles.breakdownTextLtr}>BMR: —</Text>
                    ) : (
                      <NutritionAnimatedNumber prefix="BMR: " style={summaryStyles.breakdownTextLtr} value={bmr} />
                    )}
                  </View>
                  <View style={summaryStyles.breakdownItem}>
                    <Text style={summaryStyles.additionalDot}>●</Text>
                    {additionalCalories === null ? (
                      <Text style={summaryStyles.breakdownText}>کالری اضافه: —</Text>
                    ) : (
                      <NutritionAnimatedNumber prefix="کالری اضافه: " style={summaryStyles.breakdownText} value={additionalCalories} />
                    )}
                  </View>
                </View>
              </View>
              <NutritionDualMetricRing
                label="تفکیک BMR و کالری اضافه در TDEE"
                primaryValue={bmr ?? 0}
                additionalValue={additionalCalories ?? 0}
                total={tdee}
              />
            </View>
          ) : null}
        </View>

        <View style={summaryStyles.confidenceRow}>
          <Text style={summaryStyles.confidence}>{confidenceLabel(estimate.confidence)}</Text>
          {estimate.is_stale && onRefresh ? <Button label="به‌روزرسانی" onPress={onRefresh} variant="ghost" /> : null}
        </View>

        <View accessibilityLabel="درشت‌مغذی‌های اصلی" style={summaryStyles.macroStrip}>
          {macros.map((macro) => (
            <View key={macro.code} style={summaryStyles.macroCell}>
              <Text style={summaryStyles.macroLabel}>{macro.label}</Text>
              <Text style={summaryStyles.macroValue}>
                {hasTrackedData && tracked?.[macro.code] !== undefined
                  ? `${formatWebNumber(tracked[macro.code])} گرم`
                  : formatTargetValue(macro.target)}
              </Text>
            </View>
          ))}
        </View>

        {dailyState.status === "offline" && daily === null ? (
          <Notice compact message="ثبت‌های امروز آفلاین در دسترس نیست؛ هدف‌های ذخیره‌شده نمایش داده می‌شوند." variant="offline" />
        ) : null}
        {dailyState.status === "error" && daily === null ? (
          <Notice compact message="دریافت ثبت‌های امروز انجام نشد؛ هدف‌های تغذیه نمایش داده می‌شوند." variant="warning" />
        ) : null}
      </Card>
    </View>
  );
}

function LegacyNutritionSummaryCard({
  error,
  loading,
  summary,
}: {
  readonly error: boolean;
  readonly loading: boolean;
  readonly summary: {
    readonly carbohydrate: number | null;
    readonly consumedCalories: number | null;
    readonly estimatedDailyExpenditureCalories: number | null;
    readonly fat: number | null;
    readonly progress: number;
    readonly protein: number | null;
    readonly status: string;
    readonly targetCalories: number | null;
  };
}) {
  const router = useRouter();
  if (loading) return <Skeleton height={180} />;

  return (
    <Card
      accessibilityLabel="نمایش جزئیات تغذیه"
      onPress={() => router.push("/member/nutrition")}
      style={styles.legacyHomeCard}
      variant="hero"
    >
      <View style={styles.legacyHomeHeader}>
        <View style={styles.legacyHomeCopy}>
          <Text style={styles.cardEyebrow}>هدف کالری روزانه</Text>
          <Text style={styles.calorieValue}>
            {summary.targetCalories === null ? "—" : formatNutritionNumber(summary.targetCalories)}
          </Text>
          <Text style={styles.unit}>
            مصرف امروز: {summary.consumedCalories === null ? "—" : formatNutritionNumber(summary.consumedCalories)}
          </Text>
          {summary.estimatedDailyExpenditureCalories !== null ? (
            <Text style={styles.unit}>
              مصرف تقریبی روزانه: {formatNutritionNumber(summary.estimatedDailyExpenditureCalories)}
            </Text>
          ) : null}
        </View>
        <MetricRing label="پیشرفت کالری امروز" progress={summary.progress} size={84} />
      </View>
      {error ? <Notice compact message="داده‌های تغذیه کامل دریافت نشدند." variant="warning" /> : null}
      <View style={styles.legacyMacroRow}>
        <Text style={styles.metricLabel}>پروتئین: {summary.protein === null ? "—" : formatNutritionNumber(summary.protein)}</Text>
        <Text style={styles.metricLabel}>کربوهیدرات: {summary.carbohydrate === null ? "—" : formatNutritionNumber(summary.carbohydrate)}</Text>
        <Text style={styles.metricLabel}>چربی: {summary.fat === null ? "—" : formatNutritionNumber(summary.fat)}</Text>
      </View>
    </Card>
  );
}

function firstNumericTarget(
  target: NutritionEstimate["targets"][string] | undefined,
  ...fields: readonly ("preferred" | "minimum" | "preferred_maximum" | "maximum")[]
): number | null {
  for (const field of fields) {
    const value = target?.[field];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

function formatTargetValue(target: NutritionEstimate["targets"][string] | undefined): string {
  const preferred = firstNumericTarget(target, "preferred");
  if (preferred !== null) return formatLocalizedValue(preferred, target?.unit);
  if (target?.minimum !== null && target?.minimum !== undefined && target.maximum !== null && target.maximum !== undefined) {
    return `${formatWebNumber(target.minimum)}–${formatWebNumber(target.maximum)} ${localizedUnit(target.unit)}`.trim();
  }
  return "تعیین نشده";
}

function formatLocalizedValue(value: number, unit: string | undefined): string {
  return `${formatWebNumber(value)} ${localizedUnit(unit)}`.trim();
}

function localizedUnit(unit: string | undefined): string {
  if (unit === "kcal/day") return "کیلوکالری";
  if (unit === "g/day") return "گرم";
  if (unit === "mg/day") return "میلی‌گرم";
  return unit ?? "";
}

function formatWebNumber(value: number): string {
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(value);
}

function confidenceLabel(confidence: string): string {
  if (confidence === "high") return "اطمینان بالا";
  if (confidence === "medium") return "اطمینان متوسط";
  return "اطمینان پایین";
}

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

const summaryStyles = StyleSheet.create({
  additionalDot: {
    color: fiticianTokens.colors.aqua,
  },
  bmrDot: {
    color: fiticianTokens.colors.blue,
  },
  breakdownLegend: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
    marginTop: fiticianTokens.spacing[1],
  },
  breakdownItem: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[1],
  },
  breakdownText: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
  },
  breakdownTextLtr: {
    ...LTR_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
  },
  card: {
    backgroundColor: fiticianTokens.colors.surface,
    gap: 0,
    overflow: "hidden",
    padding: 0,
  },
  calorieValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.display,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 44,
    textAlign: "right",
  },
  confidence: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  confidenceRow: {
    alignItems: "center",
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: 42,
    paddingHorizontal: fiticianTokens.spacing[4],
  },
  energyItem: {
    alignItems: "center",
    flex: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    minWidth: 0,
    padding: fiticianTokens.spacing[4],
  },
  macroCell: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[3],
  },
  macroLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  macroStrip: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
    flexDirection: "row",
  },
  macroValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
  },
  section: {
    marginBottom: fiticianTokens.spacing[1],
  },
  targetArea: {
    flexDirection: "column",
  },
  targetCopy: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  targetLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  tdeeItem: {
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
  },
  tdeeValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "right",
  },
  unit: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
});

const styles = StyleSheet.create({
  card: {
    gap: fiticianTokens.spacing[4],
    padding: fiticianTokens.spacing[5],
  },
  cardEyebrow: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  cardHeader: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  calorieValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.display,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 46,
    textAlign: "right",
  },
  headerCopy: {
    gap: fiticianTokens.spacing[1],
  },
  legacyHomeCard: {
    gap: fiticianTokens.spacing[4],
    padding: fiticianTokens.spacing[4],
  },
  legacyHomeCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  legacyHomeHeader: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  legacyMacroRow: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  metric: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flex: 1,
    gap: fiticianTokens.spacing[2],
    minWidth: 88,
    padding: fiticianTokens.spacing[3],
  },
  metricActual: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  metricGrid: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  metricLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  metricTop: {
    alignItems: "flex-start",
    gap: fiticianTokens.spacing[1],
  },
  metricValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
  },
  progressActual: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  progressBlock: {
    gap: fiticianTokens.spacing[2],
  },
  progressLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  progressLabels: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  section: {
    gap: fiticianTokens.spacing[3],
    marginBottom: fiticianTokens.spacing[4],
  },
  statusBadge: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  statusDot: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 6,
    width: 6,
  },
  statusText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  unit: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
