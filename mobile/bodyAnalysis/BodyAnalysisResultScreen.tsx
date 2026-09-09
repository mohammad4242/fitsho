import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Image, StyleSheet, Text, View } from "react-native";

import { ApiError } from "@fitician/core";
import type {
  BodyAnalysis,
  BodyAnalysisExperienceRegion,
  BodyArea,
  BodyPhoto,
  BodyPhotoSession,
  BodyProgressComparison,
  BodyProgressMeasurementDelta,
  BodyProgressState,
  BodyProgressVisualTransition,
  NormalizedBodyProgressComparisonV1,
  NormalizedBodyProgressComparisonV2,
} from "@fitician/core/body-photos";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { PrivateMediaClient } from "../media/privateMedia";
import { ExpoPrivateMediaStore } from "../media/privateMediaStore";
import { Button, Card, Notice, Skeleton } from "../ui/components";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";
import { createBodyPhotoApi } from "./bodyPhotoApi";
import { BodyAnalysisOverviewCard } from "./BodyAnalysisOverviewCard";

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
    if (userId === null) return null;
    return new PrivateMediaClient({
      authClient: { download: auth.download },
      storage: new ExpoPrivateMediaStore(),
      userId,
    });
  }, [auth.download, userId]);
  const [session, setSession] = useState<BodyPhotoSession | null>(null);
  const [analysis, setAnalysis] = useState<BodyAnalysis | null>(null);
  const [comparison, setComparison] = useState<BodyProgressComparison | null>(null);
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
      const [loadedSession, loadedAnalysis] = await Promise.all([
        api.getSession(sessionId),
        api.getAnalysis(sessionId),
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
      setComparison(await api.getComparison(sessionId).catch(() => null));
      setFailed(false);
      if (mediaClient !== null) {
        void loadPrivatePhotos(loadedSession, mediaClient)
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
          <Text style={styles.title}>نتیجه تحلیل بدن در دسترس نیست</Text>
          <Notice message={actionError ?? "دریافت نتیجه تحلیل انجام نشد."} variant="danger" />
          <Button label="تلاش دوباره" onPress={() => void load()} />
          <Button label="تاریخچه" onPress={() => router.replace("/member/body-analysis-history")} variant="secondary" />
        </View>
      </Screen>
    );
  }

  const failedAnalysis = analysis?.status === "failed";
  return (
    <Screen>
      <View style={styles.content}>
        <Text style={styles.eyebrow}>تحلیل بدن</Text>
        <Text style={styles.title}>نتیجه نشست</Text>
        <Text style={styles.body}>وضعیت نشست: {sessionStatusLabel(session.state)}</Text>
        {analysis === null ? (
          <Notice message="نتیجه هنوز آماده نشده است." variant="info" />
        ) : activeAnalysisStates.has(analysis.status) ? (
          <Notice message={analysisStatusLabel(analysis.status)} variant="info" />
        ) : null}
        {failedAnalysis ? (
          <Notice
            message={analysis.safe_error_message ?? "تحلیل کامل نشد. دوباره تلاش کن."}
            variant="danger"
          />
        ) : null}
        {actionError !== null ? <Notice message={actionError} variant="danger" /> : null}
        {analysis === null || failedAnalysis ? (
          <Button disabled={actionBusy} label="تلاش دوباره" loading={actionBusy} onPress={() => void retry()} />
        ) : null}
        {analysis !== null && analysis.result_version !== null ? (
          <ResultVersionCard analysis={analysis} />
        ) : null}
        {analysis?.photo_validation !== null && analysis?.photo_validation !== undefined ? (
          <PhotoQualityCard analysis={analysis} />
        ) : null}
        {analysis?.experience_result !== null && analysis?.experience_result !== undefined ? (
          <>
            <BodyAnalysisOverviewCard experience={analysis.experience_result} />
            <ExperienceResult experience={analysis.experience_result} />
          </>
        ) : analysis?.normalized_result !== null && analysis?.normalized_result !== undefined ? (
          <NormalizedResult analysis={analysis} />
        ) : null}
        {analysis !== null ? <ReviewStatusCard analysis={analysis} /> : null}
        {comparison !== null ? <ComparisonCard comparison={comparison} /> : null}
        {session.photos.length > 0 ? <PhotoStrip photoUris={photoUris} photos={session.photos} /> : null}
        <View style={styles.actions}>
          <Button label="تاریخچه" onPress={() => router.replace("/member/body-analysis-history")} variant="secondary" />
          <Button label="بازگشت" onPress={() => router.replace("/member")} variant="ghost" />
        </View>
      </View>
    </Screen>
  );
}

