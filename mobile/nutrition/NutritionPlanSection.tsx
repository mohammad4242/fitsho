import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { nutritionKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { Button, Card, Dialog, DisclosureCard, EmptyState, Notice, Sheet, Skeleton } from "../ui/components";
import { getMobileViewState, mobileRequestErrorMessage, type MobileViewState } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import { canGenerateNutritionEstimate, formatNutritionNumber } from "./nutritionModel";
import {
  type FoodReplacementOptions,
  type FoodReplacementPreview,
  type MealFeedbackUpdateResponse,
  type MealRemovalPreview,
  type MealReplacementOptions,
  type MealReplacementPreview,
  type NutritionPlanActionsApi,
  type WeeklyPlanFeedback,
  createNutritionPlanActionsApi,
} from "./nutritionPlanActionsApi";
import {
  createNutritionPlanApi,
  type NutritionPlanApi,
  type PlanBundleSelectResponse,
  type WeeklyPlan,
  type WeeklyPlanDay,
  type WeeklyPlanGeneration,
  type WeeklyPlanHistoryItem,
  type WeeklyPlanMeal,
} from "./nutritionPlanApi";
import {
  canEditNutritionPlan,
  classifyNutritionGenerationOutcome,
  formatNutritionPlanMoney,
  getNutritionPlanStatus,
  isNutritionPlanExecutable,
  preparedRecipePresentation,
  selectNutritionPlan,
  type PreparedRecipePresentation,
} from "./nutritionPlanModel";
import { NutritionThumbnail } from "./NutritionThumbnail";
import {
  ExpoNutritionPlanPdfStore,
  type StoredNutritionPlanPdf,
} from "./nutritionPlanPdfStore";
import type { SafetyDecision } from "./nutritionApi";
import { NutritionShoppingList } from "./NutritionShoppingList";

type PdfStatus = "checking" | "downloading" | "error" | "idle" | "ready";
type BundleRole = "budget" | "ideal";

const weekdayLabels = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"];
const generationMessages: Record<ReturnType<typeof classifyNutritionGenerationOutcome>, string> = {
  failed: "ساخت برنامه غذایی انجام نشد؛ وضعیت پروفایل و اتصال را بررسی کن.",
  infeasible: "با تنظیمات فعلی، برنامه‌ای که همه محدودیت‌ها را رعایت کند پیدا نشد.",
  price_unavailable: "قیمت مرجع تأییدشده برای ساخت این برنامه در دسترس نیست.",
  safety_blocked: "به دلیل وضعیت ایمنی، ساخت برنامه غذایی فعلاً مسدود است.",
  success: "برنامه غذایی با اطلاعات فعلی ساخته شد.",
};

const generationReasonMessages: Readonly<Record<string, string>> = {
  CARBOHYDRATE_MINIMUM_EXCEEDS_CALORIE_BUDGET: "حداقل کربوهیدرات موردنیاز با کالری هدف فعلی قابل جمع نیست.",
  FLEXIBLE_BUDGET_CAP_EXCEEDED: "حتی محدوده انعطاف‌پذیر بودجه برای برنامه فعلی کافی نیست.",
  GOAL_RESELECTION_REQUIRED: "هدف فعلی با شرایط ثبت‌شده قابل برنامه‌ریزی نیست.",
  INSUFFICIENT_PRICE_COVERAGE: "برای تعداد کافی از مواد غذایی قیمت معتبر در دسترس نیست.",
  NUTRITION_PROFILE_REQUIRED: "پروفایل تغذیه کامل نیست.",
  PHYSICIAN_MANUAL_PLAN_REQUIRED: "این شرایط به تنظیم یا بررسی پزشک نیاز دارد.",
  PROTEIN_MINIMUM_EXCEEDS_CALORIE_BUDGET: "حداقل پروتئین موردنیاز با کالری هدف فعلی قابل جمع نیست.",
  STRUCTURED_EXERCISE_REQUIRED: "اطلاعات تمرین برای ساخت برنامه کامل نیست.",
  STRICT_BUDGET_EXCEEDED: "هزینه برنامه از بودجه سخت‌گیرانه بیشتر است.",
  UNSUPPORTED_OR_HARD_BLOCKED: "ساخت خودکار برنامه با شرایط فعلی مجاز نیست.",
  USER_BUDGET_BELOW_MINIMUM_FEASIBLE: "با بودجه فعلی برنامه سازگار و شدنی پیدا نشد.",
};

const planWarningMessages: Readonly<Record<string, string>> = {
  INSUFFICIENT_PRICE_COVERAGE: "پوشش قیمت مرجع برای همه مواد غذایی کافی نیست.",
  PHYSICIAN_REVIEW_REQUIRED: "این نسخه تا بررسی پزشک برای تصمیم نهایی آماده نیست.",
  PRICE_SNAPSHOT_STALE: "قیمت‌های مرجع این نسخه ممکن است تازه نباشند.",
  SAFETY_REVIEW_REQUIRED: "این نسخه به بررسی ایمنی تغذیه نیاز دارد.",
};

export function NutritionPlanSection({ safety }: { readonly safety: SafetyDecision | null }) {
  const auth = useMobileAuth();
  const queryClient = useQueryClient();
  const connectivityStatus = useConnectivityStatus();
  const api = useMemo(
    () => createNutritionPlanApi(auth.request, auth.download),
    [auth.download, auth.request],
  );
  const actionsApi = useMemo(
    () => createNutritionPlanActionsApi(auth.request),
    [auth.request],
  );
  const pdfStore = useMemo(() => new ExpoNutritionPlanPdfStore(), []);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [generationResult, setGenerationResult] = useState<WeeklyPlanGeneration | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);

  const activeQuery = useQuery({
    queryFn: api.getActive,
    queryKey: nutritionKeys.plan("active"),
  });
  const latestQuery = useQuery({
    queryFn: api.getLatest,
    queryKey: nutritionKeys.plan("latest"),
  });
  const bundleQuery = useQuery({
    queryFn: api.getLatestBundle,
    queryKey: nutritionKeys.latestBundle(),
  });
  const historyQuery = useQuery({
    queryFn: api.getHistory,
    queryKey: nutritionKeys.plans(),
  });
  const selectedQuery = useQuery({
    enabled: selectedPlanId !== null,
    queryFn: () => api.get(selectedPlanId as string),
    queryKey: nutritionKeys.plan(selectedPlanId ?? "selected"),
  });

  const activeState = getMobileViewState(activeQuery, { connectivityStatus });
  const latestState = getMobileViewState(latestQuery, { connectivityStatus });
  const bundleState = getMobileViewState(bundleQuery, { connectivityStatus });
  const historyState = getMobileViewState(historyQuery, { connectivityStatus });
  const selectedState = getMobileViewState(selectedQuery, { connectivityStatus });
  const activePlan = viewData(activeState);
  const latestPlan = viewData(latestState);
  const bundle = viewData(bundleState);
  const history = viewData(historyState) ?? [];
  const selectedPlan = viewData(selectedState);
  const primarySelection = selectNutritionPlan(activePlan ?? null, latestPlan ?? null);
  const displayedPlan = selectedPlanId === null ? primarySelection.plan : selectedPlan;
  const historical = selectedPlanId !== null && selectedPlanId !== activePlan?.id;
  const offline = connectivityStatus === "offline";
  const canGenerate = canGenerateNutritionEstimate(safety) && !offline;
  const generate = useMutation({
    mutationFn: api.generate,
    onError: (error: unknown) => setGenerationError(nutritionPlanErrorMessage(error)),
    onSuccess: async (result) => {
      setGenerationError(null);
      setGenerationResult(result);
      setSelectedPlanId(null);
      await Promise.all([
        activeQuery.refetch(),
        latestQuery.refetch(),
        bundleQuery.refetch(),
        historyQuery.refetch(),
      ]);
    },
  });
  const selectBundle = useMutation({
    mutationFn: ({ bundleId, role }: { bundleId: string; role: BundleRole }) =>
      api.selectBundle(bundleId, { selected_plan_role: role }),
    onError: (error: unknown) => setGenerationError(nutritionPlanErrorMessage(error)),
    onSuccess: async (result: PlanBundleSelectResponse) => {
      setGenerationError(null);
      setGenerationResult(null);
      queryClient.setQueryData(nutritionKeys.plan("active"), result.plan);
      queryClient.setQueryData(nutritionKeys.plan("latest"), result.plan);
      await Promise.all([activeQuery.refetch(), latestQuery.refetch(), historyQuery.refetch()]);
    },
  });

  const loading = activePlan === undefined && latestPlan === undefined;
  const loadError = activeState.status === "error" && latestState.status === "error";
  const noPlanOffline = offline && displayedPlan === undefined;

  function retry() {
    void Promise.all([activeQuery.refetch(), latestQuery.refetch(), bundleQuery.refetch(), historyQuery.refetch()]);
  }

  function startGeneration() {
    if (!canGenerate || generate.isPending) return;
    setGenerationError(null);
    setGenerationResult(null);
    generate.mutate();
  }

  function selectHistoryVersion(version: WeeklyPlanHistoryItem) {
    if (version.id === activePlan?.id) {
      setSelectedPlanId(null);
      return;
    }
    setSelectedPlanId(version.id);
  }

  function handlePlanUpdated(next: WeeklyPlan) {
    queryClient.setQueryData(nutritionKeys.plan(next.id), next);
    queryClient.setQueryData(nutritionKeys.plan("latest"), next);
    void Promise.all([activeQuery.refetch(), latestQuery.refetch(), historyQuery.refetch()]);
  }

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeading}>
        <Text style={styles.sectionTitle}>برنامه غذایی هفتگی</Text>
        <Text style={styles.sectionHint}>نسخه فعال و تاریخچه برنامه‌ها</Text>
      </View>

      {loading ? <Skeleton height={260} /> : null}
      {loadError && displayedPlan === undefined ? (
        <Notice
          actionLabel="تلاش دوباره"
          message="برنامه غذایی دریافت نشد."
          onAction={retry}
          variant="danger"
        />
      ) : null}
      {noPlanOffline ? <Notice message="برای دریافت برنامه غذایی به اینترنت وصل شو." variant="offline" /> : null}
      {offline && displayedPlan !== undefined ? (
        <Notice message="این برنامه از حافظه امن آفلاین خوانده شده است." variant="offline" />
      ) : null}
      {displayedPlan !== undefined && displayedPlan !== null ? (
        <NutritionPlanCard
          api={api}
          actionsApi={actionsApi}
          connectivityStatus={connectivityStatus}
          historical={historical}
          onPlanUpdated={handlePlanUpdated}
          pdfStore={pdfStore}
          plan={displayedPlan}
          safety={safety}
        />
      ) : null}

      {displayedPlan === null && !loading && !loadError && !noPlanOffline ? (
        <EmptyState
          actionLabel={canGenerate ? "ساخت برنامه غذایی" : "ارزیابی ایمنی لازم است"}
          onAction={canGenerate ? startGeneration : undefined}
          title="هنوز برنامه غذایی نداری"
        >
          <Text style={styles.bodyText}>پس از تکمیل پروفایل و ارزیابی ایمنی، برنامه هفتگی از داده‌های تأییدشده ساخته می‌شود.</Text>
        </EmptyState>
      ) : null}

      {latestState.status === "error" && latestPlan !== undefined ? (
        <Notice message="تازه‌سازی آخرین نسخه انجام نشد؛ نسخه موجود نمایش داده می‌شود." variant="warning" />
      ) : null}
      {generationResult !== null ? <GenerationNotice result={generationResult} /> : null}
      {generationError !== null ? <Notice message={generationError} variant="danger" /> : null}

      <Button
        disabled={!canGenerate || generate.isPending}
        label={generate.isPending ? "در حال ساخت برنامه" : "ساخت نسخه جدید"}
        loading={generate.isPending}
        onPress={startGeneration}
        variant="secondary"
      />
      {!canGenerate && safety !== null ? <Notice message="ساخت برنامه تا تأیید ادامه مسیر ایمن انجام نمی‌شود." variant="warning" /> : null}
      {!canGenerate && safety === null ? <Notice message="ابتدا ارزیابی ایمنی تغذیه را کامل کن." variant="warning" /> : null}

      <BundleChoice
        bundle={bundle}
        disabled={!canGenerate || selectBundle.isPending}
        onSelect={(role) => {
          if (bundle?.bundle_id === null || bundle?.bundle_id === undefined) return;
          setGenerationError(null);
          selectBundle.mutate({ bundleId: bundle.bundle_id, role });
        }}
        selectedPlanId={activePlan?.id ?? null}
      />
      <NutritionPlanHistory
        activePlanId={activePlan?.id ?? null}
        history={history}
        onRetry={() => void historyQuery.refetch()}
        onSelect={selectHistoryVersion}
        selectedPlanId={selectedPlanId}
        state={historyState}
      />
    </View>
  );
}

