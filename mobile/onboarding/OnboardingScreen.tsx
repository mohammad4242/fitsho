import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Controller, useForm, useWatch, type Control, type FieldPath, type FieldValues } from "react-hook-form";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

import { ApiError } from "@fitician/core";
import type { NutritionProfileInput, SafetyProfileInput, StructuredExerciseInput } from "@fitician/core/nutrition";
import { getOnboardingSteps } from "@fitician/core/onboarding";
import type { NutritionBasicsDraft, OnboardingState } from "@fitician/core/onboarding";
import type { ProfileFormValues, ProfileInput, ProductMode } from "@fitician/core/profile";
import { validateStep } from "@fitician/core/profile-validation";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import {
  openUserEncryptedDatabase,
  type OpenedUserEncryptedDatabase,
} from "../data/encryptedUserDatabase";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import { useRefreshMobileProfileStatus } from "../ui/navigation/RouteGuards";
import { AppIcon, Button, Card, Notice, ProgressBar, TextField } from "../ui/components";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";
import {
  NativeOnboardingController,
  type NutritionSafetyResult,
} from "./onboardingController";
import { createOnboardingApi } from "./onboardingApi";
import { NativeOnboardingDraftStore } from "./nativeOnboardingDraftStore";
import { PUBLIC_ONBOARDING_SOURCE } from "../auth/authRoute";
import { hydratePublicOnboardingState } from "./publicOnboardingHandoff";
import { SecurePublicOnboardingDraftStore } from "./publicOnboardingDraftStore";
import {
  emptyProfileFormValues,
  profileFormValuesForSharedProfile,
  profileFormValuesForTrainingProfile,
  profileInputForOnboarding,
  sharedProfileInputForFormValues,
  type OnboardingFormValidationError,
} from "./onboardingForms";
import {
  getOnboardingStageProgress,
  getQuestionProgress,
  nextQuestionIndex,
  previousQuestionIndex,
} from "./onboardingQuestionFlow";
import {
  emptyExerciseFormValues,
  emptyNutritionBasicsFormValues,
  emptyNutritionPreferencesFormValues,
  emptySafetyFormValues,
  exerciseInputFromForm,
  normalizeOnboardingDigits,
  nutritionBasicsFromForm,
  nutritionInputFromForms,
  profileValidationMessage,
  safetyInputFromForm,
  type ExerciseFormValues,
  type NutritionBasicsFormValues,
  type NutritionPreferencesFormValues,
  type SafetyFormValues,
} from "./onboardingModel";

type AsyncAction = () => Promise<void>;

const sexOptions: readonly ChoiceOption[] = [
  { label: "زن", value: "female" },
  { label: "مرد", value: "male" },
  { label: "سایر", value: "other" },
  { label: "ترجیح می‌دهم نگویم", value: "prefer_not_to_say" },
];

const fitnessGoalOptions: readonly ChoiceOption[] = [
  { label: "کاهش وزن", value: "lose_weight" },
  { label: "افزایش وزن", value: "gain_weight" },
  { label: "چربی‌سوزی", value: "fat_loss" },
  { label: "عضله‌سازی", value: "build_muscle" },
  { label: "بازترکیب بدنی", value: "body_recomposition" },
  { label: "افزایش قدرت", value: "strength" },
];

const experienceOptions: readonly ChoiceOption[] = [
  { label: "ماه اول", value: "first_month" },
  { label: "مبتدی", value: "beginner" },
  { label: "متوسط", value: "intermediate" },
  { label: "پیشرفته", value: "advanced" },
];

const trainingLocationOptions: readonly ChoiceOption[] = [
  { label: "باشگاه", value: "gym" },
  { label: "خانه", value: "home" },
];

const homeSetupOptions: readonly ChoiceOption[] = [
  { label: "فقط وزن بدن", value: "bodyweight_only" },
  { label: "دمبل دارم", value: "dumbbells_available" },
];

const equipmentOptions: readonly ChoiceOption[] = [
  { label: "وزن بدن", value: "bodyweight" },
  { label: "دمبل", value: "dumbbell" },
  { label: "هالتر", value: "barbell" },
  { label: "کابل", value: "cable" },
  { label: "دستگاه", value: "machine" },
  { label: "کش", value: "resistance_band" },
  { label: "نیمکت", value: "bench" },
  { label: "میله بارفیکس", value: "pull_up_bar" },
];

const cautionOptions: readonly ChoiceOption[] = [
  { label: "کمر", value: "lower_back" },
  { label: "زانو", value: "knee" },
  { label: "شانه", value: "shoulder" },
  { label: "گردن", value: "neck" },
  { label: "مچ دست", value: "wrist" },
  { label: "مورد دیگر", value: "other" },
];

const weekdayOptions: readonly ChoiceOption[] = [
  { label: "شنبه", value: "0" },
  { label: "یکشنبه", value: "1" },
  { label: "دوشنبه", value: "2" },
  { label: "سه‌شنبه", value: "3" },
  { label: "چهارشنبه", value: "4" },
  { label: "پنجشنبه", value: "5" },
  { label: "جمعه", value: "6" },
];

const sessionDurationOptions: readonly ChoiceOption[] = [
  { label: "۳۰ دقیقه", value: "30" },
  { label: "۴۵ دقیقه", value: "45" },
  { label: "۶۰ دقیقه", value: "60" },
  { label: "۷۵ دقیقه", value: "75" },
  { label: "۹۰ دقیقه", value: "90" },
];

const planDurationOptions: readonly ChoiceOption[] = [
  { label: "۴ هفته", value: "4" },
  { label: "۶ هفته", value: "6" },
  { label: "۸ هفته", value: "8" },
];

const intensityOptions: readonly ChoiceOption[] = [
  { label: "سبک", value: "light" },
  { label: "متوسط", value: "moderate" },
  { label: "پرتوان", value: "vigorous" },
];

const activityOptions: readonly ChoiceOption[] = [
  { label: "کم‌تحرک", value: "sedentary" },
  { label: "فعالیت سبک", value: "light" },
  { label: "فعالیت متوسط", value: "moderate" },
  { label: "خیلی فعال", value: "very_active" },
];

const dietaryOptions: readonly ChoiceOption[] = [
  { label: "همه‌چیزخوار", value: "omnivore" },
  { label: "گیاه‌خواری", value: "vegetarian" },
  { label: "وگان", value: "vegan" },
];

const budgetStyleOptions: readonly ChoiceOption[] = [
  { label: "سخت‌گیرانه", value: "strict" },
  { label: "انعطاف‌پذیر", value: "flexible" },
];

const exerciseTypeOptions: readonly ChoiceOption[] = [
  { label: "مقاومتی", value: "resistance" },
  { label: "هوازی", value: "endurance" },
  { label: "ترکیبی", value: "mixed" },
  { label: "نوع دیگر", value: "other" },
];

const conditionOptions: readonly ChoiceOption[] = [
  { label: "فشار خون", value: "controlled_hypertension" },
  { label: "چربی خون", value: "lipid_disorder" },
  { label: "دیابت نوع ۲", value: "type_2_diabetes_non_insulin" },
  { label: "گوارشی", value: "stable_gastrointestinal" },
  { label: "کلیه", value: "kidney_disease" },
  { label: "دیالیز", value: "dialysis" },
  { label: "کبد", value: "liver_disease" },
  { label: "دیابت با انسولین", value: "insulin_treated_diabetes" },
  { label: "مورد دیگر", value: "other" },
];

