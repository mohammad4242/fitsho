import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, View } from "react-native";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { nutritionKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import {
  emptySafetyFormValues,
  safetyInputFromForm,
  type SafetyFormValues,
} from "../onboarding/onboardingModel";
import { AppIcon, Button, Card, Notice, PageHeading, Skeleton, TextField } from "../ui/components";
import { Screen } from "../ui/layout";
import { formatPersianNumber } from "../ui/locale";
import { getMobileViewState, mobileRequestErrorMessage, type MobileViewState } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import {
  canGenerateNutritionEstimate,
  formatNutritionNumber,
  nutritionSafetyPresentation,
  nutritionTargetRows,
  type NutritionTargetRow,
} from "./nutritionModel";
import {
  createNutritionApi,
  type NutritionEstimate,
  type NutritionProfile,
  type NutritionApi,
  type PhysicianReviewRequirement,
  type SafetyDecision,
  type SafetyEvaluation,
  type StructuredExercise,
} from "./nutritionApi";
import { NutritionPlanSection } from "./NutritionPlanSection";
import { NutritionSummaryCard } from "./NutritionSummaryCard";
import { NutritionTodayMeals } from "./NutritionTodayMeals";
import { NutritionDoctorSupervision } from "./NutritionDoctorSupervision";
import { NutritionScienceDetails } from "./NutritionScienceDetails";
import { NutritionWeightRateCard } from "./NutritionWeightRateCard";
import {
  createNutritionPlanApi,
  type WeeklyPlan,
  type WeeklyPlanGeneration,
} from "./nutritionPlanApi";

type ChoiceOption = { readonly label: string; readonly value: string };

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

const activityLabels: Readonly<Record<string, string>> = {
  light: "فعالیت سبک",
  moderate: "فعالیت متوسط",
  sedentary: "کم‌تحرک",
  very_active: "خیلی فعال",
};

const dietaryLabels: Readonly<Record<string, string>> = {
  omnivore: "همه‌چیزخوار",
  vegan: "وگان",
  vegetarian: "گیاه‌خواری",
};

const exerciseSourceLabels: Readonly<Record<string, string>> = {
  active_fitsho_plan: "برنامه تمرینی فعال",
  training_profile: "پروفایل تمرینی",
  user_reported: "گزارش کاربر",
};

export function NutritionFoundationScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const connectivityStatus = useConnectivityStatus();
  const api = useMemo(() => createNutritionApi(auth.request), [auth.request]);
  const planApi = useMemo(
    () => createNutritionPlanApi(auth.request, auth.download),
    [auth.download, auth.request],
  );
  const safetyQuery = useQuery({
    queryFn: api.getSafety,
    queryKey: nutritionKeys.safety(),
  });
  const estimateQuery = useQuery({
    queryFn: api.getCurrentEstimate,
    queryKey: nutritionKeys.estimate(),
  });
  const latestPlanQuery = useQuery({
    queryFn: planApi.getLatest,
    queryKey: nutritionKeys.plan("latest"),
  });
  const latestBundleQuery = useQuery({
    queryFn: planApi.getLatestBundle,
    queryKey: nutritionKeys.latestBundle(),
  });
  const estimateGeneration = useMutation({
    mutationFn: api.generateEstimate,
    onSuccess: (result) => queryClient.setQueryData(nutritionKeys.estimate(), result),
  });
  const safetyState = getMobileViewState(safetyQuery, { connectivityStatus });
  const estimateState = getMobileViewState(estimateQuery, { connectivityStatus });
  const latestPlanState = getMobileViewState(latestPlanQuery, { connectivityStatus });
  const latestBundleState = getMobileViewState(latestBundleQuery, { connectivityStatus });
  const safety = viewData(safetyState);
  const estimate = viewData(estimateState);
  const latestPlan = viewData(latestPlanState) ?? null;
  const latestBundle = viewData(latestBundleState) ?? null;
  const planDataReady = !latestPlanQuery.isPending && !latestBundleQuery.isPending;
  const plan = planDataReady ? resolveNutritionMainPlan(latestPlan, latestBundle) : null;
  const estimateAvailable = estimate !== undefined && estimate !== null;

  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <PageHeading
        compact
        eyebrow="امروز"
        title="تغذیه"
      />

      <NutritionDailyTools
        onOpenTracking={() => router.push("/member/nutrition-tracking")}
        onOpenCatalogue={() => router.push("/member/food-catalogue")}
      />

      <NutritionEstimateState
        canCalculate={canGenerateNutritionEstimate(safety ?? null) && connectivityStatus !== "offline"}
        calculating={estimateGeneration.isPending}
        error={estimateGeneration.error ? nutritionErrorMessage(estimateGeneration.error) : null}
        hasEstimate={estimateAvailable}
        onCalculate={() => estimateGeneration.mutate()}
        onRetry={() => void estimateQuery.refetch()}
        state={estimateState}
      />

      <NutritionSummaryCard
        connectivityStatus={connectivityStatus}
        estimate={estimate}
        onRefresh={() => void estimateQuery.refetch()}
      />

      {estimateAvailable ? (
        <NutritionWeightRateCard estimate={estimate} onRefresh={() => void estimateQuery.refetch()} />
      ) : null}
      {estimateAvailable && planDataReady ? <NutritionTodayMeals plan={plan} /> : null}
      {estimateAvailable ? <NutritionScienceDetails estimate={estimate} /> : null}
      {estimateAvailable && planDataReady ? <NutritionDoctorSupervision plan={plan} /> : null}

      {estimateAvailable ? <NutritionPlanSection safety={safety ?? null} /> : null}
    </Screen>
  );
}

