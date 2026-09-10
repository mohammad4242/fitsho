import { StyleSheet, Text, View } from "react-native";

import type { BodyProgressTimelineItem } from "@fitician/core/body-photos";

import { AppIcon, Card, SectionHeader } from "../ui/components";
import { RTL_LAYOUT, RTL_ROW } from "../ui/rtl";
import { fiticianTokens } from "../ui/tokens";
import { bodyAnalysisCopy } from "./bodyAnalysisCopy";

export function BodyAnalysisProgressStrip({
  currentSessionId,
  items,
}: {
  readonly currentSessionId: string;
  readonly items: readonly BodyProgressTimelineItem[];
}) {
  const submittedItems = items.filter(
    (item) => item.session.submitted_at !== null && item.snapshot !== null,
  );
  const recentItems = submittedItems.slice(0, 4).reverse();
  const points = recentItems.map((item) => ({
    bodyFat: bodyFatValue(item),
    date: formatDate(item.session.submitted_at ?? item.session.created_at),
    id: item.session.id,
    isCurrent: item.session.id === currentSessionId,
    weight: item.snapshot?.weight_kg ?? null,
  }));
  const first = points[0];
  const last = points[points.length - 1];
  const bodyFatChange = first !== undefined && last !== undefined && first.bodyFat !== null && last.bodyFat !== null
    ? round(last.bodyFat - first.bodyFat)
    : null;
  const weightChange = first !== undefined && last !== undefined && first.weight !== null && last.weight !== null
    ? round(last.weight - first.weight)
    : null;

  return (
    <View style={styles.container}>
      <SectionHeader
        eyebrow={bodyAnalysisCopy.progressStrip.subtitle}
        title={bodyAnalysisCopy.progressStrip.title}
      />

      {points.length <= 1 ? (
        <Card style={styles.singleCard} variant="glass">
          <View style={styles.singleIcon}>
            <AppIcon color={fiticianTokens.colors.aqua} name="clock" size={22} />
          </View>
          <View style={styles.singleCopy}>
            <Text style={styles.cardTitle}>{bodyAnalysisCopy.progressStrip.singleScanTitle}</Text>
            <Text style={styles.body}>{bodyAnalysisCopy.progressStrip.singleScanNotice}</Text>
          </View>
        </Card>
      ) : (
        <Card style={styles.card}>
          <View style={styles.summary}>
            {bodyFatChange !== null ? (
              <ChangeMetric
                label={bodyAnalysisCopy.progressStrip.bodyFatChange}
                value={formatChange(bodyFatChange, "٪")}
              />
            ) : null}
            {weightChange !== null ? (
              <ChangeMetric
                label={bodyAnalysisCopy.progressStrip.weightChange}
                value={formatChange(weightChange, "کیلو")}
              />
            ) : null}
          </View>
          <Text style={styles.recentLabel}>{bodyAnalysisCopy.progressStrip.recentScans}</Text>
          <View accessibilityRole="list" style={styles.timeline}>
            <View style={styles.timelineRail} />
            {points.map((point) => (
              <View key={point.id} style={styles.point}>
                <View style={[styles.pointDot, point.isCurrent && styles.pointDotCurrent]} />
                <Text style={[styles.pointDate, point.isCurrent && styles.pointDateCurrent]}>{point.date}</Text>
                <Text style={styles.pointMetric}>
                  {point.bodyFat === null ? "—" : `${formatNumber(point.bodyFat)}٪ BF`}
                </Text>
                <Text style={styles.pointMetric}>
                  {point.weight === null ? "—" : `${formatNumber(point.weight)} کیلو`}
                </Text>
              </View>
            ))}
          </View>
        </Card>
      )}
    </View>
  );
}

function ChangeMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.changeMetric}>
      <Text style={styles.changeLabel}>{label}</Text>
      <Text style={styles.changeValue}>{value}</Text>
    </View>
  );
}

function bodyFatValue(item: BodyProgressTimelineItem): number | null {
  const experienceValue = item.analysis?.experience_result?.body_composition.estimated_body_fat_percent;
  if (experienceValue !== null && experienceValue !== undefined) return experienceValue;
  const snapshot = item.snapshot;
  if (snapshot === null || snapshot === undefined || snapshot.height_cm <= 0 || snapshot.waist_circumference_cm <= 0) {
    return null;
  }
  const base = snapshot.sex === "male" ? 64 : 76;
  const rfm = base - 20 * (snapshot.height_cm / snapshot.waist_circumference_cm);
  return rfm > 2 && rfm < 80 ? round(rfm) : null;
}

function formatChange(value: number, unit: string): string {
  if (value === 0) return bodyAnalysisCopy.progressStrip.noChange;
  return `${value > 0 ? "+" : ""}${formatNumber(value)} ${unit}`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("fa-IR", { day: "numeric", month: "short" }).format(new Date(value));
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(value);
}

function round(value: number): number {
  return Math.round(value * 10) / 10;
}

const styles = StyleSheet.create({
  body: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  card: {
    gap: fiticianTokens.spacing[3],
  },
  cardTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  changeLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  changeMetric: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  changeValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  container: {
    gap: fiticianTokens.spacing[3],
  },
  point: {
    alignItems: "center",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  pointDate: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "center",
    writingDirection: "rtl",
  },
  pointDateCurrent: {
    color: fiticianTokens.colors.aqua,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  pointDot: {
    backgroundColor: fiticianTokens.colors.muted,
    borderColor: fiticianTokens.colors.canvas,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 3,
    height: 16,
    width: 16,
  },
  pointDotCurrent: {
    backgroundColor: fiticianTokens.colors.aqua,
  },
  pointMetric: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "center",
    writingDirection: "rtl",
  },
  recentLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  singleCard: {
    ...RTL_LAYOUT,
    ...RTL_ROW,
    alignItems: "flex-start",
    gap: fiticianTokens.spacing[3],
  },
  singleCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  singleIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderRadius: fiticianTokens.radii.pill,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  summary: {
    ...RTL_ROW,
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    gap: fiticianTokens.spacing[4],
    paddingBottom: fiticianTokens.spacing[3],
  },
  timeline: {
    ...RTL_ROW,
    gap: fiticianTokens.spacing[2],
    minHeight: 108,
    position: "relative",
  },
  timelineRail: {
    backgroundColor: fiticianTokens.colors.lineStrong,
    height: 2,
    left: "10%",
    position: "absolute",
    right: "10%",
    top: 7,
  },
});
