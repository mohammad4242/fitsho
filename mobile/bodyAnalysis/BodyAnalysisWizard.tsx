import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Image, StyleSheet, Switch, Text, View } from "react-native";
import { File } from "expo-file-system";

import { ApiError } from "@fitician/core";
import type {
  BodyAnalysis,
  BodyPhotoPurpose,
  BodyPhotoSession,
  BodyPhotoView,
} from "@fitician/core/body-photos";
import type { Sex } from "@fitician/core/profile";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { Button, Card, Notice, Skeleton } from "../ui/components";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";
import { BodyAnalysisRequirements } from "./BodyAnalysisRequirements";
import {
  BODY_PHOTO_VIEWS,
  createBodyPhotoFlowDraft,
  reconcileBodyPhotoFlowDraft,
  type BodyPhotoFlowDraft,
} from "./bodyPhotoFlow";
import { createBodyPhotoApi } from "./bodyPhotoApi";
import { SecureBodyPhotoDraftStore } from "./bodyPhotoDraftStore";
import { BodyPhotoCapture } from "./BodyPhotoCapture";
import type { BodyPhotoCapturedAsset } from "./cameraCapture";
import { createProfileApi } from "../profile/profileApi";
import {
  draftForCapturedBodyPhoto,
  isResumableBodyPhotoSession,
  nextLocalBodyPhotoView,
} from "./bodyPhotoWizardModel";

export interface BodyAnalysisWizardProps {
  readonly onExit: () => void;
  readonly purpose?: BodyPhotoPurpose;
  readonly sessionId?: string;
}

type WizardPhase =
  | "capture"
  | "error"
  | "loading"
  | "requirements"
  | "review"
  | "starting"
  | "submitting"
  | "submitted";

type UploadProgressState = {
  readonly activeView: BodyPhotoView | null;
  readonly completed: number;
  readonly total: number;
};

const activeAnalysisStates = new Set<BodyAnalysis["status"]>([
  "queued",
  "validating",
  "analyzing",
]);