const productModeOptions: readonly {
  readonly description: string;
  readonly icon: "bodyAnalysis" | "nutrition" | "target" | "training";
  readonly label: string;
  readonly mode: ProductMode;
}[] = [
  { description: "برنامه شخصی بر اساس بدن، هدف و امکاناتت", icon: "training", label: "تمرین", mode: "training" },
  { description: "برنامه غذایی متناسب با هدف، بدن و بودجه", icon: "nutrition", label: "تغذیه", mode: "nutrition" },
  { description: "یک مسیر هماهنگ برای تمرین و تغذیه", icon: "target", label: "تمرین و تغذیه", mode: "both" },
];

const authenticatedModeCopy = {
  description: "مسیرت را انتخاب کن؛ فقط همان سؤال‌هایی را می‌پرسیم که برای برنامه‌ات لازم است.",
  descriptions: {
    both: "یک برنامه هماهنگ برای نتیجه بهتر",
    nutrition: "برنامه غذایی متناسب با هدف، نیاز بدن، مواد در دسترس و بودجه",
    training: "برنامه شخصی براساس بدن، هدف، سطح، زمان و تجهیزات",
  },
  eyebrow: "شروع با مربی فیتشو",
  labels: {
    both: "تمرین و تغذیه",
    nutrition: "تغذیه",
    training: "تمرین",
  },
  title: "بیشتر در چه زمینه‌ای به کمک نیاز داری؟",
} as const;

type ChoiceOption = { readonly label: string; readonly value: string };

function firstParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

export function OnboardingScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const params = useLocalSearchParams<{ source?: string }>();
  const refreshProfileStatus = useRefreshMobileProfileStatus();
  const userId = auth.user?.id ?? null;
  const api = useMemo(() => createOnboardingApi(auth.request), [auth.request]);
  const publicDraftStore = useMemo(() => new SecurePublicOnboardingDraftStore(), []);
  const publicOnboardingSource = firstParam(params.source);
  const [controller, setController] = useState<NativeOnboardingController | null>(null);
  const [state, setState] = useState<OnboardingState | null>(null);
  const [decision, setDecision] = useState<NutritionSafetyResult["decision"] | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    if (busy) return;
    setBusy(true);
    setError(null);
    void auth.logout()
      .then(() => router.replace("/"))
      .catch((logoutError) => setError(onboardingErrorMessage(logoutError)))
      .finally(() => setBusy(false));
  }, [auth.logout, busy, router]);

  useEffect(() => {
    let active = true;
    let opened: OpenedUserEncryptedDatabase | null = null;
    setLoading(true);
    setController(null);
    setState(null);
    setError(null);
    if (userId === null) {
      setLoading(false);
      return () => {
        active = false;
      };
    }

    void (async () => {
      try {
        opened = await openUserEncryptedDatabase(userId);
        if (!active) {
          await opened.database.closeAsync();
          return;
        }
        const nextController = new NativeOnboardingController(
          api,
          new NativeOnboardingDraftStore(opened),
        );
        const initializedState = await nextController.initialize();
        if (!active) return;
        setController(nextController);
        setState(initializedState);
        if (publicOnboardingSource === PUBLIC_ONBOARDING_SOURCE) {
          try {
            const publicDraft = await publicDraftStore.load();
            if (publicDraft.status === "valid") {
              const hydratedState = await hydratePublicOnboardingState(nextController, publicDraft.state);
              await publicDraftStore.clear();
              if (active) setState(hydratedState);
            }
          } catch (handoffError) {
            if (active) setError(onboardingErrorMessage(handoffError));
          }
        }
      } catch (initializationError) {
        if (active) setError(onboardingErrorMessage(initializationError));
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
      if (opened !== null) void opened.database.closeAsync();
    };
  }, [api, publicDraftStore, publicOnboardingSource, userId]);

  const run = useCallback(
    async (action: (activeController: NativeOnboardingController) => Promise<OnboardingState>) => {
      if (controller === null || busy) return;
      setBusy(true);
      setError(null);
      try {
        setState(await action(controller));
      } catch (actionError) {
        setError(onboardingErrorMessage(actionError));
      } finally {
        setBusy(false);
      }
    },
    [busy, controller],
  );

  const goBack = useCallback((): boolean => {
    if (controller === null) return false;
    if (busy) return true;
    if (state?.step === "product_mode") return false;
    setBusy(true);
    setError(null);
    void controller.goBack()
      .then(setState)
      .catch((backError) => setError(onboardingErrorMessage(backError)))
      .finally(() => setBusy(false));
    return true;
  }, [busy, controller, state?.step]);

  useAndroidBackHandler("wizard", goBack, controller !== null && state !== null);

  const selectMode = useCallback((mode: ProductMode) => {
    void run((activeController) => activeController.selectProductMode(mode));
  }, [run]);

  const saveShared = useCallback((profile: Parameters<NativeOnboardingController["saveSharedProfile"]>[0]) => {
    void run((activeController) => activeController.saveSharedProfile(profile));
  }, [run]);

  const saveTraining = useCallback((profile: ProfileInput) => {
    void run((activeController) => activeController.saveTrainingProfile(profile));
  }, [run]);

  const saveSafety = useCallback((safety: SafetyProfileInput) => {
    if (controller === null || busy) return;
    setBusy(true);
    setError(null);
    void controller.saveNutritionSafety(safety)
      .then((result) => {
        setDecision(result.decision);
        setState(result.state);
      })
      .catch((safetyError) => setError(onboardingErrorMessage(safetyError)))
      .finally(() => setBusy(false));
  }, [busy, controller]);

  const saveExercise = useCallback((exercise: StructuredExerciseInput) => {
    void run((activeController) => activeController.saveExerciseContext(exercise));
  }, [run]);

  const saveBasics = useCallback((basics: NutritionBasicsDraft) => {
    void run((activeController) => activeController.saveNutritionBasics(basics));
  }, [run]);

  const saveNutrition = useCallback((nutrition: NutritionProfileInput) => {
    void run((activeController) => activeController.saveNutritionProfile(nutrition));
  }, [run]);

  const complete = useCallback(() => {
    if (controller === null || busy) return;
    setBusy(true);
    setError(null);
    void controller.complete()
      .then((completed) => {
        setState(completed);
        return refreshProfileStatus();
      })
      .then(() => router.replace("/member"))
      .catch((completionError) => setError(onboardingErrorMessage(completionError)))
      .finally(() => setBusy(false));
  }, [busy, controller, refreshProfileStatus, router]);

  if (loading || state === null) {
    return (
      <Screen contentWidth="reading" contentContainerStyle={styles.loadingScreen}>
        <ActivityIndicator accessibilityLabel="در حال آماده‌سازی" color={fiticianTokens.colors.aqua} />
        <Text style={styles.loadingText}>در حال آماده‌سازی مسیر شخصی تو…</Text>
        {error ? <Notice message={error} variant="danger" /> : null}
      </Screen>
    );
  }

  const persistedProgress = getOnboardingStageProgress(state.mode, state.step);
  const progressSummary = persistedProgress.total === 0
    ? "شروع شخصی‌سازی"
    : `پاسخ‌های ثبت‌شده ${persistedProgress.completed} از ${persistedProgress.total}`;

  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <View style={styles.brandRow}>
        <Text style={styles.brand}>FITICIAN</Text>
        <View style={styles.topActions}>
          {state.step !== "product_mode" ? (
            <Pressable accessibilityLabel="بازگشت" accessibilityRole="button" disabled={busy} onPress={goBack}>
              <Text style={styles.backLink}>بازگشت</Text>
            </Pressable>
          ) : null}
          <Pressable accessibilityLabel="خروج" accessibilityRole="button" disabled={busy} onPress={logout}>
            <Text style={styles.backLink}>خروج</Text>
          </Pressable>
        </View>
      </View>
      <View style={styles.progressBlock}>
        <Text style={styles.progressSummary}>{progressSummary}</Text>
        <ProgressBar label="پیشرفت مسیر شخصی‌سازی" progress={onboardingProgressValue(state)} />
      </View>
      {error ? <Notice message={error} variant="danger" /> : null}
      {state.step === "product_mode" ? (
        <ModeStage busy={busy} copy={authenticatedModeCopy} onSelect={selectMode} />
      ) : null}
      {state.step === "shared_profile" ? (
        <SharedProfileStage
          busy={busy}
          initialValues={state.shared === null
            ? emptyProfileFormValues()
            : profileFormValuesForSharedProfile(state.shared)}
          onBack={goBack}
          onSubmit={saveShared}
        />
      ) : null}
      {state.step === "nutrition_safety" ? (
        <SafetyStage
          blocked={decision?.can_continue_onboarding === false}
          busy={busy}
          initialValues={safetyFormValuesForState(state.safety)}
          onBack={goBack}
          onSubmit={saveSafety}
        />
      ) : null}
      {state.step === "training_profile" ? (
        <TrainingProfileStage
          busy={busy}
          initialValues={state.training !== null
            ? profileFormValuesForTrainingProfile(state.training)
            : state.shared === null
              ? emptyProfileFormValues()
              : profileFormValuesForSharedProfile(state.shared)}
          onBack={goBack}
          onSubmit={saveTraining}
        />
      ) : null}
      {state.step === "exercise_context" ? (
        <ExerciseStage
          busy={busy}
          initialValues={exerciseFormValuesForState(state.structuredExercise)}
          onBack={goBack}
          onSubmit={saveExercise}
        />
      ) : null}
      {state.step === "nutrition_basics" ? (
        <NutritionBasicsStage
          busy={busy}
          initialValues={nutritionBasicsFormValuesForState(state.nutritionBasics)}
          onBack={goBack}
          onSubmit={saveBasics}
        />
      ) : null}
      {state.step === "nutrition_preferences" ? (
        <NutritionPreferencesStage
          basics={state.nutritionBasics}
          busy={busy}
          initialValues={nutritionPreferencesFormValuesForState(state.nutrition)}
          onBack={goBack}
          onSubmit={saveNutrition}
        />
      ) : null}
      {state.step === "review" ? (
        <ReviewStage busy={busy} mode={state.mode} onComplete={complete} state={state} />
      ) : null}
      {state.step === "complete" ? <CompletedStage onContinue={() => router.replace("/member")} /> : null}
    </Screen>
  );
}

