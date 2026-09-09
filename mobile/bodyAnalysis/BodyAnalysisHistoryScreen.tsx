import { useEffect, useMemo, useState } from "react";
import { useRouter } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import type {
  BodyProgressTimelineItem,
  BodyProgressTimelineResponse,
  BodyPhotoSessionState,
} from "@fitician/core/body-photos";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { AppIcon, Button, Card, EmptyState, Notice, PageHeading, SectionHeader, Skeleton } from "../ui/components";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";
import { createBodyPhotoApi } from "./bodyPhotoApi";
import { buildBodyProgressLandingSummary } from "./bodyAnalysisPresentation";

const statusLabels: Record<BodyPhotoSessionState, string> = {
  analyzing: "در حال تحلیل",
  awaiting_consent: "در انتظار رضایت",
  completed: "تکمیل‌شده",
  deleted: "حذف‌شده",
  draft: "پیش‌نویس",
  failed: "ناموفق",
  queued: "در صف تحلیل",
  review_pending: "در انتظار بررسی تخصصی",
  uploaded: "تصاویر ثبت‌شده",
  uploading: "در حال بارگذاری",
  validating: "در حال بررسی کیفیت",
};

export interface BodyAnalysisHistoryScreenProps {
  readonly tabRoot?: boolean;
}

export function BodyAnalysisHistoryScreen({ tabRoot = false }: BodyAnalysisHistoryScreenProps = {}) {
  const auth = useMobileAuth();
  const router = useRouter();
  const api = useMemo(
    () => createBodyPhotoApi(auth.request, auth.upload, auth.download),
    [auth.download, auth.request, auth.upload],
  );
  const [timeline, setTimeline] = useState<BodyProgressTimelineResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<BodyProgressTimelineItem | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadTimeline() {
    setFailed(false);
    try {
      setTimeline(await api.getTimeline());
    } catch {
      setFailed(true);
    }
  }

  useEffect(() => {
    void loadTimeline();
  }, [api]);

  async function deleteTargetSession() {
    if (deleteTarget === null || busy) return;
    setBusy(true);
    try {
      await api.deleteSession(deleteTarget.session.id);
      setTimeline((current) => current === null
        ? current
        : { ...current, items: current.items.filter((item) => item.session.id !== deleteTarget.session.id) });
      setDeleteTarget(null);
    } finally {
      setBusy(false);
    }
  }

  if (timeline === null && !failed) {
    return (
      <Screen scroll={false}>
        <View style={styles.loading}>
          <Skeleton accessibilityLabel="در حال بارگذاری تاریخچه تحلیل بدن" height={32} width="68%" />
          <Skeleton accessibilityLabel="در حال بارگذاری تاریخچه تحلیل بدن" height={180} />
        </View>
      </Screen>
    );
  }

  if (failed || timeline === null) {
    return (
      <Screen scroll={false}>
        <View style={styles.statusState}>
          <Text style={styles.title}>تاریخچه تحلیل بدن در دسترس نیست</Text>
          <Notice message="دریافت نشست‌های تحلیل انجام نشد." variant="danger" />
          <Button label="تلاش دوباره" onPress={() => void loadTimeline()} />
          {!tabRoot ? <Button label="بازگشت" onPress={() => router.replace("/member")} variant="ghost" /> : null}
        </View>
      </Screen>
    );
  }

  const { incomplete, latestAnalysis, submitted } = buildBodyProgressLandingSummary(timeline.items);

  return (
    <Screen contentContainerStyle={styles.screen}>
      <View style={styles.content}>
        <PageHeading
          action={<Button label="تحلیل جدید" onPress={() => router.push("/member/body-analysis")} style={styles.headerAction} />}
          compact
          eyebrow="تحلیل بدن"
          supportingText="نشست‌ها، وضعیت بررسی تخصصی و نسخه نتیجه را از همین‌جا دنبال کن."
          title="تاریخچه و روند پیشرفت"
        />
        {!tabRoot ? (
          <View style={styles.actions}>
            <Button label="بازگشت" onPress={() => router.replace("/member")} variant="ghost" />
          </View>
        ) : null}
        {latestAnalysis !== null ? (
          <LatestProgressCard
            item={latestAnalysis}
            onOpen={() => router.push(`/member/body-analysis-result/${encodeURIComponent(latestAnalysis.session.id)}`)}
          />
        ) : null}
        {timeline.items.length === 0 ? (
          <EmptyState actionLabel="شروع تحلیل" onAction={() => router.push("/member/body-analysis")} title="هنوز تحلیلی ثبت نشده است">
            اولین نشست تحلیل بدن را با عکس‌های سه‌نما شروع کن.
          </EmptyState>
        ) : null}
        {incomplete.length > 0 ? (
          <View style={styles.section}>
            <SectionHeader eyebrow="نیاز به ادامه" title="نشست‌های ناتمام" />
            <View style={styles.list}>
              {incomplete.map((item) => (
                <HistoryCard
                  key={item.session.id}
                  busy={busy}
                  item={item}
                  onDelete={() => setDeleteTarget(item)}
                  onOpen={() => router.push(`/member/body-analysis-result/${encodeURIComponent(item.session.id)}`)}
                  onResume={() => router.push({
                    pathname: "/member/body-analysis",
                    params: { sessionId: item.session.id },
                  })}
                  pendingDelete={deleteTarget?.session.id === item.session.id}
                  onCancelDelete={() => setDeleteTarget(null)}
                  onConfirmDelete={() => void deleteTargetSession()}
                />
              ))}
            </View>
          </View>
        ) : null}
        {submitted.length > 0 ? (
          <View style={styles.section}>
            <SectionHeader eyebrow="روند طولی" title="روند تحلیل‌ها" />
            <View style={styles.list}>
              {submitted.map((item) => (
                <HistoryCard
                  key={item.session.id}
                  busy={busy}
                  item={item}
                  onDelete={() => setDeleteTarget(item)}
                  onOpen={() => router.push(`/member/body-analysis-result/${encodeURIComponent(item.session.id)}`)}
                  onResume={() => router.push({
                    pathname: "/member/body-analysis",
                    params: { sessionId: item.session.id },
                  })}
                  pendingDelete={deleteTarget?.session.id === item.session.id}
                  onCancelDelete={() => setDeleteTarget(null)}
                  onConfirmDelete={() => void deleteTargetSession()}
                />
              ))}
            </View>
          </View>
        ) : null}
      </View>
    </Screen>
  );
}