function resolveNutritionMainPlan(
  latestPlan: WeeklyPlan | null,
  latestBundle: WeeklyPlanGeneration | null,
): WeeklyPlan | null {
  if (
    latestBundle?.bundle_id
    && latestBundle.comparison?.show_ideal_plan
    && latestBundle.ideal_plan
    && latestBundle.budget_plan
  ) {
    const selectedRole = latestBundle.selected_plan_role === "ideal"
      || latestBundle.selected_plan_role === "ideal_reference"
      ? "ideal"
      : latestBundle.selected_plan_role === "budget"
        ? "budget"
        : latestBundle.selected_plan_id
          ? latestBundle.selected_plan_id === latestBundle.ideal_plan.id ? "ideal" : "budget"
          : null;
    return selectedRole === "ideal" ? latestBundle.ideal_plan : latestBundle.budget_plan;
  }
  return latestPlan;
}

function NutritionDailyTools({
  onOpenCatalogue,
  onOpenTracking,
}: {
  readonly onOpenCatalogue: () => void;
  readonly onOpenTracking: () => void;
}) {
  return (
    <View style={styles.dailyTools}>
      <Card
        accessibilityLabel="ثبت تغذیه"
        onPress={onOpenTracking}
        style={styles.dailyToolCard}
        variant="hero"
      >
        <View style={styles.dailyToolCopy}>
          <AppIcon color={fiticianTokens.colors.aqua} name="nutrition" size={fiticianTokens.iconSize.lg} />
          <Text style={styles.dailyToolTitle}>ثبت تغذیه</Text>
          <Text style={styles.dailyToolSubtitle}>دستی یا با عکس</Text>
        </View>
        <AppIcon color={fiticianTokens.colors.aqua} name="arrowLeft" size={fiticianTokens.iconSize.md} />
      </Card>
      <Card
        accessibilityLabel="کاتالوگ"
        onPress={onOpenCatalogue}
        style={styles.dailyToolCard}
        variant="interactive"
      >
        <View style={styles.dailyToolCopy}>
          <AppIcon color={fiticianTokens.colors.amber} name="foodLog" size={fiticianTokens.iconSize.lg} />
          <Text style={styles.dailyToolTitle}>کاتالوگ</Text>
          <Text style={styles.dailyToolSubtitle}>مرجع مواد غذایی</Text>
        </View>
        <AppIcon color={fiticianTokens.colors.amber} name="arrowLeft" size={fiticianTokens.iconSize.md} />
      </Card>
    </View>
  );
}