export interface ModeStageCopy {
  readonly description?: string;
  readonly descriptions?: Partial<Record<ProductMode, string>>;
  readonly eyebrow?: string;
  readonly labels?: Partial<Record<ProductMode, string>>;
  readonly showDescriptions?: boolean;
  readonly title?: string;
}

export function ModeStage({
  busy,
  copy,
  onSelect,
}: {
  readonly busy: boolean;
  readonly copy?: ModeStageCopy;
  readonly onSelect: (mode: ProductMode) => void;
}) {
  return (
    <StageFrame
      description={copy?.description}
      eyebrow={copy?.eyebrow ?? "شروع شخصی‌سازی"}
      title={copy?.title ?? "در چه زمینه‌ای به کمک نیاز داری؟"}
    >
      <View style={styles.modeList}>
        {productModeOptions.map((option) => (
          <Pressable
            accessibilityLabel={copy?.labels?.[option.mode] ?? option.label}
            accessibilityRole="button"
            accessibilityState={{ disabled: busy }}
            disabled={busy}
            key={option.mode}
            onPress={() => onSelect(option.mode)}
            style={({ pressed }) => [styles.modeCard, option.mode === "both" && styles.recommendedCard, pressed && styles.pressed]}
          >
            <View style={styles.modeAccent} />
            <View style={[styles.modeIcon, option.mode === "both" && styles.modeIconRecommended]}>
              <AppIcon
                color={option.mode === "both" ? fiticianTokens.colors.amber : fiticianTokens.colors.aqua}
                name={option.icon}
                size={fiticianTokens.iconSize.lg}
              />
            </View>
            <View style={styles.modeContent}>
              {option.mode === "both" ? <Text style={styles.recommended}>پیشنهاد فیتشو</Text> : null}
              <Text style={styles.modeTitle}>{copy?.labels?.[option.mode] ?? option.label}</Text>
              {copy?.showDescriptions === false ? null : (
                <Text style={styles.modeDescription}>{copy?.descriptions?.[option.mode] ?? option.description}</Text>
              )}
            </View>
          </Pressable>
        ))}
      </View>
    </StageFrame>
  );
}

export function SharedProfileStage({
  busy,
  initialValues,
  onBack,
  onSubmit,
}: {
  readonly busy: boolean;
  readonly initialValues: ProfileFormValues;
  readonly onBack: () => boolean;
  readonly onSubmit: (profile: Parameters<NativeOnboardingController["saveSharedProfile"]>[0]) => void;
}) {
  const { control, getValues, setError } = useForm<ProfileFormValues>({ defaultValues: initialValues });
  const submit = () => {
    const values = getValues();
    const errors = {
      ...validateStep(values, 1, new Date()),
      ...validateStep(values, 2, new Date()),
    };
    if (Object.keys(errors).length > 0) {
      setProfileErrors(setError, errors);
      return;
    }
    onSubmit(sharedProfileInputForFormValues(values));
  };

  return (
    <StageFrame
      description="اطلاعات پایه کمک می‌کند برنامه با بدن و هدف واقعی تو هماهنگ شود."
      eyebrow="اطلاعات پایه"
      onBack={onBack}
      progress="۱ از ۲"
      title="اول خودت را معرفی کن"
    >
      <GuidedQuestionFlow busy={busy} nextLabel="ادامه" onBack={onBack} onSubmit={submit}>
        {[
          <View key="identity" style={styles.formStack}>
            <ControlledTextField control={control} label="نام نمایشی" name="display_name" />
            <ControlledTextField
              control={control}
              keyboardType="numbers-and-punctuation"
              label="تاریخ تولد"
              name="birth_date"
              placeholder="۱۳۷۵/۰۱/۰۱"
              textDirection="ltr"
              normalizeInput
            />
            <ControlledChoice control={control} label="جنسیت" name="sex" options={sexOptions} />
          </View>,
          <View key="body" style={styles.formStack}>
            <Text style={styles.questionTitle}>بدنت را بهتر بشناسیم</Text>
            <Text style={styles.helper}>اعداد را با واحد مشخص وارد کن تا برنامه دقیق‌تر تنظیم شود.</Text>
            <View style={styles.twoColumns}>
              <ControlledTextField
                control={control}
                keyboardType="decimal-pad"
                label="قد (سانتی‌متر)"
                name="height_cm"
                textDirection="ltr"
                normalizeInput
              />
              <ControlledTextField
                control={control}
                keyboardType="decimal-pad"
                label="وزن (کیلوگرم)"
                name="current_weight_kg"
                textDirection="ltr"
                normalizeInput
              />
            </View>
          </View>,
          <View key="goal" style={styles.formStack}>
            <Text style={styles.questionTitle}>هدف تو چیست؟</Text>
            <Text style={styles.sectionLabel}>اندازه‌های اختیاری</Text>
            <Text style={styles.helper}>برای دقت بیشتر، اندازه را با حداکثر دو رقم اعشار وارد کن.</Text>
            <View style={styles.twoColumns}>
              <ControlledTextField
                control={control}
                keyboardType="decimal-pad"
                label="دور شانه"
                name="shoulder_circumference_cm"
                textDirection="ltr"
                normalizeInput
              />
              <ControlledTextField
                control={control}
                keyboardType="decimal-pad"
                label="دور کمر"
                name="waist_circumference_cm"
                textDirection="ltr"
                normalizeInput
              />
            </View>
            <ControlledTextField
              control={control}
              keyboardType="decimal-pad"
              label="دور باسن"
              name="hip_circumference_cm"
              textDirection="ltr"
              normalizeInput
            />
            <ControlledChoice control={control} label="هدف اصلی" name="fitness_goal" options={fitnessGoalOptions} />
          </View>,
        ]}
      </GuidedQuestionFlow>
    </StageFrame>
  );
}