function NutritionPlanCard({
  actionsApi,
  api,
  connectivityStatus,
  historical,
  onPlanUpdated,
  pdfStore,
  plan,
  safety,
}: {
  readonly actionsApi: NutritionPlanActionsApi;
  readonly api: NutritionPlanApi;
  readonly connectivityStatus: ConnectivityStatus;
  readonly historical: boolean;
  readonly onPlanUpdated: (plan: WeeklyPlan) => void;
  readonly pdfStore: ExpoNutritionPlanPdfStore;
  readonly plan: WeeklyPlan;
  readonly safety: SafetyDecision | null;
}) {
  const queryClient = useQueryClient();
  const [currentPlan, setCurrentPlan] = useState(plan);
  const feedbackQuery = useQuery({
    enabled: !historical,
    queryFn: () => actionsApi.getFeedback(plan.id),
    queryKey: nutritionKeys.mealFeedback(plan.id),
  });
  const status = getNutritionPlanStatus(currentPlan, historical);
  const executable = isNutritionPlanExecutable(currentPlan, historical);
  const editable = canEditNutritionPlan(currentPlan, historical, connectivityStatus === "offline")
    && safety?.can_continue_onboarding === true;
  const [selectedDayIndex, setSelectedDayIndex] = useState(0);
  const selectedDay = currentPlan.days[selectedDayIndex] ?? currentPlan.days[0] ?? null;

  useEffect(() => {
    setCurrentPlan(plan);
    setSelectedDayIndex(0);
  }, [plan.id, plan.revision]);

  if (!currentPlan.is_user_visible) {
    return <Notice message="این نسخه برای نمایش عضو آماده نیست." variant="info" />;
  }

  return (
    <View style={styles.planStack}>
      <Card style={styles.planCard}>
        <View style={styles.planHeading}>
          <View style={styles.planCopy}>
            <Text style={styles.eyebrow}>{planHeadingEyebrow(currentPlan, historical)}</Text>
            <Text accessibilityRole="header" style={styles.planTitle}>{planTitle(currentPlan)}</Text>
          </View>
          <StatusBadge status={status} />
        </View>
        {historical ? <Notice message="این نسخه فقط برای مشاهده تاریخچه است و برنامه فعال تو نیست." variant="info" /> : null}
        {!executable && !historical ? <PlanReviewNotice status={status} /> : null}
        <View style={styles.statsGrid}>
          <PlanStat label="هزینه هفتگی" value={formatNutritionPlanMoney(currentPlan.weekly_cost_irr)} />
          <PlanStat label="بودجه هفتگی" value={formatNutritionPlanMoney(currentPlan.weekly_budget_irr)} />
          <PlanStat label="تعداد روز" value={formatNutritionNumber(currentPlan.days.length)} />
          <PlanStat label="نسخه" value={formatNutritionNumber(currentPlan.revision)} />
        </View>
        <View style={styles.planContext}>
          <PlanContextItem label="نقش برنامه" value={planRoleLabel(currentPlan.plan_role)} />
          <PlanContextItem label="وضعیت پزشک" value={planApprovalLabel(currentPlan)} />
          <PlanContextItem label="شروع برنامه" value={formatPlanDate(currentPlan.start_date)} />
        </View>
        {currentPlan.physician_user_visible_notes ? (
          <Notice message={currentPlan.physician_user_visible_notes} title="یادداشت پزشک" variant="info" />
        ) : null}
        {currentPlan.physician_change_summary.length > 0 ? (
          <Notice message="پزشک در این نسخه تغییراتی ثبت کرده است؛ جزئیات در وضعیت همین برنامه اعمال شده‌اند." title="خلاصه تغییرات پزشک" variant="info" />
        ) : null}
        <PlanWarnings codes={currentPlan.warning_codes} />
        <SummaryRow label="وضعیت بودجه" value={budgetStatusLabel(currentPlan.budget_status)} />
      </Card>

      {selectedDay !== null ? (
        <View style={styles.daysSection}>
          <Text style={styles.sectionTitle}>روزهای برنامه</Text>
          <DaySelector days={currentPlan.days} selectedDayIndex={selectedDayIndex} onSelect={setSelectedDayIndex} />
          <NutritionDayCard
            actionsApi={actionsApi}
            canEdit={editable}
            day={selectedDay}
            feedback={feedbackQuery.data?.feedback ?? {}}
            onFeedbackSaved={(result) => {
              queryClient.setQueryData<WeeklyPlanFeedback>(nutritionKeys.mealFeedback(currentPlan.id), {
                feedback: {
                  ...feedbackQuery.data?.feedback,
                  [result.meal_id]: result.feedback_type,
                },
              });
            }}
            onLockChanged={(mealId, isLocked) => {
              setCurrentPlan((previous) => updateMealLock(previous, mealId, isLocked));
            }}
            onPlanUpdated={(next) => {
              setCurrentPlan(next);
              onPlanUpdated(next);
            }}
            planId={currentPlan.id}
          />
        </View>
      ) : (
        <Notice message="برای این نسخه هنوز روزی ثبت نشده است." variant="info" />
      )}
      <NutritionShoppingList
        api={api}
        connectivityStatus={connectivityStatus}
        executable={executable}
        historical={historical}
        planId={currentPlan.id}
      />
      <NutritionPlanPdf api={api} connectivityStatus={connectivityStatus} pdfStore={pdfStore} planId={plan.id} />
    </View>
  );
}

