import { useCallback, useEffect, useMemo, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";

import { ApiError } from "@fitician/core";
import type {
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

type WizardPhase = "capture" | "error" | "loading" | "requirements" | "review" | "starting";

export function BodyAnalysisWizard({
  onExit,
  purpose = "initial_plan",
  sessionId,
}: BodyAnalysisWizardProps) {
  const auth = useMobileAuth();
  const userId = auth.user?.id ?? null;
  const api = useMemo(() => createBodyPhotoApi(auth.request), [auth.request]);
  const profileApi = useMemo(() => createProfileApi(auth.request), [auth.request]);
  const draftStore = useMemo(() => new SecureBodyPhotoDraftStore(), []);
  const [phase, setPhase] = useState<WizardPhase>("loading");
  const [session, setSession] = useState<BodyPhotoSession | null>(null);
  const [draft, setDraft] = useState<BodyPhotoFlowDraft | null>(null);
  const [activeView, setActiveView] = useState<BodyPhotoView | null>(null);
  const [capturedAssets, setCapturedAssets] = useState<Partial<Record<BodyPhotoView, BodyPhotoCapturedAsset>>>({});
  const [sex, setSex] = useState<Sex | null>(null);
  const [error, setError] = useState<string | null>(null);

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
    await draftStore.save(userId, nextDraft);
    setCapturedAssets((current) => ({ ...current, [activeView]: asset }));
    setDraft(nextDraft);
    setActiveView(nextView);
    setPhase(nextView === null ? "review" : "capture");
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
            <Button label="بازگشت" onPress={onExit} variant="secondary" />
          </View>
        </View>
      </Screen>
    );
  }

  if (phase === "requirements") {
    return (
      <BodyAnalysisRequirements
        onCancel={onExit}
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

  if (phase === "review") {
    return (
      <CaptureReview
        assets={capturedAssets}
        onEdit={(view) => {
          setActiveView(view);
          setPhase("capture");
        }}
        onExit={onExit}
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
        initialCaptureMode={draft.capture_mode}
        initialGhostScale={draft.ghost_scale}
        initialSideProfile={draft.side_profile}
        onCancel={onExit}
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

function isBodyPhotoView(value: string): value is BodyPhotoView {
  return value === "front" || value === "side" || value === "back";
}

function CaptureReview({
  assets,
  onEdit,
  onExit,
}: {
  readonly assets: Partial<Record<BodyPhotoView, BodyPhotoCapturedAsset>>;
  readonly onEdit: (view: BodyPhotoView) => void;
  readonly onExit: () => void;
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
            return (
              <Card key={view} style={styles.reviewCard}>
                {asset === undefined ? (
                  <Text style={styles.body}>{viewLabel(view)} در این دستگاه ثبت نشد.</Text>
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
        <Button label="بستن" onPress={onExit} variant="ghost" />
      </View>
    </Screen>
  );
}

function viewLabel(view: BodyPhotoView): string {
  if (view === "front") return "روبه‌رو";
  if (view === "side") return "نیمرخ";
  return "پشت";
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
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 42,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