function NutritionEstimateState({
  calculating,
  canCalculate,
  error,
  hasEstimate,
  onCalculate,
  onRetry,
  state,
}: {
  readonly calculating: boolean;
  readonly canCalculate: boolean;
  readonly error: string | null;
  readonly hasEstimate: boolean;
  readonly onCalculate: () => void;
  readonly onRetry: () => void;
  readonly state: MobileViewState<NutritionEstimate | null>;
}) {
  if (hasEstimate || state.status === "loading") return null;
  if (state.status === "offline") {
    return <Notice message="برای دریافت برآورد تغذیه به اینترنت وصل شو." variant="offline" />;
  }
  if (state.status === "error") {
    return <Notice actionLabel="تلاش دوباره" message="برآورد تغذیه دریافت نشد." onAction={onRetry} variant="danger" />;
  }
  if (state.status !== "empty") return null;

  return (
    <Card style={styles.estimateStateCard}>
      <Text style={styles.sectionTitle}>هنوز برآوردی ثبت نشده</Text>
      <Text style={styles.bodyText}>اطلاعات پروفایل فعلی را به یک برآورد شفاف تبدیل کن.</Text>
      <Button
        disabled={!canCalculate}
        label="محاسبه هدف‌ها"
        loading={calculating}
        onPress={onCalculate}
      />
      {!canCalculate ? <Notice message="ابتدا ارزیابی ایمنی تغذیه را کامل کن." variant="warning" /> : null}
      {error !== null ? <Notice message={error} variant="danger" /> : null}
    </Card>
  );
}

export function NutritionProfileSection({
  onEdit,
  onRetry,
  state,
}: {
  readonly onEdit: () => void;
  readonly onRetry: () => void;
  readonly state: MobileViewState<NutritionProfile | null>;
}) {
  const profile = viewData(state);
  if (state.status === "loading") return <Skeleton height={190} />;
  if (state.status === "error" && profile === undefined) {
    return <Notice actionLabel="تلاش دوباره" message="پروفایل تغذیه دریافت نشد." onAction={onRetry} variant="danger" />;
  }
  if (state.status === "offline" && profile === undefined) {
    return <Notice message="برای دریافت پروفایل تغذیه به اینترنت وصل شو." variant="offline" />;
  }
  if (profile === undefined || profile === null) {
    return (
      <Card style={styles.sectionCard}>
        <Text style={styles.sectionTitle}>پروفایل تغذیه</Text>
        <Notice message="پروفایل تغذیه هنوز تکمیل نشده است." variant="warning" />
        <Button label="تکمیل در پروفایل" onPress={onEdit} variant="secondary" />
      </Card>
    );
  }

  return (
    <Card style={styles.sectionCard}>
      <View style={styles.sectionHeading}>
        <Text style={styles.sectionTitle}>پروفایل تغذیه</Text>
        <Text style={styles.statusText}>{profile.onboarding_status === "completed" ? "کامل" : "در حال تکمیل"}</Text>
      </View>
      <SummaryRow label="الگوی غذایی" value={dietaryLabels[profile.dietary_pattern] ?? profile.dietary_pattern} />
      <SummaryRow label="فعالیت روزانه" value={activityLabels[profile.daily_activity_level] ?? profile.daily_activity_level} />
      <SummaryRow
        label="وعده و میان‌وعده"
        value={`${formatPersianNumber(profile.effective_main_meal_slots ?? profile.meals_per_day ?? 0, { maximumFractionDigits: 0 })} وعده · ${formatPersianNumber(profile.effective_snack_slots ?? profile.snacks_per_day ?? 0, { maximumFractionDigits: 0 })} میان‌وعده`}
      />
      <SummaryRow label="بودجه هفتگی" value={`${formatPersianNumber(Math.floor(profile.weekly_budget_irr / 10), { maximumFractionDigits: 0 })} تومان`} />
      {profile.physician_review_required ? (
        <Notice message="ادامه بعضی عملیات تغذیه به بررسی پزشک نیاز دارد." variant="warning" />
      ) : null}
      <Button label="ویرایش پروفایل تغذیه" onPress={onEdit} variant="ghost" />
    </Card>
  );
}