export function TrainingProfileStage({
  busy,
  initialValues,
  onBack,
  onSubmit,
}: {
  readonly busy: boolean;
  readonly initialValues: ProfileFormValues;
  readonly onBack: () => boolean;
  readonly onSubmit: (profile: ProfileInput) => void;
}) {
  const { control, getValues, setError, setValue } = useForm<ProfileFormValues>({ defaultValues: initialValues });
  const location = useWatch({ control, name: "training_location" });
  const submit = () => {
    try {
      onSubmit(profileInputForOnboarding(getValues(), new Date()));
    } catch (validationError) {
      if (isOnboardingFormValidationError(validationError)) {
        setProfileErrors(setError, validationError.errors);
      }
    }
  };

  return (
    <StageFrame
      description="جزئیات تمرین، ساختار برنامه را به زمان و امکانات واقعی تو وصل می‌کند."
      eyebrow="مسیر تمرین"
      onBack={onBack}
      progress="۲ از ۲"
      title="برنامه تمرینت را تنظیم کن"
    >
      <GuidedQuestionFlow busy={busy} nextLabel="ذخیره و ادامه" onBack={onBack} onSubmit={submit}>
        {[
          <View key="experience" style={styles.formStack}>
            <ControlledChoice control={control} label="سطح تجربه" name="experience_level" options={experienceOptions} />
            <ControlledTextField
              control={control}
              hint="اگر تمرین منظم نداشتی، خالی بگذار."
              keyboardType="number-pad"
              label="سابقه تمرین (ماه، اختیاری)"
              name="training_age_months"
              textDirection="ltr"
              normalizeInput
            />
          </View>,
          <View key="setup" style={styles.formStack}>
            <ControlledTextField
              control={control}
              keyboardType="number-pad"
              label="روزهای تمرین در هفته"
              name="training_days_per_week"
              textDirection="ltr"
              normalizeInput
            />
            <ControlledChoice control={control} label="محل تمرین" name="training_location" options={trainingLocationOptions} />
            {location === "home" ? (
              <>
                <ControlledChoice
                  control={control}
                  label="امکانات اصلی خانه"
                  name="home_training_setup"
                  options={homeSetupOptions}
                  onChangeValue={(value) => {
                    if (value === "bodyweight_only") {
                      setValue("available_equipment", ["bodyweight", "pull_up_bar"]);
                    } else if (value === "dumbbells_available") {
                      setValue("available_equipment", ["bodyweight", "dumbbell"]);
                    }
                  }}
                />
                <ControlledMultiChoice
                  control={control}
                  label="تجهیزات در دسترس"
                  name="available_equipment"
                  options={equipmentOptions}
                />
              </>
            ) : null}
          </View>,
          <View key="plan" style={styles.formStack}>
            <ControlledChoice
              control={control}
              label="زمان هر جلسه"
              name="session_duration_minutes"
              options={sessionDurationOptions}
            />
            <ControlledChoice control={control} label="شدت معمول تمرین" name="training_intensity" options={intensityOptions} />
            <ControlledMultiChoice
              allowEmpty
              control={control}
              label="موارد احتیاط"
              name="training_cautions"
              options={cautionOptions}
              emptyLabel="موردی ندارم"
            />
            <ControlledMultiChoice
              control={control}
              label="روزهای ترجیحی (اختیاری)"
              name="preferred_weekdays"
              options={weekdayOptions}
              numericValues
            />
            <ControlledChoice control={control} label="مدت برنامه" name="plan_duration_weeks" options={planDurationOptions} />
          </View>,
        ]}
      </GuidedQuestionFlow>
    </StageFrame>
  );
}

export function SafetyStage({
  blocked,
  busy,
  initialValues,
  onBack,
  onSubmit,
}: {
  readonly blocked: boolean;
  readonly busy: boolean;
  readonly initialValues: SafetyFormValues;
  readonly onBack: () => boolean;
  readonly onSubmit: (safety: SafetyProfileInput) => void;
}) {
  const { control, handleSubmit } = useForm<SafetyFormValues>({ defaultValues: initialValues });

  return (
    <StageFrame
      description="پاسخ‌های ایمنی مسیر تغذیه را مشخص می‌کنند؛ اطلاعات حساس فقط برای تصمیم‌گیری ایمن استفاده می‌شود."
      eyebrow="بررسی ایمنی"
      onBack={onBack}
      progress="۱ از ۴"
      title="قبل از تغذیه، ایمنی مهم‌تر است"
    >
      {blocked ? (
        <Notice
          message="برای حفظ ایمنی، ادامه این مسیر به بررسی پزشک فیتشو نیاز دارد. پاسخ‌های مجاز ذخیره شده‌اند."
          variant="warning"
        />
      ) : null}
      <GuidedQuestionFlow
        busy={busy}
        nextLabel={blocked ? "ارزیابی دوباره" : "ادامه"}
        onBack={onBack}
        onSubmit={() => void handleSubmit((values) => onSubmit(safetyInputFromForm(values)))()}
      >
        {[
          <View key="medical" style={styles.formStack}>
            <ControlledMultiChoice control={control} label="شرایط پزشکی" name="conditions" options={conditionOptions} csvValues />
            <ControlledTextField
              control={control}
              hint="نام داروها را با ویرگول جدا کن."
              label="داروهای مصرفی"
              name="medications"
            />
          </View>,
          <View key="history" style={styles.formStack}>
            <ToggleField control={control} label="سابقه واکنش خطرناک غذایی" name="dangerous_food_reaction_history" />
            <ToggleField control={control} label="بارداری" name="pregnant" />
            <ToggleField control={control} label="شیردهی" name="breastfeeding" />
            <ToggleField control={control} label="اختلال خوردن تشخیص داده‌شده" name="eating_disorder_diagnosed" />
            <ToggleField control={control} label="علائم فعال اختلال خوردن" name="eating_disorder_active_symptoms" />
          </View>,
          <View key="safety" style={styles.formStack}>
            <ToggleField control={control} label="علائم اورژانسی یا خطرناک" name="emergency_or_danger_symptoms" />
            <ToggleField control={control} label="تداخل پیچیده دارو و غذا" name="complex_medication_food_interaction" />
            <ControlledTextField
              control={control}
              label="محدودیت غذایی پزشک (اختیاری)"
              name="physician_dietary_restrictions"
              multiline
            />
            <ControlledTextField
              control={control}
              label="توضیح مهم دیگر (اختیاری)"
              name="other_relevant_condition"
              multiline
            />
          </View>,
        ]}
      </GuidedQuestionFlow>
    </StageFrame>
  );
}

