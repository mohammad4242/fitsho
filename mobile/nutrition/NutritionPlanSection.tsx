import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { nutritionKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { AppIcon, Button, Card, Dialog, DisclosureCard, EmptyState, Notice, Sheet, Skeleton } from "../ui/components";
import { getMobileViewState, mobileRequestErrorMessage, type MobileViewState } from "../ui/requestState";
import { RTL_ROW } from "../ui/rtl";
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
          history={history}
          historyState={historyState}
          activePlanId={activePlan?.id ?? null}
          onHistoryRetry={() => void historyQuery.refetch()}
          onHistorySelect={selectHistoryVersion}
          selectedPlanId={selectedPlanId}
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
  activePlanId,
  history,
  historyState,
  onHistoryRetry,
  onHistorySelect,
  selectedPlanId,
}: {
  readonly actionsApi: NutritionPlanActionsApi;
  readonly api: NutritionPlanApi;
  readonly connectivityStatus: ConnectivityStatus;
  readonly historical: boolean;
  readonly onPlanUpdated: (plan: WeeklyPlan) => void;
  readonly pdfStore: ExpoNutritionPlanPdfStore;
  readonly plan: WeeklyPlan;
  readonly safety: SafetyDecision | null;
  readonly activePlanId: string | null;
  readonly history: readonly WeeklyPlanHistoryItem[];
  readonly historyState: MobileViewState<WeeklyPlanHistoryItem[]>;
  readonly onHistoryRetry: () => void;
  readonly onHistorySelect: (version: WeeklyPlanHistoryItem) => void;
  readonly selectedPlanId: string | null;
}) {
  const queryClient = useQueryClient();
  const [currentPlan, setCurrentPlan] = useState(plan);
  const feedbackQuery = useQuery({
    enabled: !historical,
    queryFn: () => actionsApi.getFeedback(plan.id),
    queryKey: nutritionKeys.mealFeedback(plan.id),
  });
  const executable = isNutritionPlanExecutable(currentPlan, historical);
  const editable = canEditNutritionPlan(currentPlan, historical, connectivityStatus === "offline")
    && safety?.can_continue_onboarding === true;
  const [selectedDayIndex, setSelectedDayIndex] = useState(0);
  const selectedDay = currentPlan.days.find((day) => day.day_index === selectedDayIndex) ?? currentPlan.days[0] ?? null;

  useEffect(() => {
    setCurrentPlan(plan);
    setSelectedDayIndex(0);
  }, [plan.id, plan.revision]);

  if (!currentPlan.is_user_visible) {
    return <Notice message="این نسخه برای نمایش عضو آماده نیست." variant="info" />;
  }

  return (
    <View style={styles.planStack}>
      <View style={styles.planHeading}>
        <Text style={styles.eyebrow}>{planHeadingEyebrow(currentPlan, historical)}</Text>
        <Text accessibilityRole="header" style={styles.planTitle}>{planTitle(currentPlan)}</Text>
      </View>
      {historical ? <ReferencePlanNotice /> : <PhysicianReviewCard plan={currentPlan} />}
      <PlanMetadata plan={currentPlan} />
      {currentPlan.physician_user_visible_notes ? (
        <PlanNotice message={currentPlan.physician_user_visible_notes} title="یادداشت پزشک" />
      ) : null}
      {currentPlan.physician_change_summary.length > 0 ? (
        <PlanChangeSummary changes={currentPlan.physician_change_summary} />
      ) : null}
      <PlanWarnings codes={currentPlan.warning_codes} />

      <DisclosureCard defaultExpanded={false} style={styles.planDisclosure} title="برنامه تغذیه">
        <BudgetLedger plan={currentPlan} />
        {selectedDay !== null ? (
          <View style={styles.daysSection}>
            <DaySelector days={currentPlan.days} selectedDayIndex={selectedDayIndex} onSelect={setSelectedDayIndex} />
            <NutritionDayCard
              actionsApi={actionsApi}
              api={api}
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
        <NutritionPlanHistory
          activePlanId={activePlanId}
          history={history}
          onRetry={onHistoryRetry}
          onSelect={onHistorySelect}
          selectedPlanId={selectedPlanId}
          state={historyState}
        />
      </DisclosureCard>

      <NutritionNutrientDisclosure currentPlan={currentPlan} />
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

function PhysicianReviewCard({ plan }: { readonly plan: WeeklyPlan }) {
  const approved = plan.physician_approved && plan.review_status === "approved";
  return (
    <View style={[styles.reviewCard, approved ? styles.reviewApproved : styles.reviewPending]}>
      <View style={[styles.reviewBadge, RTL_ROW]}>
        <View style={[styles.doctorAvatar, approved && styles.doctorAvatarApproved]}>
          <Text style={styles.doctorEmoji}>🧑‍⚕️</Text>
        </View>
        <View style={styles.reviewContent}>
          <Text style={[styles.reviewTitle, approved ? styles.reviewTitleApproved : styles.reviewTitlePending]}>
            {approved ? "تأییدشده توسط پزشک" : "در انتظار بررسی پزشک"}
          </Text>
          {!approved ? <Text style={styles.reviewSubtitle}>پیش‌نویس موقت؛ نیازمند بررسی پزشک</Text> : null}
          {approved && plan.physician_approved_at ? (
            <Text style={styles.reviewSubtitle}>تاریخ تأیید: {formatPlanDateTime(plan.physician_approved_at)}</Text>
          ) : null}
        </View>
      </View>
    </View>
  );
}

function ReferencePlanNotice() {
  return (
    <View style={styles.referenceNotice}>
      <Text style={styles.referenceNoticeText}>این نسخه فقط برای مشاهده تاریخچه است و برنامه فعال تو نیست.</Text>
    </View>
  );
}

function PlanMetadata({ plan }: { readonly plan: WeeklyPlan }) {
  const references = plan.price_snapshot.references;
  const mainMeals = snapshotNumber(plan.input_snapshot, "main_meals_per_day");
  const snacks = snapshotNumber(plan.input_snapshot, "snacks_per_day");
  const mainMealsLabel = mainMeals === null ? "—" : formatNutritionNumber(mainMeals);
  const snacksLabel = snacks === null ? "—" : formatNutritionNumber(snacks);
  return (
    <View style={styles.meta}>
      <View style={[styles.metaChip, RTL_ROW]}>
        <Text style={styles.metaIcon}>📋</Text>
        <Text style={styles.metaValue}>نسخه {formatNutritionNumber(plan.revision)}</Text>
        <Text style={styles.metaTag}>{lifecycleLabel(plan.lifecycle_status)}</Text>
      </View>
      <View style={[styles.metaChip, RTL_ROW]}>
        <Text style={styles.metaIcon}>🏷️</Text>
        <Text style={styles.metaText}>
          {references !== undefined && references !== null ? "قیمت‌ها به‌روز و معتبر" : "استعلام قیمت"}
        </Text>
      </View>
      <View style={[styles.metaChip, RTL_ROW]}>
        <Text style={styles.metaIcon}>🍽️</Text>
        <Text style={styles.metaText}>چیدمان: {mainMealsLabel} وعده اصلی + {snacksLabel} میان‌وعده</Text>
      </View>
    </View>
  );
}

function PlanNotice({ message, title }: { readonly message: string; readonly title: string }) {
  return (
    <View style={styles.planNotice}>
      <Text style={styles.planNoticeTitle}>{title}</Text>
      <Text style={styles.planNoticeMessage}>{message}</Text>
    </View>
  );
}

function PlanChangeSummary({ changes }: { readonly changes: readonly { [key: string]: unknown }[] }) {
  return (
    <View style={styles.planNotice}>
      <Text style={styles.planNoticeTitle}>خلاصه تغییرات پزشک</Text>
      {changes.map((change, index) => (
        <View key={`${String(change.operation ?? change.action ?? "change")}-${index}`} style={[styles.changeRow, RTL_ROW]}>
          <Text style={styles.changeBullet}>•</Text>
          <Text style={styles.planNoticeMessage}>{String(change.operation ?? change.action ?? "تغییر برنامه")}</Text>
        </View>
      ))}
    </View>
  );
}

function BudgetLedger({ plan }: { readonly plan: WeeklyPlan }) {
  const status = plan.budget_status;
  const statusStyle = status === "within_budget"
    ? styles.ledgerValueWithin
    : status === "over_budget"
      ? styles.ledgerValueOver
      : status === "flexible_overage"
        ? styles.ledgerValueFlexible
        : styles.ledgerValue;
  const icon = status === "within_budget" ? "✅" : status === "over_budget" ? "⚠️" : "📊";
  return (
    <View accessibilityLabel="بودجه برنامه" style={styles.ledger}>
      <LedgerItem icon="🏷️" label="هزینه برآوردی هفته" value={formatNutritionPlanMoney(plan.weekly_cost_irr)} valueStyle={styles.ledgerValueCost} />
      <LedgerItem icon="👛" label="بودجه هفتگی" value={formatNutritionPlanMoney(plan.weekly_budget_irr)} valueStyle={styles.ledgerValue} />
      <LedgerItem icon={icon} label="وضعیت بودجه" value={budgetStatusLabel(status)} valueStyle={statusStyle} />
    </View>
  );
}

function LedgerItem({ icon, label, value, valueStyle }: { readonly icon: string; readonly label: string; readonly value: string; readonly valueStyle: object }) {
  return (
    <View style={[styles.ledgerItem, RTL_ROW]}>
      <Text style={styles.ledgerIcon}>{icon}</Text>
      <View style={styles.ledgerContent}>
        <Text style={styles.ledgerLabel}>{label}</Text>
        <Text style={[styles.ledgerValue, valueStyle]}>{value}</Text>
      </View>
    </View>
  );
}

function NutritionNutrientDisclosure({ currentPlan }: { readonly currentPlan: WeeklyPlan }) {
  return (
    <DisclosureCard defaultExpanded={false} style={styles.planDisclosure} title="هدف در برابر مقدار برنامه">
      <View style={styles.nutrientGrid}>
        {Object.values(currentPlan.nutrients).map((nutrient) => (
          <View key={nutrient.nutrient_code} style={styles.nutrientCard}>
            <Text style={styles.nutrientLabel}>{nutritionLabel(nutrient.nutrient_code)}</Text>
            <Text style={styles.nutrientValue}>{formatNutritionNumber(nutrient.planned)} {nutrient.unit}</Text>
            <Text style={[styles.nutrientStatus, nutrientStatusStyle(nutrient.status)]}>{nutritionStatusLabel(nutrient.status)}</Text>
            <Text style={styles.nutrientDetail}>
              {nutrient.reference_kind ? `مرجع: ${nutrient.reference_kind}` : "مرجع هدف برنامه"}
              {nutrient.data_confidence ? ` · اطمینان: ${nutrient.data_confidence}` : ""}
            </Text>
            {nutrient.difference_from_preferred !== null ? (
              <Text style={styles.nutrientDetail}>اختلاف با مقدار ترجیحی: {formatNutritionNumber(nutrient.difference_from_preferred)}</Text>
            ) : null}
          </View>
        ))}
      </View>
    </DisclosureCard>
  );
}

function snapshotNumber(snapshot: { [key: string]: unknown }, key: string): number | null {
  const value = snapshot[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function NutritionDayCard({
  actionsApi,
  api,
  canEdit,
  day,
  feedback,
  onFeedbackSaved,
  onLockChanged,
  onPlanUpdated,
  planId,
}: {
  readonly actionsApi: NutritionPlanActionsApi;
  readonly api: NutritionPlanApi;
  readonly canEdit: boolean;
  readonly day: WeeklyPlanDay;
  readonly feedback: WeeklyPlanFeedback["feedback"];
  readonly onFeedbackSaved: (result: MealFeedbackUpdateResponse) => void;
  readonly onLockChanged: (mealId: string, isLocked: boolean) => void;
  readonly onPlanUpdated: (plan: WeeklyPlan) => void;
  readonly planId: string;
}) {
  const [regenerating, setRegenerating] = useState(false);
  const [regenerateError, setRegenerateError] = useState<string | null>(null);

  async function regenerateUnlockedMeals() {
    if (!canEdit || regenerating) return;
    setRegenerating(true);
    setRegenerateError(null);
    try {
      const next = await api.partialRegenerate(planId, [day.day_index]);
      onPlanUpdated(next);
    } catch (error) {
      setRegenerateError(nutritionPlanErrorMessage(error));
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <View style={styles.dayCard}>
      <View style={styles.dailySummary}>
        <View style={styles.dailySummaryItem}>
          <Text style={styles.dailySummaryValue}>
            {formatNutritionNumber(day.nutrient_totals.energy_kcal ?? 0)} kcal
          </Text>
          <Text style={styles.dailySummaryLabel}>جمع روز</Text>
        </View>
        <View style={styles.dailySummaryItem}>
          <Text style={styles.dailySummaryValue}>{formatNutritionPlanMoney(day.cost_irr)}</Text>
          <Text style={styles.dailySummaryLabel}>هزینه</Text>
        </View>
        <View style={styles.dailySummaryItem}>
          <Text style={styles.dailySummaryValue}>{formatNutritionNumber(day.nutrient_totals.protein_g ?? 0)} g</Text>
          <Text style={styles.dailySummaryLabel}>پروتئین</Text>
        </View>
        <View style={styles.dailySummaryItem}>
          <Text style={styles.dailySummaryValue}>{formatNutritionNumber(day.nutrient_totals.carbohydrate_g ?? 0)} g</Text>
          <Text style={styles.dailySummaryLabel}>کربوهیدرات</Text>
        </View>
      </View>
      {canEdit && day.meals.some((meal) => !meal.is_locked) ? (
        <Button
          disabled={regenerating}
          label="بازسازی وعده‌های باز این روز"
          loading={regenerating}
          onPress={() => void regenerateUnlockedMeals()}
          variant="secondary"
        />
      ) : null}
      {regenerateError !== null ? <Notice message={regenerateError} variant="danger" /> : null}
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
    </View>
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
  const mealLabel = meal.name_fa ?? meal.name_en ?? "وعده غذایی";
  const mealName = meal.meal_code === null || meal.meal_code === undefined
    ? mealLabel
    : `${meal.meal_code} — ${mealLabel}`;
  const mealMacroEntries = ["energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "total_fat_g", "fibre_g", "sodium_mg", "free_sugar_g", "saturated_fat_g"].flatMap((code) => {
    const value = meal.nutrient_totals[code];
    return typeof value === "number" ? [{ code, unit: code === "energy_kcal" ? "kcal" : code.endsWith("_mg") ? "mg" : "g", value }] : [];
  });
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
      summary={`${mealRoleLabel(meal.slot_role)} · ${formatNutritionNumber(meal.nutrient_totals.energy_kcal ?? 0)} kcal · ${formatNutritionPlanMoney(meal.cost_irr)}`}
      style={styles.mealCard}
      title={mealName}
    >
      {meal.is_locked ? <Text style={styles.lockedLabel}>این وعده قفل شده است</Text> : null}
      {meal.foods.length > 0 ? (
        <View style={styles.foodStack}>
          {meal.foods.map((food) => (
            <View key={`${food.slug}-${food.food_id ?? food.item_kind}`}>
              <View style={[styles.foodRow, RTL_ROW]}>
                <Text style={styles.foodName}>{food.name_fa || food.name_en}</Text>
                <Text style={styles.foodAmount}>{formatNutritionNumber(food.grams)} گرم</Text>
              </View>
              <PreparedRecipeSummary summary={preparedRecipePresentation(food)} />
            </View>
          ))}
        </View>
      ) : <Text style={styles.bodyText}>جزئیات این وعده هنوز در دسترس نیست.</Text>}
      {mealMacroEntries.length > 0 ? (
        <View style={[styles.mealNutrients, RTL_ROW]}>
          {mealMacroEntries.map((nutrient) => (
            <View key={nutrient.code} style={styles.mealNutrient}>
              <Text style={styles.mealNutrientValue}>{formatNutritionNumber(nutrient.value)} {nutrient.unit}</Text>
              <Text style={styles.mealNutrientLabel}>{nutritionLabel(nutrient.code)}</Text>
            </View>
          ))}
        </View>
      ) : null}
      {error !== null ? <Notice message={error} variant="danger" /> : null}
      <View style={[styles.mealActions, RTL_ROW]}>
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
                style={[styles.option, RTL_ROW, selected && styles.optionSelected]}
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
    <View style={styles.pdfCta}>
      <Pressable
        accessibilityLabel="دانلود نسخه PDF برنامه غذایی"
        accessibilityRole="button"
        accessibilityState={{ busy: status === "downloading", disabled: status === "checking" || status === "downloading" || (connectivityStatus === "offline" && stored === null) }}
        disabled={status === "checking" || status === "downloading" || (connectivityStatus === "offline" && stored === null)}
        onPress={() => void (stored === null ? download() : open())}
        style={({ pressed }) => [styles.pdfPressable, RTL_ROW, pressed && styles.pdfPressed]}
      >
        <View style={styles.pdfIcon}>
          <AppIcon color={fiticianTokens.colors.aqua} name="document" size={fiticianTokens.iconSize.lg} />
        </View>
        <View style={styles.pdfContent}>
          <Text style={styles.pdfTitle}>دانلود نسخه PDF برنامه غذایی</Text>
          <Text style={styles.pdfSubtitle}>دریافت فایل چاپی کامل با روزها، عکس غذاها و جدول ماکروها</Text>
        </View>
      </Pressable>
      {status === "checking" ? <Skeleton height={4} /> : null}
      {connectivityStatus === "offline" && stored === null ? (
        <Text style={styles.pdfOffline}>برای دریافت PDF به اینترنت وصل شو.</Text>
      ) : null}
      {status === "error" ? <Notice message="دریافت یا باز کردن PDF انجام نشد؛ دوباره تلاش کن." variant="danger" /> : null}
    </View>
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
      <View style={[styles.planChoiceHeading, RTL_ROW]}>
        <Text style={[styles.planChoiceLabel, selected && styles.planChoiceLabelSelected]}>{label}</Text>
        {selected ? <Text style={styles.planChoiceActive}>برنامه فعال شما</Text> : null}
      </View>
      <Text style={[styles.planChoiceSubtitle, selected && styles.planChoiceSubtitleSelected]}>
        {formatNutritionPlanMoney(plan.weekly_cost_irr)} در هفته
      </Text>
      <View style={[styles.planChoiceMetrics, RTL_ROW]}>
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
      <Text style={styles.historyHeading}>تاریخچه نسخه‌ها</Text>
      {state.status === "offline" ? <Notice message="فهرست تاریخچه تازه‌سازی نشده است." variant="offline" /> : null}
      {history.map((version) => (
        <Card
          key={version.id}
          onPress={() => onSelect(version)}
          style={styles.historyCard}
          variant={version.id === selectedPlanId || version.id === activePlanId ? "raised" : "interactive"}
        >
          <View style={[styles.historyRow, RTL_ROW]}>
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
  const orderedDays = [...days].sort((first, second) => first.day_index - second.day_index);
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={[styles.daySelector, RTL_ROW]}
    >
      {orderedDays.map((day) => (
        <Pressable
          accessibilityRole="tab"
          accessibilityState={{ selected: day.day_index === selectedDayIndex }}
          key={`${day.day_index}-${day.plan_date}`}
          onPress={() => onSelect(day.day_index)}
          style={[styles.dayTab, day.day_index === selectedDayIndex && styles.dayTabSelected]}
        >
          <Text style={[styles.dayTabLabel, day.day_index === selectedDayIndex && styles.dayTabLabelSelected]}>
            {weekdayLabels[day.day_index] ?? `روز ${day.day_index + 1}`}
          </Text>
          <Text style={[styles.dayTabDate, day.day_index === selectedDayIndex && styles.dayTabDateSelected]}>{formatPlanDate(day.plan_date)}</Text>
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

function planHeadingEyebrow(_plan: WeeklyPlan, historical: boolean): string {
  if (historical) return "نسخه قبلی";
  return "برنامه هفتگی";
}

function lifecycleLabel(status: string): string {
  const values: Readonly<Record<string, string>> = {
    active: "فعال",
    archived: "بایگانی‌شده",
    awaiting_lab_information: "در انتظار اطلاعات آزمایش",
    changes_requested: "نیازمند تغییر",
    pending_physician_review: "در انتظار بررسی",
    physician_approved: "تأییدشده",
    physician_review_in_progress: "در حال بررسی پزشک",
    rejected: "ردشده",
  };
  return values[status] ?? status;
}

function planTitle(plan: WeeklyPlan): string {
  if (plan.plan_role === "ideal") return "برنامه ایده‌آل";
  return "برنامه غذایی تو";
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

function viewData<TData>(state: MobileViewState<TData>): TData | undefined {
  if (state.status === "loading") return undefined;
  return "data" in state ? state.data : undefined;
}

function budgetStatusLabel(value: string): string {
  if (value === "within_budget") return "در محدوده بودجه";
  if (value === "flexible_overage") return "کمی بالاتر از بودجه انعطاف‌پذیر";
  if (value === "over_budget") return "بالاتر از بودجه";
  return value;
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
  const values: Readonly<Record<string, string>> = {
    carbohydrate: "کربوهیدرات",
    carbohydrate_g: "کربوهیدرات",
    carbohydrates: "کربوهیدرات",
    calcium_mg: "کلسیم",
    energy: "انرژی",
    energy_kcal: "انرژی",
    fat: "چربی",
    fat_g: "چربی",
    fibre: "فیبر",
    fibre_g: "فیبر",
    fiber: "فیبر",
    free_sugar_g: "قند آزاد",
    goal_calories: "انرژی",
    protein: "پروتئین",
    protein_g: "پروتئین",
    saturated_fat_g: "چربی اشباع",
    sodium_mg: "سدیم",
    total_fat: "چربی کل",
    total_fat_g: "چربی کل",
  };
  return values[value] ?? value.replaceAll("_", " ");
}

function nutritionStatusLabel(value: string): string {
  const values: Readonly<Record<string, string>> = {
    above_applicable_limit: "بالاتر از حد مجاز",
    below_minimum: "کمتر از حداقل",
    below_preferred_but_acceptable: "کمتر از ترجیح، قابل‌قبول",
    below_reference_target: "شکاف نسبت به مرجع غذایی",
    data_incomplete: "داده ناکامل",
    within_target: "در محدوده",
  };
  return values[value] ?? value;
}

function nutrientStatusStyle(value: string) {
  if (value === "within_target") return styles.nutrientStatusPositive;
  if (value === "above_applicable_limit") return styles.nutrientStatusDanger;
  if (value === "data_incomplete" || value === "below_minimum" || value === "below_reference_target") {
    return styles.nutrientStatusWarning;
  }
  return styles.nutrientStatusNeutral;
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  cardTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "auto",
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  changeBullet: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  changeRow: {
    alignItems: "flex-start",
    gap: fiticianTokens.spacing[2],
  },
  dayCard: {
    gap: fiticianTokens.spacing[3],
  },
  dailySummary: {
    backgroundColor: fiticianTokens.colors.surfaceHighlight,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    direction: "rtl",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
    padding: fiticianTokens.spacing[3],
  },
  dailySummaryItem: {
    alignItems: "stretch",
    flexGrow: 1,
    flexShrink: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: "44%",
  },
  dailySummaryLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  dailySummaryValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  daySelector: {
    direction: "rtl",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    paddingBottom: fiticianTokens.spacing[1],
  },
  dayTab: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.teal,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 80,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  dayTabDate: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  dayTabLabelSelected: {
    color: fiticianTokens.colors.canvas,
  },
  dayTabSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  daysSection: {
    gap: fiticianTokens.spacing[3],
  },
  doctorAvatar: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.warningSurface,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flexShrink: 0,
    height: 56,
    justifyContent: "center",
    width: 56,
  },
  doctorEmoji: {
    fontSize: 28,
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  foodAmount: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  foodName: {
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "auto",
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  historyRevision: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
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
  historyHeading: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  historyTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  lockedLabel: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  ledger: {
    alignItems: "stretch",
    gap: fiticianTokens.spacing[2],
    width: "100%",
  },
  ledgerContent: {
    alignItems: "stretch",
    flex: 1,
    gap: 2,
    minWidth: 0,
  },
  ledgerIcon: {
    fontSize: 16,
    lineHeight: 22,
  },
  ledgerItem: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[2],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
    width: "100%",
  },
  ledgerLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  ledgerValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  ledgerValueCost: {
    color: fiticianTokens.colors.aqua,
  },
  ledgerValueFlexible: {
    color: fiticianTokens.colors.amber,
  },
  ledgerValueOver: {
    color: fiticianTokens.colors.danger,
  },
  ledgerValueWithin: {
    color: fiticianTokens.colors.success,
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
  mealNutrient: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.surface,
    borderRadius: fiticianTokens.radii.small,
    flexGrow: 0,
    flexShrink: 0,
    gap: fiticianTokens.spacing[1],
    padding: fiticianTokens.spacing[2],
    width: "47%",
  },
  mealNutrientLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  mealNutrients: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
    paddingHorizontal: fiticianTokens.spacing[3],
  },
  mealNutrientValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  mealStack: {
    gap: fiticianTokens.spacing[2],
  },
  meta: {
    alignItems: "center",
    direction: "rtl",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  metaChip: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceHighlight,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flexDirection: "row",
    flexGrow: 0,
    flexShrink: 1,
    gap: fiticianTokens.spacing[1],
    maxWidth: "100%",
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  metaIcon: {
    fontSize: 15,
    lineHeight: 18,
  },
  metaTag: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderRadius: fiticianTokens.radii.pill,
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    overflow: "hidden",
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: 2,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  metaText: {
    color: fiticianTokens.colors.mist,
    flexShrink: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  metaValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  nutrientCard: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[1],
    padding: fiticianTokens.spacing[3],
    width: "100%",
  },
  nutrientGrid: {
    alignItems: "stretch",
    flexDirection: "column",
    gap: fiticianTokens.spacing[2],
  },
  nutrientLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  nutrientDetail: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  nutrientStatus: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  nutrientStatusDanger: {
    color: fiticianTokens.colors.danger,
  },
  nutrientStatusNeutral: {
    color: fiticianTokens.colors.muted,
  },
  nutrientStatusPositive: {
    color: fiticianTokens.colors.success,
  },
  nutrientStatusWarning: {
    color: fiticianTokens.colors.amber,
  },
  nutrientValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  optionName: {
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    textAlign: "auto",
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
  pdfCta: {
    backgroundColor: fiticianTokens.colors.teal,
    borderColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    overflow: "hidden",
    width: "100%",
  },
  pdfContent: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  pdfIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.aquaAtmosphere,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 52,
    justifyContent: "center",
    width: 52,
  },
  pdfOffline: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    paddingHorizontal: fiticianTokens.spacing[4],
    paddingBottom: fiticianTokens.spacing[3],
    textAlign: "auto",
    writingDirection: "rtl",
  },
  pdfPressed: {
    opacity: 0.82,
  },
  pdfPressable: {
    alignItems: "center",
    gap: fiticianTokens.spacing[3],
    minHeight: 104,
    padding: fiticianTokens.spacing[4],
  },
  pdfSubtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  pdfTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
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
    textAlign: "auto",
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  planChoiceMetricValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
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
    textAlign: "auto",
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  planChoiceSubtitleSelected: {
    color: fiticianTokens.colors.ink,
  },
  planTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 40,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  planHeading: {
    alignItems: "stretch",
    gap: fiticianTokens.spacing[1],
  },
  planDisclosure: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.large,
    padding: 0,
  },
  planNotice: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.surfaceTranslucent,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    gap: fiticianTokens.spacing[1],
    padding: fiticianTokens.spacing[3],
  },
  planNoticeMessage: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  planNoticeTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  planStack: {
    gap: fiticianTokens.spacing[3],
  },
  referenceNotice: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.infoSurface,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    padding: fiticianTokens.spacing[3],
  },
  referenceNoticeText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  reviewApproved: {
    backgroundColor: fiticianTokens.colors.successSurface,
    borderColor: fiticianTokens.colors.success,
  },
  doctorAvatarApproved: {
    backgroundColor: fiticianTokens.colors.successSurface,
    borderColor: fiticianTokens.colors.success,
  },
  reviewBadge: {
    alignItems: "center",
    gap: fiticianTokens.spacing[3],
  },
  reviewCard: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.warningSurface,
    borderColor: fiticianTokens.colors.amber,
    borderRadius: fiticianTokens.radii.extraLarge,
    borderWidth: 1,
    padding: fiticianTokens.spacing[3],
  },
  reviewContent: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  reviewPending: {
    backgroundColor: fiticianTokens.colors.warningSurface,
    borderColor: fiticianTokens.colors.amber,
  },
  reviewSubtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  reviewTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  reviewTitleApproved: {
    color: fiticianTokens.colors.success,
  },
  reviewTitlePending: {
    color: fiticianTokens.colors.amber,
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
    textAlign: "auto",
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
    textAlign: "auto",
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  preparedRecipeTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
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
});