export function BodyAnalysisWizard({
  onExit,
  purpose = "initial_plan",
  sessionId,
}: BodyAnalysisWizardProps) {
  const auth = useMobileAuth();
  const userId = auth.user?.id ?? null;
  const api = useMemo(
    () => createBodyPhotoApi(auth.request, auth.upload, auth.download),
    [auth.download, auth.request, auth.upload],
  );
  const profileApi = useMemo(() => createProfileApi(auth.request), [auth.request]);
  const draftStore = useMemo(() => new SecureBodyPhotoDraftStore(), []);
  const [phase, setPhase] = useState<WizardPhase>("loading");
  const [session, setSession] = useState<BodyPhotoSession | null>(null);
  const [draft, setDraft] = useState<BodyPhotoFlowDraft | null>(null);
  const [activeView, setActiveView] = useState<BodyPhotoView | null>(null);
  const [capturedAssets, setCapturedAssets] = useState<Partial<Record<BodyPhotoView, BodyPhotoCapturedAsset>>>({});
  const [analysis, setAnalysis] = useState<BodyAnalysis | null>(null);
  const [sex, setSex] = useState<Sex | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [operationalConsent, setOperationalConsent] = useState(false);
  const [modelTrainingConsent, setModelTrainingConsent] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgressState | null>(null);
  const capturedAssetsRef = useRef(capturedAssets);
  const complete = session !== null && ["front", "side", "back"].every((view) => (
    capturedAssets[view as BodyPhotoView] !== undefined
    || session.photos.some((photo) => photo.view === view)
  ));

  useEffect(() => {
    capturedAssetsRef.current = capturedAssets;
  }, [capturedAssets]);

  useEffect(() => {
    return () => deleteCapturedAssets(capturedAssetsRef.current);
  }, []);

  useEffect(() => {
    if (userId === null) return undefined;
    let active = true;
    setPhase("loading");
    setError(null);
    void loadWizardState({
      api,
      draftStore,
      purpose,
      requestedSessionId: sessionId,
      userId,
    }).then((loaded) => {
      if (!active) return;
      if (loaded.session === null) {
        setDraft(loaded.draft);
        setPhase("requirements");
        return;
      }
      setSession(loaded.session);
      setOperationalConsent(loaded.session.operational_processing_consent?.granted ?? false);
      setModelTrainingConsent(loaded.session.model_training_consent?.granted ?? false);
      setDraft(loaded.draft);
      setActiveView(loaded.draft.current_view);
      setPhase(loaded.draft.current_view === null ? "review" : "capture");
    }).catch((cause: unknown) => {
      if (!active) return;
      setError(bodyPhotoWizardErrorMessage(cause));
      setPhase("error");
    });
    return () => {
      active = false;
    };
  }, [api, draftStore, purpose, sessionId, userId]);

  useEffect(() => {
    if (userId === null) return undefined;
    let active = true;
    void profileApi.getProfile()
      .then((profile) => {
        if (active) setSex(profile?.sex ?? null);
      })
      .catch(() => {
        if (active) setSex(null);
      });
    return () => {
      active = false;
    };
  }, [profileApi, userId]);

  useEffect(() => {
    if (phase !== "submitted" || session === null || analysis === null || !activeAnalysisStates.has(analysis.status)) {
      return undefined;
    }
    let active = true;
    const timer = setTimeout(() => {
      void api.getAnalysis(session.id)
        .then((next) => {
          if (active && next !== null) setAnalysis(next);
        })
        .catch(() => undefined);
    }, 3000);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [analysis, api, phase, session]);

  const updateDraft = useCallback((changes: Partial<BodyPhotoFlowDraft>) => {
    if (userId === null) return;
    setDraft((current) => {
      if (current === null) return current;
      const next = { ...current, ...changes, updated_at: Date.now() };
      void draftStore.save(userId, next);
      return next;
    });
  }, [draftStore, userId]);

  async function confirmMeasurements() {
    if (userId === null || phase === "starting") return;
    setPhase("starting");
    setError(null);
    try {
      const created = await api.createSession(purpose);
      const nextDraft = createBodyPhotoFlowDraft(purpose, created.id, created);
      await draftStore.save(userId, nextDraft);
      setSession(created);
      setDraft(nextDraft);
      setActiveView(nextDraft.current_view);
      setOperationalConsent(false);
      setModelTrainingConsent(false);
      setAnalysis(null);
      setPhase("capture");
    } catch (cause) {
      setError(bodyPhotoWizardErrorMessage(cause));
      setPhase("error");
    }
  }

  async function captureConfirmed(asset: BodyPhotoCapturedAsset) {
    if (session === null || draft === null || activeView === null || userId === null) return;
    const localViews = Object.keys(capturedAssets).filter(isBodyPhotoView);
    const nextView = nextLocalBodyPhotoView(session, localViews, activeView);
    const nextDraft = draftForCapturedBodyPhoto(
      draft,
      activeView,
      nextView,
      asset.source,
    );
    const previous = capturedAssets[activeView];
    if (previous !== undefined && previous.uri !== asset.uri) deleteLocalFile(previous.uri);
    await draftStore.save(userId, nextDraft);
    setCapturedAssets((current) => ({ ...current, [activeView]: asset }));
    setDraft(nextDraft);
    setActiveView(nextView);
    setPhase(nextView === null ? "review" : "capture");
  }

  function exitWizard() {
    deleteCapturedAssets(capturedAssetsRef.current);
    onExit();
  }

  async function submitAnalysis() {
    if (session === null || !complete || !operationalConsent || phase === "submitting") return;
    const pendingViews = (Object.keys(capturedAssets) as BodyPhotoView[]).filter((view) => (
      capturedAssets[view] !== undefined
      && !session.photos.some((photo) => photo.view === view)
    ));
    setPhase("submitting");
    setError(null);
    setUploadProgress({ activeView: null, completed: 0, total: pendingViews.length });
    let currentSession = session;
    try {
      for (const [index, view] of pendingViews.entries()) {
        const asset = capturedAssets[view];
        if (asset === undefined) continue;
        setUploadProgress({ activeView: view, completed: index, total: pendingViews.length });
        currentSession = await api.uploadPhoto(currentSession.id, view, asset);
        setSession(currentSession);
        setUploadProgress({ activeView: null, completed: index + 1, total: pendingViews.length });
      }
      if (!["front", "side", "back"].every((view) => currentSession.photos.some((photo) => photo.view === view))) {
        throw new Error("Three cropped body photos are required");
      }
      const submitted = await api.submitSession(
        currentSession.id,
        operationalConsent,
        modelTrainingConsent,
      );
      setSession(submitted);
      const started = await api.startAnalysis(submitted.id, true);
      setAnalysis(started);
      setUploadProgress(null);
      setPhase("submitted");
    } catch (cause) {
      setError(bodyPhotoSubmitErrorMessage(cause));
      setUploadProgress((current) => current === null ? null : { ...current, activeView: null });
      setPhase("review");
    }
  }

  async function retryAnalysis() {
    if (session === null || phase !== "submitted") return;
    setPhase("submitting");
    setError(null);
    try {
      const next = await api.retryAnalysis(session.id, true);
      setAnalysis(next);
      setPhase("submitted");
    } catch (cause) {
      setError(bodyPhotoSubmitErrorMessage(cause));
      setPhase("submitted");
    }
  }

  if (phase === "loading") {
    return (
      <Screen scroll={false}>
        <View style={styles.loading}>
          <Skeleton accessibilityLabel="در حال آماده‌سازی تحلیل بدن" height={32} width="64%" />
          <Skeleton accessibilityLabel="در حال آماده‌سازی تحلیل بدن" height={180} />
        </View>
      </Screen>
    );
  }

  if (phase === "error") {
    return (
      <Screen scroll={false}>
        <View style={styles.errorState}>
          <Text style={styles.eyebrow}>تحلیل بدن</Text>
          <Text style={styles.title}>ادامه این نشست ممکن نیست</Text>
          <Notice message={error ?? "خطایی در آماده‌سازی نشست رخ داد."} variant="danger" />
          <View style={styles.actions}>
            <Button label="شروع دوباره" onPress={() => {
              setError(null);
              setPhase("requirements");
            }} />
            <Button label="بازگشت" onPress={exitWizard} variant="secondary" />
          </View>
        </View>
      </Screen>
    );
  }

  if (phase === "requirements") {
    return (
      <BodyAnalysisRequirements
        onCancel={exitWizard}
        onConfirmed={() => void confirmMeasurements()}
      />
    );
  }

  if (phase === "starting") {
    return (
      <Screen scroll={false}>
        <View style={styles.loading}>
          <Skeleton accessibilityLabel="در حال ساخت نشست تحلیل بدن" height={32} width="70%" />
          <Text style={styles.body}>نشست امن تحلیل بدن در حال آماده‌سازی است.</Text>
        </View>
      </Screen>
    );
  }

  if (phase === "submitting") {
    return (
      <SubmissionProgress
        error={error}
        onExit={exitWizard}
        progress={uploadProgress}
      />
    );
  }

  if (phase === "submitted") {
    return (
      <AnalysisSubmitted
        analysis={analysis}
        error={error}
        onExit={exitWizard}
        onRetry={() => void retryAnalysis()}
      />
    );
  }

  if (phase === "review") {
    return (
      <CaptureReview
        assets={capturedAssets}
        error={error}
        onEdit={(view) => {
          setActiveView(view);
          setPhase("capture");
        }}
        onExit={exitWizard}
        onModelTrainingConsentChange={setModelTrainingConsent}
        onOperationalConsentChange={setOperationalConsent}
        onSubmit={() => void submitAnalysis()}
        operationalConsent={operationalConsent}
        modelTrainingConsent={modelTrainingConsent}
        session={session}
      />
    );
  }

  if (session === null || draft === null || activeView === null) {
    return null;
  }

  return (
    <Screen>
      <BodyPhotoCapture
        key={`${activeView}-${Object.keys(capturedAssets).length}`}
        completedViews={BODY_PHOTO_VIEWS.filter((view) => (
          capturedAssets[view] !== undefined
          || session.photos.some((photo) => photo.view === view)
        ))}
        initialCaptureMode={draft.capture_mode}
        initialGhostScale={draft.ghost_scale}
        initialSideProfile={draft.side_profile}
        onCancel={exitWizard}
        onCaptured={captureConfirmed}
        onGhostScaleChange={(scale) => updateDraft({ ghost_scale: scale })}
        onSideProfileChange={(nextSideProfile) => updateDraft({ side_profile: nextSideProfile })}
        sex={sex}
        view={activeView}
      />
    </Screen>
  );
}

type LoadedWizardState = {
  readonly draft: BodyPhotoFlowDraft;
  readonly session: BodyPhotoSession | null;
};

async function loadWizardState(options: {
  readonly api: ReturnType<typeof createBodyPhotoApi>;
  readonly draftStore: SecureBodyPhotoDraftStore;
  readonly purpose: BodyPhotoPurpose;
  readonly requestedSessionId?: string;
  readonly userId: string;
}): Promise<LoadedWizardState> {
  const storedDraft = await options.draftStore.load(options.userId);
  const requestedId = options.requestedSessionId?.trim() || storedDraft?.session_id || null;
  if (requestedId !== null) {
    try {
      const session = await options.api.getSession(requestedId);
      if (!isResumableBodyPhotoSession(session)) {
        await options.draftStore.clear(options.userId);
        return {
          draft: createBodyPhotoFlowDraft(options.purpose),
          session: null,
        };
      }
      const draft = reconcileBodyPhotoFlowDraft(
        storedDraft?.session_id === session.id ? storedDraft : createBodyPhotoFlowDraft(session.purpose, session.id, session),
        session,
      );
      await options.draftStore.save(options.userId, draft);
      return { draft, session };
    } catch (cause) {
      if (!(cause instanceof ApiError && cause.status === 404) || options.requestedSessionId !== undefined) {
        throw cause;
      }
      await options.draftStore.clear(options.userId);
    }
  }

  const draft = storedDraft?.session_id === null || storedDraft === null
    ? storedDraft ?? createBodyPhotoFlowDraft(options.purpose)
    : createBodyPhotoFlowDraft(options.purpose);
  await options.draftStore.save(options.userId, draft);
  return { draft, session: null };
}

function bodyPhotoWizardErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) {
    return "این درخواست از آدرس امن فیتیچیان ارسال نشد. دوباره تلاش کن.";
  }
  if (error instanceof ApiError && error.status >= 500) {
    return "سرویس تحلیل بدن موقتاً در دسترس نیست.";
  }
  return "آماده‌سازی تحلیل بدن انجام نشد. دوباره تلاش کن.";
}

function bodyPhotoSubmitErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) {
    return "ارسال از مسیر امن فیتیچیان انجام نشد. دوباره تلاش کن.";
  }
  if (error instanceof ApiError && error.status === 409) {
    return "وضعیت این نشست تغییر کرده است. نشست را دوباره باز کن.";
  }
  if (error instanceof ApiError && error.status >= 500) {
    return "سرویس تحلیل بدن موقتاً در دسترس نیست. اطلاعات ثبت‌شده حفظ شد.";
  }
  return "ارسال امن تصاویر انجام نشد. عکس‌های ثبت‌شده حفظ شدند؛ دوباره تلاش کن.";
}

function isBodyPhotoView(value: string): value is BodyPhotoView {
  return value === "front" || value === "side" || value === "back";
}

function CaptureReview({
  assets,
  error,
  onEdit,
  onExit,
  onModelTrainingConsentChange,
  onOperationalConsentChange,
  onSubmit,
  operationalConsent,
  modelTrainingConsent,
  session,
}: {
  readonly assets: Partial<Record<BodyPhotoView, BodyPhotoCapturedAsset>>;
  readonly error: string | null;
  readonly onEdit: (view: BodyPhotoView) => void;
  readonly onExit: () => void;
  readonly onModelTrainingConsentChange: (value: boolean) => void;
  readonly onOperationalConsentChange: (value: boolean) => void;
  readonly onSubmit: () => void;
  readonly operationalConsent: boolean;
  readonly modelTrainingConsent: boolean;
  readonly session: BodyPhotoSession | null;
}) {
  return (
    <Screen>
      <View style={styles.review}>
        <Text style={styles.eyebrow}>سه نمای بدن آماده شد</Text>
        <Text style={styles.title}>تصاویر را مرور کن</Text>
        <Text style={styles.body}>
          این مرحله فقط پیش‌نمایش محلی عکس‌هاست. هیچ تصویر خامی در نشست قابل بازیابی ذخیره نشده است.
        </Text>
        <View style={styles.reviewGrid}>
          {(["front", "side", "back"] as const).map((view) => {
            const asset = assets[view];
            const uploaded = session?.photos.some((photo) => photo.view === view) === true;
            return (
              <Card key={view} style={styles.reviewCard}>
                {asset === undefined ? (
                  <Text style={styles.body}>{uploaded
                    ? `${viewLabel(view)} قبلاً در نشست امن ثبت شده است.`
                    : `${viewLabel(view)} در این دستگاه ثبت نشد.`}</Text>
                ) : (
                  <Image
                    accessibilityLabel={`پیش‌نمایش ${viewLabel(view)}`}
                    source={{ uri: asset.uri }}
                    style={styles.reviewImage}
                  />
                )}
                <Button label={`ویرایش ${viewLabel(view)}`} onPress={() => onEdit(view)} variant="secondary" />
              </Card>
            );
          })}
        </View>
        <Notice
          message="ارسال، رضایت‌نامه و شروع تحلیل در مرحله امن پردازش تصویر انجام می‌شود."
          variant="info"
        />
        <ConsentToggle
          label="با پردازش عملیاتی تصاویر برای تحلیل بدن موافقم."
          onValueChange={onOperationalConsentChange}
          value={operationalConsent}
        />
        <ConsentToggle
          label="با استفاده از تصاویر برای بهبود مدل‌ها موافقم (اختیاری)."
          onValueChange={onModelTrainingConsentChange}
          value={modelTrainingConsent}
        />
        <Button
          disabled={!operationalConsent}
          label="ارسال و شروع تحلیل"
          onPress={onSubmit}
        />
        {error !== null ? <Notice message={error} variant="danger" /> : null}
        <Button label="بستن" onPress={onExit} variant="ghost" />
      </View>
    </Screen>
  );
}

