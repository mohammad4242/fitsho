import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { nutritionKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { Card, EmptyState, Notice, Skeleton, TextField } from "../ui/components";
import { getMobileViewState } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import {
  adherencePercentLabel,
  checkInStatusLabel,
  trackingDataStatusLabel,
} from "./nutritionTrackingModel";
import {
  createNutritionTrackingApi,
  type NutritionDailyTracking,
  type NutritionTrackingApi,
} from "./nutritionTrackingApi";
import { formatNutritionNumber } from "./nutritionModel";

export function NutritionAdherenceSection() {
  const auth = useMobileAuth();
  const connectivityStatus = useConnectivityStatus();
  const today = useMemo(todayIsoDate, []);
  const [rangeStart, setRangeStart] = useState(() => daysAgoIsoDate(6));
  const api = useMemo(
    () => createNutritionTrackingApi(auth.request, auth.download),
    [auth.download, auth.request],
  );
  const validRange = isIsoDate(rangeStart) && rangeStart <= today;
  const adherenceQuery = useQuery({
    enabled: validRange,
    queryFn: () => api.getAdherence(rangeStart, today),
    queryKey: nutritionKeys.adherence(rangeStart, today),
  });
  const historyQuery = useQuery({
    enabled: validRange,
    queryFn: () => api.getTrackingHistory(rangeStart, today),
    queryKey: nutritionKeys.trackingHistory(rangeStart, today),
  });
  const adherenceState = getMobileViewState(adherenceQuery, { connectivityStatus });
  const historyState = getMobileViewState(historyQuery, { connectivityStatus });
  const adherence = stateData(adherenceState);
  const history = stateData(historyState) ?? [];

  if (!validRange) {
    return (
      <Card style={styles.card}>
        <Text style={styles.title}>روند پایبندی</Text>
        <TextField
          accessibilityLabel="شروع بازه پایبندی"
          error="تاریخ شروع باید به شکل میلادی YYYY-MM-DD و پیش از امروز باشد."
          label="از تاریخ"
          onChangeText={setRangeStart}
          textDirection="ltr"
          value={rangeStart}
        />
      </Card>
    );
  }
  if (adherenceState.status === "loading") return <Skeleton height={500} />;
  if (adherenceState.status === "error" && adherence === undefined) {
    return (
      <Notice
        actionLabel="تلاش دوباره"
        message="روند پایبندی دریافت نشد."
        onAction={() => void adherenceQuery.refetch()}
        variant="danger"
      />
    );
  }
  if (adherenceState.status === "offline" && adherence === undefined) {
    return <Notice message="برای مشاهده روند پایبندی به اینترنت وصل شو." variant="offline" />;
  }
  if (adherence === undefined) return null;

  return (
    <Card style={styles.card}>
      <View style={styles.heading}>
        <View style={styles.headingCopy}>
          <Text style={styles.title}>روند پایبندی</Text>
          <Text style={styles.bodyText}>دقت ثبت، وضعیت وعده‌ها و فاصله مصرف واقعی از برنامه را در یک بازه ببین.</Text>
        </View>
        <TextField
          accessibilityLabel="شروع بازه پایبندی"
          label="از تاریخ"
          onChangeText={setRangeStart}
          textDirection="ltr"
          value={rangeStart}
        />
      </View>
      {adherenceState.status === "offline" || adherenceState.status === "stale" ? (
        <Notice message="آخرین روند ذخیره‌شده نمایش داده می‌شود." variant="offline" />
      ) : null}
      {adherence.days.length === 0 ? (
        <EmptyState title="روندی برای این بازه نیست">با ثبت وعده‌ها و وضعیت روز، روند پایبندی ساخته می‌شود.</EmptyState>
      ) : (
        <View style={styles.dayStack}>
          {adherence.days.map((day) => (
            <AdherenceDayCard key={day.date} day={day} />
          ))}
        </View>
      )}
      {adherence.weight_trend.length > 0 ? (
        <Notice
          message={adherence.weight_causality_claimed
            ? "روند وزن کنار پایبندی نمایش داده می‌شود؛ این نمایش به‌تنهایی رابطه علت و معلولی را ثابت نمی‌کند."
            : "روند وزن کنار پایبندی نمایش داده می‌شود و به‌تنهایی رابطه علت و معلولی را ثابت نمی‌کند."}
          title="یادآوری درباره روند وزن"
          variant="info"
        />
      ) : null}
      <View style={styles.historyBlock}>
        <Text style={styles.cardSubtitle}>تاریخچه ثبت‌ها</Text>
        {historyState.status === "error" && history.length === 0 ? (
          <Notice actionLabel="تلاش دوباره" message="تاریخچه ثبت‌ها دریافت نشد." onAction={() => void historyQuery.refetch()} variant="danger" />
        ) : history.length === 0 ? (
          <Text style={styles.bodyText}>در این بازه ثبتی وجود ندارد.</Text>
        ) : (
          <View style={styles.historyStack}>
            {history.map((day) => <HistoryRow day={day} key={day.entry_date} />)}
          </View>
        )}
      </View>
    </Card>
  );
}

function AdherenceDayCard({
  day,
}: {
  readonly day: NonNullable<Awaited<ReturnType<NutritionTrackingApi["getAdherence"]>>>["days"][number];
}) {
  return (
    <View style={styles.dayCard}>
      <View style={styles.sectionHeading}>
        <Text style={styles.dayDate}>{day.date}</Text>
        <View style={styles.headingCopy}>
          <Text style={styles.entryTitle}>{checkInStatusLabel(day.check_in_status)}</Text>
          <Text style={styles.mutedText}>{trackingDataStatusLabel(day.status)}</Text>
        </View>
      </View>
      {day.status === "insufficient_data" ? (
        <Notice message="برای این روز داده کافی برای محاسبه پایبندی وجود ندارد." variant="warning" />
      ) : (
        <View style={styles.metricsStack}>
          <AdherenceMetric label="کالری" value={day.calorie_adherence} />
          <AdherenceMetric label="پروتئین" value={day.protein_adherence} />
          <AdherenceMetric label="وعده‌ها" value={day.meal_adherence} />
          <Text style={styles.completeness}>کامل بودن ثبت: {formatNutritionNumber(Math.round(day.tracking_completeness))}٪</Text>
        </View>
      )}
    </View>
  );
}

function AdherenceMetric({ label, value }: { readonly label: string; readonly value: number | null }) {
  const numeric = value === null || !Number.isFinite(value) ? null : Math.max(0, Math.min(100, value));
  return (
    <View style={styles.metricBlock}>
      <View style={styles.metricLabelRow}>
        <Text style={styles.metricValue}>{adherencePercentLabel(value)}</Text>
        <Text style={styles.bodyText}>{label}</Text>
      </View>
      <View accessibilityLabel={`${label}: ${adherencePercentLabel(value)}`} style={styles.progressTrack}>
        <View style={[styles.progressFill, { width: `${numeric ?? 0}%` }]} />
      </View>
    </View>
  );
}

function HistoryRow({ day }: { readonly day: NutritionDailyTracking }) {
  return (
    <View style={styles.historyRow}>
      <Text style={styles.historyCount}>{formatNutritionNumber(day.entries.length)} مورد</Text>
      <View style={styles.headingCopy}>
        <Text style={styles.entryTitle}>{day.entry_date}</Text>
        <Text style={styles.mutedText}>{checkInStatusLabel(day.check_in_status)}</Text>
      </View>
    </View>
  );
}

function stateData<TData>(state: ReturnType<typeof getMobileViewState<TData>>): TData | undefined {
  if (state.status === "loading") return undefined;
  return "data" in state ? state.data : undefined;
}

function isIsoDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/u.test(value);
}