export function SafetySection({
  api,
  connectivityStatus,
  state,
}: {
  readonly api: NutritionApi;
  readonly connectivityStatus: ConnectivityStatus;
  readonly state: MobileViewState<SafetyDecision | null>;
}) {
  const queryClient = useQueryClient();
  const decision = viewData(state);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<SafetyFormValues>(emptySafetyFormValues());
  const [preview, setPreview] = useState<SafetyEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const evaluate = useMutation({
    mutationFn: api.evaluateSafety,
    onError: (mutationError: unknown) => setError(nutritionErrorMessage(mutationError)),
    onSuccess: (result) => {
      setPreview(result);
      setError(null);
    },
  });
  const save = useMutation({
    mutationFn: api.saveSafety,
    onError: (mutationError: unknown) => setError(nutritionErrorMessage(mutationError)),
    onSuccess: (result) => {
      queryClient.setQueryData(nutritionKeys.safety(), result);
      void queryClient.invalidateQueries({ queryKey: nutritionKeys.estimate() });
      void queryClient.invalidateQueries({ queryKey: nutritionKeys.reviewRequirement() });
      setEditing(false);
      setPreview(null);
      setError(null);
    },
  });
  const offline = connectivityStatus === "offline";

  if (state.status === "loading") return <Skeleton height={220} />;
  if (state.status === "error" && decision === undefined) {
    return <Notice message="وضعیت ایمنی دریافت نشد." variant="danger" />;
  }
  if (state.status === "offline" && decision === undefined) {
    return <Notice message="برای دریافت وضعیت ایمنی به اینترنت وصل شو." variant="offline" />;
  }

  const presentation = nutritionSafetyPresentation(decision ?? null);
  function openEditor() {
    setDraft(emptySafetyFormValues());
    setPreview(null);
    setError(null);
    setEditing(true);
  }
  function toggleCondition(value: string) {
    const current = selectedConditions(draft.conditions);
    const next = current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value];
    setDraft((currentDraft) => ({ ...currentDraft, conditions: next.join(",") }));
  }
  function evaluateDraft() {
    if (offline) {
      setError("ارزیابی ایمنی بدون اینترنت انجام نمی‌شود.");
      return;
    }
    setError(null);
    evaluate.mutate(safetyInputFromForm(draft));
  }
  function saveDraft() {
    if (preview === null) {
      setError("ابتدا ارزیابی ایمنی را انجام بده.");
      return;
    }
    if (offline) {
      setError("ثبت ارزیابی ایمنی بدون اینترنت انجام نمی‌شود.");
      return;
    }
    setError(null);
    save.mutate(safetyInputFromForm(draft));
  }

  return (
    <Card style={styles.sectionCard}>
      <View style={styles.sectionHeading}>
        <Text style={styles.sectionTitle}>ایمنی تغذیه</Text>
        <Text style={[styles.statusText, presentation.blocked && styles.statusDanger]}>{presentation.title}</Text>
      </View>
      {state.status === "offline" ? <Notice message="آخرین تصمیم ایمنی نمایش داده می‌شود." variant="offline" /> : null}
      {!editing ? (
        <>
          <Notice message={presentation.message} variant={presentation.variant} />
          <Text style={styles.bodyText}>اطلاعات حساس پاسخ‌های قبلی روی صفحه نمایش داده نمی‌شود.</Text>
          <Button label="ارزیابی دوباره ایمنی" onPress={openEditor} variant="secondary" />
        </>
      ) : (
        <SafetyEditor
          draft={draft}
          error={error}
          evaluating={evaluate.isPending}
          offline={offline}
          preview={preview}
          saving={save.isPending}
          onChange={(next) => {
            setDraft(next);
            setPreview(null);
          }}
          onEvaluate={evaluateDraft}
          onSave={saveDraft}
          onToggleCondition={toggleCondition}
        />
      )}
    </Card>
  );
}