export function ExerciseStage({
  busy,
  initialValues,
  onBack,
  onSubmit,
}: {
  readonly busy: boolean;
  readonly initialValues: ExerciseFormValues;
  readonly onBack: () => boolean;
  readonly onSubmit: (exercise: StructuredExerciseInput) => void;
}) {
  const { control, handleSubmit } = useForm<ExerciseFormValues>({ defaultValues: initialValues });
  const trains = useWatch({ control, name: "trains" });
  return (
    <StageFrame
      description="برای برآورد بهتر نیازهای تغذیه، فعالیت خارج از فیتشو را هم در نظر می‌گیریم."
      eyebrow="فعالیت روزمره"
      onBack={onBack}
      progress="۲ از ۴"
      title="خارج از فیتشو هم تمرین می‌کنی؟"
    >
      <GuidedQuestionFlow
        busy={busy}
        nextLabel="ادامه"
        onBack={onBack}
        onSubmit={() => void handleSubmit((values) => onSubmit(exerciseInputFromForm(values)))()}
      >
        {[
          <View key="activity" style={styles.formStack}>
            <ToggleField control={control} label="تمرین منظم دارم" name="trains" />
          </View>,
          ...(trains
            ? [
                <View key="details" style={styles.formStack}>
                  <ControlledChoice control={control} label="نوع فعالیت" name="exercise_type" options={exerciseTypeOptions} />
                  <ControlledTextField
                    control={control}
                    keyboardType="number-pad"
                    label="روز در هفته"
                    name="days_per_week"
                    textDirection="ltr"
                    normalizeInput
                  />
                  <ControlledTextField
                    control={control}
                    keyboardType="number-pad"
                    label="دقیقه در هر جلسه"
                    name="minutes_per_session"
                    textDirection="ltr"
                    normalizeInput
                  />
                  <ControlledChoice control={control} label="شدت فعالیت" name="intensity" options={intensityOptions} />
                </View>,
              ]
            : []),
        ]}
      </GuidedQuestionFlow>
    </StageFrame>
  );
}

export function NutritionBasicsStage({
  busy,
  initialValues,
  onBack,
  onSubmit,
}: {
  readonly busy: boolean;
  readonly initialValues: NutritionBasicsFormValues;
  readonly onBack: () => boolean;
  readonly onSubmit: (basics: NutritionBasicsDraft) => void;
}) {
  const { control, getValues, setError } = useForm<NutritionBasicsFormValues>({ defaultValues: initialValues });
  const submit = () => {
    const values = getValues();
    const budgetText = normalizeOnboardingDigits(values.monthly_food_budget_toman.replaceAll(",", "").trim());
    const budget = Number(budgetText);
    if (budgetText === "" || !Number.isFinite(budget) || !Number.isInteger(budget) || budget < 0) {
      setError("monthly_food_budget_toman", { message: "بودجه ماهانه را وارد کن." });
      return;
    }
    onSubmit(nutritionBasicsFromForm(values));
  };
  return (
    <StageFrame
      description="بودجه و عادت‌های پایه، ورودی برنامه غذایی هستند؛ محاسبات نهایی در بک‌اند انجام می‌شود."
      eyebrow="پایه تغذیه"
      onBack={onBack}
      progress="۳ از ۴"
      title="شرایط واقعی زندگی‌ات را بگو"
    >
      <GuidedQuestionFlow busy={busy} nextLabel="ادامه" onBack={onBack} onSubmit={submit}>
        {[
          <View key="budget" style={styles.formStack}>
            <ControlledChoice control={control} label="فعالیت روزانه" name="daily_activity_level" options={activityOptions} />
            <ControlledTextField
              control={control}
              hint="مبلغ را به تومان وارد کن."
              keyboardType="number-pad"
              label="بودجه ماهانه غذا"
              name="monthly_food_budget_toman"
              textDirection="ltr"
              normalizeInput
            />
            <ControlledChoice control={control} label="نوع بودجه" name="budget_style" options={budgetStyleOptions} />
          </View>,
          <View key="preferences" style={styles.formStack}>
            <ControlledTextField
              control={control}
              hint="اختیاری؛ مقدار امن پیش‌فرض در صورت خالی بودن استفاده می‌شود."
              keyboardType="decimal-pad"
              label="تغییر وزن هفتگی (کیلوگرم)"
              name="target_weight_change_kg_per_week"
              textDirection="ltr"
              normalizeInput
            />
            <ControlledChoice
              control={control}
              label="الگوی تغذیه"
              name="dietary_pattern"
              options={dietaryOptions}
            />
            <ControlledTextField control={control} label="حساسیت‌های غذایی" name="allergies" />
            <ControlledTextField control={control} label="عدم تحمل غذایی" name="intolerances" />
          </View>,
        ]}
      </GuidedQuestionFlow>
    </StageFrame>
  );
}