function NutritionDayCard({
  actionsApi,
  canEdit,
  day,
  feedback,
  onFeedbackSaved,
  onLockChanged,
  onPlanUpdated,
  planId,
}: {
  readonly actionsApi: NutritionPlanActionsApi;
  readonly canEdit: boolean;
  readonly day: WeeklyPlanDay;
  readonly feedback: WeeklyPlanFeedback["feedback"];
  readonly onFeedbackSaved: (result: MealFeedbackUpdateResponse) => void;
  readonly onLockChanged: (mealId: string, isLocked: boolean) => void;
  readonly onPlanUpdated: (plan: WeeklyPlan) => void;
  readonly planId: string;
}) {
  return (
    <Card style={styles.dayCard}>
      <View style={styles.dayHeading}>
        <View style={styles.dayCopy}>
          <Text style={styles.dayTitle}>{weekdayLabels[day.day_index] ?? `روز ${day.day_index + 1}`}</Text>
          <Text style={styles.dayDate}>{formatPlanDate(day.plan_date)}</Text>
        </View>
        <Text style={styles.dayCost}>{formatNutritionPlanMoney(day.cost_irr)}</Text>
      </View>
      <View style={styles.nutrientGrid}>
        {Object.entries(day.nutrient_totals).slice(0, 4).map(([code, value]) => (
          <View key={code} style={styles.nutrientChip}>
            <Text style={styles.nutrientValue}>{formatNutritionNumber(value)}</Text>
            <Text style={styles.nutrientLabel}>{nutritionLabel(code)}</Text>
          </View>
        ))}
      </View>
      <View style={styles.mealStack}>
        {day.meals.map((meal) => (
          <NutritionMealCard
            actionsApi={actionsApi}
            canEdit={canEdit}
            feedbackType={feedback[meal.id]}
            key={meal.id}
            meal={meal}
            onFeedbackSaved={onFeedbackSaved}
            onLockChanged={onLockChanged}
            onPlanUpdated={onPlanUpdated}
            planId={planId}
          />
        ))}
      </View>
    </Card>
  );
}

type ReplacementSelector =
  | { readonly kind: "food"; readonly options: FoodReplacementOptions | null; readonly selectedId: string | null; readonly targetFoodId: string | null }
  | { readonly kind: "meal"; readonly options: MealReplacementOptions | null; readonly selectedId: string | null };

type PlanEditPreview =
  | { readonly data: MealRemovalPreview; readonly kind: "remove" }
  | { readonly data: MealReplacementPreview; readonly kind: "meal"; readonly replacementId: string }
  | { readonly data: FoodReplacementPreview; readonly foodId: string; readonly kind: "food"; readonly replacementId: string };

type MealAction = "confirm" | "feedback" | "lock" | "options";