function SafetyEditor({
  draft,
  error,
  evaluating,
  offline,
  onChange,
  onEvaluate,
  onSave,
  onToggleCondition,
  preview,
  saving,
}: {
  readonly draft: SafetyFormValues;
  readonly error: string | null;
  readonly evaluating: boolean;
  readonly offline: boolean;
  readonly onChange: (next: SafetyFormValues) => void;
  readonly onEvaluate: () => void;
  readonly onSave: () => void;
  readonly onToggleCondition: (value: string) => void;
  readonly preview: SafetyEvaluation | null;
  readonly saving: boolean;
}) {
  const booleanFields: readonly { readonly label: string; readonly name: keyof SafetyFormValues }[] = [
    { label: "سابقه واکنش خطرناک غذایی", name: "dangerous_food_reaction_history" },
    { label: "بارداری", name: "pregnant" },
    { label: "شیردهی", name: "breastfeeding" },
    { label: "اختلال خوردن تشخیص داده‌شده", name: "eating_disorder_diagnosed" },
    { label: "علائم فعال اختلال خوردن", name: "eating_disorder_active_symptoms" },
    { label: "علائم اورژانسی یا خطرناک", name: "emergency_or_danger_symptoms" },
    { label: "تداخل پیچیده دارو و غذا", name: "complex_medication_food_interaction" },
  ];

  return (
    <View style={styles.formStack}>
      <Text style={styles.bodyText}>برای تغییر تصمیم، اطلاعات را دوباره وارد و ابتدا ارزیابی کن.</Text>
      <ChoiceButtons
        disabled={evaluating || saving}
        label="شرایط پزشکی"
        options={conditionOptions}
        selected={selectedConditions(draft.conditions)}
        onSelect={onToggleCondition}
      />
      <TextField
        editable={!evaluating && !saving}
        hint="نام داروها را با ویرگول جدا کن."
        label="داروهای مصرفی"
        onChangeText={(medications) => onChange({ ...draft, medications })}
        value={draft.medications}
      />
      {booleanFields.map((field) => (
        <SafetyToggle
          key={field.name}
          label={field.label}
          disabled={evaluating || saving}
          value={Boolean(draft[field.name])}
          onChange={(value) => onChange({ ...draft, [field.name]: value })}
        />
      ))}
      <TextField
        editable={!evaluating && !saving}
        label="محدودیت غذایی پزشک"
        multiline
        onChangeText={(value) => onChange({ ...draft, physician_dietary_restrictions: value })}
        value={draft.physician_dietary_restrictions}
      />
      <TextField
        editable={!evaluating && !saving}
        label="توضیح مهم دیگر"
        multiline
        onChangeText={(value) => onChange({ ...draft, other_relevant_condition: value })}
        value={draft.other_relevant_condition}
      />
      {preview !== null ? (
        <Notice
          message={preview.message}
          title={preview.can_continue_onboarding ? "نتیجه ارزیابی" : "این نتیجه ادامه مسیر را مسدود می‌کند"}
          variant={preview.can_continue_onboarding ? "success" : "warning"}
        />
      ) : null}
      {error !== null ? <Notice message={error} variant="danger" /> : null}
      {offline ? <Notice message="برای ارزیابی یا ثبت ایمنی به اینترنت وصل شو." variant="offline" /> : null}
      <View style={styles.actionRow}>
        <Button disabled={offline} label="ارزیابی ایمنی" loading={evaluating} onPress={onEvaluate} />
        <Button disabled={offline || preview === null} label="ثبت نتیجه" loading={saving} onPress={onSave} variant="secondary" />
      </View>
    </View>
  );
}