function LatestProgressCard({
  item,
  onOpen,
}: {
  readonly item: BodyProgressTimelineItem;
  readonly onOpen: () => void;
}) {
  const hasAnalysis = item.analysis !== null;
  const hasMeaningfulResult = hasAnalysis && hasAnalysisResult(item);
  return (
    <View style={styles.section}>
      <SectionHeader eyebrow="وضعیت فعلی" title="آخرین وضعیت تحلیل" />
      <Card style={styles.latestCard} variant="hero">
        <View style={styles.latestHeader}>
          <View style={styles.latestIconTile}>
            <AppIcon color={fiticianTokens.colors.aqua} name="bodyAnalysis" size={22} />
          </View>
          <View style={styles.latestCopy}>
            <Text style={styles.latestEyebrow}>آخرین نشست</Text>
            <Text style={styles.latestTitle}>
              {hasMeaningfulResult ? "نتیجه آخرین نشست آماده است" : "آخرین نشست در حال پیگیری است"}
            </Text>
            <Text style={styles.latestMeta}>
              {formatDate(item.session.created_at)} · {statusLabels[item.session.state]}
            </Text>
          </View>
        </View>
        <Text style={styles.body}>{latestSummaryLabel(item)}</Text>
        <ProgressSummaryMetrics item={item} />
        {hasAnalysis ? (
          <View style={styles.actions}>
            <Button
              label={hasMeaningfulResult ? "مشاهده آخرین نتیجه" : "مشاهده وضعیت آخرین نشست"}
              onPress={onOpen}
              variant="secondary"
            />
          </View>
        ) : null}
      </Card>
    </View>
  );
}