function NutritionMealCard({
  actionsApi,
  canEdit,
  feedbackType,
  meal,
  onFeedbackSaved,
  onLockChanged,
  onPlanUpdated,
  planId,
}: {
  readonly actionsApi: NutritionPlanActionsApi;
  readonly canEdit: boolean;
  readonly feedbackType: WeeklyPlanFeedback["feedback"][string] | undefined;
  readonly meal: WeeklyPlanMeal;
  readonly onFeedbackSaved: (result: MealFeedbackUpdateResponse) => void;
  readonly onLockChanged: (mealId: string, isLocked: boolean) => void;
  readonly onPlanUpdated: (plan: WeeklyPlan) => void;
  readonly planId: string;
}) {
  const mealName = meal.name_fa ?? meal.name_en ?? meal.meal_code ?? "وعده غذایی";
  const [busy, setBusy] = useState<MealAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selector, setSelector] = useState<ReplacementSelector | null>(null);
  const [preview, setPreview] = useState<PlanEditPreview | null>(null);
  const editable = canEdit && busy === null;

  async function toggleLock() {
    if (!canEdit || busy !== null) return;
    setBusy("lock");
    setError(null);
    try {
      const result = await actionsApi.setMealLock(planId, meal.id, !meal.is_locked);
      onLockChanged(result.meal_id, result.is_locked);
    } catch (actionError) {
      setError(nutritionPlanErrorMessage(actionError));
    } finally {
      setBusy(null);
    }
  }

  async function saveFeedback(feedback: "liked" | "disliked") {
    if (!canEdit || busy !== null) return;
    setBusy("feedback");
    setError(null);
    try {
      const result = await actionsApi.setMealFeedback(planId, meal.id, {
        feedback_type: feedback,
        notes: null,
      });
      onFeedbackSaved(result);
    } catch (actionError) {
      setError(nutritionPlanErrorMessage(actionError));
    } finally {
      setBusy(null);
    }
  }

  async function openMealReplacement() {
    if (!canEdit || meal.is_locked || busy !== null) return;
    setBusy("options");
    setError(null);
    setSelector({ kind: "meal", options: null, selectedId: null });
    try {
      const options = await actionsApi.getMealReplacementOptions(planId, meal.id);
      setSelector({ kind: "meal", options, selectedId: null });
    } catch (actionError) {
      setSelector(null);
      setError(nutritionPlanErrorMessage(actionError));
    } finally {
      setBusy(null);
    }
  }

  async function openFoodReplacement() {
    if (!canEdit || meal.is_locked || busy !== null) return;
    setError(null);
    setSelector({ kind: "food", options: null, selectedId: null, targetFoodId: null });
  }

  async function loadFoodReplacementOptions(foodId: string) {
    if (selector?.kind !== "food" || busy !== null) return;
    setBusy("options");
    setError(null);
    try {
      const options = await actionsApi.getFoodReplacementOptions(planId, meal.id, foodId);
      setSelector({ ...selector, options, targetFoodId: foodId, selectedId: null });
    } catch (actionError) {
      setError(nutritionPlanErrorMessage(actionError));
    } finally {
      setBusy(null);
    }
  }

  async function previewSelectedReplacement() {
    if (selector === null || selector.selectedId === null || busy !== null) return;
    setBusy("options");
    setError(null);
    try {
      if (selector.kind === "meal" && selector.options !== null) {
        const replacement = selector.options.options.find((option) => option.id === selector.selectedId);
        if (replacement === undefined) return;
        const data = await actionsApi.previewReplaceMeal(planId, {
          expected_plan_revision_id: planId,
          meal_id: meal.id,
          replacement_meal_id: replacement.id,
        });
        setPreview({ data, kind: "meal", replacementId: replacement.id });
        setSelector(null);
      } else if (selector.kind === "food" && selector.options !== null && selector.targetFoodId !== null) {
        const replacement = selector.options.options.find((option) => option.food_id === selector.selectedId);
        if (replacement === undefined) return;
        const data = await actionsApi.previewReplaceFood(planId, {
          expected_plan_revision_id: planId,
          food_id: selector.targetFoodId,
          meal_id: meal.id,
          replacement_food_id: replacement.food_id,
        });
        setPreview({ data, foodId: selector.targetFoodId, kind: "food", replacementId: replacement.food_id });
        setSelector(null);
      }
    } catch (actionError) {
      setError(nutritionPlanErrorMessage(actionError));
    } finally {
      setBusy(null);
    }
  }

  async function previewRemoval() {
    if (!canEdit || meal.is_locked || busy !== null) return;
    setBusy("options");
    setError(null);
    try {
      const data = await actionsApi.previewRemoveMeal(planId, meal.id);
      setPreview({ data, kind: "remove" });
    } catch (actionError) {
      setError(nutritionPlanErrorMessage(actionError));
    } finally {
      setBusy(null);
    }
  }

  async function confirmPreview() {
    if (preview === null || busy !== null) return;
    setBusy("confirm");
    setError(null);
    try {
      const next = preview.kind === "remove"
        ? await actionsApi.confirmRemoveMeal(planId, {
          expected_plan_revision_id: preview.data.expected_plan_revision_id,
          meal_id: preview.data.meal_id,
        })
        : preview.kind === "meal"
          ? await actionsApi.confirmReplaceMeal(planId, {
            expected_plan_revision_id: preview.data.expected_plan_revision_id,
            meal_id: preview.data.meal_id,
            replacement_meal_id: preview.replacementId,
          })
          : await actionsApi.confirmReplaceFood(planId, {
            expected_plan_revision_id: preview.data.expected_plan_revision_id,
            food_id: preview.data.food_id,
            meal_id: preview.data.meal_id,
            replacement_food_id: preview.replacementId,
          });
      setPreview(null);
      setSelector(null);
      onPlanUpdated(next);
    } catch (actionError) {
      setError(nutritionPlanErrorMessage(actionError));
    } finally {
      setBusy(null);
    }
  }

  return (
    <DisclosureCard
      leading={<NutritionThumbnail imageUrl={meal.image_url} name={mealName} style={styles.mealThumbnail} />}
      summary={`${mealRoleLabel(meal.slot_role)} · ${formatNutritionPlanMoney(meal.cost_irr)}`}
      style={styles.mealCard}
      title={mealName}
    >
      {meal.is_locked ? <Text style={styles.lockedLabel}>این وعده قفل شده است</Text> : null}
      {meal.foods.length > 0 ? (
        <View style={styles.foodStack}>
          {meal.foods.map((food) => (
            <View key={`${food.slug}-${food.food_id ?? food.item_kind}`}>
              <View style={styles.foodRow}>
                <Text style={styles.foodName}>{food.name_fa || food.name_en}</Text>
                <Text style={styles.foodAmount}>{formatNutritionNumber(food.grams)} گرم</Text>
              </View>
              <PreparedRecipeSummary summary={preparedRecipePresentation(food)} />
            </View>
          ))}
        </View>
      ) : <Text style={styles.bodyText}>جزئیات این وعده هنوز در دسترس نیست.</Text>}
      {error !== null ? <Notice message={error} variant="danger" /> : null}
      <View style={styles.mealActions}>
        <Button
          disabled={!editable}
          label={meal.is_locked ? "باز کردن قفل" : "قفل وعده"}
          loading={busy === "lock"}
          onPress={() => void toggleLock()}
          variant="ghost"
        />
        <Button
          disabled={!editable}
          label={feedbackType === "liked" ? "پسندیده شد" : "پسندیدم"}
          loading={busy === "feedback"}
          onPress={() => void saveFeedback("liked")}
          variant="ghost"
        />
        <Button
          disabled={!editable}
          label={feedbackType === "disliked" ? "کمتر پیشنهاد بده ✓" : "کمتر پیشنهاد بده"}
          loading={busy === "feedback"}
          onPress={() => void saveFeedback("disliked")}
          variant="ghost"
        />
        <Button
          disabled={!editable || meal.is_locked}
          label="تعویض وعده"
          loading={busy === "options" && selector?.kind === "meal"}
          onPress={() => void openMealReplacement()}
          variant="secondary"
        />
        {meal.foods.some((food) => food.food_id !== null) ? (
          <Button
            disabled={!editable || meal.is_locked}
            label="تعویض ماده غذایی"
            onPress={() => void openFoodReplacement()}
            variant="secondary"
          />
        ) : null}
        <Button
          disabled={!editable || meal.is_locked}
          label="حذف وعده"
          loading={busy === "options" && selector === null}
          onPress={() => void previewRemoval()}
          variant="danger"
        />
      </View>
      <ReplacementSheet
        busy={busy === "options"}
        onClose={() => setSelector(null)}
        onFoodTarget={loadFoodReplacementOptions}
        onSelect={(selectedId) => {
          if (selector === null) return;
          setSelector({ ...selector, selectedId });
        }}
        onSubmit={() => void previewSelectedReplacement()}
        selector={selector}
        meal={meal}
      />
      <Dialog
        confirmLabel="تأیید تغییر"
        destructive={preview?.kind === "remove"}
        message={previewMessage(preview)}
        onClose={() => setPreview(null)}
        onConfirm={() => void confirmPreview()}
        title="تأیید تغییر برنامه"
        visible={preview !== null}
      >
        {previewRequiresReview(preview) ? <Notice message="این تغییر نیازمند بررسی دوباره پزشک است." variant="warning" /> : null}
      </Dialog>
    </DisclosureCard>
  );
}