export function StructuredExerciseSection({ state }: { readonly state: MobileViewState<StructuredExercise | null> }) {
  const exercise = viewData(state);
  if (state.status === "loading") return <Skeleton height={105} />;
  if (state.status === "error" && exercise === undefined) {
    return <Notice message="اطلاعات فعالیت برای برآورد دریافت نشد." variant="warning" />;
  }
  if (state.status === "offline" && exercise === undefined) {
    return <Notice message="برای دریافت اطلاعات فعالیت به اینترنت وصل شو." variant="offline" />;
  }
  if (exercise === undefined || exercise === null) return null;

  return (
    <Card style={styles.sectionCard}>
      <Text style={styles.sectionTitle}>فعالیت ساختاریافته</Text>
      <Text style={styles.bodyText}>منبع: {exerciseSourceLabels[exercise.source] ?? exercise.source}</Text>
      <Text style={styles.bodyText}>
        {exercise.trains
          ? `${formatPersianNumber(exercise.days_per_week ?? 0, { maximumFractionDigits: 0 })} روز در هفته · ${formatPersianNumber(exercise.minutes_per_session ?? 0, { maximumFractionDigits: 0 })} دقیقه · ${exerciseTypeLabel(exercise.exercise_type)}`
          : "در حال حاضر فعالیت ساختاریافته‌ای ثبت نشده است."}
      </Text>
    </Card>
  );
}

export function ReviewRequirementSection({ state }: { readonly state: MobileViewState<PhysicianReviewRequirement | null> }) {
  const review = viewData(state);
  if (state.status === "loading") return <Skeleton height={100} />;
  if (state.status === "error" && review === undefined) {
    return <Notice message="وضعیت بررسی پزشک دریافت نشد." variant="warning" />;
  }
  if (review === undefined || review === null || !review.required) return null;

  return (
    <Notice
      message={reviewStatusLabel(review.status)}
      title="بررسی پزشک لازم است"
      variant={review.status === "approved" ? "success" : "warning"}
    />
  );
}

