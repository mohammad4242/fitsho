import { useRouter } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { AppIcon, Button, Card, ProgressBar } from "../ui/components";
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

  return (
    <Card onPress={() => router.push("/member/nutrition")} style={styles.card} variant="glass">
      <View style={styles.header}>
        <View style={styles.headingCopy}>
          <Text style={styles.eyebrow}>سوخت امروز</Text>
          <Text style={styles.title}>تغذیه</Text>
        </View>
        <View style={styles.iconBadge}>
          <AppIcon color={fiticianTokens.colors.aqua} name="nutrition" size={fiticianTokens.iconSize.lg} />
        </View>
      </View>

      {loading ? (
        <View style={styles.loadingBlock}>
          <Text style={styles.loadingText}>در حال خواندن هدف روزانه…</Text>
          <ProgressBar label="در حال بارگذاری تغذیه" progress={0.42} />
        </View>
      ) : hasTarget ? (
        <>
          <View style={styles.calorieRow}>
            <View style={styles.calorieCopy}>
              <Text style={styles.calorieValue}>{formatNumber(consumed ?? summary.targetCalories ?? 0)}</Text>
              <Text style={styles.calorieLabel}>
                {consumed === null
                  ? "هدف کالری روزانه"
                  : `از ${formatNumber(summary.targetCalories ?? 0)} کیلوکالری`}
              </Text>
            </View>
            <View style={styles.progressRing}>
              <Text style={styles.progressValue}>{Math.round(summary.progress * 100)}٪</Text>
              <Text style={styles.progressLabel}>امروز</Text>
            </View>
          </View>
          <ProgressBar label="پیشرفت کالری امروز" progress={summary.progress} />
          <View style={styles.macroRow}>
            <Macro label="پروتئین" value={summary.protein} color={fiticianTokens.colors.aqua} />
            <Macro label="کربوهیدرات" value={summary.carbohydrate} color="#78a9ff" />
            <Macro label="چربی" value={summary.fat} color="#f2b85b" />
          </View>
          <View style={styles.statusRow}>
            <Text style={styles.statusText}>{statusLabel(summary.status)}</Text>
            <Text style={styles.statusHint}>برای ثبت وعده‌ها وارد تغذیه شو</Text>
          </View>
          {error ? <Text style={styles.errorText}>بخشی از اطلاعات تغذیه به‌روز نشد.</Text> : null}
        </>
      ) : (
        <View style={styles.emptyBlock}>
          <Text style={styles.emptyTitle}>هدف غذایی هنوز آماده نیست</Text>
          <Text style={styles.emptyText}>پروفایل تغذیه‌ات را کامل کن تا هدف روزانه را ببینی.</Text>
          <Button label="رفتن به تغذیه" onPress={() => router.push("/member/nutrition")} variant="secondary" />
        </View>
      )}
    </Card>
  );
}

function Macro({ color, label, value }: { readonly color: string; readonly label: string; readonly value: number | null }) {
  return (
    <View style={styles.macro}>
      <View style={[styles.macroDot, { backgroundColor: color }]} />
      <Text style={styles.macroValue}>{value === null ? "—" : `${formatNumber(value)}g`}</Text>
      <Text style={styles.macroLabel}>{label}</Text>
    </View>
  );
}

function formatNumber(value: number): string {
  return Math.round(value).toLocaleString("fa-IR");
}

function statusLabel(status: HomeNutritionSummary["status"]): string {
  if (status === "pending") return "در انتظار بررسی پزشک";
  if (status === "on_plan") return "امروز روی مسیر هستی";
  if (status === "off_plan") return "امروز از مسیر فاصله داشتی";
  return "هدف روزانه فعال است";
}

const styles = StyleSheet.create({
  card: {
    gap: 16,
  },
  calorieCopy: {
    flex: 1,
    gap: 4,
  },
  calorieLabel: {
    color: "#94aba5",
    fontFamily: "Vazirmatn",
    fontSize: 12,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  calorieRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: 16,
  },
  calorieValue: {
    color: "#e8f4f1",
    fontFamily: "Sora",
    fontSize: 29,
    fontWeight: "800",
    textAlign: "right",
  },
  emptyBlock: {
    gap: 10,
  },
  emptyText: {
    color: "#94aba5",
    fontFamily: "Vazirmatn",
    fontSize: 13,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  emptyTitle: {
    color: "#e8f4f1",
    fontFamily: "Vazirmatn",
    fontSize: 16,
    fontWeight: "700",
    textAlign: "right",
    writingDirection: "rtl",
  },
  errorText: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  eyebrow: {
    color: "#50dfce",
    fontFamily: "Vazirmatn",
    fontSize: 13,
    fontWeight: "700",
    textAlign: "right",
    writingDirection: "rtl",
  },
  header: {
    alignItems: "center",
    flexDirection: "row-reverse",
    justifyContent: "space-between",
  },
  headingCopy: {
    flex: 1,
    gap: 4,
  },
  iconBadge: {
    alignItems: "center",
    backgroundColor: "rgba(80,223,206,0.10)",
    borderColor: "rgba(80,223,206,0.22)",
    borderRadius: 16,
    borderWidth: 1,
    height: 52,
    justifyContent: "center",
    width: 52,
  },
  loadingBlock: {
    gap: 12,
  },
  loadingText: {
    color: "#94aba5",
    fontFamily: "Vazirmatn",
    fontSize: 13,
    textAlign: "right",
    writingDirection: "rtl",
  },
  macro: {
    alignItems: "flex-end",
    flex: 1,
    gap: 3,
  },
  macroDot: {
    borderRadius: 99,
    height: 7,
    marginBottom: 2,
    width: 7,
  },
  macroLabel: {
    color: "#94aba5",
    fontFamily: "Vazirmatn",
    fontSize: 11,
    textAlign: "right",
    writingDirection: "rtl",
  },
  macroRow: {
    flexDirection: "row-reverse",
    gap: 12,
  },
  macroValue: {
    color: "#e8f4f1",
    fontFamily: "Sora",
    fontSize: 14,
    fontWeight: "700",
  },
  progressLabel: {
    color: "#94aba5",
    fontFamily: "Vazirmatn",
    fontSize: 10,
    writingDirection: "rtl",
  },
  progressRing: {
    alignItems: "center",
    backgroundColor: "rgba(80,223,206,0.10)",
    borderColor: "rgba(80,223,206,0.28)",
    borderRadius: 48,
    borderWidth: 5,
    height: 86,
    justifyContent: "center",
    width: 86,
  },
  progressValue: {
    color: "#50dfce",
    fontFamily: "Sora",
    fontSize: 17,
    fontWeight: "800",
  },
  statusHint: {
    color: "#94aba5",
    flex: 1,
    fontFamily: "Vazirmatn",
    fontSize: 11,
    textAlign: "left",
    writingDirection: "rtl",
  },
  statusRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: 8,
  },
  statusText: {
    color: "#66c89f",
    fontFamily: "Vazirmatn",
    fontSize: 12,
    fontWeight: "700",
    textAlign: "right",
    writingDirection: "rtl",
  },
  title: {
    color: "#e8f4f1",
    fontFamily: "Lalezar",
    fontSize: 25,
    lineHeight: 34,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