export function NutritionPreferencesStage({
  basics,
  busy,
  initialValues,
  onBack,
  onSubmit,
}: {
  readonly basics: NutritionBasicsDraft | null;
  readonly busy: boolean;
  readonly initialValues: NutritionPreferencesFormValues;
  readonly onBack: () => boolean;
  readonly onSubmit: (nutrition: NutritionProfileInput) => void;
}) {
  const { control, getValues, setError } = useForm<NutritionPreferencesFormValues>({ defaultValues: initialValues });
  const checkIn = useWatch({ control, name: "daily_check_in_enabled" });
  const submit = () => {
    const values = getValues();
    const meals = Number(normalizeOnboardingDigits(values.meals_per_day));
    const snacks = Number(normalizeOnboardingDigits(values.snacks_per_day));
    if (!Number.isInteger(meals) || meals < 2 || meals > 6) {
      setError("meals_per_day", { message: "تعداد وعده اصلی باید بین ۲ تا ۶ باشد." });
      return;
    }
    if (!Number.isInteger(snacks) || snacks < 0 || snacks > 3) {
      setError("snacks_per_day", { message: "تعداد میان‌وعده باید بین ۰ تا ۳ باشد." });
      return;
    }
    if (basics === null) {
      setError("meals_per_day", { message: "ابتدا اطلاعات پایه تغذیه را کامل کن." });
      return;
    }
    onSubmit(nutritionInputFromForms({
      daily_activity_level: basics.daily_activity_level,
      monthly_food_budget_toman: String(Math.floor(basics.individual_monthly_food_budget_irr / 10)),
      budget_style: basics.budget_style,
      target_weight_change_kg_per_week: basics.target_weight_change_kg_per_week == null
        ? ""
        : String(basics.target_weight_change_kg_per_week),
      weight_rate_mode: basics.weight_rate_mode ?? "safe",
      allergies: basics.allergies.map((item) => item.name).join(", "),
      intolerances: basics.intolerances.map((item) => item.name).join(", "),
      dietary_pattern: basics.dietary_pattern,
    }, values));
  };

  return (
    <StageFrame
      description="جزئیات وعده‌ها و ترجیحات، شکل برنامه را مشخص می‌کنند. پیشنهادهای قیمت فقط از داده‌های تأییدشده بک‌اند می‌آیند."
      eyebrow="ترجیحات تغذیه"
      onBack={onBack}
      progress="۴ از ۴"
      title="برنامه غذایی را برای زندگی‌ات تنظیم کن"
    >
      <GuidedQuestionFlow busy={busy} nextLabel="بازبینی برنامه" onBack={onBack} onSubmit={submit}>
        {[
          <View key="schedule" style={styles.formStack}>
            <ControlledTextField
              control={control}
              keyboardType="number-pad"
              label="وعده اصلی در روز"
              name="meals_per_day"
              textDirection="ltr"
              normalizeInput
            />
            <ControlledTextField
              control={control}
              keyboardType="number-pad"
              label="میان‌وعده در روز"
              name="snacks_per_day"
              textDirection="ltr"
              normalizeInput
            />
            <ControlledChoice
              control={control}
              label="شروع هفته برنامه"
              name="preferred_plan_start_day"
              options={[
                { label: "شنبه", value: "saturday" },
                { label: "یکشنبه", value: "sunday" },
                { label: "دوشنبه", value: "monday" },
                { label: "سه‌شنبه", value: "tuesday" },
                { label: "چهارشنبه", value: "wednesday" },
                { label: "پنجشنبه", value: "thursday" },
                { label: "جمعه", value: "friday" },
              ]}
            />
          </View>,
          <View key="preferences" style={styles.formStack}>
            <ControlledTextField control={control} label="غذاهای مورد علاقه" name="favourite_foods" />
            <ControlledTextField control={control} label="غذاهای نامطلوب" name="disliked_foods" />
            <ControlledTextField control={control} label="محدودیت فرهنگی یا مذهبی" name="religious_cultural_exclusions" />
            <ControlledTextField control={control} label="شرایط کاری یا شیفت (اختیاری)" name="work_shift_context" />
          </View>,
          <View key="check-in" style={styles.formStack}>
            <ToggleField control={control} label="یادآوری ثبت روزانه فعال باشد" name="daily_check_in_enabled" />
            {checkIn ? (
              <ControlledTextField
                control={control}
                label="زمان یادآوری"
                name="preferred_check_in_time"
                placeholder="۲۱:۰۰"
                textDirection="ltr"
                normalizeInput
              />
            ) : null}
          </View>,
        ]}
      </GuidedQuestionFlow>
    </StageFrame>
  );
}

export function ReviewStage({
  busy,
  mode,
  onComplete,
  state,
}: {
  readonly busy: boolean;
  readonly mode: ProductMode | null;
  readonly onComplete: () => void;
  readonly state: OnboardingState;
}) {
  return (
    <StageFrame
      description="پاسخ‌ها ثبت شده‌اند. بعد از تأیید، فیتشو مسیرت را بر اساس اطلاعات بک‌اند ادامه می‌دهد."
      eyebrow="یک نگاه آخر"
      title="آماده‌ای شروع کنیم؟"
    >
      <Card variant="raised">
        <View style={styles.reviewList}>
          <ReviewRow label="مسیر انتخابی" value={mode === "training" ? "تمرین" : mode === "nutrition" ? "تغذیه" : "تمرین و تغذیه"} />
          <ReviewRow label="اطلاعات پایه" value={state.shared === null ? "کامل نشده" : "ثبت شده"} />
          {mode !== "training" ? <ReviewRow label="ایمنی تغذیه" value={state.safety === null ? "کامل نشده" : "ثبت شده"} /> : null}
          {mode !== "nutrition" ? <ReviewRow label="برنامه تمرین" value={state.training === null ? "کامل نشده" : "ثبت شده"} /> : null}
          {mode !== "training" ? <ReviewRow label="ترجیحات تغذیه" value={state.nutrition === null ? "کامل نشده" : "ثبت شده"} /> : null}
        </View>
      </Card>
      <ActionBar busy={busy} onNext={onComplete} nextLabel="تأیید و شروع" />
    </StageFrame>
  );
}

export function CompletedStage({ onContinue }: { readonly onContinue: () => void }) {
  return (
    <StageFrame
      description="پروفایل تو آماده است. از خانه می‌توانی برنامه و پیشرفتت را دنبال کنی."
      eyebrow="شروع شد"
      title="مسیر شخصی تو آماده است"
    >
      <Notice message="پروفایل با موفقیت ثبت شد." variant="success" />
      <Button label="ورود به خانه" onPress={onContinue} />
    </StageFrame>
  );
}

function StageFrame({
  children,
  description,
  eyebrow,
  onBack,
  progress,
  title,
}: {
  readonly children: ReactNode;
  readonly description?: string;
  readonly eyebrow: string;
  readonly onBack?: () => boolean;
  readonly progress?: string;
  readonly title: string;
}) {
  return (
    <View style={styles.stage}>
      <View style={styles.heading}>
        <View style={styles.headingTop}>
          <Text style={styles.eyebrow}>{eyebrow}</Text>
          {progress ? <Text style={styles.progress}>{progress}</Text> : null}
        </View>
        <Text accessibilityRole="header" style={styles.title}>{title}</Text>
        {description ? <Text style={styles.description}>{description}</Text> : null}
      </View>
      {children}
      {onBack && progress === undefined ? <Button label="بازگشت" onPress={onBack} variant="ghost" /> : null}
    </View>
  );
}

function ActionBar({
  busy,
  onBack,
  onNext,
  nextLabel,
}: {
  readonly busy: boolean;
  readonly onBack?: () => boolean;
  readonly onNext: AsyncAction | (() => void);
  readonly nextLabel: string;
}) {
  return (
    <View style={styles.actions}>
      {onBack ? <Button disabled={busy} label="قبلی" onPress={onBack} variant="secondary" /> : null}
      <Button disabled={busy} label={nextLabel} loading={busy} onPress={() => void onNext()} style={styles.nextButton} />
    </View>
  );
}

function GuidedQuestionFlow({
  busy,
  children,
  nextLabel,
  onBack,
  onSubmit,
}: {
  readonly busy: boolean;
  readonly children: readonly ReactNode[];
  readonly nextLabel: string;
  readonly onBack?: () => boolean;
  readonly onSubmit: () => void;
}) {
  const [questionIndex, setQuestionIndex] = useState(0);
  const questionCount = Math.max(1, children.length);
  const progress = getQuestionProgress(questionIndex, questionCount);

  useEffect(() => {
    setQuestionIndex((current) => Math.min(current, questionCount - 1));
  }, [questionCount]);

  function goBack() {
    if (questionIndex > 0) {
      setQuestionIndex(previousQuestionIndex(questionIndex));
      return true;
    }
    return onBack?.() ?? false;
  }

  function goNext() {
    if (questionIndex < questionCount - 1) {
      setQuestionIndex(nextQuestionIndex(questionIndex, questionCount));
      return;
    }
    onSubmit();
  }

  return (
    <View style={styles.questionFlow}>
      <View style={styles.questionMeta}>
        <Text style={styles.questionEyebrow}>مسیر هدایت‌شده</Text>
        <Text style={styles.questionProgress}>سؤال {progress.current} از {progress.total}</Text>
      </View>
      <ProgressBar label="پیشرفت سؤال‌ها" progress={progress.progress} />
      <Card variant="glass" style={styles.questionCard}>
        {children[questionIndex] ?? null}
      </Card>
      <ActionBar busy={busy} onBack={goBack} onNext={goNext} nextLabel={questionIndex === questionCount - 1 ? nextLabel : "ادامه"} />
    </View>
  );
}