export function NutritionEstimateSection({
  api,
  connectivityStatus,
  onRetry,
  profile,
  safety,
  state,
}: {
  readonly api: NutritionApi;
  readonly connectivityStatus: ConnectivityStatus;
  readonly onRetry: () => void;
  readonly profile: NutritionProfile | null;
  readonly safety: SafetyDecision | null;
  readonly state: MobileViewState<NutritionEstimate | null>;
}) {
  const queryClient = useQueryClient();
  const estimate = viewData(state);
  const [error, setError] = useState<string | null>(null);
  const generate = useMutation({
    mutationFn: api.generateEstimate,
    onError: (mutationError: unknown) => setError(nutritionErrorMessage(mutationError)),
    onSuccess: (result) => {
      queryClient.setQueryData(nutritionKeys.estimate(), result);
      setError(null);
    },
  });
  const offline = connectivityStatus === "offline";
  const canGenerate = canGenerateNutritionEstimate(safety) && !offline;

  if (state.status === "loading") return <Skeleton height={240} />;
  if (state.status === "error" && estimate === undefined) {
    return <Notice actionLabel="تلاش دوباره" message="برآورد تغذیه دریافت نشد." onAction={onRetry} variant="danger" />;
  }
  if (state.status === "offline" && estimate === undefined) {
    return <Notice message="برای دریافت برآورد تغذیه به اینترنت وصل شو." variant="offline" />;
  }
  if (estimate === undefined || estimate === null) {
    const safetyPresentation = nutritionSafetyPresentation(safety);
    return (
      <Card style={styles.sectionCard}>
        <Text style={styles.sectionTitle}>برآورد تغذیه</Text>
        <Notice message={safetyPresentation.blocked ? safetyPresentation.message : "هنوز برآوردی برای این پروفایل ساخته نشده است."} variant={safetyPresentation.blocked ? safetyPresentation.variant : "info"} />
        {profile?.physician_review_required ? <Notice message="پیش از ساخت برآورد، وضعیت بررسی پزشک را دنبال کن." variant="warning" /> : null}
        <Button
          disabled={!canGenerate}
          label="ساخت برآورد تغذیه"
          loading={generate.isPending}
          onPress={() => {
            setError(null);
            generate.mutate();
          }}
        />
        {error !== null ? <Notice message={error} variant="danger" /> : null}
      </Card>
    );
  }

  const rows = nutritionTargetRows(estimate);
  return (
    <Card style={styles.sectionCard}>
      <View style={styles.sectionHeading}>
        <Text style={styles.sectionTitle}>برآورد تغذیه</Text>
        <Text style={styles.statusText}>{estimate.status === "active" ? "فعال" : "نیازمند بررسی"}</Text>
      </View>
      {state.status === "offline" || estimate.is_stale ? (
        <Notice message="این برآورد قدیمی است و ممکن است تازه‌ترین وضعیت پروفایل نباشد." variant="offline" />
      ) : null}
      {estimate.status === "review_required" ? (
        <Notice message="این برآورد تا بررسی لازم، مبنای تصمیم نهایی برنامه غذایی نیست." variant="warning" />
      ) : null}
      <Text style={styles.bodyText}>اطمینان محاسبه: {confidenceLabel(estimate.confidence)}</Text>
      <View style={styles.targetGrid}>
        {rows.map((row) => <TargetRow key={row.code} row={row} />)}
      </View>
      {error !== null ? <Notice message={error} variant="danger" /> : null}
      <Button
        disabled={!canGenerate}
        label="محاسبه دوباره"
        loading={generate.isPending}
        onPress={() => {
          setError(null);
          generate.mutate();
        }}
        variant="secondary"
      />
      {!canGenerate && safety !== null ? <Notice message={nutritionSafetyPresentation(safety).message} variant="warning" /> : null}
    </Card>
  );
}

function TargetRow({ row }: { readonly row: NutritionTargetRow }) {
  return (
    <View style={styles.targetRow}>
      <Text style={styles.targetValue}>{targetValueLabel(row)}</Text>
      <Text style={styles.targetLabel}>{row.label}</Text>
    </View>
  );
}

