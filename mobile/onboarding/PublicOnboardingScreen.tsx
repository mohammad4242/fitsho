import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaFrame } from "react-native-safe-area-context";

import {
  createInitialOnboardingState,
  transitionOnboardingState,
  type OnboardingEvent,
  type OnboardingState,
} from "@fitician/core/onboarding";
import type { ProductMode, ProfileFormValues } from "@fitician/core/profile";
import { validateStep } from "@fitician/core/profile-validation";

import { onboardingRoute, PUBLIC_ONBOARDING_SOURCE } from "../auth/authRoute";
import { AppIcon, Notice, StateSkeleton } from "../ui/components";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import { Screen } from "../ui/layout";
import { mobileRequestErrorMessage } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import {
  emptyProfileFormValues,
  profileFormValuesForSharedProfile,
  profileFormValuesForTrainingProfile,
  profileInputForOnboarding,
  sharedProfileInputForFormValues,
} from "./onboardingForms";
import { SecurePublicOnboardingDraftStore } from "./publicOnboardingDraftStore";
import { GuidedSharedProfileQuestions } from "./public/GuidedSharedProfileQuestions";
import { GuidedTrainingQuestions } from "./public/GuidedTrainingQuestions";
import { PublicAccountStep } from "./public/PublicAccountStep";
import {
  PublicNutritionOnboardingFlow,
  type PublicNutritionAnswers,
} from "./public/PublicNutritionOnboardingFlow";

const copy = {
  header: "اطلاعاتت تا زمان ساخت حساب فقط در همین تب نگه‌داری می‌شود.",
  mode: {
    both: "تمرین و تغذیه",
    eyebrow: "شروع با مربی فیتشو",
    nutrition: "برنامه تغذیه",
    recommended: "پیشنهاد فیتشو",
    title: "تو چه زمینه‌ای به کمک نیاز داری؟",
    training: "برنامه تمرینی",
  },
} as const;

