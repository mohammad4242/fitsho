import { useState, useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { AppIcon, Card, Notice } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import type { NutritionEstimate } from "./nutritionApi";
import { createNutritionApi } from "./nutritionApi";

const rateFields = [
  "requested_weight_change_kg_per_week",
  "recommended_weight_change_kg_per_week",
  "applied_weight_change_kg_per_week",
] as const;

export function NutritionWeightRateCard({
  estimate,
  onRefresh,
}: {
  readonly estimate: NutritionEstimate;
  readonly onRefresh?: () => void;
}) {
  const snapshot = estimate.input_snapshot;
  const requested = snapshot === undefined || snapshot === null ? null : numericSnapshotValue(snapshot[rateFields[0]]);
  const recommended = snapshot === undefined || snapshot === null ? null : numericSnapshotValue(snapshot[rateFields[1]]);
  const applied = snapshot === undefined || snapshot === null ? null : numericSnapshotValue(snapshot[rateFields[2]]);
  if (requested === null && recommended === null && applied === null) return null;

  const rateMode = snapshot?.weight_rate_mode === "user_override" ? "user_override" : "safe";
  const isOverride = rateMode === "user_override"
    || estimate.confidence_reasons.includes("WEIGHT_RATE_USER_OVERRIDE_APPLIED");
  const isClamped = !isOverride
    && estimate.confidence_reasons.includes("WEIGHT_RATE_CLAMPED_FOR_AUTOMATIC_SAFETY");

  return (
    <Card accessibilityLabel="نرخ تغییر وزن هفتگی" style={styles.card}>
      <View style={styles.header}>
        <View style={styles.titleGroup}>
          <AppIcon color={fiticianTokens.colors.aqua} name="scale" size={fiticianTokens.iconSize.md} />
          <Text style={styles.title}>نرخ تغییر وزن هفتگی</Text>
          <Text style={[styles.badge, isOverride ? styles.overrideBadge : isClamped ? styles.clampedBadge : styles.safeBadge]}>
            {isOverride
              ? "نرخ دلخواه من"
              : isClamped
                ? "تنظیم‌شده برای ایمنی خودکار"
                : "تنظیم ایمن پیشنهادی"}
          </Text>
        </View>
        <RateModeControls mode={rateMode} onRefresh={onRefresh} />
      </View>

      <View style={styles.rateGrid}>
        <RateValue label="درخواست شما" value={requested} />
        <RateValue label="مقدار پیشنهادی" value={recommended} />
        <RateValue
          label={isOverride ? "مقدار اعمال‌شده (نرخ مستقیم)" : isClamped ? "مقدار اعمال‌شده (تنظیم ایمنی)" : "مقدار اعمال‌شده"}
          value={applied}
          variant={isOverride ? "override" : isClamped ? "clamped" : "default"}
        />
      </View>
    </Card>
  );
}

function RateModeControls({
  mode,
  onRefresh,
}: {
  readonly mode: "safe" | "user_override";
  readonly onRefresh?: () => void;
}) {
  const auth = useMobileAuth();
  const api = useMemo(() => createNutritionApi(auth.request), [auth.request]);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function switchMode(nextMode: "safe" | "user_override") {
    if (nextMode === mode || switching) return;
    setSwitching(true);
    setError(null);
    try {
      const profile = await api.getNutritionProfile();
      if (profile !== null) {
        await api.saveNutritionProfile({ ...profile, weight_rate_mode: nextMode });
        await api.generateEstimate();
        onRefresh?.();
      }
    } catch {
      setError("تغییر حالت نرخ وزن انجام نشد؛ دوباره تلاش کن.");
    } finally {
      setSwitching(false);
    }
  }

  return (
    <View style={styles.modeArea}>
      <View style={styles.modeRow}>
        <Pressable
          accessibilityLabel="تنظیم ایمن پیشنهادی"
          accessibilityRole="button"
          accessibilityState={{ disabled: switching, selected: mode === "safe" }}
          disabled={switching}
          onPress={() => void switchMode("safe")}
          style={[styles.modeButton, mode === "safe" && styles.modeButtonActive]}
        >
          <AppIcon color={mode === "safe" ? fiticianTokens.colors.canvas : fiticianTokens.colors.aqua} name="shield" size={fiticianTokens.iconSize.sm} />
          <Text style={[styles.modeText, mode === "safe" && styles.modeTextActive]}>تنظیم ایمن پیشنهادی</Text>
        </Pressable>
        <Pressable
          accessibilityLabel="اعمال نرخ دلخواه من"
          accessibilityRole="button"
          accessibilityState={{ disabled: switching, selected: mode === "user_override" }}
          disabled={switching}
          onPress={() => void switchMode("user_override")}
          style={[styles.modeButton, mode === "user_override" && styles.modeButtonOverride]}
        >
          <AppIcon color={mode === "user_override" ? fiticianTokens.colors.canvas : fiticianTokens.colors.amber} name="flash" size={fiticianTokens.iconSize.sm} />
          <Text style={[styles.modeText, mode === "user_override" && styles.modeTextActive]}>اعمال نرخ دلخواه من</Text>
        </Pressable>
      </View>
      {error !== null ? <Notice compact message={error} variant="warning" /> : null}
    </View>
  );
}

function RateValue({
  label,
  value,
  variant = "default",
}: {
  readonly label: string;
  readonly value: number | null;
  readonly variant?: "clamped" | "default" | "override";
}) {
  return (
    <View style={[styles.rateItem, variant === "clamped" && styles.rateItemClamped, variant === "override" && styles.rateItemOverride]}>
      <Text style={styles.rateLabel}>{label}</Text>
      <Text style={styles.rateValue}>{value === null ? "—" : `${formatRate(value)} کیلوگرم/هفته`}</Text>
    </View>
  );
}

function numericSnapshotValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function formatRate(value: number): string {
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(value);
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: "center",
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    marginTop: 0,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: 2,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  card: {
    gap: fiticianTokens.spacing[3],
    marginBottom: fiticianTokens.spacing[1],
    padding: fiticianTokens.spacing[3],
  },
  clampedBadge: {
    backgroundColor: "rgba(239, 68, 68, 0.14)",
    borderColor: "rgba(239, 68, 68, 0.3)",
    color: fiticianTokens.colors.danger,
  },
  header: {
    alignItems: "flex-start",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
    justifyContent: "space-between",
  },
  modeArea: {
    alignItems: "flex-start",
    flexShrink: 0,
    gap: fiticianTokens.spacing[1],
  },
  modeButton: {
    alignItems: "center",
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[1],
    minHeight: 32,
    paddingHorizontal: fiticianTokens.spacing[2],
  },
  modeButtonActive: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  modeButtonOverride: {
    backgroundColor: fiticianTokens.colors.amber,
    borderColor: fiticianTokens.colors.amber,
  },
  modeRow: {
    alignItems: "center",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[1],
    justifyContent: "flex-end",
  },
  modeText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  modeTextActive: {
    color: fiticianTokens.colors.canvas,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  overrideBadge: {
    backgroundColor: "rgba(245, 158, 11, 0.14)",
    borderColor: "rgba(245, 158, 11, 0.3)",
    color: fiticianTokens.colors.amber,
  },
  rateGrid: {
    flexDirection: "column",
    gap: fiticianTokens.spacing[2],
  },
  rateItem: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[1],
    justifyContent: "space-between",
    minHeight: 44,
    minWidth: 0,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  rateItemClamped: {
    backgroundColor: "rgba(239, 68, 68, 0.08)",
    borderColor: "rgba(239, 68, 68, 0.25)",
  },
  rateItemOverride: {
    backgroundColor: "rgba(245, 158, 11, 0.08)",
    borderColor: "rgba(245, 158, 11, 0.25)",
  },
  rateLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    flexShrink: 1,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  rateValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  safeBadge: {
    backgroundColor: "rgba(80, 223, 206, 0.1)",
    borderColor: "rgba(80, 223, 206, 0.25)",
    color: fiticianTokens.colors.aqua,
  },
  title: {
    color: fiticianTokens.colors.ink,
    flexShrink: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    minWidth: 150,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  titleGroup: {
    alignItems: "center",
    flexGrow: 1,
    flexShrink: 1,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
    minWidth: 180,
  },
});
