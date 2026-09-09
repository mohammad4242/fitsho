import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { AppIcon, Button, MetricRing, MetricStrip, StateSkeleton } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import type { HomeNutritionSummary } from "./homeModel";

export interface NutritionSummaryCardProps {
  readonly error?: boolean;
  readonly loading: boolean;
  readonly summary: HomeNutritionSummary;
}

export function NutritionSummaryCard({ error = false, loading, summary }: NutritionSummaryCardProps) {
  const router = useRouter();
  const hasTarget = summary.targetCalories !== null;
  const consumed = summary.consumedCalories;

  if (loading && !hasTarget) return <StateSkeleton variant="card" />;

  return (
    <Pressable
      accessibilityLabel="نمایش جزئیات تغذیه"
      accessibilityRole="button"
      onPress={() => router.push("/member/nutrition")}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={styles.content}>
        <View style={styles.header}>
          <View style={styles.headingCopy}>
            <Text style={styles.eyebrow}>سوخت امروز</Text>
            <Text style={styles.title}>تغذیه روزانه</Text>
          </View>
          <View style={styles.iconBadge}>
            <AppIcon color={fiticianTokens.colors.aqua} name="nutrition" size={fiticianTokens.iconSize.md} />
          </View>
        </View>

        {hasTarget ? (
          <>
            <View style={styles.calorieRow}>
              <View style={styles.calorieValues}>
                {consumed !== null ? (
                  <CalorieMetric label="مصرف امروز" value={consumed} />
                ) : null}
                <CalorieMetric
                  label="هدف کالری روزانه"
                  value={summary.targetCalories ?? 0}
                  withDivider={consumed !== null}
                />
              </View>
              <MetricRing label="پیشرفت کالری امروز" progress={summary.progress} />
            </View>
            <MetricStrip
              items={[
                { accent: fiticianTokens.colors.aqua, label: "پروتئین", value: formatMetric(summary.protein) },
                { accent: fiticianTokens.colors.blue, label: "کربوهیدرات", value: formatMetric(summary.carbohydrate) },
                { accent: fiticianTokens.colors.amber, label: "چربی", value: formatMetric(summary.fat) },
              ]}
            />
            {error ? <Text style={styles.errorText}>بخشی از اطلاعات تغذیه به‌روز نشد.</Text> : null}
          </>
        ) : (
          <View style={styles.emptyBlock}>
            <Text style={styles.emptyTitle}>هدف غذایی هنوز آماده نیست</Text>
            <Text style={styles.emptyText}>پروفایل تغذیه‌ات را کامل کن تا هدف روزانه را ببینی.</Text>
            <Button label="رفتن به تغذیه" onPress={() => router.push("/member/nutrition")} variant="secondary" />
          </View>
        )}
      </View>
    </Pressable>
  );
}

function CalorieMetric({
  label,
  value,
  withDivider = false,
}: {
  readonly label: string;
  readonly value: number;
  readonly withDivider?: boolean;
}) {
  return (
    <View style={[styles.calorieMetric, withDivider && styles.calorieMetricDivider]}>
      <Text style={styles.calorieValue}>{formatNumber(value)}</Text>
      <Text style={styles.calorieLabel}>{label}</Text>
    </View>
  );
}

function formatNumber(value: number): string {
  return Math.round(value).toLocaleString("fa-IR");
}

function formatMetric(value: number | null): string {
  return value === null ? "—" : `${formatNumber(value)}g`;
}

const styles = StyleSheet.create({
  calorieMetric: { flex: 1, gap: fiticianTokens.spacing[1], minWidth: 0 },
  calorieMetricDivider: {
    borderRightColor: fiticianTokens.colors.line,
    borderRightWidth: 1,
    paddingRight: fiticianTokens.spacing[3],
  },
  calorieLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 19,
    textAlign: "right",
    writingDirection: "rtl",
  },
  calorieValues: {
    flex: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    minWidth: 0,
  },
  calorieRow: { alignItems: "center", flexDirection: "row-reverse", gap: fiticianTokens.spacing[4] },
  calorieValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.metric,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "right",
  },
  card: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.extraLarge,
    borderWidth: 1,
    elevation: fiticianTokens.shadows.card.elevation,
    minHeight: 236,
    shadowColor: fiticianTokens.shadows.card.color,
    shadowOffset: fiticianTokens.shadows.card.offset,
    shadowOpacity: fiticianTokens.shadows.card.opacity,
    shadowRadius: fiticianTokens.shadows.card.radius,
  },
  content: { gap: fiticianTokens.spacing[4], padding: fiticianTokens.spacing[4] },
  emptyBlock: { gap: fiticianTokens.spacing[2] },
  emptyText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  emptyTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  errorText: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  header: { alignItems: "center", flexDirection: "row-reverse", justifyContent: "space-between" },
  headingCopy: { flex: 1, gap: 2 },
  iconBadge: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 46,
    justifyContent: "center",
    width: 46,
  },
  pressed: { opacity: 0.88, transform: [{ scale: fiticianTokens.motion.pressedScale }] },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
    lineHeight: 32,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