function ConsentToggle({
  label,
  onValueChange,
  value,
}: {
  readonly label: string;
  readonly onValueChange: (value: boolean) => void;
  readonly value: boolean;
}) {
  return (
    <View style={styles.consentRow}>
      <Text style={styles.body}>{label}</Text>
      <Switch
        accessibilityLabel={label}
        onValueChange={onValueChange}
        thumbColor={value ? fiticianTokens.colors.aqua : fiticianTokens.colors.muted}
        trackColor={{ false: fiticianTokens.colors.lineStrong, true: fiticianTokens.colors.surfaceInteractive }}
        value={value}
      />
    </View>
  );
}

function SubmissionProgress({
  error,
  onExit,
  progress,
}: {
  readonly error: string | null;
  readonly onExit: () => void;
  readonly progress: UploadProgressState | null;
}) {
  const completed = progress?.completed ?? 0;
  const total = progress?.total ?? 0;
  const retrying = progress === null;
  return (
    <Screen scroll={false}>
      <View style={styles.statusState}>
        <Text style={styles.eyebrow}>ارسال امن تحلیل بدن</Text>
        <Text style={styles.title}>{retrying ? "درخواست تحلیل دوباره در حال ارسال است" : "تصاویرت در حال ارسال است"}</Text>
        <Text style={styles.body}>
          {retrying
            ? "وضعیت آخرین نشست دوباره بررسی می‌شود."
            : "فقط نسخه‌های برش‌خورده و رمزگذاری‌شده برای نشست تحلیل ارسال می‌شوند."}
        </Text>
        <Skeleton accessibilityLabel="در حال ارسال تصاویر تحلیل بدن" height={12} />
        {total > 0 ? <Text style={styles.body}>نمایش {completed} از {total} آماده شد.</Text> : null}
        {progress?.activeView !== null && progress?.activeView !== undefined ? (
          <Text style={styles.body}>در حال ارسال نمای {viewLabel(progress.activeView)}…</Text>
        ) : null}
        {error !== null ? <Notice message={error} variant="danger" /> : null}
        <Button label="بازگشت" onPress={onExit} variant="ghost" />
      </View>
    </Screen>
  );
}