function ResultVersionCard({ analysis }: { readonly analysis: BodyAnalysis }) {
  return (
    <Card style={styles.card}>
      <Text style={styles.cardTitle}>نسخه نتیجه</Text>
      <Text style={styles.body}>نسخه {analysis.result_version} · منبع {resultSourceLabel(analysis.result_source)}</Text>
      <Text style={styles.body}>اعتماد کلی: {formatPercent(analysis.overall_confidence)}</Text>
      {analysis.unverified_warning ? (
        <Notice message="این نتیجه هنوز توسط هر دو متخصص تأیید نشده است." variant="warning" />
      ) : (
        <Notice message="این نسخه توسط روند بررسی تخصصی تأیید شده است." variant="success" />
      )}
    </Card>
  );
}

function PhotoQualityCard({ analysis }: { readonly analysis: BodyAnalysis }) {
  const validation = analysis.photo_validation;
  if (validation === null || validation === undefined) return null;
  return (
    <Card style={styles.card}>
      <Text style={styles.cardTitle}>بازخورد کیفیت تصاویر</Text>
      <Text style={styles.body}>{validation.accepted ? "سه تصویر برای تحلیل قابل استفاده بود." : "کیفیت تصویر نیاز به اصلاح دارد."}</Text>
      <Text style={styles.body}>اطمینان بررسی: {formatPercent(validation.confidence)}</Text>
      {validation.issues.map((issue) => (
        <Text key={issue.view} style={styles.issueText}>
          {viewLabel(issue.view)}: {issue.reasons.map(photoQualityReasonLabel).join("، ")}
        </Text>
      ))}
    </Card>
  );
}

function ExperienceResult({
  experience,
}: {
  readonly experience: NonNullable<BodyAnalysis["experience_result"]>;
}) {
  const focus = experience.regions.filter((region) => (
    region.display_classification === "primary_priority"
    || region.display_classification === "room_to_grow"
  )).slice(0, 3);
  const strengths = experience.regions.filter((region) => region.display_classification === "stronger").slice(0, 3);
  return (
    <View style={styles.section}>
      <Card style={styles.card}>
        <Text style={styles.cardTitle}>برداشت اولیه</Text>
        <Text style={styles.body}>وضعیت ارزیابی: {experience.assessment_status === "complete" ? "کامل" : "ناقص"}</Text>
        <Text style={styles.body}>نتیجه: {experience.first_impression.message_key}</Text>
      </Card>
      <Card style={styles.card}>
        <Text style={styles.cardTitle}>اولویت‌های قابل مشاهده</Text>
        {focus.length === 0 ? <Text style={styles.body}>اولویت مشخصی ثبت نشده است.</Text> : focus.map(regionText)}
      </Card>
      <Card style={styles.card}>
        <Text style={styles.cardTitle}>نقاط قوت قابل مشاهده</Text>
        {strengths.length === 0 ? <Text style={styles.body}>نقطه قوت جداگانه‌ای ثبت نشده است.</Text> : strengths.map(regionText)}
      </Card>
    </View>
  );
}

function regionText(region: BodyAnalysisExperienceRegion) {
  return (
    <Text key={region.area} style={styles.body}>
      {bodyAreaLabel(region.area)} · {regionClassificationLabel(region.display_classification)}
    </Text>
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
        <Text style={styles.body}>نسخه قرارداد: {result.schema_version}</Text>
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
    <Card style={styles.card}>
      <Text style={styles.cardTitle}>وضعیت بررسی تخصصی</Text>
      <Text style={styles.body}>مربی: {reviewLabel(analysis.coach_review.decision)}</Text>
      <Text style={styles.body}>پزشک: {reviewLabel(analysis.doctor_review.decision)}</Text>
      <Text style={styles.muted}>{analysis.fully_reviewed ? "هر دو بررسی تکمیل شده است." : "نتیجه تا تکمیل بررسی‌ها مقدماتی است."}</Text>
    </Card>
  );
}

