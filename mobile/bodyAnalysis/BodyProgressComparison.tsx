import { StyleSheet, Text, View } from "react-native";

import type {
  BodyArea,
  BodyProgressComparison,
  BodyProgressMeasurementDelta,
  BodyProgressState,
  BodyProgressVisualTransition,
  NormalizedBodyProgressComparisonV1,
  NormalizedBodyProgressComparisonV2,
} from "@fitician/core/body-photos";

import { bodyAreaLabel } from "./bodyAnalysisPresentation";
import { Card, DisclosureCard, ProgressBar, SectionHeader } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";

export function BodyProgressComparisonCard({ comparison }: { readonly comparison: BodyProgressComparison }) {
  const normalized = comparison.normalized_result;
  return (
    <View style={styles.section}>
      <SectionHeader eyebrow="از جلسه قبلی تا امروز" title="مقایسه پیشرفت" />
      <Card style={styles.card}>
        {normalized.schema_version === "2.0" ? (
          <V2Comparison comparison={normalized} />
        ) : (
          <LegacyComparison comparison={normalized} />
        )}
      </Card>
    </View>
  );
}

function V2Comparison({ comparison }: { readonly comparison: NormalizedBodyProgressComparisonV2 }) {
  const measurements = comparison.measurement_deltas.filter(isAvailableMeasurement);
  const biggestChange = selectBiggestChange(comparison.visual_transitions);
  return (
    <View style={styles.section}>
      <Text style={styles.body}>
        {formatNumber(comparison.interval_days)} روز بین {formatDate(comparison.previous_session_date)} و {formatDate(comparison.current_session_date)}
      </Text>
      <ChangeSummary transition={biggestChange} />
      <SectionHeader title="اندازه‌گیری‌ها" />
      {measurements.length === 0 ? (
        <Text style={styles.muted}>برای این دو بررسی اندازه‌گیری دقیقی ثبت نشده.</Text>
      ) : (
        measurements.map((measurement) => <MeasurementComparison key={measurement.measurement} delta={measurement} />)
      )}
      {comparison.visual_transitions.length > 0 ? (
        <DisclosureCard summary="مشاهده‌های تصویری استاندارد، نه اندازه‌گیری مستقیم عضله" title="جزئیات تغییرهای تصویری">
          <View style={styles.section}>
            {comparison.visual_transitions.map(visualChangeText)}
          </View>
        </DisclosureCard>
      ) : null}
    </View>
  );
}

function LegacyComparison({ comparison }: { readonly comparison: NormalizedBodyProgressComparisonV1 }) {
  const changes = comparison.areas.filter((item) => item.state !== "unchanged").slice(0, 4);
  return <ChangeSummary transition={selectBiggestChange(comparison.areas)} empty={changes.length === 0} />;
}

function ChangeSummary({
  empty = false,
  transition,
}: {
  readonly empty?: boolean;
  readonly transition: { body_area: BodyArea; state: BodyProgressState } | null;
}) {
  return (
    <View style={styles.changeSummary}>
      <Text style={styles.changeTitle}>بیشترین تغییر</Text>
      {transition === null || empty ? (
        <Text style={styles.muted}>تغییر واضحی نسبت به بررسی قبلی دیده نشد.</Text>
      ) : (
        <>
          <Text style={styles.changeArea}>{bodyAreaLabel(transition.body_area)}</Text>
          <Text style={styles.body}>
            {transition.state === "improved" ? "نسبت به بررسی قبلی بیشترین تغییر مثبت رو داشته." : "نسبت به بررسی قبلی ضعیف‌تر دیده شده."}
          </Text>
        </>
      )}
    </View>
  );
}

function MeasurementComparison({ delta }: { readonly delta: BodyProgressMeasurementDelta }) {
  const previous = delta.previous ?? 0;
  const current = delta.current ?? 0;
  const maximum = Math.max(1, previous, current);
  const unit = delta.unit === "kg" ? "کیلوگرم" : "سانتی‌متر";
  return (
    <View style={styles.measurement}>
      <View style={styles.measurementHeading}>
        <Text style={styles.cardTitle}>{measurementLabel(delta.measurement)}</Text>
        <Text style={styles.muted}>{unit}</Text>
      </View>
      <ProgressBar color={fiticianTokens.colors.muted} label={`قبلی ${measurementLabel(delta.measurement)}`} progress={previous / maximum} />
      <ProgressBar label={`فعلی ${measurementLabel(delta.measurement)}`} progress={current / maximum} />
      <View style={styles.measurementValues}>
        <Text style={styles.muted}>قبلی: {formatNumber(delta.previous)} {unit}</Text>
        <Text style={styles.body}>فعلی: {formatNumber(delta.current)} {unit}</Text>
      </View>
    </View>
  );
}

function visualChangeText(transition: BodyProgressVisualTransition) {
  return (
    <Text key={transition.body_area} style={styles.body}>
      {bodyAreaLabel(transition.body_area)} · {progressStateLabel(transition.state)} · اطمینان {formatPercent(transition.change_confidence)}
    </Text>
  );
}

function selectBiggestChange(
  transitions: Array<Pick<BodyProgressVisualTransition, "body_area" | "state" | "change_confidence">>,
): { body_area: BodyArea; state: BodyProgressState } | null {
  const meaningful = transitions.filter((transition) => (
    transition.state === "improved" || transition.state === "declined_or_less_balanced"
  ));
  if (meaningful.length === 0) return null;
  const biggest = [...meaningful].sort((left, right) => right.change_confidence - left.change_confidence)[0];
  return biggest === undefined ? null : { body_area: biggest.body_area, state: biggest.state };
}

function isAvailableMeasurement(delta: BodyProgressMeasurementDelta): boolean {
  return delta.availability === "exact" && delta.previous !== null && delta.current !== null;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" }).format(new Date(value));
}

function formatNumber(value: number | null): string {
  return value === null ? "—" : new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 2 }).format(value);
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}٪`;
}

function measurementLabel(value: BodyProgressMeasurementDelta["measurement"]): string {
  const labels: Record<BodyProgressMeasurementDelta["measurement"], string> = {
    hip_circumference_cm: "دور باسن",
    shoulder_circumference_cm: "دور شانه",
    waist_circumference_cm: "دور کمر",
    weight_kg: "وزن",
  };
  return labels[value];
}

function progressStateLabel(value: BodyProgressState): string {
  if (value === "improved") return "بهبود یافته";
  if (value === "declined_or_less_balanced") return "نیازمند توجه";
  if (value === "unchanged") return "بدون تغییر قابل اتکا";
  return "نامشخص";
}

const styles = StyleSheet.create({
  body: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "right",
    writingDirection: "rtl",
  },
  card: {
    gap: fiticianTokens.spacing[2],
  },
  cardTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  changeArea: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  changeSummary: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[1],
    padding: fiticianTokens.spacing[3],
  },
  changeTitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  measurement: {
    gap: fiticianTokens.spacing[2],
  },
  measurementHeading: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  measurementValues: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  muted: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  section: {
    gap: fiticianTokens.spacing[3],
  },
});