function ReplacementSheet({
  busy,
  meal,
  onClose,
  onFoodTarget,
  onSelect,
  onSubmit,
  selector,
}: {
  readonly busy: boolean;
  readonly meal: WeeklyPlanMeal;
  readonly onClose: () => void;
  readonly onFoodTarget: (foodId: string) => void;
  readonly onSelect: (id: string) => void;
  readonly onSubmit: () => void;
  readonly selector: ReplacementSelector | null;
}) {
  const visible = selector !== null;
  const options = selector?.options;
  const targetFood = selector?.kind === "food" ? meal.foods.find((food) => food.food_id === selector.targetFoodId) : undefined;
  return (
    <Sheet onClose={onClose} title={selector?.kind === "food" ? "تعویض ماده غذایی" : "تعویض وعده"} visible={visible}>
      {selector?.kind === "food" && selector.targetFoodId === null ? (
        <View style={styles.optionStack}>
          <Text style={styles.bodyText}>ابتدا ماده غذایی موردنظر را انتخاب کن.</Text>
          {meal.foods.filter((food) => food.food_id !== null).map((food) => (
            <Button
              key={food.food_id}
              label={food.name_fa || food.name_en}
              onPress={() => onFoodTarget(food.food_id as string)}
              variant="secondary"
            />
          ))}
        </View>
      ) : options === null ? (
        <Skeleton height={160} />
      ) : selector !== null && options !== undefined ? (
        <View style={styles.optionStack}>
          <Text style={styles.bodyText}>
            {targetFood ? `جایگزین‌های ${targetFood.name_fa || targetFood.name_en}` : "یک جایگزین سازگار را انتخاب کن."}
          </Text>
          {options.options.length === 0 ? <Notice message="جایگزین سازگاری در دسترس نیست." variant="info" /> : null}
          {options.options.map((option) => {
            const id = "food_id" in option ? option.food_id : option.id;
            const name = option.name_fa || option.name_en;
            const selected = selector.selectedId === id;
            return (
              <Pressable
                accessibilityRole="radio"
                accessibilityState={{ checked: selected }}
                key={id}
                onPress={() => onSelect(id)}
                style={[styles.option, selected && styles.optionSelected]}
              >
                <NutritionThumbnail imageUrl={option.image_url} name={name} style={styles.optionThumbnail} />
                <Text style={[styles.optionName, selected && styles.optionNameSelected]}>{name}</Text>
                <Text style={styles.optionMeta}>{formatNutritionPlanMoney(option.cost_irr)}</Text>
              </Pressable>
            );
          })}
          <Button disabled={busy || selector.selectedId === null} label="بررسی تغییر" loading={busy} onPress={onSubmit} />
        </View>
      ) : null}
    </Sheet>
  );
}

function previewMessage(preview: PlanEditPreview | null): string {
  if (preview === null) return "";
  if (preview.kind === "remove") {
    return `حذف این وعده حدود ${formatNutritionPlanMoney(Math.abs(preview.data.weekly_cost_delta_irr))} تغییر هزینه دارد. این عملیات قابل بازگشت خودکار نیست.`;
  }
  const delta = preview.kind === "meal" ? preview.data.weekly_cost_delta_irr : preview.data.cost_delta_irr;
  return `این تغییر ${delta >= 0 ? "حدود " : "حدود "}${formatNutritionPlanMoney(Math.abs(delta))} در هزینه اثر می‌گذارد. قبل از ثبت، خلاصه تغییر را بررسی کن.`;
}

function previewRequiresReview(preview: PlanEditPreview | null): boolean {
  if (preview === null) return false;
  return preview.data.requires_physician_review;
}

function updateMealLock(plan: WeeklyPlan, mealId: string, isLocked: boolean): WeeklyPlan {
  return {
    ...plan,
    days: plan.days.map((day) => ({
      ...day,
      meals: day.meals.map((meal) => meal.id === mealId ? { ...meal, is_locked: isLocked } : meal),
    })),
  };
}

function PreparedRecipeSummary({ summary }: { readonly summary: PreparedRecipePresentation | null }) {
  if (summary === null) return null;
  return (
    <View style={styles.preparedRecipeCard}>
      <View style={styles.preparedRecipeHeading}>
        <Text style={styles.preparedRecipeTitle}>خلاصه دستور آماده</Text>
        <Text style={[styles.preparedRecipeStatus, summary.status === "estimated" && styles.preparedRecipeEstimated]}>
          {summary.status === "estimated" ? "تخمینی" : "تأیید شده"}
        </Text>
      </View>
      {summary.nutrients.length > 0 ? (
        <View style={styles.preparedRecipeNutrients}>
          {summary.nutrients.map((nutrient) => (
            <Text key={nutrient.code} style={styles.preparedRecipeNutrient}>
              {nutritionLabel(nutrient.code)}: {formatNutritionNumber(nutrient.value)}
            </Text>
          ))}
        </View>
      ) : null}
      {summary.costIrrPer100g !== null ? (
        <Text style={styles.preparedRecipeCost}>
          {formatNutritionPlanMoney(summary.costIrrPer100g)} در ۱۰۰ گرم
        </Text>
      ) : null}
    </View>
  );
}

