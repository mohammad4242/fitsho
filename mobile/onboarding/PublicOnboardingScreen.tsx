import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { createInitialOnboardingState, transitionOnboardingState, type OnboardingEvent, type OnboardingState } from "@fitician/core/onboarding";

import { PUBLIC_ONBOARDING_SOURCE } from "../auth/authRoute";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import { AppIcon, Button, Card, Notice, PageHeading, ProgressBar, StateSkeleton } from "../ui/components";
import { Screen } from "../ui/layout";
import { mobileRequestErrorMessage } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import {
  ExerciseStage,
  ModeStage,
  NutritionBasicsStage,
  NutritionPreferencesStage,
  nutritionBasicsFormValuesForState,
  nutritionPreferencesFormValuesForState,
  SafetyStage,
  safetyFormValuesForState,
  SharedProfileStage,
  TrainingProfileStage,
  exerciseFormValuesForState,
} from "./OnboardingScreen";
import { getOnboardingStageProgress } from "./onboardingQuestionFlow";
import {
  emptyProfileFormValues,
  profileFormValuesForSharedProfile,
  profileFormValuesForTrainingProfile,
} from "./onboardingForms";
import { SecurePublicOnboardingDraftStore } from "./publicOnboardingDraftStore";

const publicOnboardingCopy = {
  header: "اطلاعاتت تا زمان ساخت حساب فقط در همین تب نگه‌داری می‌شود.",
  mode: {
    eyebrow: "شروع با مربی فیتشو",
    labels: {
      both: "تمرین و تغذیه",
      nutrition: "برنامه تغذیه",
      training: "برنامه تمرینی",
    },
    title: "تو چه زمینه‌ای به کمک نیاز داری؟",
  },
  account: {
    description: "پاسخ‌ها بعد از ورود امن به حساب فیتشو منتقل می‌شوند.",
    edit: "بازگشت و ویرایش پاسخ‌ها",
    eyebrow: "آخرین قدم",
    securityBody: "پاسخ‌ها تا لحظه‌ی ساخت حساب در همین تب می‌مانند.",
    securityTitle: "مسیر امن انتقال اطلاعات",
    title: "حالا حسابت را بساز",
  },
} as const;