function AnalysisSubmitted({
  analysis,
  error,
  onExit,
  onRetry,
}: {
  readonly analysis: BodyAnalysis | null;
  readonly error: string | null;
  readonly onExit: () => void;
  readonly onRetry: () => void;
}) {
  const status = analysis?.status ?? "queued";
  const failed = analysis?.status === "failed";
  return (
    <Screen scroll={false}>
      <View style={styles.statusState}>
        <Text style={styles.eyebrow}>تحلیل بدن</Text>
        <Text style={styles.title}>{failed ? "تحلیل کامل نشد" : "تحلیل در حال آماده‌سازی است"}</Text>
        <Text style={styles.body}>{analysisStatusLabel(status)}</Text>
        {analysis?.safe_error_message !== null && analysis?.safe_error_message !== undefined ? (
          <Notice message={analysis.safe_error_message} variant="danger" />
        ) : null}
        {error !== null ? <Notice message={error} variant="danger" /> : null}
        {activeAnalysisStates.has(status) ? (
          <Skeleton accessibilityLabel="تحلیل بدن در حال انجام است" height={12} />
        ) : null}
        {failed ? <Button label="تلاش دوباره" onPress={onRetry} /> : null}
        <Button label="بازگشت به خانه" onPress={onExit} variant="secondary" />
      </View>
    </Screen>
  );
}