function NutritionPlanPdf({
  api,
  connectivityStatus,
  pdfStore,
  planId,
}: {
  readonly api: NutritionPlanApi;
  readonly connectivityStatus: ConnectivityStatus;
  readonly pdfStore: ExpoNutritionPlanPdfStore;
  readonly planId: string;
}) {
  const [status, setStatus] = useState<PdfStatus>("checking");
  const [stored, setStored] = useState<StoredNutritionPlanPdf | null>(null);

  useEffect(() => {
    let mounted = true;
    setStatus("checking");
    setStored(null);
    void pdfStore.get(planId).then((value) => {
      if (!mounted) return;
      setStored(value);
      setStatus(value === null ? "idle" : "ready");
    }).catch(() => {
      if (mounted) setStatus("idle");
    });
    return () => {
      mounted = false;
    };
  }, [pdfStore, planId]);

  async function download() {
    setStatus("downloading");
    try {
      const result = await api.downloadPdf(planId);
      setStored(await pdfStore.save(planId, result));
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }

  async function open() {
    if (stored === null) return;
    try {
      await Linking.openURL(stored.uri);
    } catch {
      setStatus("error");
    }
  }

  return (
    <Card style={styles.pdfCard}>
      <Text style={styles.cardTitle}>نسخه PDF</Text>
      <Text style={styles.bodyText}>فایل برنامه در فضای امن دستگاه ذخیره می‌شود و پس از باز کردن دوباره اپ باقی می‌ماند.</Text>
      {status === "checking" ? <Skeleton height={52} /> : null}
      {status !== "checking" && stored === null ? (
        <Button
          disabled={connectivityStatus === "offline" || status === "downloading"}
          label="ذخیره PDF برای استفاده آفلاین"
          loading={status === "downloading"}
          onPress={() => void download()}
          variant="secondary"
        />
      ) : null}
      {stored !== null ? (
        <View style={styles.pdfActions}>
          <Button label="باز کردن PDF" onPress={() => void open()} />
          <Button
            disabled={connectivityStatus === "offline"}
            label="دریافت دوباره"
            onPress={() => void download()}
            variant="ghost"
          />
        </View>
      ) : null}
      {status === "error" ? <Notice message="دریافت یا باز کردن PDF انجام نشد؛ دوباره تلاش کن." variant="danger" /> : null}
    </Card>
  );
}

function BundleChoice({
  bundle,
  disabled,
  onSelect,
  selectedPlanId,
}: {
  readonly bundle: WeeklyPlanGeneration | null | undefined;
  readonly disabled: boolean;
  readonly onSelect: (role: BundleRole) => void;
  readonly selectedPlanId: string | null;
}) {
  if (
    bundle === undefined
    || bundle === null
    || bundle.bundle_id === null
    || bundle.budget_plan === null
    || bundle.budget_plan === undefined
    || bundle.ideal_plan === null
    || bundle.ideal_plan === undefined
    || bundle.comparison?.show_ideal_plan !== true
  ) return null;

  const selectedRole = bundle.selected_plan_role === "ideal"
    || bundle.selected_plan_id === bundle.ideal_plan.id
    || selectedPlanId === bundle.ideal_plan.id
    ? "ideal"
    : bundle.selected_plan_role === "budget" || selectedPlanId === bundle.budget_plan.id
      ? "budget"
      : null;

  return (
    <Card style={styles.sectionCard}>
      <Text accessibilityRole="header" style={styles.cardTitle}>مقایسه و انتخاب نسخه</Text>
      <Text style={styles.bodyText}>{comparisonExplanation(bundle.comparison)}</Text>
      {bundle.comparison.monthly_cost_gap_irr !== null && bundle.comparison.monthly_cost_gap_irr !== undefined ? (
        <Text style={styles.comparisonCost}>
          اختلاف هزینه ماهانه: {formatNutritionPlanMoney(bundle.comparison.monthly_cost_gap_irr)}
        </Text>
      ) : null}
      <View style={styles.choiceStack}>
        <PlanChoice
          disabled={disabled}
          label="نسخه اقتصادی"
          plan={bundle.budget_plan}
          selected={selectedRole === "budget"}
          onPress={() => onSelect("budget")}
        />
        <PlanChoice
          disabled={disabled}
          label="نسخه ایده‌آل"
          plan={bundle.ideal_plan}
          selected={selectedRole === "ideal"}
          onPress={() => onSelect("ideal")}
        />
      </View>
    </Card>
  );
}

function PlanChoice({
  disabled,
  label,
  onPress,
  plan,
  selected,
}: {
  readonly disabled: boolean;
  readonly label: string;
  readonly onPress: () => void;
  readonly plan: WeeklyPlan;
  readonly selected: boolean;
}) {
  return (
    <Pressable
      accessibilityLabel={selected ? `${label}، برنامه فعال شما` : label}
      accessibilityRole="radio"
      accessibilityState={{ checked: selected, disabled }}
      disabled={disabled}
      onPress={onPress}
      style={[styles.planChoice, selected && styles.planChoiceSelected]}
    >
      <View style={styles.planChoiceHeading}>
        <Text style={[styles.planChoiceLabel, selected && styles.planChoiceLabelSelected]}>{label}</Text>
        {selected ? <Text style={styles.planChoiceActive}>برنامه فعال شما</Text> : null}
      </View>
      <Text style={[styles.planChoiceSubtitle, selected && styles.planChoiceSubtitleSelected]}>
        {formatNutritionPlanMoney(plan.weekly_cost_irr)} در هفته
      </Text>
      <View style={styles.planChoiceMetrics}>
        <PlanChoiceMetric label="کالری" value={planMetricLabel(plan, "goal_calories")} />
        <PlanChoiceMetric label="پروتئین" value={planMetricLabel(plan, "protein")} />
        <PlanChoiceMetric label="کربوهیدرات" value={planMetricLabel(plan, "carbohydrate")} />
      </View>
    </Pressable>
  );
}

function PlanChoiceMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.planChoiceMetric}>
      <Text style={styles.planChoiceMetricValue}>{value}</Text>
      <Text style={styles.planChoiceMetricLabel}>{label}</Text>
    </View>
  );
}