export function PublicOnboardingScreen() {
  const router = useRouter();
  const store = useMemo(() => new SecurePublicOnboardingDraftStore(), []);
  const [state, setState] = useState<OnboardingState | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void store.load()
      .then((result) => {
        if (!active) return;
        setState(result.status === "valid" ? result.state : createInitialOnboardingState());
      })
      .catch(() => {
        if (active) {
          setError("ذخیره مسیر شخصی‌سازی در دسترس نیست. دوباره تلاش کن.");
          setState(createInitialOnboardingState());
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [store]);

  const run = useCallback((event: OnboardingEvent) => {
    if (state === null || busy) return;
    setBusy(true);
    setError(null);
    void (async () => {
      const next = transitionOnboardingState(state, event);
      await store.save(next);
      setState(next);
    })()
      .catch((transitionError: unknown) => setError(publicOnboardingErrorMessage(transitionError)))
      .finally(() => setBusy(false));
  }, [busy, state, store]);

  const goBack = useCallback((): boolean => {
    if (state === null || state.step === "product_mode") return false;
    if (busy) return true;
    setBusy(true);
    setError(null);
    void (async () => {
      const previous = transitionOnboardingState(state, { type: "back" });
      await store.save(previous);
      setState(previous);
    })()
      .catch((backError: unknown) => setError(publicOnboardingErrorMessage(backError)))
      .finally(() => setBusy(false));
    return true;
  }, [busy, state, store]);

  useAndroidBackHandler("wizard", goBack, state !== null && !loading);

  if (loading || state === null) {
    return (
      <Screen contentWidth="reading" contentContainerStyle={styles.loadingScreen}>
        <StateSkeleton style={styles.loadingSkeleton} variant="hero" />
        <ActivityIndicator accessibilityLabel="در حال آماده‌سازی" color={fiticianTokens.colors.aqua} />
        <Text style={styles.loadingText}>در حال آماده‌سازی مسیر شخصی تو…</Text>
      </Screen>
    );
  }

  const progress = onboardingProgress(state);
  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <View style={styles.brandRow}>
        <Text style={styles.brand}>FITICIAN</Text>
        <View style={styles.progressPill}>
          <View style={styles.progressDot} />
          <Text style={styles.progressText}>{progress}</Text>
        </View>
      </View>
      <View style={styles.publicHeaderNote} testID="public-onboarding-header-note">
        <AppIcon color={fiticianTokens.colors.aqua} name="shield" size={fiticianTokens.iconSize.sm} />
        <Text style={styles.publicHeaderNoteText}>{publicOnboardingCopy.header}</Text>
      </View>
      <View style={styles.progressTrack}>
        <ProgressBar label="پیشرفت مسیر شخصی‌سازی" progress={onboardingProgressValue(state)} />
      </View>
      {error ? <Notice message={error} variant="danger" /> : null}
      {state.step === "product_mode" ? (
        <ModeStage
          busy={busy}
          copy={{
            eyebrow: publicOnboardingCopy.mode.eyebrow,
            labels: publicOnboardingCopy.mode.labels,
            showDescriptions: false,
            title: publicOnboardingCopy.mode.title,
          }}
          onSelect={(mode) => run({ mode, type: "select_product_mode" })}
        />
      ) : null}
      {state.step === "shared_profile" ? (
        <SharedProfileStage
          busy={busy}
          initialValues={state.shared === null ? emptyProfileFormValues() : profileFormValuesForSharedProfile(state.shared)}
          onBack={goBack}
          onSubmit={(profile) => run({ profile, type: "save_shared_profile" })}
        />
      ) : null}
      {state.step === "nutrition_safety" ? (
        <SafetyStage
          blocked={false}
          busy={busy}
          initialValues={safetyFormValuesForState(state.safety)}
          onBack={goBack}
          onSubmit={(safety) => run({ safety, type: "save_nutrition_safety" })}
        />
      ) : null}
      {state.step === "training_profile" ? (
        <TrainingProfileStage
          busy={busy}
          initialValues={state.training === null
            ? state.shared === null ? emptyProfileFormValues() : profileFormValuesForSharedProfile(state.shared)
            : profileFormValuesForTrainingProfile(state.training)}
          onBack={goBack}
          onSubmit={(profile) => run({ profile, type: "save_training_profile" })}
        />
      ) : null}
      {state.step === "exercise_context" ? (
        <ExerciseStage
          busy={busy}
          initialValues={exerciseFormValuesForState(state.structuredExercise)}
          onBack={goBack}
          onSubmit={(exercise) => run({ exercise, type: "save_exercise_context" })}
        />
      ) : null}
      {state.step === "nutrition_basics" ? (
        <NutritionBasicsStage
          busy={busy}
          initialValues={nutritionBasicsFormValuesForState(state.nutritionBasics)}
          onBack={goBack}
          onSubmit={(basics) => run({ basics, type: "save_nutrition_basics" })}
        />
      ) : null}
      {state.step === "nutrition_preferences" ? (
        <NutritionPreferencesStage
          basics={state.nutritionBasics}
          busy={busy}
          initialValues={nutritionPreferencesFormValuesForState(state.nutrition)}
          onBack={goBack}
          onSubmit={(nutrition) => run({ profile: nutrition, type: "save_nutrition_profile" })}
        />
      ) : null}
      {state.step === "review" ? <AccountHandoffStage onBack={goBack} onRegister={() => router.push({ pathname: "/auth/register", params: { source: PUBLIC_ONBOARDING_SOURCE } })} onSignIn={() => router.push({ pathname: "/auth/sign-in", params: { source: PUBLIC_ONBOARDING_SOURCE } })} /> : null}
      {state.step === "complete" ? <Notice message="این مسیر قبلاً تکمیل شده است." variant="success" /> : null}
    </Screen>
  );
}

function AccountHandoffStage({
  onBack,
  onRegister,
  onSignIn,
}: {
  readonly onBack: () => boolean;
  readonly onRegister: () => void;
  readonly onSignIn: () => void;
}) {
  return (
    <View style={styles.stage}>
      <PageHeading
        compact={false}
        eyebrow={publicOnboardingCopy.account.eyebrow}
        supportingText={publicOnboardingCopy.account.description}
        testID="public-onboarding-account-heading"
        title={publicOnboardingCopy.account.title}
      />
      <Button label={publicOnboardingCopy.account.edit} onPress={onBack} variant="ghost" />
      <Card variant="hero" style={styles.accountCard}>
        <View style={styles.accountIcon}>
          <AppIcon accessibilityLabel="امنیت" color={fiticianTokens.colors.aqua} name="shield" size={fiticianTokens.iconSize.lg} />
        </View>
        <View style={styles.accountCopy}>
          <Text style={styles.accountTitle}>{publicOnboardingCopy.account.securityTitle}</Text>
          <Text style={styles.accountDescription}>{publicOnboardingCopy.account.securityBody}</Text>
        </View>
      </Card>
      <View style={styles.accountActions}>
        <Button label="ساخت حساب و ذخیره پاسخ‌ها" onPress={onRegister} />
        <Button label="ورود و ذخیره پاسخ‌ها" onPress={onSignIn} variant="secondary" />
      </View>
    </View>
  );
}

function onboardingProgress(state: OnboardingState): string {
  const progress = getOnboardingStageProgress(state.mode, state.step);
  if (progress.total === 0) return "شروع";
  return `پاسخ‌های ثبت‌شده ${progress.completed} از ${progress.total}`;
}

function onboardingProgressValue(state: OnboardingState): number {
  return getOnboardingStageProgress(state.mode, state.step).progress;
}

function publicOnboardingErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message !== "") {
    if (error.message.includes("incomplete")) return "پاسخ‌ها را کامل کن و دوباره تلاش کن.";
  }
  return mobileRequestErrorMessage(error, "ذخیره پاسخ‌ها انجام نشد. دوباره تلاش کن.");
}

const styles = StyleSheet.create({
  accountActions: {
    gap: fiticianTokens.spacing[3],
  },
  accountCard: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[4],
  },
  accountCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[2],
  },
  accountDescription: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  accountIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    height: 56,
    justifyContent: "center",
    width: 56,
  },
  accountTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 24,
    textAlign: "right",
    writingDirection: "rtl",
  },
  brand: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    letterSpacing: 1.4,
    writingDirection: "ltr",
  },
  brandRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    justifyContent: "space-between",
    width: "100%",
  },
  loadingScreen: {
    alignItems: "center",
    gap: fiticianTokens.spacing[4],
    justifyContent: "center",
  },
  loadingSkeleton: {
    alignSelf: "stretch",
  },
  loadingText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    textAlign: "center",
    writingDirection: "rtl",
  },
  progressDot: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 6,
    width: 6,
  },
  progressPill: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[2],
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  progressText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    writingDirection: "rtl",
  },
  progressTrack: {
    marginTop: -fiticianTokens.spacing[3],
  },
  publicHeaderNote: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[2],
    width: "100%",
  },
  publicHeaderNoteText: {
    color: fiticianTokens.colors.muted,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  screen: {
    gap: fiticianTokens.spacing[5],
    paddingBottom: fiticianTokens.spacing[7],
  },
  stage: {
    gap: fiticianTokens.spacing[5],
  },
});