function ComparisonCard({ comparison }: { readonly comparison: BodyProgressComparison }) {
  const normalized = comparison.normalized_result;
  return (
    <Card style={styles.card}>
      <Text style={styles.cardTitle}>مقایسه با نشست قبلی</Text>
      {normalized.schema_version === "2.0" ? (
        <V2Comparison comparison={normalized} />
      ) : (
        <LegacyComparison comparison={normalized} />
      )}
    </Card>
  );
}

function V2Comparison({ comparison }: { readonly comparison: NormalizedBodyProgressComparisonV2 }) {
  const measurements = comparison.measurement_deltas.filter(isAvailableMeasurement);
  const changes = comparison.visual_transitions.filter((item) => item.state !== "unchanged").slice(0, 4);
  return (
    <View style={styles.section}>
      <Text style={styles.body}>فاصله دو نشست: {comparison.interval_days} روز</Text>
      {measurements.length === 0 ? (
        <Text style={styles.muted}>اندازه قابل مقایسه‌ای ثبت نشده است.</Text>
      ) : measurements.map(measurementText)}
      {changes.length === 0 ? (
        <Text style={styles.muted}>تغییر بصری قابل اتکایی ثبت نشده است.</Text>
      ) : changes.map(visualChangeText)}
    </View>
  );
}

function LegacyComparison({ comparison }: { readonly comparison: NormalizedBodyProgressComparisonV1 }) {
  const changes = comparison.areas.filter((item) => item.state !== "unchanged").slice(0, 4);
  return changes.length === 0 ? (
    <Text style={styles.muted}>مقایسه بصری قابل اتکایی ثبت نشده است.</Text>
  ) : (
    <View style={styles.section}>{changes.map((item) => (
      <Text key={item.body_area} style={styles.body}>
        {bodyAreaLabel(item.body_area)} · {progressStateLabel(item.state)}
      </Text>
    ))}</View>
  );
}

function measurementText(delta: BodyProgressMeasurementDelta) {
  return (
    <Text key={delta.measurement} style={styles.body}>
      {measurementLabel(delta.measurement)}: {formatNumber(delta.previous)} ← {formatNumber(delta.current)} {delta.unit === "kg" ? "کیلو" : "سانتی‌متر"}
    </Text>
  );
}

function visualChangeText(transition: BodyProgressVisualTransition) {
  return (
    <Text key={transition.body_area} style={styles.body}>
      {bodyAreaLabel(transition.body_area)} · {progressStateLabel(transition.state)} · اطمینان {formatPercent(transition.change_confidence)}
    </Text>
  );
}