function NutritionPlanHistory({
  activePlanId,
  history,
  onRetry,
  onSelect,
  selectedPlanId,
  state,
}: {
  readonly activePlanId: string | null;
  readonly history: readonly WeeklyPlanHistoryItem[];
  readonly onRetry: () => void;
  readonly onSelect: (version: WeeklyPlanHistoryItem) => void;
  readonly selectedPlanId: string | null;
  readonly state: MobileViewState<WeeklyPlanHistoryItem[]>;
}) {
  if (state.status === "loading") return <Skeleton height={120} />;
  if (state.status === "error" && history.length === 0) {
    return <Notice actionLabel="تلاش دوباره" message="تاریخچه برنامه دریافت نشد." onAction={onRetry} variant="danger" />;
  }
  if (state.status === "offline" && history.length === 0) {
    return <Notice message="تاریخچه برنامه در حالت آفلاین در دسترس نیست." variant="offline" />;
  }
  if (history.length === 0) return null;

  return (
    <View style={styles.historySection}>
      <Text style={styles.sectionTitle}>تاریخچه برنامه‌ها</Text>
      {state.status === "offline" ? <Notice message="فهرست تاریخچه تازه‌سازی نشده است." variant="offline" /> : null}
      {history.map((version) => (
        <Card
          key={version.id}
          onPress={() => onSelect(version)}
          style={styles.historyCard}
          variant={version.id === selectedPlanId || version.id === activePlanId ? "raised" : "interactive"}
        >
          <View style={styles.historyRow}>
            <View style={styles.historyCopy}>
              <Text style={styles.historyTitle}>{historyTitle(version)}</Text>
              <Text style={styles.historyDate}>{formatPlanDateTime(version.created_at)}</Text>
            </View>
            <Text style={styles.historyRevision}>نسخه {formatNutritionNumber(version.revision)}</Text>
          </View>
        </Card>
      ))}
    </View>
  );
}

