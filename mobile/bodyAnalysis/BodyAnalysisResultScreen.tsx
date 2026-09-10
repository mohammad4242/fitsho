import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Image, StyleSheet, Text, View } from "react-native";

import { ApiError } from "@fitician/core";
import type {
  BodyAnalysis,
  BodyPhoto,
  BodyPhotoSession,
  BodyProgressComparison,
  BodyProgressTimelineItem,
} from "@fitician/core/body-photos";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import {
  Button,
  Card,
  DisclosureCard,
  AppIcon,
  Notice,
  PageHeading,
  SectionHeader,
  Skeleton,
} from "../ui/components";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";
import { createBodyPhotoApi } from "./bodyPhotoApi";
import { BodyAnalysisExperienceTabs } from "./BodyAnalysisExperienceTabs";
import { bodyAnalysisCopy, bodyPhotoCopy } from "./bodyAnalysisCopy";
import { bodyAreaLabel } from "./bodyAnalysisPresentation";
import {
  createPrivateBodyPhotoClient,
  loadPrivateBodyPhotoUris,
} from "./bodyPhotoPrivateMedia";
import { BodyProgressComparisonCard } from "./BodyProgressComparison";

const activeAnalysisStates = new Set<BodyAnalysis["status"]>([
  "queued",
  "validating",
  "analyzing",
]);