function ProgressSummaryMetrics({ item }: { readonly item: BodyProgressTimelineItem }) {
  const metrics = item.snapshot === null
    ? experienceSummaryMetrics(item)
    : snapshotSummaryMetrics(item);
  if (metrics.length === 0) return null;
  return (
    <View style={styles.summaryMetricGrid}>
      {metrics.map((metric) => (
        <View key={metric.label} style={styles.summaryMetric}>
          <Text style={styles.summaryMetricLabel}>{metric.label}</Text>
          <Text style={styles.summaryMetricValue}>{metric.value}</Text>
        </View>
      ))}
    </View>
  );
}

function snapshotSummaryMetrics(item: BodyProgressTimelineItem): readonly SummaryMetric[] {
  const snapshot = item.snapshot;
  if (snapshot === null) return [];
  return [
    { label: "وزن ثبت‌شده", value: `${formatMetric(snapshot.weight_kg)} کیلو` },
    { label: "دور کمر", value: `${formatMetric(snapshot.waist_circumference_cm)} سانتی‌متر` },
    { label: "دور شانه", value: `${formatMetric(snapshot.shoulder_circumference_cm)} سانتی‌متر` },
    { label: "دور باسن", value: `${formatMetric(snapshot.hip_circumference_cm)} سانتی‌متر` },
  ];
}

function experienceSummaryMetrics(item: BodyProgressTimelineItem): readonly SummaryMetric[] {
  const composition = item.analysis?.experience_result?.body_composition;
  if (composition === undefined || composition === null) return [];
  const metrics: SummaryMetric[] = [];
  if (composition.bmi !== null && Number.isFinite(composition.bmi)) {
    metrics.push({ label: "شاخص توده بدنی", value: formatMetric(composition.bmi) });
  }
  if (
    composition.estimated_body_fat_percent !== null
    && Number.isFinite(composition.estimated_body_fat_percent)
  ) {
    metrics.push({
      label: "چربی تخمینی",
      value: `${formatMetric(composition.estimated_body_fat_percent)}٪`,
    });
  }
  return metrics;
}

type SummaryMetric = { readonly label: string; readonly value: string };

function latestSummaryLabel(item: BodyProgressTimelineItem): string {
  if (item.session.submitted_at === null) {
    return `این نشست هنوز ارسال نشده است؛ ${formatCount(item.photos.length)} نمای استاندارد ثبت شده است.`;
  }
  if (item.analysis !== null && hasAnalysisResult(item)) {
    return item.comparison === null
      ? "نسخه نتیجه برای مشاهده آماده است."
      : comparisonLabel(item.comparison.normalized_result);
  }
  if (item.analysis !== null) return `وضعیت نتیجه: ${statusLabels[item.analysis.status]}.`;
  return "نتیجه این نشست هنوز آماده نشده است.";
}

function hasAnalysisResult(item: BodyProgressTimelineItem): boolean {
  const analysis = item.analysis;
  return analysis !== null && (
    analysis.result_version !== null
    || analysis.normalized_result !== null
    || analysis.experience_result != null
  );
}

function HistoryCard({
  busy,
  item,
  onCancelDelete,
  onConfirmDelete,
  onDelete,
  onOpen,
  onResume,
  pendingDelete,
}: {
  readonly busy: boolean;
  readonly item: BodyProgressTimelineItem;
  readonly onCancelDelete: () => void;
  readonly onConfirmDelete: () => void;
  readonly onDelete: () => void;
  readonly onOpen: () => void;
  readonly onResume: () => void;
  readonly pendingDelete: boolean;
}) {
  const hasAnalysis = item.analysis !== null;
  const isIncomplete = item.session.submitted_at === null;
  return (
    <Card style={styles.card}>
      <View style={styles.cardHeading}>
        <Text style={styles.cardDate}>{formatDate(item.session.created_at)}</Text>
        <Text style={styles.status}>{statusLabels[item.session.state]}</Text>
      </View>
      <Text style={styles.body}>تعداد نماهای ثبت‌شده: {formatCount(item.photos.length)} از ۳</Text>
      {item.analysis?.result_version !== null && item.analysis?.result_version !== undefined ? (
        <Text style={styles.body}>نسخه نتیجه: {item.analysis.result_version}</Text>
      ) : null}
      <View style={styles.reviewRow}>
        <Text style={styles.reviewText}>مربی: {reviewLabel(item.review_state.coach.decision)}</Text>
        <Text style={styles.reviewText}>پزشک: {reviewLabel(item.review_state.doctor.decision)}</Text>
      </View>
      {item.comparison !== null ? (
        <Text style={styles.comparisonText}>{comparisonLabel(item.comparison.normalized_result)}</Text>
      ) : null}
      {pendingDelete ? (
        <View style={styles.deleteConfirm}>
          <Text style={styles.body}>این نشست و تصاویر خصوصی آن حذف شود؟</Text>
          <View style={styles.actions}>
            <Button disabled={busy} label="حذف قطعی" onPress={onConfirmDelete} variant="danger" />
            <Button disabled={busy} label="انصراف" onPress={onCancelDelete} variant="ghost" />
          </View>
        </View>
      ) : (
        <View style={styles.actions}>
          {isIncomplete ? (
            <Button label="ادامه نشست" onPress={onResume} variant="secondary" />
          ) : hasAnalysis ? (
            <Button label="مشاهده نتیجه" onPress={onOpen} variant="secondary" />
          ) : null}
          <Button label="حذف" onPress={onDelete} variant="danger" />
        </View>
      )}
    </Card>
  );
}