function DaySelector({
  days,
  onSelect,
  selectedDayIndex,
}: {
  readonly days: readonly WeeklyPlanDay[];
  readonly onSelect: (index: number) => void;
  readonly selectedDayIndex: number;
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.daySelector}>
      {days.map((day, index) => (
        <Pressable
          accessibilityRole="tab"
          accessibilityState={{ selected: index === selectedDayIndex }}
          key={`${day.day_index}-${day.plan_date}`}
          onPress={() => onSelect(index)}
          style={[styles.dayTab, index === selectedDayIndex && styles.dayTabSelected]}
        >
          <Text style={[styles.dayTabLabel, index === selectedDayIndex && styles.dayTabLabelSelected]}>
            {weekdayLabels[day.day_index] ?? `روز ${day.day_index + 1}`}
          </Text>
          <Text style={[styles.dayTabDate, index === selectedDayIndex && styles.dayTabDateSelected]}>{formatPlanDate(day.plan_date)}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

function GenerationNotice({ result }: { readonly result: WeeklyPlanGeneration }) {
  const status = classifyNutritionGenerationOutcome(result.outcome);
  if (status === "success") return <Notice message={generationMessages.success} variant="success" />;
  const reasons = [...new Set(result.reason_codes.map((code) => generationReasonMessages[code]).filter((message): message is string => message !== undefined))];
  const message = reasons.length > 0 ? `${generationMessages[status]} ${reasons.join(" ")}` : generationMessages[status];
  return <Notice message={message} variant="warning" />;
}

function PlanReviewNotice({ status }: { readonly status: ReturnType<typeof getNutritionPlanStatus> }) {
  if (status === "pending_review" || status === "physician_review") {
    return <Notice message="این پیش‌نویس تا بررسی پزشک برنامه نهایی نیست و برای خرید نهایی قابل اتکا نیست." variant="warning" />;
  }
  if (status === "changes_requested") {
    return <Notice message="پزشک برای ادامه اصلاح یا اطلاعات بیشتری خواسته است." variant="warning" />;
  }
  if (status === "rejected") return <Notice message="این نسخه توسط پزشک تأیید نشده و قابل اجرا نیست." variant="danger" />;
  return null;
}

function StatusBadge({ status }: { readonly status: ReturnType<typeof getNutritionPlanStatus> }) {
  const label = status === "active"
    ? "فعال"
    : status === "historical"
      ? "تاریخی"
      : status === "pending_review" || status === "physician_review"
        ? "در انتظار بررسی"
        : status === "changes_requested"
          ? "نیازمند اصلاح"
          : status === "rejected"
            ? "رد شده"
            : status === "archived"
              ? "بایگانی"
              : "نسخه اولیه";
  return <Text style={[styles.statusBadge, status === "active" ? styles.statusActive : styles.statusPending]}>{label}</Text>;
}

function PlanStat({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.planStat}>
      <Text style={styles.planStatValue}>{value}</Text>
      <Text style={styles.planStatLabel}>{label}</Text>
    </View>
  );
}

function PlanContextItem({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.planContextItem}>
      <Text style={styles.planContextValue}>{value}</Text>
      <Text style={styles.planContextLabel}>{label}</Text>
    </View>
  );
}

function planHeadingEyebrow(plan: WeeklyPlan, historical: boolean): string {
  if (historical) return "نسخه قبلی";
  if (plan.lifecycle_status === "active") return "برنامه فعال";
  if (plan.physician_approved) return "تأییدشده برای اجرا";
  return "پیش‌نویس در انتظار بررسی";
}

function planRoleLabel(value: string | null | undefined): string {
  if (value === "budget") return "با بودجه شما";
  if (value === "ideal") return "ایده‌آل";
  return "برنامه غذایی";
}

function planTitle(plan: WeeklyPlan): string {
  if (plan.plan_role === "budget") return "برنامه با بودجه شما";
  if (plan.plan_role === "ideal") return "برنامه ایده‌آل";
  return "برنامه غذایی تو";
}

function planApprovalLabel(plan: WeeklyPlan): string {
  if (plan.physician_approved && plan.review_status === "approved") return "تأیید شده";
  if (plan.lifecycle_status === "rejected" || plan.review_status === "rejected") return "تأیید نشده";
  return "در انتظار بررسی";
}

function planMetricLabel(plan: WeeklyPlan, code: string): string {
  const metric = plan.nutrients[code];
  if (metric === undefined || !Number.isFinite(metric.planned)) return "—";
  const unit = metric.unit === "kcal/day" ? "کیلوکالری" : metric.unit === "g/day" ? "گرم" : metric.unit;
  return `${formatNutritionNumber(metric.planned)} ${unit}`;
}

function comparisonExplanation(
  comparison: NonNullable<WeeklyPlanGeneration["comparison"]>,
): string {
  if (comparison.meaningful_quality_improvement) {
    return "نسخه ایده‌آل بهبود معناداری در کیفیت یا پوشش مواد مغذی دارد؛ نسخه اقتصادی همچنان بر اساس بودجه شما محاسبه شده است.";
  }
  if (comparison.monthly_cost_gap_irr !== null && comparison.monthly_cost_gap_irr !== undefined) {
    return "دو نسخه با همان داده‌های مرجع تأییدشده مقایسه شده‌اند؛ اختلاف هزینه و مقدارهای اصلی را پیش از فعال‌سازی ببین.";
  }
  return "هر دو نسخه از داده‌های مرجع تأییدشده استفاده می‌کنند؛ یکی را به عنوان برنامه فعال انتخاب کن.";
}

function PlanWarnings({ codes }: { readonly codes: readonly string[] }) {
  const messages = [...new Set(codes.map((code) => planWarningMessages[code]).filter((message): message is string => message !== undefined))];
  if (messages.length === 0) return null;
  return <Notice message={messages.join(" ")} title="هشدارهای برنامه" variant="warning" />;
}

function SummaryRow({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.summaryRow}>
      <Text style={styles.summaryLabel}>{label}</Text>
      <Text style={styles.bodyText}>{value}</Text>
    </View>
  );
}

function viewData<TData>(state: MobileViewState<TData>): TData | undefined {
  if (state.status === "loading") return undefined;
  return "data" in state ? state.data : undefined;
}

function budgetStatusLabel(value: string): string {
  if (value === "within_budget") return "در محدوده بودجه";
  if (value === "flexible_overage") return "با مازاد انعطاف‌پذیر";
  if (value === "over_budget") return "بیش از بودجه";
  if (value === "unconstrained") return "بدون محدودیت بودجه";
  return "وضعیت بودجه ثبت نشده";
}

function formatPlanDate(value: string): string {
  return new Intl.DateTimeFormat("fa-IR", { day: "numeric", month: "short" }).format(
    new Date(`${value}T00:00:00Z`),
  );
}

function formatPlanDateTime(value: string): string {
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" }).format(new Date(value));
}

function historyTitle(version: WeeklyPlanHistoryItem): string {
  if (version.lifecycle_status === "active") return "نسخه فعال";
  if (version.lifecycle_status === "pending_physician_review") return "پیش‌نویس در انتظار پزشک";
  if (version.lifecycle_status === "rejected") return "نسخه ردشده";
  return "نسخه قبلی";
}

function mealRoleLabel(value: string): string {
  if (value === "main_meal") return "وعده اصلی";
  if (value === "snack") return "میان‌وعده";
  if (value === "free_meal") return "وعده آزاد";
  if (value === "post_workout") return "پس از تمرین";
  return "وعده غذایی";
}

function nutritionLabel(value: string): string {
  if (value === "energy" || value === "calories") return "انرژی";
  if (value === "protein") return "پروتئین";
  if (value === "carbohydrate" || value === "carbohydrates") return "کربوهیدرات";
  if (value === "fat") return "چربی";
  if (value === "fibre" || value === "fiber") return "فیبر";
  return "سایر مواد مغذی";
}

function nutritionPlanErrorMessage(error: unknown): string {
  return mobileRequestErrorMessage(error, "عملیات برنامه غذایی انجام نشد؛ اتصال را بررسی کن و دوباره تلاش کن.");
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

const styles = StyleSheet.create({
  bodyText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 24,
    textAlign: "right",
    writingDirection: "rtl",
  },
  cardTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  choiceStack: {
    gap: fiticianTokens.spacing[2],
  },
  comparisonCost: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  dayCard: {
    gap: fiticianTokens.spacing[3],
  },
  dayCost: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  dayCopy: {
    alignItems: "stretch",
    gap: fiticianTokens.spacing[1],
  },
  dayDate: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  dayHeading: {
    alignItems: "flex-start",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  daySelector: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    paddingBottom: fiticianTokens.spacing[1],
  },
  dayTab: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 92,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  dayTabDate: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  dayTabDateSelected: {
    color: fiticianTokens.colors.canvas,
  },
  dayTabLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  dayTabLabelSelected: {
    color: fiticianTokens.colors.canvas,
  },
  dayTabSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  dayTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  daysSection: {
    gap: fiticianTokens.spacing[3],
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  foodAmount: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  foodName: {
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  foodRow: {
    alignItems: "center",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[2],
  },
  foodStack: {
    gap: fiticianTokens.spacing[1],
  },
  historyCard: {
    marginBottom: fiticianTokens.spacing[2],
  },
  historyCopy: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  historyDate: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  historyRevision: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  historyRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  historySection: {
    alignItems: "stretch",
    gap: fiticianTokens.spacing[2],
  },
  historyTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  lockedLabel: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  mealCard: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[2],
    padding: 0,
  },
  mealActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  mealThumbnail: {
    flexShrink: 0,
    height: 64,
    width: 64,
  },
  mealStack: {
    gap: fiticianTokens.spacing[2],
  },
  nutrientChip: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: "22%",
    padding: fiticianTokens.spacing[2],
  },
  nutrientGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  nutrientLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  nutrientValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  option: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    padding: fiticianTokens.spacing[3],
  },
  optionMeta: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  optionName: {
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    textAlign: "right",
    writingDirection: "rtl",
  },
  optionNameSelected: {
    color: fiticianTokens.colors.aqua,
  },
  optionThumbnail: {
    height: 56,
    width: 56,
  },
  optionSelected: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.aqua,
  },
  optionStack: {
    gap: fiticianTokens.spacing[3],
  },
  pdfActions: {
    gap: fiticianTokens.spacing[2],
  },
  pdfCard: {
    alignItems: "stretch",
    gap: fiticianTokens.spacing[3],
  },
  planCard: {
    gap: fiticianTokens.spacing[3],
  },
  planChoice: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[1],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    padding: fiticianTokens.spacing[3],
  },
  planChoiceActive: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  planChoiceHeading: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    justifyContent: "space-between",
    width: "100%",
  },
  planChoiceMetric: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.surface,
    borderRadius: fiticianTokens.radii.small,
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
    padding: fiticianTokens.spacing[2],
  },
  planChoiceMetricLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  planChoiceMetricValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  planChoiceMetrics: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[1],
    width: "100%",
  },
  planChoiceLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  planChoiceLabelSelected: {
    color: fiticianTokens.colors.aqua,
  },
  planChoiceSelected: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.aqua,
  },
  planChoiceSubtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  planChoiceSubtitleSelected: {
    color: fiticianTokens.colors.ink,
  },
  planCopy: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  planTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
    lineHeight: 32,
    textAlign: "right",
    writingDirection: "rtl",
  },
  planHeading: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  planContext: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  planContextItem: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
    padding: fiticianTokens.spacing[2],
  },
  planContextLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  planContextValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  planStack: {
    gap: fiticianTokens.spacing[3],
  },
  planStat: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    flexGrow: 1,
    flexShrink: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: "46%",
    padding: fiticianTokens.spacing[3],
  },
  planStatLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  planStatValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  preparedRecipeCard: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    gap: fiticianTokens.spacing[2],
    marginTop: fiticianTokens.spacing[2],
    padding: fiticianTokens.spacing[3],
  },
  preparedRecipeCost: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  preparedRecipeEstimated: {
    color: fiticianTokens.colors.amber,
  },
  preparedRecipeHeading: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  preparedRecipeNutrient: {
    color: fiticianTokens.colors.muted,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  preparedRecipeNutrients: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  preparedRecipeStatus: {
    color: fiticianTokens.colors.success,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  preparedRecipeTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  section: {
    alignItems: "stretch",
    gap: fiticianTokens.spacing[3],
    marginBottom: fiticianTokens.spacing[3],
  },
  sectionCard: {
    gap: fiticianTokens.spacing[3],
  },
  sectionHeading: {
    alignItems: "stretch",
    gap: fiticianTokens.spacing[1],
  },
  sectionHint: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  sectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  statusActive: {
    backgroundColor: fiticianTokens.colors.success,
    color: fiticianTokens.colors.canvas,
  },
  statusBadge: {
    borderRadius: fiticianTokens.radii.pill,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    overflow: "hidden",
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
    textAlign: "center",
    writingDirection: "rtl",
  },
  statusPending: {
    backgroundColor: fiticianTokens.colors.amber,
    color: fiticianTokens.colors.canvas,
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
    flexDirection: "row",
    justifyContent: "space-between",
  },
  statsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
});