export function BodyAnalysisResultScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const params = useLocalSearchParams<{ sessionId?: string | string[] }>();
  const sessionId = firstParam(params.sessionId);
  const userId = auth.user?.id ?? null;
  const api = useMemo(
    () => createBodyPhotoApi(auth.request, auth.upload, auth.download),
    [auth.download, auth.request, auth.upload],
  );
  const mediaClient = useMemo(() => {
    return createPrivateBodyPhotoClient(auth.download, userId);
  }, [auth.download, userId]);
  const [session, setSession] = useState<BodyPhotoSession | null>(null);
  const [analysis, setAnalysis] = useState<BodyAnalysis | null>(null);
  const [comparison, setComparison] = useState<BodyProgressComparison | null>(null);
  const [progressItems, setProgressItems] = useState<readonly BodyProgressTimelineItem[]>([]);
  const [photoUris, setPhotoUris] = useState<Partial<Record<BodyPhoto["view"], string>>>({});
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (sessionId === undefined || sessionId.trim().length === 0) {
      setFailed(true);
      setLoading(false);
      return;
    }
    setLoading(true);
    setFailed(false);
    try {
      const [loadedSession, loadedAnalysis, loadedTimeline] = await Promise.all([
        api.getSession(sessionId),
        api.getAnalysis(sessionId),
        api.getTimeline().catch(() => null),
      ]);
      let effectiveAnalysis = loadedAnalysis;
      if (effectiveAnalysis === null && loadedSession.state === "queued") {
        try {
          effectiveAnalysis = await api.startAnalysis(sessionId, true);
        } catch {
          setActionError("تحلیل هنوز شروع نشده است. دوباره تلاش کن.");
        }
      }
      setSession(loadedSession);
      setAnalysis(effectiveAnalysis);
      setProgressItems(loadedTimeline?.items ?? []);
      setComparison(await api.getComparison(sessionId).catch(() => null));
      setFailed(false);
      if (mediaClient !== null) {
        void loadPrivateBodyPhotoUris(loadedSession.photos, mediaClient, `body-analysis-${loadedSession.id}`)
          .then(setPhotoUris)
          .catch(() => undefined);
      }
    } catch (error) {
      setFailed(true);
      setActionError(bodyAnalysisLoadErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [api, mediaClient, sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (sessionId === undefined || analysis === null || !activeAnalysisStates.has(analysis.status)) {
      return undefined;
    }
    let active = true;
    const timer = setTimeout(() => {
      void api.getAnalysis(sessionId)
        .then((next) => {
          if (active && next !== null) setAnalysis(next);
        })
        .catch(() => undefined);
    }, 3000);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [analysis, api, sessionId]);

  async function retry() {
    if (sessionId === undefined || actionBusy) return;
    setActionBusy(true);
    setActionError(null);
    try {
      const next = analysis?.status === "failed"
        ? await api.retryAnalysis(sessionId, true)
        : await api.startAnalysis(sessionId, true);
      setAnalysis(next);
    } catch (error) {
      setActionError(bodyAnalysisLoadErrorMessage(error));
    } finally {
      setActionBusy(false);
    }
  }

  if (loading) {
    return (
      <Screen scroll={false}>
        <View style={styles.loading}>
          <Skeleton accessibilityLabel="در حال بارگذاری نتیجه تحلیل بدن" height={36} width="70%" />
          <Skeleton accessibilityLabel="در حال بارگذاری نتیجه تحلیل بدن" height={220} />
        </View>
      </Screen>
    );
  }

  if (failed || session === null) {
    return (
      <Screen scroll={false}>
        <View style={styles.statusState}>
          <Text style={styles.title}>{bodyPhotoCopy.results.loadError}</Text>
          <Notice message={actionError ?? bodyPhotoCopy.results.loadError} variant="danger" />
          <Button label="تلاش دوباره" onPress={() => void load()} />
          <Button label="تاریخچه" onPress={() => router.replace("/member/body-analysis-history")} variant="secondary" />
        </View>
      </Screen>
    );
  }

  const failedAnalysis = analysis?.status === "failed";
  return (
    <Screen contentContainerStyle={styles.screen}>
      <View style={styles.content}>
        <PageHeading
          action={<Button label="تاریخچه" onPress={() => router.replace("/member/body-analysis-history")} style={styles.headerAction} variant="ghost" />}
          eyebrow={bodyPhotoCopy.eyebrow}
          supportingText={`${bodyPhotoCopy.results.sessionDate.replace("{{date}}", formatSessionDate(session.created_at))} · وضعیت: ${sessionStatusLabel(session.state)}`}
          title={bodyPhotoCopy.results.title}
        />
        {analysis === null ? (
          <Notice message={bodyPhotoCopy.results.notStarted} variant="info" />
        ) : activeAnalysisStates.has(analysis.status) ? (
          <Notice message={`${analysisStatusLabel(analysis.status)} · ${bodyPhotoCopy.results.processingHelp}`} variant="info" />
        ) : null}
        {failedAnalysis ? (
          <Notice
            message={analysisFailureMessage(analysis)}
            variant="danger"
          />
        ) : null}
        {actionError !== null ? <Notice message={actionError} variant="danger" /> : null}
        {analysis !== null && failedAnalysis && analysis.photo_validation !== null ? (
          <PhotoQualityCard analysis={analysis} />
        ) : null}
        {analysis === null || failedAnalysis ? (
          <Button disabled={actionBusy} label={bodyPhotoCopy.results.retry} loading={actionBusy} onPress={() => void retry()} />
        ) : null}
        {analysis?.experience_result !== null && analysis?.experience_result !== undefined ? (
          <BodyAnalysisExperienceTabs
            experience={analysis.experience_result}
            progressItems={progressItems}
            progressSessionId={analysis.session_id}
            review={<ReviewStatusCard analysis={analysis} />}
          />
        ) : analysis?.normalized_result !== null && analysis?.normalized_result !== undefined ? (
          <NormalizedResult analysis={analysis} />
        ) : null}
        {analysis !== null && hasAnalysisResult(analysis) && !hasExperienceResult(analysis) ? <ReviewStatusCard analysis={analysis} /> : null}
        {comparison !== null && !hasExperienceResult(analysis) ? <BodyProgressComparisonCard comparison={comparison} /> : null}
        {analysis !== null && hasAnalysisResult(analysis) ? (
          <PrivacyDisclaimer />
        ) : null}
        {session.photos.length > 0 ? <PhotoDetails photoUris={photoUris} photos={session.photos} /> : null}
        {analysis !== null && analysis.result_version !== null ? <ResultDetailsDisclosure analysis={analysis} /> : null}
        {analysis?.normalized_result !== null && analysis?.normalized_result !== undefined ? (
          <Button label="مشاهده برنامه تمرینی" onPress={() => router.push("/member/workouts")} />
        ) : null}
        <View style={styles.actions}>
          <Button label="تاریخچه" onPress={() => router.replace("/member/body-analysis-history")} variant="secondary" />
          <Button label="بازگشت" onPress={() => router.replace("/member")} variant="ghost" />
        </View>
      </View>
    </Screen>
  );
}

function PhotoQualityCard({ analysis }: { readonly analysis: BodyAnalysis }) {
  const validation = analysis.photo_validation;
  if (validation === null || validation === undefined) return null;
  return (
    <Card style={styles.card}>
      <Text style={styles.cardTitle}>{bodyPhotoCopy.quality.title}</Text>
      <Text style={styles.body}>{validation.accepted ? "سه تصویر برای تحلیل قابل استفاده بود." : "کیفیت تصویر نیاز به اصلاح دارد."}</Text>
      <Text style={styles.body}>{bodyPhotoCopy.quality.landmarks}: {formatPercent(validation.confidence)}</Text>
      {validation.issues.map((issue) => (
        <Text key={issue.view} style={styles.issueText}>
          {viewLabel(issue.view)}: {issue.reasons.map(photoQualityReasonLabel).join("، ")}
        </Text>
      ))}
    </Card>
  );
}

function NormalizedResult({ analysis }: { readonly analysis: BodyAnalysis }) {
  const result = analysis.normalized_result;
  if (result === null || result === undefined) return null;
  return (
    <View style={styles.section}>
      <Card style={styles.card}>
        <Text style={styles.cardTitle}>خلاصه تحلیل</Text>
        <Text style={styles.body}>اعتماد کلی: {formatPercent(result.overall_confidence)}</Text>
        <Text style={styles.muted}>نتیجهٔ استاندارد و اعتبارسنجی‌شدهٔ این تحلیل نمایش داده می‌شود.</Text>
      </Card>
      {result.findings.slice(0, 13).map((finding) => (
        <Card key={finding.body_area} style={styles.card}>
          <View style={styles.cardHeading}>
            <Text style={styles.cardTitle}>{bodyAreaLabel(finding.body_area)}</Text>
            <Text style={styles.status}>{classificationLabel(finding.classification)}</Text>
          </View>
          <Text style={styles.body}>{finding.explanation}</Text>
          <Text style={styles.muted}>اعتماد: {formatPercent(finding.confidence)}</Text>
        </Card>
      ))}
    </View>
  );
}

function ReviewStatusCard({ analysis }: { readonly analysis: BodyAnalysis }) {
  return (
    <View style={styles.section}>
      <SectionHeader eyebrow="نظر متخصصان" title={bodyPhotoCopy.results.reviewTitle} />
      <Card style={styles.card}>
        <ReviewRow label={bodyPhotoCopy.results.reviewRoles.doctor} review={analysis.doctor_review} />
        <ReviewRow label={bodyPhotoCopy.results.reviewRoles.coach} review={analysis.coach_review} />
      </Card>
      <Text style={styles.muted}>
        {analysis.fully_reviewed ? bodyAnalysisCopy.review.approved : bodyAnalysisCopy.review.provisional}
      </Text>
    </View>
  );
}

function ReviewRow({
  label,
  review,
}: {
  readonly label: string;
  readonly review: BodyAnalysis["coach_review"];
}) {
  const approved = review.decision === "approved";
  return (
    <View accessibilityLabel={`${label}: ${reviewLabel(review.decision)}`} style={styles.reviewRow}>
      <View style={[styles.reviewDot, approved && styles.reviewDotApproved]} />
      <Text style={styles.body}>{label}</Text>
      <Text style={[styles.reviewValue, approved && styles.reviewValueApproved]}>{reviewLabel(review.decision)}</Text>
    </View>
  );
}

function PrivacyDisclaimer() {
  return (
    <Card style={styles.disclaimerCard} variant="glass">
      <View style={styles.disclaimerHeading}>
        <Text style={styles.cardTitle}>{bodyAnalysisCopy.disclaimer.title}</Text>
        <AppIcon color={fiticianTokens.colors.aqua} name="shield" size={20} />
      </View>
      <Text style={styles.body}>{bodyAnalysisCopy.disclaimer.body}</Text>
    </Card>
  );
}

function PhotoDetails({
  photoUris,
  photos,
}: {
  readonly photoUris: Partial<Record<BodyPhoto["view"], string>>;
  readonly photos: BodyPhoto[];
}) {
  return (
    <DisclosureCard
      icon="shield"
      summary={bodyPhotoCopy.results.photosLabel}
      title={bodyPhotoCopy.results.photosLabel}
    >
      <View style={styles.photoRow}>
        {photos.map((photo) => (
          <View key={photo.id} style={styles.photoItem}>
            {photoUris[photo.view] === undefined ? (
              <Text style={styles.muted}>محافظت‌شده</Text>
            ) : (
              <Image
                accessibilityLabel={replaceView(bodyPhotoCopy.results.photoAlt, viewLabel(photo.view))}
                resizeMode="contain"
                source={{ uri: photoUris[photo.view] }}
                style={styles.photo}
              />
            )}
            <Text style={styles.muted}>{viewLabel(photo.view)}</Text>
          </View>
        ))}
      </View>
    </DisclosureCard>
  );
}

function ResultDetailsDisclosure({ analysis }: { readonly analysis: BodyAnalysis }) {
  const validation = analysis.photo_validation;
  return (
    <DisclosureCard
      icon="shield"
      summary="اطلاعات فنی و وضعیت کیفیت ورودی، برای بررسی بیشتر"
      title="جزئیات فنی نتیجه"
    >
      <View style={styles.section}>
        {analysis.result_version !== null ? <Text style={styles.body}>پردازش نتیجه برای این تحلیل ثبت شده است.</Text> : null}
        <Text style={styles.body}>ساختار دادهٔ نتیجه با موفقیت اعتبارسنجی شده است.</Text>
        <Text style={styles.body}>منبع نتیجه: {resultSourceLabel(analysis.result_source)}</Text>
        <Text style={styles.body}>اطمینان کلی: {formatPercent(analysis.overall_confidence)}</Text>
        {validation ? (
          <>
            <Text style={styles.body}>{validation.accepted ? "سه تصویر برای تحلیل قابل استفاده بود." : "کیفیت تصویر نیاز به اصلاح دارد."}</Text>
            <Text style={styles.body}>اطمینان بررسی عکس: {formatPercent(validation.confidence)}</Text>
          </>
        ) : null}
      </View>
    </DisclosureCard>
  );
}

function bodyAnalysisLoadErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 404) return "این نشست تحلیل پیدا نشد.";
  if (error instanceof ApiError && error.status >= 500) return "سرویس تحلیل بدن موقتاً در دسترس نیست.";
  return "دریافت نتیجه تحلیل انجام نشد. دوباره تلاش کن.";
}