export function PublicOnboardingScreen() {
  const router = useRouter();
  const { width } = useSafeAreaFrame();
  const compactLayout = width <= 650;
  const store = useMemo(() => new SecurePublicOnboardingDraftStore(), []);
  const questionBackRef = useRef<(() => void) | null>(null);
  const [state, setState] = useState<OnboardingState | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sharedValues, setSharedValues] = useState(emptyProfileFormValues);
  const [trainingValues, setTrainingValues] = useState(emptyProfileFormValues);

  useEffect(() => {
    let active = true;
    void store.load()
      .then((result) => {
        if (!active) return;
        setState(result.status === "valid" ? result.state : createInitialOnboardingState());
      })
      .catch(() => {
        if (!active) return;
        setError("ذخیره مسیر شخصی‌سازی در دسترس نیست. دوباره تلاش کن.");
        setState(createInitialOnboardingState());
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [store]);

  useEffect(() => {
    if (state?.step === "shared_profile") {
      setSharedValues(state.shared === null ? emptyProfileFormValues() : profileFormValuesForSharedProfile(state.shared));
    }
    if (state?.step === "training_profile") {
      setTrainingValues(state.training === null
        ? state.shared === null ? emptyProfileFormValues() : profileFormValuesForSharedProfile(state.shared)
        : profileFormValuesForTrainingProfile(state.training));
    }
  }, [state]);

  const registerQuestionBack = useCallback((handler: () => void) => {
    questionBackRef.current = handler;
    return () => {
      if (questionBackRef.current === handler) questionBackRef.current = null;
    };
  }, []);

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

  const handleAndroidBack = useCallback((): boolean => {
    if (questionBackRef.current !== null) {
      questionBackRef.current();
      return true;
    }
    return goBack();
  }, [goBack]);

  useAndroidBackHandler("wizard", handleAndroidBack, state !== null && !loading);

  const saveShared = useCallback((values: ProfileFormValues) => {
    const errors = {
      ...validateStep(values, 1, new Date()),
      ...validateStep(values, 2, new Date()),
    };
    if (Object.keys(errors).length > 0) {
      setError("پاسخ‌های شخصی و بدنی را بررسی کن.");
      return;
    }
    run({ profile: sharedProfileInputForFormValues(values), type: "save_shared_profile" });
  }, [run]);

  const saveTraining = useCallback((values: ProfileFormValues) => {
    try {
      run({ profile: profileInputForOnboarding(values, new Date()), type: "save_training_profile" });
    } catch {
      setError("پاسخ‌های تمرینی را کامل کن و دوباره تلاش کن.");
    }
  }, [run]);

  const saveNutrition = useCallback((answers: PublicNutritionAnswers) => {
    if (state === null || state.mode === null || (state.mode !== "nutrition" && state.mode !== "both") || busy) return;
    setBusy(true);
    setError(null);
    void (async () => {
      let next = transitionOnboardingState(state, { safety: answers.safety, type: "save_nutrition_safety" });
      if (state.mode === "both") {
        if (answers.training === undefined) throw new Error("Public onboarding draft is incomplete");
        next = transitionOnboardingState(next, { profile: answers.training, type: "save_training_profile" });
      } else {
        if (answers.structuredExercise === undefined) throw new Error("Public onboarding draft is incomplete");
        next = transitionOnboardingState(next, { exercise: answers.structuredExercise, type: "save_exercise_context" });
      }
      next = transitionOnboardingState(next, { basics: answers.nutritionBasics, type: "save_nutrition_basics" });
      await store.save(next);
      setState(next);
    })()
      .catch((nutritionError: unknown) => setError(publicOnboardingErrorMessage(nutritionError)))
      .finally(() => setBusy(false));
  }, [busy, state, store]);

  const editAnswers = useCallback(() => {
    if (state === null || busy || state.step === "shared_profile") return;
    setBusy(true);
    setError(null);
    void (async () => {
      let next = state;
      while (next.step !== "shared_profile") {
        next = transitionOnboardingState(next, { type: "back" });
      }
      await store.save(next);
      setState(next);
    })()
      .catch((editError: unknown) => setError(publicOnboardingErrorMessage(editError)))
      .finally(() => setBusy(false));
  }, [busy, state, store]);

  if (loading || state === null) {
    return (
      <Screen contentWidth="reading" contentContainerStyle={styles.loadingScreen}>
        <StateSkeleton style={styles.loadingSkeleton} variant="hero" />
        <ActivityIndicator accessibilityLabel="در حال آماده‌سازی" color={fiticianTokens.colors.aqua} />
        <Text style={styles.loadingText}>در حال آماده‌سازی مسیر شخصی تو…</Text>
      </Screen>
    );
  }

  const accountMode = state.step === "review" || state.step === "nutrition_preferences" ? state.mode : null;
  if (accountMode !== null) {
    return (
      <Screen contentWidth="full" contentContainerStyle={styles.accountScreen} scroll={false}>
        {error ? <Notice message={error} variant="danger" /> : null}
        <PublicAccountStep
          mode={accountMode}
          onAuthenticated={() => router.replace(onboardingRoute(PUBLIC_ONBOARDING_SOURCE))}
          onEdit={editAnswers}
        />
      </Screen>
    );
  }

  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <View style={styles.header}>
        <Text style={styles.brand}>فیتشو</Text>
        {compactLayout ? null : <Text style={styles.headerNote}>{copy.header}</Text>}
      </View>
      {error ? <Notice message={error} variant="danger" /> : null}
      {state.step === "product_mode" ? (
        <ModeSelection
          busy={busy}
          compactLayout={compactLayout}
          onSelect={(mode) => run({ mode, type: "select_product_mode" })}
        />
      ) : null}
      {state.step === "shared_profile" ? (
        <GuidedSharedProfileQuestions
          onBack={goBack}
          onChange={(field, value) => setSharedValues((current) => ({ ...current, [field]: value }))}
          onComplete={saveShared}
          onRegisterBack={registerQuestionBack}
          values={sharedValues}
        />
      ) : null}
      {state.step === "training_profile" && state.mode === "training" ? (
        <GuidedTrainingQuestions
          onBack={goBack}
          onChange={(field, value) => setTrainingValues((current) => ({
            ...current,
            [field]: value,
            ...(field === "training_location" && value === "gym" ? { home_training_setup: "" } : {}),
          }))}
          onComplete={saveTraining}
          onRegisterBack={registerQuestionBack}
          values={trainingValues}
        />
      ) : null}
      {state.step === "nutrition_safety" && (state.mode === "nutrition" || state.mode === "both") ? (
        <PublicNutritionOnboardingFlow
          mode={state.mode}
          onBack={goBack}
          onComplete={saveNutrition}
          onRegisterBack={registerQuestionBack}
          state={state}
        />
      ) : null}
      {(state.step === "review" || state.step === "nutrition_preferences") && state.mode !== null ? (
        <PublicAccountStep
          mode={state.mode}
          onAuthenticated={() => router.replace(onboardingRoute(PUBLIC_ONBOARDING_SOURCE))}
          onEdit={editAnswers}
        />
      ) : null}
      {state.step === "complete" ? <Notice message="این مسیر قبلاً تکمیل شده است." variant="success" /> : null}
    </Screen>
  );
}

function ModeSelection({
  busy,
  compactLayout,
  onSelect,
}: {
  readonly busy: boolean;
  readonly compactLayout: boolean;
  readonly onSelect: (mode: ProductMode) => void;
}) {
  const modes = [
    ["training", copy.mode.training, "training"],
    ["nutrition", copy.mode.nutrition, "nutrition"],
    ["both", copy.mode.both, "target"],
  ] as const;
  return (
    <View style={styles.modeSelection} testID="public-mode-selection">
      <Text style={styles.eyebrow}>{copy.mode.eyebrow}</Text>
      <Text accessibilityRole="header" style={styles.modeTitle}>{copy.mode.title}</Text>
      <View style={styles.modeCards}>
        {modes.map(([mode, label, icon]) => (
          <Pressable
            accessibilityLabel={label}
            accessibilityRole="button"
            disabled={busy}
            key={mode}
            onPress={() => onSelect(mode)}
            style={[
              styles.modeCard,
              compactLayout && styles.modeCardCompact,
              mode === "both" && styles.modeCardRecommended,
            ]}
          >
            <View
              style={[
                styles.modeIcon,
                compactLayout && styles.modeIconCompact,
                mode === "both" && styles.modeIconRecommended,
              ]}
            >
              <AppIcon color={mode === "both" ? fiticianTokens.colors.canvas : fiticianTokens.colors.aqua} name={icon} size={24} />
            </View>
            <View style={styles.modeCopy}>
              <Text style={styles.modeLabel}>{label}</Text>
              {mode === "both" ? <Text style={styles.modeBadge}>{copy.mode.recommended}</Text> : null}
            </View>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function publicOnboardingErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.includes("incomplete")) {
    return "پاسخ‌ها را کامل کن و دوباره تلاش کن.";
  }
  return mobileRequestErrorMessage(error, "ذخیره پاسخ‌ها انجام نشد. دوباره تلاش کن.");
}

const styles = StyleSheet.create({
  brand: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  header: {
    alignItems: "center",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    minHeight: 80,
    paddingVertical: fiticianTokens.spacing[3],
    width: "100%",
  },
  headerNote: {
    color: fiticianTokens.colors.muted,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "auto",
    writingDirection: "rtl",
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
  modeBadge: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    color: fiticianTokens.colors.canvas,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    overflow: "hidden",
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: 3,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  modeCard: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    minHeight: 116,
    paddingHorizontal: fiticianTokens.spacing[4],
    paddingVertical: fiticianTokens.spacing[3],
    width: "100%",
  },
  modeCardCompact: {
    minHeight: 100,
  },
  modeCardRecommended: {
    backgroundColor: fiticianTokens.colors.aquaAtmosphere,
    borderColor: fiticianTokens.colors.aqua,
  },
  modeCards: {
    gap: fiticianTokens.spacing[3],
    width: "100%",
  },
  modeCopy: {
    alignItems: "flex-start",
    flex: 1,
    gap: fiticianTokens.spacing[2],
  },
  modeIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 60,
    justifyContent: "center",
    width: 60,
  },
  modeIconCompact: {
    height: 52,
    width: 52,
  },
  modeIconRecommended: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  modeLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  modeSelection: {
    alignSelf: "center",
    gap: fiticianTokens.spacing[4],
    maxWidth: 520,
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[6],
    width: "100%",
  },
  modeTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: 34,
    lineHeight: 45,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  screen: {
    gap: fiticianTokens.spacing[4],
    paddingBottom: fiticianTokens.spacing[7],
  },
  accountScreen: {
    backgroundColor: fiticianTokens.colors.canvas,
    paddingHorizontal: 0,
    paddingVertical: 0,
  },
});