function analysisStatusLabel(status: BodyAnalysis["status"]): string {
  if (status === "queued") return "در صف پردازش قرار گرفت.";
  if (status === "validating") return "کیفیت و استاندارد تصاویر در حال بررسی است.";
  if (status === "analyzing") return "تحلیل محلی و سرویس امن در حال انجام است.";
  if (status === "review_pending") return "نتیجه برای بررسی مربی و پزشک ارسال شده است.";
  if (status === "completed") return "نتیجه آماده است و پس از بررسی تخصصی نمایش داده می‌شود.";
  return "تحلیل به پایان نرسید.";
}

function viewLabel(view: BodyPhotoView): string {
  if (view === "front") return "روبه‌رو";
  if (view === "side") return "نیمرخ";
  return "پشت";
}

function deleteCapturedAssets(
  assets: Partial<Record<BodyPhotoView, BodyPhotoCapturedAsset>>,
): void {
  const uris = new Set(
    Object.values(assets)
      .filter((asset): asset is BodyPhotoCapturedAsset => asset !== undefined)
      .map((asset) => asset.uri),
  );
  uris.forEach(deleteLocalFile);
}

function deleteLocalFile(uri: string): void {
  try {
    const file = new File(uri);
    if (file.exists) file.delete();
  } catch {
    // Temporary crop cleanup is best effort only.
  }
}

const styles = StyleSheet.create({
  actions: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  body: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "right",
    writingDirection: "rtl",
  },
  consentRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  errorState: {
    gap: fiticianTokens.spacing[4],
    justifyContent: "center",
    minHeight: 420,
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  loading: {
    gap: fiticianTokens.spacing[4],
    justifyContent: "center",
    minHeight: 420,
  },
  review: {
    gap: fiticianTokens.spacing[3],
    paddingBottom: fiticianTokens.spacing[6],
  },
  reviewCard: {
    gap: fiticianTokens.spacing[3],
  },
  reviewGrid: {
    gap: fiticianTokens.spacing[3],
  },
  reviewImage: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderRadius: fiticianTokens.radii.medium,
    height: 260,
    width: "100%",
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