function ChoiceButtons({
  disabled = false,
  label,
  onSelect,
  options,
  selected,
}: {
  readonly disabled?: boolean;
  readonly label: string;
  readonly onSelect: (value: string) => void;
  readonly options: readonly ChoiceOption[];
  readonly selected: readonly string[];
}) {
  return (
    <View style={styles.formGroup}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.choiceRow}>
        {options.map((option) => {
          const isSelected = selected.includes(option.value);
          return (
            <Pressable
              accessibilityRole="checkbox"
              accessibilityState={{ checked: isSelected }}
              disabled={disabled}
              key={option.value}
              onPress={() => onSelect(option.value)}
              style={[styles.choice, isSelected && styles.choiceSelected]}
            >
              <Text style={[styles.choiceText, isSelected && styles.choiceTextSelected]}>{option.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function SafetyToggle({
  disabled = false,
  label,
  onChange,
  value,
}: {
  readonly disabled?: boolean;
  readonly label: string;
  readonly onChange: (value: boolean) => void;
  readonly value: boolean;
}) {
  return (
    <Pressable accessibilityRole="switch" accessibilityState={{ checked: value, disabled }} disabled={disabled} onPress={() => onChange(!value)} style={styles.toggleRow}>
      <Switch
        disabled={disabled}
        onValueChange={onChange}
        thumbColor={fiticianTokens.colors.ink}
        trackColor={{ false: fiticianTokens.colors.lineStrong, true: fiticianTokens.colors.aqua }}
        value={value}
      />
      <Text style={styles.toggleLabel}>{label}</Text>
    </Pressable>
  );
}

function SummaryRow({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.summaryRow}>
      <Text style={styles.bodyText}>{value}</Text>
      <Text style={styles.summaryLabel}>{label}</Text>
    </View>
  );
}

function viewData<TData>(state: MobileViewState<TData>): TData | undefined {
  if (state.status === "loading") return undefined;
  return "data" in state ? state.data : undefined;
}

function targetValueLabel(row: NutritionTargetRow): string {
  const lower = row.minimum ?? row.preferred;
  const upper = row.preferredMaximum ?? row.maximum;
  if (lower !== null && upper !== null && lower !== upper) {
    return `${formatNutritionNumber(lower)}–${formatNutritionNumber(upper)} ${row.unit}`;
  }
  const value = row.preferred ?? row.minimum ?? row.preferredMaximum ?? row.maximum;
  return value === null ? "—" : `${formatNutritionNumber(value)} ${row.unit}`;
}

function selectedConditions(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function confidenceLabel(value: string): string {
  return value === "high" ? "بالا" : value === "medium" ? "متوسط" : "پایین";
}

function exerciseTypeLabel(value: StructuredExercise["exercise_type"]): string {
  if (value === "resistance") return "مقاومتی";
  if (value === "endurance") return "هوازی";
  if (value === "mixed") return "ترکیبی";
  return value === null ? "نامشخص" : "نوع دیگر";
}

function reviewStatusLabel(value: PhysicianReviewRequirement["status"]): string {
  if (value === "approved") return "بررسی پزشک تأیید شده است.";
  if (value === "rejected") return "درخواست بررسی پزشک رد شده است؛ ادامه مسیر را از وضعیت حساب دنبال کن.";
  if (value === "changes_requested") return "پزشک برای ادامه، اصلاحات یا اطلاعات بیشتری خواسته است.";
  if (value === "pending") return "درخواست بررسی پزشک در صف بررسی است.";
  return "درخواست بررسی پزشک هنوز ثبت نشده است.";
}

function nutritionErrorMessage(error: unknown): string {
  return mobileRequestErrorMessage(error, "عملیات تغذیه انجام نشد؛ اتصال را بررسی کن و دوباره تلاش کن.");
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

const styles = StyleSheet.create({
  actionRow: {
    gap: fiticianTokens.spacing[2],
  },
  bodyText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 24,
    textAlign: "right",
    writingDirection: "rtl",
  },
  dailyToolCard: {
    alignItems: "center",
    flex: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    minHeight: 58,
    padding: fiticianTokens.spacing[3],
  },
  dailyToolCopy: {
    alignItems: "flex-end",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  dailyTools: {
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[2],
  },
  dailyToolSubtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  dailyToolTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  estimateStateCard: {
    gap: fiticianTokens.spacing[3],
    marginBottom: fiticianTokens.spacing[1],
  },
  choice: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  choiceRow: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  choiceSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  choiceText: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  choiceTextSelected: {
    color: fiticianTokens.colors.canvas,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  fieldLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.medium,
    textAlign: "right",
    writingDirection: "rtl",
  },
  formGroup: {
    gap: fiticianTokens.spacing[2],
  },
  formStack: {
    gap: fiticianTokens.spacing[3],
  },
  sectionCard: {
    gap: fiticianTokens.spacing[3],
    marginBottom: fiticianTokens.spacing[3],
  },
  screen: {
    gap: fiticianTokens.spacing[3],
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[3],
  },
  sectionHeading: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  sectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  statusDanger: {
    color: fiticianTokens.colors.danger,
  },
  statusText: {
    color: fiticianTokens.colors.aqua,
    flexShrink: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  summaryLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  summaryRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    justifyContent: "space-between",
  },
  targetGrid: {
    gap: fiticianTokens.spacing[2],
  },
  targetLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  targetRow: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    flexDirection: "row-reverse",
    justifyContent: "space-between",
    padding: fiticianTokens.spacing[3],
  },
  targetValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "left",
    writingDirection: "ltr",
  },
  toggleLabel: {
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  toggleRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
  },
});