function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function formatSessionDate(value: string): string {
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function sessionStatusLabel(status: BodyPhotoSession["state"]): string {
  return bodyPhotoCopy.status[status];
}

function analysisStatusLabel(status: BodyAnalysis["status"]): string {
  return bodyPhotoCopy.results.analysisStatus[status];
}

function analysisFailureMessage(analysis: BodyAnalysis): string {
  const providerMessages: Record<string, string> = bodyPhotoCopy.results.providerErrors;
  return providerMessages[analysis.error_code ?? ""]
    ?? analysis.safe_error_message
    ?? bodyPhotoCopy.results.failedSafe;
}

function hasAnalysisResult(analysis: BodyAnalysis): boolean {
  return (
    (analysis.experience_result !== null && analysis.experience_result !== undefined)
    || analysis.normalized_result !== null
  );
}

function hasExperienceResult(analysis: BodyAnalysis | null): boolean {
  return analysis?.experience_result !== null && analysis?.experience_result !== undefined;
}

function resultSourceLabel(source: BodyAnalysis["result_source"]): string {
  if (source === "coach") return "مربی";
  if (source === "doctor") return "پزشک";
  return "هوش مصنوعی";
}

function reviewLabel(decision: string | null): string {
  if (decision === "approved") return "تأییدشده";
  if (decision === "changes_required") return "نیازمند اصلاح";
  if (decision === "rejected") return "ردشده";
  return "در انتظار";
}

function classificationLabel(value: string): string {
  if (value === "strength") return "نقطه قوت";
  if (value === "mild_lag") return "نیازمند توجه";
  if (value === "clear_lag") return "اولویت بالا";
  if (value === "uncertain") return "نامشخص";
  return "متعادل";
}

function photoQualityReasonLabel(value: string): string {
  const labels: Record<string, string> = bodyPhotoCopy.results.photoValidation;
  return labels[value] ?? "نیازمند بررسی";
}

function viewLabel(view: BodyPhoto["view"]): string {
  return bodyPhotoCopy.views[view];
}

function replaceView(template: string, view: string): string {
  return template.replace("{{view}}", view);
}

function formatPercent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}٪`;
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  changeArea: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  card: {
    gap: fiticianTokens.spacing[2],
  },
  cardHeading: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  cardTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  content: {
    gap: fiticianTokens.spacing[4],
    paddingBottom: fiticianTokens.spacing[6],
  },
  disclaimerCard: {
    gap: fiticianTokens.spacing[3],
  },
  disclaimerHeading: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  headerAction: {
    minHeight: 42,
    paddingHorizontal: fiticianTokens.spacing[3],
  },
  issueText: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  loading: {
    gap: fiticianTokens.spacing[4],
    justifyContent: "center",
    minHeight: 420,
  },
  muted: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "auto",
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
  photo: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderRadius: fiticianTokens.radii.medium,
    height: 160,
    width: 104,
  },
  photoItem: {
    alignItems: "center",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  photoRow: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  reviewDot: {
    backgroundColor: fiticianTokens.colors.muted,
    borderRadius: fiticianTokens.radii.pill,
    height: 9,
    width: 9,
  },
  reviewDotApproved: {
    backgroundColor: fiticianTokens.colors.success,
  },
  reviewRow: {
    alignItems: "center",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
  },
  reviewValue: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    marginInlineStart: "auto",
    textAlign: "auto",
    writingDirection: "rtl",
  },
  reviewValueApproved: {
    color: fiticianTokens.colors.success,
  },
  section: {
    gap: fiticianTokens.spacing[3],
  },
  screen: {
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[3],
  },
  status: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
});