function PhotoStrip({
  photoUris,
  photos,
}: {
  readonly photoUris: Partial<Record<BodyPhoto["view"], string>>;
  readonly photos: BodyPhoto[];
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.cardTitle}>تصاویر خصوصی نشست</Text>
      <View style={styles.photoRow}>
        {photos.map((photo) => (
          <View key={photo.id} style={styles.photoItem}>
            {photoUris[photo.view] === undefined ? (
              <Text style={styles.muted}>محافظت‌شده</Text>
            ) : (
              <Image
                accessibilityLabel={`تصویر ${viewLabel(photo.view)}`}
                source={{ uri: photoUris[photo.view] }}
                style={styles.photo}
              />
            )}
            <Text style={styles.muted}>{viewLabel(photo.view)}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

async function loadPrivatePhotos(
  session: BodyPhotoSession,
  client: PrivateMediaClient,
): Promise<Partial<Record<BodyPhoto["view"], string>>> {
  const safeSessionId = session.id.replace(/[^A-Za-z0-9._-]/gu, "_");
  const entries = await Promise.all(session.photos.map(async (photo) => {
    try {
      const stored = await client.download({
        fileName: `body-analysis-${safeSessionId}-${photo.view}.jpg`,
        path: photo.content_url,
      });
      return [photo.view, stored.uri] as const;
    } catch {
      return null;
    }
  }));
  return Object.fromEntries(
    entries.filter((entry): entry is readonly [BodyPhoto["view"], string] => entry !== null),
  );
}

function isAvailableMeasurement(delta: BodyProgressMeasurementDelta): boolean {
  return delta.availability === "exact" && delta.previous !== null && delta.current !== null;
}

function bodyAnalysisLoadErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 404) return "این نشست تحلیل پیدا نشد.";
  if (error instanceof ApiError && error.status >= 500) return "سرویس تحلیل بدن موقتاً در دسترس نیست.";
  return "دریافت نتیجه تحلیل انجام نشد. دوباره تلاش کن.";
}

function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function sessionStatusLabel(status: BodyPhotoSession["state"]): string {
  const labels: Record<BodyPhotoSession["state"], string> = {
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
  return labels[status];
}

function analysisStatusLabel(status: BodyAnalysis["status"]): string {
  if (status === "queued") return "تحلیل در صف پردازش است.";
  if (status === "validating") return "کیفیت تصاویر در حال بررسی است.";
  if (status === "analyzing") return "تحلیل در حال انجام است.";
  return status === "review_pending" ? "نتیجه در انتظار بررسی تخصصی است." : "نتیجه آماده است.";
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

function regionClassificationLabel(value: BodyAnalysisExperienceRegion["display_classification"]): string {
  if (value === "stronger") return "قوی‌تر";
  if (value === "room_to_grow") return "جای رشد";
  if (value === "primary_priority") return "اولویت اصلی";
  if (value === "not_assessable") return "قابل ارزیابی نیست";
  return "متعادل";
}

function progressStateLabel(value: BodyProgressState): string {
  if (value === "improved") return "بهبود یافته";
  if (value === "declined_or_less_balanced") return "نیازمند توجه";
  if (value === "unchanged") return "بدون تغییر قابل اتکا";
  return "نامشخص";
}

function photoQualityReasonLabel(value: string): string {
  const labels: Record<string, string> = {
    clothing_obscures_body: "لباس فرم بدن را پوشانده است",
    exactly_one_person_required: "فقط یک نفر باید در تصویر باشد",
    full_body_not_visible: "تمام بدن در کادر نیست",
    low_lighting: "نور کم است",
    low_sharpness: "تصویر واضح نیست",
    photo_uncertain: "کیفیت تصویر قطعی نیست",
    unsuitable_background: "پس‌زمینه مناسب نیست",
    wrong_view: "نمای تصویر با نمای انتخاب‌شده هماهنگ نیست",
  };
  return labels[value] ?? "نیازمند بررسی";
}

function bodyAreaLabel(area: BodyArea): string {
  const labels: Record<BodyArea, string> = {
    arms: "بازوها",
    back: "پشت",
    calves: "ساق پا",
    chest: "سینه",
    forearms: "ساعدها",
    glutes: "باسن",
    hamstrings: "همسترینگ",
    lats: "زیربغل",
    quads: "چهارسر ران",
    shoulders: "سرشانه‌ها",
    symmetry: "تقارن",
    visible_alignment_or_posture: "هم‌راستایی و وضعیت بدن",
    waist_midsection: "کمر و میان‌تنه",
  };
  return labels[area];
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

function viewLabel(view: BodyPhoto["view"]): string {
  if (view === "front") return "روبه‌رو";
  if (view === "side") return "نیمرخ";
  return "پشت";
}

function formatPercent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}٪`;
}

function formatNumber(value: number | null): string {
  return value === null ? "—" : new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 2 }).format(value);
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
    textAlign: "right",
    writingDirection: "rtl",
  },
  content: {
    gap: fiticianTokens.spacing[4],
    paddingBottom: fiticianTokens.spacing[6],
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  issueText: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "right",
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
    textAlign: "right",
    writingDirection: "rtl",
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
  section: {
    gap: fiticianTokens.spacing[3],
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