function reviewLabel(decision: string | null): string {
  if (decision === "approved") return "تأیید شد";
  if (decision === "changes_required") return "نیازمند اصلاح";
  if (decision === "rejected") return "رد شد";
  return "در انتظار";
}

function comparisonLabel(
  value: NonNullable<BodyProgressTimelineItem["comparison"]>["normalized_result"],
): string {
  if (value.schema_version === "2.0") {
    const changed = value.visual_transitions.filter((item) => item.state !== "unchanged");
    return changed.length === 0
      ? "در مقایسه قبلی تغییر قابل اتکایی ثبت نشده است."
      : `${formatCount(changed.length)} تغییر بصری با مقایسه استاندارد ثبت شده است.`;
  }
  return value.areas.length === 0
    ? "مقایسه بصری هنوز نتیجه قابل اتکایی ندارد."
    : `${formatCount(value.areas.length)} ناحیه در مقایسه قبلی بررسی شده است.`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" }).format(new Date(value));
}

function formatMetric(value: number): string {
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(value);
}

function formatCount(value: number): string {
  return new Intl.NumberFormat("fa-IR").format(value);
}

const styles = StyleSheet.create({
  actions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  body: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "right",
    writingDirection: "rtl",
  },
  card: {
    gap: fiticianTokens.spacing[3],
  },
  cardDate: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    writingDirection: "rtl",
  },
  cardHeading: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  comparisonText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "right",
    writingDirection: "rtl",
  },
  content: {
    gap: fiticianTokens.spacing[4],
    paddingBottom: fiticianTokens.spacing[6],
  },
  deleteConfirm: {
    borderColor: fiticianTokens.colors.danger,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  headerAction: {
    paddingHorizontal: fiticianTokens.spacing[3],
  },
  latestCard: {
    gap: fiticianTokens.spacing[4],
  },
  latestCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  latestEyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  latestHeader: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
  },
  latestIconTile: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 48,
    justifyContent: "center",
    width: 48,
  },
  latestMeta: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  latestTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 30,
    textAlign: "right",
    writingDirection: "rtl",
  },
  list: {
    gap: fiticianTokens.spacing[3],
  },
  loading: {
    gap: fiticianTokens.spacing[4],
    justifyContent: "center",
    minHeight: 420,
  },
  reviewRow: {
    gap: fiticianTokens.spacing[1],
  },
  reviewText: {
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
  screen: {
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[3],
  },
  summaryMetric: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flexBasis: "46%",
    flexGrow: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 130,
    padding: fiticianTokens.spacing[3],
  },
  summaryMetricGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  summaryMetricLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 19,
    textAlign: "right",
    writingDirection: "rtl",
  },
  summaryMetricValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 24,
    textAlign: "right",
    writingDirection: "rtl",
  },
  status: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    writingDirection: "rtl",
  },
  statusState: {
    gap: fiticianTokens.spacing[4],
    justifyContent: "center",
    minHeight: 420,
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 42,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