function ReviewRow({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.reviewRow}>
      <Text style={styles.reviewValue}>{value}</Text>
      <Text style={styles.reviewLabel}>{label}</Text>
    </View>
  );
}

function ControlledTextField<TFieldValues extends FieldValues>({
  control,
  hint,
  keyboardType,
  label,
  multiline = false,
  name,
  normalizeInput = false,
  placeholder,
  textDirection = "rtl",
}: {
  readonly control: Control<TFieldValues>;
  readonly hint?: string;
  readonly keyboardType?: "decimal-pad" | "email-address" | "number-pad" | "numbers-and-punctuation" | "phone-pad";
  readonly label: string;
  readonly multiline?: boolean;
  readonly name: FieldPath<TFieldValues>;
  readonly normalizeInput?: boolean;
  readonly placeholder?: string;
  readonly textDirection?: "ltr" | "rtl";
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <TextField
          autoCapitalize="none"
          error={fieldState.error?.message}
          hint={hint}
          keyboardType={keyboardType}
          label={label}
          multiline={multiline}
          numberOfLines={multiline ? 3 : 1}
          onBlur={field.onBlur}
          onChangeText={(value) => field.onChange(normalizeInput ? normalizeOnboardingDigits(value) : value)}
          placeholder={placeholder}
          textDirection={textDirection}
          value={String(field.value ?? "")}
        />
      )}
    />
  );
}

function ControlledChoice<TFieldValues extends FieldValues>({
  control,
  label,
  name,
  onChangeValue,
  options,
}: {
  readonly control: Control<TFieldValues>;
  readonly label: string;
  readonly name: FieldPath<TFieldValues>;
  readonly onChangeValue?: (value: string) => void;
  readonly options: readonly ChoiceOption[];
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <ChoiceButtons
          error={fieldState.error?.message}
          label={label}
          onChange={(value) => {
            field.onChange(value);
            onChangeValue?.(value);
          }}
          options={options}
          value={String(field.value ?? "")}
        />
      )}
    />
  );
}

function ControlledMultiChoice<TFieldValues extends FieldValues>({
  allowEmpty = false,
  control,
  csvValues = false,
  emptyLabel,
  label,
  name,
  numericValues = false,
  options,
}: {
  readonly allowEmpty?: boolean;
  readonly control: Control<TFieldValues>;
  readonly csvValues?: boolean;
  readonly emptyLabel?: string;
  readonly label: string;
  readonly name: FieldPath<TFieldValues>;
  readonly numericValues?: boolean;
  readonly options: readonly ChoiceOption[];
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => {
        const rawValue = field.value;
        const current = csvValues
          ? String(rawValue ?? "").split(",").filter(Boolean)
          : Array.isArray(rawValue) ? rawValue.map(String) : [];
        const selectedValues: string[] = current;
        const setValues = (values: string[]) => {
          if (csvValues) field.onChange(values.join(","));
          else if (numericValues) field.onChange(values.map(Number));
          else field.onChange(values);
        };
        return (
          <ChoiceButtons
            allowEmpty={allowEmpty}
            emptyLabel={emptyLabel}
            error={fieldState.error?.message}
            label={label}
            onChange={(value) => {
              const next = selectedValues.includes(value)
                ? selectedValues.filter((item) => item !== value)
                : [...selectedValues, value];
              setValues(next);
            }}
            onEmpty={allowEmpty ? () => setValues([]) : undefined}
            options={options}
            value={selectedValues}
          />
        );
      }}
    />
  );
}

type SafetyBooleanName =
  | "dangerous_food_reaction_history"
  | "pregnant"
  | "breastfeeding"
  | "eating_disorder_diagnosed"
  | "eating_disorder_active_symptoms"
  | "emergency_or_danger_symptoms"
  | "complex_medication_food_interaction";

function ToggleField({
  control,
  label,
  name,
}: {
  readonly control: Control<SafetyFormValues> | Control<ExerciseFormValues> | Control<NutritionPreferencesFormValues>;
  readonly label: string;
  readonly name: SafetyBooleanName | "trains" | "daily_check_in_enabled";
}) {
  return (
    <Controller
      control={control as unknown as Control<FieldValues>}
      name={name as FieldPath<FieldValues>}
      render={({ field }) => (
        <Pressable
          accessibilityRole="switch"
          accessibilityState={{ checked: Boolean(field.value) }}
          onPress={() => field.onChange(!field.value)}
          style={styles.toggleRow}
        >
          <Switch
            onValueChange={field.onChange}
            thumbColor={fiticianTokens.colors.ink}
            trackColor={{ false: fiticianTokens.colors.lineStrong, true: fiticianTokens.colors.aqua }}
            value={Boolean(field.value)}
          />
          <Text style={styles.toggleLabel}>{label}</Text>
        </Pressable>
      )}
    />
  );
}

function ChoiceButtons({
  allowEmpty = false,
  emptyLabel = "ندارم",
  error,
  label,
  onChange,
  onEmpty,
  options,
  value,
}: {
  readonly allowEmpty?: boolean;
  readonly emptyLabel?: string;
  readonly error?: string;
  readonly label: string;
  readonly onChange: (value: string) => void;
  readonly onEmpty?: () => void;
  readonly options: readonly ChoiceOption[];
  readonly value: readonly string[] | string;
}) {
  const selected = Array.isArray(value) ? value : [value];
  return (
    <View style={styles.choiceField}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.choiceGrid}>
        {options.map((option) => {
          const isSelected = selected.includes(option.value);
          return (
            <Pressable
              accessibilityRole="radio"
              accessibilityState={{ selected: isSelected }}
              key={option.value}
              onPress={() => onChange(option.value)}
              style={[styles.choice, isSelected && styles.choiceSelected]}
            >
              <Text style={[styles.choiceText, isSelected && styles.choiceTextSelected]}>{option.label}</Text>
            </Pressable>
          );
        })}
        {allowEmpty && onEmpty ? (
          <Pressable
            accessibilityRole="radio"
            accessibilityState={{ selected: selected.length === 0 }}
            onPress={onEmpty}
            style={[styles.choice, selected.length === 0 && styles.choiceSelected]}
          >
            <Text style={[styles.choiceText, selected.length === 0 && styles.choiceTextSelected]}>{emptyLabel}</Text>
          </Pressable>
        ) : null}
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );
}

function setProfileErrors(
  setError: (name: keyof ProfileFormValues, error: { type?: string; message?: string }) => void,
  errors: Partial<Record<keyof ProfileFormValues, string>>,
): void {
  for (const [field, code] of Object.entries(errors)) {
    if (code !== undefined) {
      setError(field as keyof ProfileFormValues, {
        message: profileValidationMessage(code),
        type: "manual",
      });
    }
  }
}

