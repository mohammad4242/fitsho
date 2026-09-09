import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { getOnboardingSteps, createInitialOnboardingState, transitionOnboardingState, type OnboardingEvent, type OnboardingState } from "@fitician/core/onboarding";
import type { ProductMode } from "@fitician/core/profile";

import { PUBLIC_ONBOARDING_SOURCE } from "../auth/authRoute";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import { AppIcon, Button, Card, Notice, ProgressBar, StateSkeleton } from "../ui/components";
import { Screen } from "../ui/layout";
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
import {
  emptyProfileFormValues,
  profileFormValuesForSharedProfile,
  profileFormValuesForTrainingProfile,
} from "./onboardingForms";
import { SecurePublicOnboardingDraftStore } from "./publicOnboardingDraftStore";

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
      <View style={styles.progressTrack}>
        <ProgressBar label="پیشرفت مسیر شخصی‌سازی" progress={onboardingProgressValue(state)} />
      </View>
      {error ? <Notice message={error} variant="danger" /> : null}
      {state.step === "product_mode" ? <ModeStage busy={busy} onSelect={(mode) => run({ mode, type: "select_product_mode" })} /> : null}
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
      {state.step === "review" ? <AccountHandoffStage mode={state.mode} onBack={goBack} onRegister={() => router.push({ pathname: "/auth/register", params: { source: PUBLIC_ONBOARDING_SOURCE } })} onSignIn={() => router.push({ pathname: "/auth/sign-in", params: { source: PUBLIC_ONBOARDING_SOURCE } })} /> : null}
      {state.step === "complete" ? <Notice message="این مسیر قبلاً تکمیل شده است." variant="success" /> : null}
    </Screen>
  );
}

function AccountHandoffStage({
  mode,
  onBack,
  onRegister,
  onSignIn,
}: {
  readonly mode: ProductMode | null;
  readonly onBack: () => boolean;
  readonly onRegister: () => void;
  readonly onSignIn: () => void;
}) {
  return (
    <View style={styles.stage}>
      <View style={styles.heading}>
        <Text style={styles.eyebrow}>آخرین قدم</Text>
        <Text accessibilityRole="header" style={styles.title}>مسیرت آماده است</Text>
        <Text style={styles.description}>برای ذخیره امن پاسخ‌ها و ساخت برنامه شخصی، یک حساب فیتشو بساز یا وارد حساب خودت شو.</Text>
      </View>
      <Card variant="hero" style={styles.accountCard}>
        <View style={styles.accountIcon}>
          <AppIcon accessibilityLabel="امنیت" color={fiticianTokens.colors.aqua} name="shield" size={fiticianTokens.iconSize.lg} />
        </View>
        <View style={styles.accountCopy}>
          <Text style={styles.accountTitle}>اطلاعاتت همراه خودت می‌ماند</Text>
          <Text style={styles.accountDescription}>پاسخ‌های مسیر {productModeLabel(mode)} فقط برای شخصی‌سازی تجربه تو استفاده می‌شوند.</Text>
        </View>
      </Card>
      <View style={styles.accountActions}>
        <Button label="ساخت حساب جدید" onPress={onRegister} />
        <Button label="ورود به حساب" onPress={onSignIn} variant="secondary" />
        <Button label="ویرایش پاسخ‌ها" onPress={onBack} variant="ghost" />
      </View>
    </View>
  );
}

function productModeLabel(mode: ProductMode | null): string {
  if (mode === "training") return "تمرین";
  if (mode === "nutrition") return "تغذیه";
  return "تمرین و تغذیه";
}

function onboardingProgress(state: OnboardingState): string {
  if (state.mode === null) return "شروع";
  const steps = getOnboardingSteps(state.mode);
  const index = Math.min(steps.indexOf(state.step) + 1, steps.length - 1);
  return `گام ${index} از ${steps.length - 1}`;
}

function onboardingProgressValue(state: OnboardingState): number {
  if (state.mode === null || state.step === "product_mode") return 0;
  const steps = getOnboardingSteps(state.mode);
  const index = steps.indexOf(state.step);
  if (index <= 0) return 0;
  return Math.min(1, index / Math.max(1, steps.length - 1));
}

function publicOnboardingErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message !== "") {
    if (error.message.includes("incomplete")) return "پاسخ‌ها را کامل کن و دوباره تلاش کن.";
    return error.message.includes("Request failed")
      ? "ذخیره پاسخ‌ها انجام نشد. اتصال را بررسی کن."
      : error.message;
  }
  return "ذخیره پاسخ‌ها انجام نشد. دوباره تلاش کن.";
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
  description: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  eyebrow: {
    color: fiticianTokens.colors.coral,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  heading: {
    gap: fiticianTokens.spacing[3],
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
  screen: {
    gap: fiticianTokens.spacing[5],
    paddingBottom: fiticianTokens.spacing[7],
  },
  stage: {
    gap: fiticianTokens.spacing[5],
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
