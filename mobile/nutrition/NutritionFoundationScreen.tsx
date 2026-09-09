import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, View } from "react-native";

import { ApiError, irrToToman } from "@fitician/core";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { nutritionKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import {
  emptySafetyFormValues,
  safetyInputFromForm,
  type SafetyFormValues,
} from "../onboarding/onboardingModel";
import { Button, Card, Notice, Skeleton, TextField } from "../ui/components";
import { Screen } from "../ui/layout";
import { getMobileViewState, type MobileViewState } from "../ui/requestState";
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
import { NutritionCatalogueSection } from "./NutritionCatalogueSection";
import { NutritionTrackingSection } from "./NutritionTrackingSection";
import { NutritionAdherenceSection } from "./NutritionAdherenceSection";
import { NutritionClinicalSection } from "./NutritionClinicalSection";
import { NutritionSummaryCard } from "./NutritionSummaryCard";

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
  const connectivityStatus = useConnectivityStatus();
  const api = useMemo(() => createNutritionApi(auth.request), [auth.request]);
  const profileQuery = useQuery({
    queryFn: api.getNutritionProfile,
    queryKey: nutritionKeys.profile(),
  });
  const safetyQuery = useQuery({
    queryFn: api.getSafety,
    queryKey: nutritionKeys.safety(),
  });
  const estimateQuery = useQuery({
    queryFn: api.getCurrentEstimate,
    queryKey: nutritionKeys.estimate(),
  });
  const reviewQuery = useQuery({
    queryFn: api.getReviewRequirement,
    queryKey: nutritionKeys.reviewRequirement(),
  });
  const exerciseQuery = useQuery({
    queryFn: api.getStructuredExercise,
    queryKey: nutritionKeys.structuredExercise(),
  });
  const profileState = getMobileViewState(profileQuery, { connectivityStatus });
  const safetyState = getMobileViewState(safetyQuery, { connectivityStatus });
  const estimateState = getMobileViewState(estimateQuery, { connectivityStatus });
  const reviewState = getMobileViewState(reviewQuery, { connectivityStatus });
  const exerciseState = getMobileViewState(exerciseQuery, { connectivityStatus });
  const profile = viewData(profileState);
  const safety = viewData(safetyState);
  const estimate = viewData(estimateState);

  return (
    <Screen contentWidth="reading">
      <View style={styles.header}>
        <Text style={styles.brand}>FITICIAN</Text>
        <Text accessibilityRole="header" style={styles.title}>تغذیه</Text>
        <Text style={styles.intro}>
          وضعیت ایمنی، اطلاعات پایه و برآوردهای تغذیه‌ای تو از همین‌جا قابل مشاهده است.
        </Text>
      </View>

      <NutritionSummaryCard
        connectivityStatus={connectivityStatus}
        estimate={estimate}
      />

      <NutritionProfileSection
        onEdit={() => router.push("/member/profile")}
        onRetry={() => void profileQuery.refetch()}
        state={profileState}
      />
      <SafetySection
        api={api}
        connectivityStatus={connectivityStatus}
        state={safetyState}
      />
      <StructuredExerciseSection state={exerciseState} />
      <ReviewRequirementSection state={reviewState} />
      <NutritionEstimateSection
        api={api}
        connectivityStatus={connectivityStatus}
        profile={profile ?? null}
        safety={safety ?? null}
        onRetry={() => void estimateQuery.refetch()}
        state={estimateState}
      />
      <NutritionPlanSection safety={safety ?? null} />
      <NutritionCatalogueSection />
      <NutritionTrackingSection />
      <NutritionAdherenceSection />
      <NutritionClinicalSection />
    </Screen>
  );
}

function NutritionProfileSection({
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
      {state.status === "offline" ? <Notice message="آخرین نسخه ذخیره‌شده نمایش داده می‌شود." variant="offline" /> : null}
      <SummaryRow label="الگوی غذایی" value={dietaryLabels[profile.dietary_pattern] ?? profile.dietary_pattern} />
      <SummaryRow label="فعالیت روزانه" value={activityLabels[profile.daily_activity_level] ?? profile.daily_activity_level} />
      <SummaryRow label="وعده و میان‌وعده" value={`${profile.effective_main_meal_slots ?? profile.meals_per_day ?? 0} وعده · ${profile.effective_snack_slots ?? profile.snacks_per_day ?? 0} میان‌وعده`} />
      <SummaryRow label="بودجه هفتگی" value={`${irrToToman(profile.weekly_budget_irr)} تومان`} />
      {profile.physician_review_required ? (
        <Notice message="ادامه بعضی عملیات تغذیه به بررسی پزشک نیاز دارد." variant="warning" />
      ) : null}
      <Button label="ویرایش پروفایل تغذیه" onPress={onEdit} variant="ghost" />
    </Card>
  );
}

function SafetySection({
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

function StructuredExerciseSection({ state }: { readonly state: MobileViewState<StructuredExercise | null> }) {
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
          ? `${exercise.days_per_week ?? 0} روز در هفته · ${exercise.minutes_per_session ?? 0} دقیقه · ${exerciseTypeLabel(exercise.exercise_type)}`
          : "در حال حاضر فعالیت ساختاریافته‌ای ثبت نشده است."}
      </Text>
    </Card>
  );
}

function ReviewRequirementSection({ state }: { readonly state: MobileViewState<PhysicianReviewRequirement | null> }) {
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

function NutritionEstimateSection({
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
  if (error instanceof ApiError && error.message !== "Request failed") return error.message;
  return "عملیات تغذیه انجام نشد؛ اتصال را بررسی کن و دوباره تلاش کن.";
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
  brand: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    letterSpacing: 1.4,
    textAlign: "left",
    writingDirection: "ltr",
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
  header: {
    alignItems: "flex-end",
    gap: fiticianTokens.spacing[2],
    marginBottom: fiticianTokens.spacing[4],
  },
  intro: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 27,
    textAlign: "right",
    writingDirection: "rtl",
  },
  sectionCard: {
    gap: fiticianTokens.spacing[3],
    marginBottom: fiticianTokens.spacing[3],
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
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 40,
    textAlign: "right",
    writingDirection: "rtl",
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
