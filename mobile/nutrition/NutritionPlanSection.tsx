import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { ApiError } from "@fitician/core";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { nutritionKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { Button, Card, EmptyState, Notice, Skeleton } from "../ui/components";
import { getMobileViewState, type MobileViewState } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import { canGenerateNutritionEstimate, formatNutritionNumber } from "./nutritionModel";
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
  classifyNutritionGenerationOutcome,
  formatNutritionPlanMoney,
  getNutritionPlanStatus,
  isNutritionPlanExecutable,
  preparedRecipePresentation,
  selectNutritionPlan,
  type PreparedRecipePresentation,
} from "./nutritionPlanModel";
import {
  ExpoNutritionPlanPdfStore,
  type StoredNutritionPlanPdf,
} from "./nutritionPlanPdfStore";
import type { SafetyDecision } from "./nutritionApi";

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

export function NutritionPlanSection({ safety }: { readonly safety: SafetyDecision | null }) {
  const auth = useMobileAuth();
  const queryClient = useQueryClient();
  const connectivityStatus = useConnectivityStatus();
  const api = useMemo(
    () => createNutritionPlanApi(auth.request, auth.download),
    [auth.download, auth.request],
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
          connectivityStatus={connectivityStatus}
          historical={historical}
          pdfStore={pdfStore}
          plan={displayedPlan}
          stale={offline || (selectedPlanId === null && (activeState.status === "stale" || latestState.status === "stale"))}
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
        disabled={offline || selectBundle.isPending}
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
  api,
  connectivityStatus,
  historical,
  pdfStore,
  plan,
  stale,
}: {
  readonly api: NutritionPlanApi;
  readonly connectivityStatus: ConnectivityStatus;
  readonly historical: boolean;
  readonly pdfStore: ExpoNutritionPlanPdfStore;
  readonly plan: WeeklyPlan;
  readonly stale: boolean;
}) {
  const status = getNutritionPlanStatus(plan, historical);
  const executable = isNutritionPlanExecutable(plan, historical);
  const [selectedDayIndex, setSelectedDayIndex] = useState(0);
  const selectedDay = plan.days[selectedDayIndex] ?? plan.days[0] ?? null;

  useEffect(() => {
    setSelectedDayIndex(0);
  }, [plan.id, plan.revision]);

  if (!plan.is_user_visible) {
    return <Notice message="این نسخه برای نمایش عضو آماده نیست." variant="info" />;
  }

  return (
    <View style={styles.planStack}>
      <Card style={styles.planCard}>
        <View style={styles.planHeading}>
          <View style={styles.planCopy}>
            <Text style={styles.eyebrow}>{historical ? "نسخه قبلی" : "آخرین نسخه"}</Text>
            <Text style={styles.planTitle}>برنامه غذایی تو</Text>
          </View>
          <StatusBadge status={status} />
        </View>
        {stale ? <Notice message="این برنامه قدیمی است؛ قبل از خرید یا تصمیم جدید، اتصال را بررسی کن." variant="offline" /> : null}
        {historical ? <Notice message="این نسخه فقط برای مشاهده تاریخچه است و برنامه فعال تو نیست." variant="info" /> : null}
        {!executable && !historical ? <PlanReviewNotice status={status} /> : null}
        <View style={styles.statsGrid}>
          <PlanStat label="هزینه هفتگی" value={formatNutritionPlanMoney(plan.weekly_cost_irr)} />
          <PlanStat label="بودجه هفتگی" value={formatNutritionPlanMoney(plan.weekly_budget_irr)} />
          <PlanStat label="تعداد روز" value={formatNutritionNumber(plan.days.length)} />
          <PlanStat label="نسخه" value={formatNutritionNumber(plan.revision)} />
        </View>
        {plan.physician_user_visible_notes ? (
          <Notice message={plan.physician_user_visible_notes} title="یادداشت پزشک" variant="info" />
        ) : null}
        {plan.warning_codes.length > 0 ? (
          <Notice message={plan.warning_codes.join("\n")} title="هشدارهای برنامه" variant="warning" />
        ) : null}
        <SummaryRow label="وضعیت بودجه" value={budgetStatusLabel(plan.budget_status)} />
        <SummaryRow label="شروع برنامه" value={formatPlanDate(plan.start_date)} />
      </Card>

      {selectedDay !== null ? (
        <View style={styles.daysSection}>
          <Text style={styles.sectionTitle}>روزهای برنامه</Text>
          <DaySelector days={plan.days} selectedDayIndex={selectedDayIndex} onSelect={setSelectedDayIndex} />
          <NutritionDayCard day={selectedDay} />
        </View>
      ) : (
        <Notice message="برای این نسخه هنوز روزی ثبت نشده است." variant="info" />
      )}
      <NutritionPlanPdf api={api} connectivityStatus={connectivityStatus} pdfStore={pdfStore} planId={plan.id} />
    </View>
  );
}