function isOnboardingFormValidationError(error: unknown): error is OnboardingFormValidationError {
  return error instanceof Error && error.name === "OnboardingFormValidationError";
}

function onboardingErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.message !== "Request failed") return error.message;
  if (error instanceof Error && error.message !== "") {
    if (error.message.includes("Structured exercise")) return "اطلاعات فعالیت را کامل کن.";
    if (error.message.includes("incomplete")) return "پاسخ‌ها را کامل کن و دوباره تلاش کن.";
  }
  return "ارتباط با سرور برقرار نشد. اتصال را بررسی کن و دوباره تلاش کن.";
}

export function safetyFormValuesForState(safety: SafetyProfileInput | null): SafetyFormValues {
  if (safety === null) return emptySafetyFormValues();
  return {
    conditions: safety.conditions.map((condition) => condition.code).join(","),
    medications: safety.medications.map((medication) => medication.name).join(", "),
    dangerous_food_reaction_history: safety.dangerous_food_reaction_history,
    pregnant: safety.pregnant,
    breastfeeding: safety.breastfeeding,
    eating_disorder_diagnosed: safety.eating_disorder_diagnosed,
    eating_disorder_active_symptoms: safety.eating_disorder_active_symptoms,
    emergency_or_danger_symptoms: safety.emergency_or_danger_symptoms,
    complex_medication_food_interaction: safety.complex_medication_food_interaction,
    physician_dietary_restrictions: safety.physician_dietary_restrictions ?? "",
    other_relevant_condition: safety.other_relevant_condition ?? "",
  };
}

function onboardingProgressValue(state: OnboardingState): number {
  if (state.mode !== null && !getOnboardingSteps(state.mode).includes(state.step)) return 0;
  return getOnboardingStageProgress(state.mode, state.step).progress;
}

export function exerciseFormValuesForState(exercise: StructuredExerciseInput | null): ExerciseFormValues {
  if (exercise === null || exercise.trains === false) return emptyExerciseFormValues();
  return {
    trains: true,
    exercise_type: exercise.exercise_type,
    days_per_week: String(exercise.days_per_week),
    minutes_per_session: String(exercise.minutes_per_session),
    intensity: exercise.intensity,
  };
}

export function nutritionBasicsFormValuesForState(basics: NutritionBasicsDraft | null): NutritionBasicsFormValues {
  if (basics === null) return emptyNutritionBasicsFormValues();
  return {
    daily_activity_level: basics.daily_activity_level,
    monthly_food_budget_toman: String(Math.floor(basics.individual_monthly_food_budget_irr / 10)),
    budget_style: basics.budget_style,
    target_weight_change_kg_per_week: basics.target_weight_change_kg_per_week == null
      ? ""
      : String(basics.target_weight_change_kg_per_week),
    weight_rate_mode: basics.weight_rate_mode ?? "safe",
    allergies: basics.allergies.map((item) => item.name).join(", "),
    intolerances: basics.intolerances.map((item) => item.name).join(", "),
    dietary_pattern: basics.dietary_pattern,
  };
}

export function nutritionPreferencesFormValuesForState(
  nutrition: NutritionProfileInput | null,
): NutritionPreferencesFormValues {
  if (nutrition === null) return emptyNutritionPreferencesFormValues();
  return {
    meals_per_day: String(nutrition.meals_per_day),
    snacks_per_day: String(nutrition.snacks_per_day),
    preferred_plan_start_day: nutrition.preferred_plan_start_day,
    favourite_foods: nutrition.favourite_foods.join(", "),
    disliked_foods: nutrition.disliked_foods.join(", "),
    religious_cultural_exclusions: nutrition.religious_cultural_exclusions.join(", "),
    work_shift_context: nutrition.work_shift_context ?? "",
    daily_check_in_enabled: nutrition.daily_check_in_enabled,
    preferred_check_in_time: nutrition.preferred_check_in_time?.slice(0, 5) ?? "21:00",
  };
}

const styles = StyleSheet.create({
  actions: {
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "flex-start",
  },
  backLink: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    padding: fiticianTokens.spacing[2],
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
  choice: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flexGrow: 1,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[3],
  },
  choiceField: {
    gap: fiticianTokens.spacing[2],
  },
  choiceGrid: {
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  choiceSelected: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.aqua,
  },
  choiceText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "center",
    writingDirection: "rtl",
  },
  choiceTextSelected: {
    color: fiticianTokens.colors.aqua,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  description: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  error: {
    color: fiticianTokens.colors.danger,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
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
  fieldLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  formStack: {
    gap: fiticianTokens.spacing[4],
  },
  heading: {
    gap: fiticianTokens.spacing[3],
  },
  headingTop: {
    alignItems: "center",
    flexDirection: "row-reverse",
    justifyContent: "space-between",
  },
  helper: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  loadingScreen: {
    alignItems: "center",
    gap: fiticianTokens.spacing[4],
    justifyContent: "center",
  },
  loadingText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    textAlign: "center",
    writingDirection: "rtl",
  },
  modeAccent: {
    backgroundColor: fiticianTokens.colors.coral,
    borderRadius: fiticianTokens.radii.pill,
    height: 56,
    width: 5,
  },
  modeCard: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.card,
    borderWidth: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[4],
    minHeight: 112,
    padding: fiticianTokens.spacing[4],
  },
  modeContent: {
    flex: 1,
    gap: fiticianTokens.spacing[2],
  },
  modeIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 52,
    justifyContent: "center",
    width: 52,
  },
  modeIconRecommended: {
    backgroundColor: fiticianTokens.colors.warningSurface,
    borderColor: fiticianTokens.colors.amber,
  },
  modeDescription: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  modeList: {
    gap: fiticianTokens.spacing[3],
  },
  modeTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    textAlign: "right",
    writingDirection: "rtl",
  },
  nextButton: {
    flex: 1,
  },
  pressed: {
    opacity: 0.86,
    transform: [{ scale: fiticianTokens.motion.pressedScale }],
  },
  progress: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    writingDirection: "rtl",
  },
  progressBlock: {
    gap: fiticianTokens.spacing[2],
  },
  progressSummary: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  questionCard: {
    minHeight: 220,
  },
  questionEyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  questionFlow: {
    gap: fiticianTokens.spacing[3],
  },
  questionMeta: {
    alignItems: "center",
    flexDirection: "row-reverse",
    justifyContent: "space-between",
  },
  questionProgress: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    writingDirection: "rtl",
  },
  questionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 30,
    textAlign: "right",
    writingDirection: "rtl",
  },
  recommended: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  recommendedCard: {
    borderColor: fiticianTokens.colors.lineStrong,
  },
  reviewLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  reviewList: {
    gap: fiticianTokens.spacing[4],
  },
  reviewRow: {
    alignItems: "center",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row-reverse",
    justifyContent: "space-between",
    paddingBottom: fiticianTokens.spacing[3],
  },
  reviewValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  screen: {
    gap: fiticianTokens.spacing[5],
    paddingBottom: fiticianTokens.spacing[7],
  },
  sectionLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  stage: {
    gap: fiticianTokens.spacing[5],
    width: "100%",
  },
  topActions: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 42,
    textAlign: "right",
    writingDirection: "rtl",
  },
  toggleLabel: {
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  toggleRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
  },
  twoColumns: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
});