function todayIsoDate(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function daysAgoIsoDate(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

const styles = StyleSheet.create({
  bodyText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "right",
    writingDirection: "rtl",
  },
  card: {
    gap: fiticianTokens.spacing[3],
    marginTop: fiticianTokens.spacing[3],
  },
  cardSubtitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  completeness: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  dayCard: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  dayDate: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    writingDirection: "ltr",
  },
  dayStack: {
    gap: fiticianTokens.spacing[3],
  },
  heading: {
    gap: fiticianTokens.spacing[2],
  },
  headingCopy: {
    alignItems: "flex-end",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  historyBlock: {
    borderTopColor: fiticianTokens.colors.lineStrong,
    borderTopWidth: 1,
    gap: fiticianTokens.spacing[3],
    paddingTop: fiticianTokens.spacing[4],
  },
  historyRow: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    padding: fiticianTokens.spacing[3],
  },
  historyStack: {
    gap: fiticianTokens.spacing[2],
  },
  historyCount: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "left",
    writingDirection: "rtl",
  },
  metricBlock: {
    gap: fiticianTokens.spacing[2],
  },
  metricLabelRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    justifyContent: "space-between",
  },
  metricValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    writingDirection: "ltr",
  },
  metricsStack: {
    gap: fiticianTokens.spacing[3],
  },
  mutedText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  progressFill: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: "100%",
  },
  progressTrack: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderRadius: fiticianTokens.radii.pill,
    height: 8,
    overflow: "hidden",
    width: "100%",
  },
  sectionHeading: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  entryTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