function NutritionDayCard({ day }: { readonly day: WeeklyPlanDay }) {
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
        {day.meals.map((meal) => <NutritionMealCard key={meal.id} meal={meal} />)}
      </View>
    </Card>
  );
}

function NutritionMealCard({ meal }: { readonly meal: WeeklyPlanMeal }) {
  const mealName = meal.name_fa ?? meal.name_en ?? meal.meal_code ?? "وعده غذایی";
  return (
    <View style={styles.mealCard}>
      <View style={styles.mealHeading}>
        <View style={styles.mealCopy}>
          <Text style={styles.mealTitle}>{mealName}</Text>
          {meal.name_en && meal.name_en !== meal.name_fa ? <Text style={styles.mealEnglish}>{meal.name_en}</Text> : null}
        </View>
        <Text style={styles.mealMeta}>{mealRoleLabel(meal.slot_role)} · {formatNutritionPlanMoney(meal.cost_irr)}</Text>
      </View>
      {meal.is_locked ? <Text style={styles.lockedLabel}>این وعده قفل شده است</Text> : null}
      {meal.foods.length > 0 ? (
        <View style={styles.foodStack}>
          {meal.foods.map((food) => (
            <View key={`${food.slug}-${food.food_id ?? food.item_kind}`}>
              <View style={styles.foodRow}>
                <Text style={styles.foodAmount}>{formatNutritionNumber(food.grams)} گرم</Text>
                <Text style={styles.foodName}>{food.name_fa || food.name_en}</Text>
              </View>
              <PreparedRecipeSummary summary={preparedRecipePresentation(food)} />
            </View>
          ))}
        </View>
      ) : <Text style={styles.bodyText}>جزئیات این وعده هنوز در دسترس نیست.</Text>}
    </View>
  );
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
      <Text style={styles.cardTitle}>انتخاب نسخه برنامه</Text>
      <Text style={styles.bodyText}>هر دو نسخه از همان داده‌های مرجع تأییدشده استفاده می‌کنند؛ یکی را به عنوان برنامه فعال انتخاب کن.</Text>
      <View style={styles.choiceStack}>
        <PlanChoice
          disabled={disabled}
          label="نسخه اقتصادی"
          selected={selectedRole === "budget"}
          subtitle={formatNutritionPlanMoney(bundle.budget_plan.weekly_cost_irr)}
          onPress={() => onSelect("budget")}
        />
        <PlanChoice
          disabled={disabled}
          label="نسخه ایده‌آل"
          selected={selectedRole === "ideal"}
          subtitle={formatNutritionPlanMoney(bundle.ideal_plan.weekly_cost_irr)}
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
  selected,
  subtitle,
}: {
  readonly disabled: boolean;
  readonly label: string;
  readonly onPress: () => void;
  readonly selected: boolean;
  readonly subtitle: string;
}) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ checked: selected, disabled }}
      disabled={disabled}
      onPress={onPress}
      style={[styles.planChoice, selected && styles.planChoiceSelected]}
    >
      <Text style={[styles.planChoiceLabel, selected && styles.planChoiceLabelSelected]}>{label}</Text>
      <Text style={[styles.planChoiceSubtitle, selected && styles.planChoiceSubtitleSelected]}>{subtitle}</Text>
    </Pressable>
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
  return <Notice message={`${generationMessages[status]}${result.reason_codes.length > 0 ? ` (${result.reason_codes.join(", ")})` : ""}`} variant="warning" />;
}

