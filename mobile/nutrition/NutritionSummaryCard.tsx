import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import type { NutritionEstimate } from "./nutritionApi";
import { createNutritionTrackingApi } from "./nutritionTrackingApi";
import { nutritionKeys } from "../data/queryKeys";
import { useMobileAuth } from "../auth/MobileAuthProvider";
import type { ConnectivityStatus } from "../platform/connectivity";
import { Button, Card, Notice, ProgressBar, SectionHeader, Skeleton } from "../ui/components";
import { getMobileViewState } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import { buildNutritionSummary, type NutritionSummaryMetric } from "./nutritionSummaryModel";
import { formatNutritionNumber } from "./nutritionModel";

export function NutritionSummaryCard({
  connectivityStatus,
  estimate,
}: {
  readonly connectivityStatus: ConnectivityStatus;
  readonly estimate: NutritionEstimate | null | undefined;
}) {
  const auth = useMobileAuth();
  const router = useRouter();
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

  const summary = buildNutritionSummary(estimate, daily?.actual_totals ?? null);
  const trackingStatus = daily?.check_in_status ?? "not_recorded";
  return (
    <View style={styles.section}>
      <SectionHeader eyebrow="امروز" title="سوخت و هدف روزانه" />
      <Card variant="hero" style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={styles.statusBadge}>
            <View style={styles.statusDot} />
            <Text style={styles.statusText}>{trackingStatusLabel(trackingStatus)}</Text>
          </View>
          <View style={styles.headerCopy}>
            <Text style={styles.cardEyebrow}>هدف کالری</Text>
            <Text style={styles.calorieValue}>
              {summary.calories.target === null ? "—" : formatNutritionNumber(summary.calories.target)}
            </Text>
            <Text style={styles.unit}>کیلوکالری روزانه</Text>
          </View>
        </View>
        <View style={styles.progressBlock}>
          <View style={styles.progressLabels}>
            <Text style={styles.progressActual}>
              {summary.calories.actual === null
                ? "هنوز ثبت نشده"
                : `${formatNutritionNumber(summary.calories.actual)} دریافت‌شده`}
            </Text>
            <Text style={styles.progressLabel}>پیشرفت امروز</Text>
          </View>
          <ProgressBar
            label="پیشرفت کالری امروز"
            progress={summary.calories.progress ?? 0}
          />
        </View>
        <View style={styles.metricGrid}>
          {summary.macros.map((metric) => <MacroMetric key={metric.code} metric={metric} />)}
        </View>
        {dailyState.status === "offline" && daily === null ? (
          <Notice compact message="ثبت‌های امروز آفلاین در دسترس نیست؛ هدف‌های ذخیره‌شده نمایش داده می‌شوند." variant="offline" />
        ) : null}
        {dailyState.status === "error" && daily === null ? (
          <Notice compact message="دریافت ثبت‌های امروز انجام نشد؛ هدف‌های تغذیه نمایش داده می‌شوند." variant="warning" />
        ) : null}
        <Button label="ثبت غذا" onPress={() => router.push("/member/nutrition-tracking")} variant="secondary" />
      </Card>
    </View>
  );
}

function MacroMetric({ metric }: { readonly metric: NutritionSummaryMetric }) {
  return (
    <View style={styles.metric}>
      <View style={styles.metricTop}>
        <Text style={styles.metricValue}>{metric.target === null ? "—" : formatNutritionNumber(metric.target)}</Text>
        <Text style={styles.metricLabel}>{metric.label}</Text>
      </View>
      <ProgressBar
        color={metric.color}
        label={`${metric.label} پیشرفت`}
        progress={metric.progress ?? 0}
      />
      <Text style={styles.metricActual}>
        {metric.actual === null ? "ثبت نشده" : `${formatNutritionNumber(metric.actual)} ${metric.unit}`}
      </Text>
    </View>
  );
}

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function trackingStatusLabel(status: string): string {
  if (status === "on_plan") return "همسو با برنامه";
  if (status === "mostly_on_plan") return "تقریباً همسو";
  if (status === "off_plan") return "نیازمند توجه";
  return "امروز ثبت نشده";
}

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
    flexDirection: "row-reverse",
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
    flexDirection: "row-reverse",
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
    textAlign: "left",
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
    flexDirection: "row-reverse",
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
    flexDirection: "row-reverse",
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