function PlanReviewNotice({ status }: { readonly status: ReturnType<typeof getNutritionPlanStatus> }) {
  if (status === "pending_review" || status === "physician_review") {
    return <Notice message="این پیش‌نویس تا بررسی پزشک برنامه نهایی نیست و برای خرید نهایی قابل اتکا نیست." variant="warning" />;
  }
  if (status === "changes_requested") {
    return <Notice message="پزشک برای ادامه اصلاح یا اطلاعات بیشتری خواسته است." variant="warning" />;
  }
  if (status === "rejected") return <Notice message="این نسخه توسط پزشک تأیید نشده و قابل اجرا نیست." variant="danger" />;
  return <Notice message="این نسخه هنوز برای استفاده نهایی فعال نشده است." variant="info" />;
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

function budgetStatusLabel(value: string): string {
  if (value === "within_budget") return "در محدوده بودجه";
  if (value === "flexible_overage") return "با مازاد انعطاف‌پذیر";
  if (value === "over_budget") return "بیش از بودجه";
  if (value === "unconstrained") return "بدون محدودیت بودجه";
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
  return value;
}

function nutritionLabel(value: string): string {
  if (value === "energy" || value === "calories") return "انرژی";
  if (value === "protein") return "پروتئین";
  if (value === "carbohydrate" || value === "carbohydrates") return "کربوهیدرات";
  if (value === "fat") return "چربی";
  if (value === "fibre" || value === "fiber") return "فیبر";
  return value;
}

function nutritionPlanErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.message !== "Request failed") return error.message;
  return "عملیات برنامه غذایی انجام نشد؛ اتصال را بررسی کن و دوباره تلاش کن.";
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
  dayCard: {
    gap: fiticianTokens.spacing[3],
  },
  dayCost: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "left",
    writingDirection: "rtl",
  },
  dayCopy: {
    alignItems: "flex-end",
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
    flexDirection: "row-reverse",
    justifyContent: "space-between",
  },
  daySelector: {
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[2],
    paddingBottom: fiticianTokens.spacing[1],
  },
  dayTab: {
    alignItems: "flex-end",
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
    textAlign: "left",
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
    flexDirection: "row-reverse",
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
    alignItems: "flex-end",
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
    textAlign: "left",
    writingDirection: "rtl",
  },
  historyRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
  },
  historySection: {
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
    padding: fiticianTokens.spacing[3],
  },
  mealCopy: {
    alignItems: "flex-end",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  mealEnglish: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "ltr",
  },
  mealHeading: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[2],
    justifyContent: "space-between",
  },
  mealMeta: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "left",
    writingDirection: "rtl",
  },
  mealStack: {
    gap: fiticianTokens.spacing[2],
  },
  mealTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
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
    flexDirection: "row-reverse",
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
  pdfActions: {
    gap: fiticianTokens.spacing[2],
  },
  pdfCard: {
    gap: fiticianTokens.spacing[3],
  },
  planCard: {
    gap: fiticianTokens.spacing[3],
  },
  planChoice: {
    alignItems: "flex-end",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[1],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    padding: fiticianTokens.spacing[3],
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
    alignItems: "flex-end",
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
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  planStack: {
    gap: fiticianTokens.spacing[3],
  },
  planStat: {
    alignItems: "flex-end",
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
    flexDirection: "row-reverse",
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
    flexDirection: "row-reverse",
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
    gap: fiticianTokens.spacing[3],
    marginBottom: fiticianTokens.spacing[3],
  },
  sectionCard: {
    gap: fiticianTokens.spacing[3],
  },
  sectionHeading: {
    alignItems: "flex-end",
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
    flexDirection: "row-reverse",
    justifyContent: "space-between",
  },
  statsGrid: {
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
});
