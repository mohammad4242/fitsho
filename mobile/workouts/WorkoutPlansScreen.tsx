import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { WorkoutGenerationMethod } from "@fitician/core/profile";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Alert, Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { useEffect, useMemo, useRef, useState } from "react";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { profileKeys, workoutKeys } from "../data/queryKeys";
import { createProfileApi } from "../profile/profileApi";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import {
  AppIcon,
  Button,
  Card,
  EmptyState,
  Notice,
  Skeleton,
  SegmentedControl,
} from "../ui/components";
import { Screen } from "../ui/layout";
import { formatPersianNumber } from "../ui/locale";
import { getMobileViewState, type MobileViewState } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import { languageForDirection, type MobileLanguage } from "../ui/rtl";
import {
  createWorkoutPlanApi,
  type WorkoutDay,
  type WorkoutPlan,
  type WorkoutPlanExercise,
  type WorkoutPlanVersionSummary,
} from "./workoutApi";
import { createWorkoutCycleApi } from "./workoutCycleApi";
import {
  classifyWorkoutGenerationError,
  findPendingWorkoutPlanId,
  getUserVisibleWorkoutWarnings,
  getWorkoutPlanSummaryStatus,
  isWorkoutPlanExecutable,
  workoutPlanAverageDuration,
} from "./workoutModel";
import {
  ExpoWorkoutPlanPdfStore,
  type StoredWorkoutPlanPdf,
} from "./workoutPdfStore";
import {
  CompletionFeedbackDetails,
  CompletionFeedbackToolCell,
  useCompletionFeedbackController,
  WorkoutCyclePanel,
  type WorkoutReplacementRequest,
} from "./WorkoutCyclePanel";
import type { WorkoutGenerationErrorKind } from "./workoutModel";
import { ExerciseMedia } from "../exercises/ExerciseMedia";

type PdfStatus = "downloading" | "error" | "idle" | "ready";

const generationErrorMessages: Record<WorkoutGenerationErrorKind, string> = {
  cooldown: "ساخت برنامه به‌تازگی انجام شده است؛ کمی بعد دوباره تلاش کن.",
  failed: "ساخت برنامه انجام نشد. وضعیت پروفایل و اتصال اینترنت را بررسی کن.",
  in_progress: "ساخت یک برنامهٔ دیگر در حال انجام است؛ کمی بعد وضعیت برنامه را بررسی کن.",
  unsupported: "با تنظیمات فعلی، برنامه امن و قابل ساختی پیدا نشد. پروفایل تمرینی را بررسی کن.",
};

export function WorkoutPlansScreen() {
  const auth = useMobileAuth();
  const params = useLocalSearchParams<{ cycleId?: string | string[]; planId?: string | string[] }>();
  const queryClient = useQueryClient();
  const connectivityStatus = useConnectivityStatus();
  const api = useMemo(
    () => createWorkoutPlanApi(auth.request, auth.download),
    [auth.download, auth.request],
  );
  const cycleApi = useMemo(() => createWorkoutCycleApi(auth.request), [auth.request]);
  const profileApi = useMemo(() => createProfileApi(auth.request), [auth.request]);
  const pdfStore = useMemo(() => new ExpoWorkoutPlanPdfStore(), []);
  const planTargetId = firstParam(params.planId);
  const cycleTargetId = firstParam(params.cycleId);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(planTargetId ?? null);
  const [generationError, setGenerationError] = useState<WorkoutGenerationErrorKind | null>(null);
  const [replacementRequest, setReplacementRequest] = useState<WorkoutReplacementRequest | null>(null);
  const [generationMethod, setGenerationMethod] = useState<WorkoutGenerationMethod>("fitsho_coach");
  const [generationMethodError, setGenerationMethodError] = useState<string | null>(null);
  const [deletingPlanId, setDeletingPlanId] = useState<string | null>(null);
  const [deletionError, setDeletionError] = useState<string | null>(null);
  const [hiddenDeletedPlanIds, setHiddenDeletedPlanIds] = useState<ReadonlySet<string>>(() => new Set());
  const [generatedForegroundPlan, setGeneratedForegroundPlan] = useState<WorkoutPlan | null>(null);

  useEffect(() => {
    setSelectedPlanId(planTargetId ?? null);
  }, [planTargetId]);

  const activeQuery = useQuery({
    queryFn: api.getActive,
    queryKey: workoutKeys.plan("active"),
  });
  const historyQuery = useQuery({
    queryFn: api.getHistory,
    queryKey: workoutKeys.plans(),
  });
  const profileQuery = useQuery({
    queryFn: profileApi.getProfile,
    queryKey: profileKeys.current(),
  });
  const history = (historyQuery.data ?? []).filter((version) => !hiddenDeletedPlanIds.has(version.id));
  const pendingPlanId = findPendingWorkoutPlanId(history);
  const pendingQuery = useQuery({
    enabled: pendingPlanId !== null,
    queryFn: () => api.get(pendingPlanId as string),
    queryKey: workoutKeys.plan(pendingPlanId ?? "pending"),
  });
  const selectedQuery = useQuery({
    enabled: selectedPlanId !== null,
    queryFn: () => api.get(selectedPlanId as string),
    queryKey: workoutKeys.plan(selectedPlanId ?? "selected"),
  });
  const activeState = getMobileViewState(activeQuery, {
    connectivityStatus,
    isEmpty: (data) => data === null,
  });
  const historyState = getMobileViewState(historyQuery, {
    connectivityStatus,
    isEmpty: (data) => data.length === 0,
  });
  const pendingState = getMobileViewState(pendingQuery, { connectivityStatus });
  const selectedState = getMobileViewState(selectedQuery, { connectivityStatus });
  const activePlan = viewData(activeState);
  const pendingPlan = pendingPlanId === null ? undefined : viewData(pendingState);
  const selectedPlan = selectedPlanId === null ? undefined : viewData(selectedState);
  const loadedCurrentPlan = pendingPlanId !== null ? pendingPlan : activePlan;
  const currentPlan = generatedForegroundPlan
    ?? loadedCurrentPlan;
  const currentPlanId = currentPlan?.id ?? pendingPlanId;
  const displayedPlan = selectedPlanId === null ? currentPlan : selectedPlan;
  const isViewingHistorical = selectedPlanId !== null && selectedPlanId !== currentPlanId;
  const profileGenerationMethod = profileQuery.data?.workout_generation_method;
  const generationMethodMutation = useMutation({
    mutationFn: (method: WorkoutGenerationMethod) => profileApi.updateProfile({ workout_generation_method: method }),
    onSuccess: (profile) => {
      queryClient.setQueryData(profileKeys.current(), profile);
    },
  });
  const generation = useMutation({
    mutationFn: () => api.generate(),
    onError: (error: unknown) => setGenerationError(classifyWorkoutGenerationError(error)),
    onSuccess: async (result) => {
      setGenerationError(null);
      setSelectedPlanId(null);
      setGeneratedForegroundPlan(result.plan);
      queryClient.setQueryData(workoutKeys.plan(result.plan.id), result.plan);
      if (result.plan.status === "active") {
        queryClient.setQueryData(workoutKeys.plan("active"), result.plan);
      } else {
        queryClient.setQueryData(workoutKeys.plan("active"), null);
        queryClient.setQueryData(workoutKeys.plan("pending"), result.plan);
      }
      await Promise.all([
        activeQuery.refetch(),
        historyQuery.refetch(),
        pendingPlanId === null ? Promise.resolve() : pendingQuery.refetch(),
      ]);
    },
  });
  const deletion = useMutation({
    mutationFn: (planId: string) => api.deletePlan(planId),
    mutationKey: ["workout-plan-deletion"],
    onError: () => {
      setDeletionError("حذف نسخه قدیمی برنامه انجام نشد؛ دوباره تلاش کن.");
    },
    onSuccess: async (_result, planId) => {
      setDeletionError(null);
      setHiddenDeletedPlanIds((current) => new Set(current).add(planId));
      if (selectedPlanId === planId) setSelectedPlanId(null);
      queryClient.setQueryData<WorkoutPlanVersionSummary[]>(
        workoutKeys.plans(),
        (current) => current?.filter((version) => version.id !== planId),
      );
      queryClient.removeQueries({ exact: true, queryKey: workoutKeys.plan(planId) });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: workoutKeys.plans() }),
        queryClient.invalidateQueries({ queryKey: workoutKeys.plan("active") }),
      ]);
    },
    onSettled: () => setDeletingPlanId(null),
  });

  useEffect(() => {
    if (!generationMethodMutation.isPending) {
      setGenerationMethod(profileGenerationMethod ?? "fitsho_coach");
    }
  }, [generationMethodMutation.isPending, profileGenerationMethod]);

  useEffect(() => {
    if (generatedForegroundPlan !== null && loadedCurrentPlan?.id === generatedForegroundPlan.id) {
      setGeneratedForegroundPlan(null);
    }
  }, [generatedForegroundPlan, loadedCurrentPlan?.id]);

  const pendingLoading = pendingPlanId !== null && pendingState.status === "loading";
  const loading = activeState.status === "loading"
    || (activePlan === undefined && historyState.status === "loading")
    || (selectedPlanId === null && pendingLoading && generatedForegroundPlan === null);
  const activeLoadError = activeState.status === "error"
    && activePlan === undefined
    && currentPlan === undefined;
  const activeOffline = activeState.status === "offline"
    && activePlan === undefined
    && currentPlan === undefined;
  const canUpdateDisplayedPlan = selectedPlanId === null
    && !loading
    && !activeLoadError
    && !activeOffline
    && displayedPlan !== undefined
    && displayedPlan !== null
    && displayedPlan.status !== "failed"
    && displayedPlan.days.length > 0;

  function retry() {
    void Promise.all([activeQuery.refetch(), historyQuery.refetch()]);
  }

  function startGeneration() {
    if (generation.isPending) return;
    setGenerationError(null);
    generation.mutate();
  }

  function selectHistoryVersion(version: WorkoutPlanVersionSummary) {
    setReplacementRequest(null);
    if (version.id === currentPlanId) {
      setSelectedPlanId(null);
      return;
    }
    setSelectedPlanId(version.id);
  }

  function confirmDelete(version: WorkoutPlanVersionSummary) {
    if (!isDeletableWorkoutPlanVersion(version) || deletingPlanId === version.id) return;
    Alert.alert(
      "حذف نسخه قدیمی",
      "این نسخه از تاریخچه برنامه‌های تمرینی شما حذف شود؟",
      [
        { text: "انصراف", style: "cancel" },
        {
          text: "حذف",
          style: "destructive",
          onPress: () => {
            setDeletionError(null);
            setDeletingPlanId(version.id);
            deletion.mutate(version.id);
          },
        },
      ],
    );
  }

  function startReplacement(exerciseId: string) {
    setReplacementRequest((current) => ({
      exerciseId,
      requestId: (current?.requestId ?? 0) + 1,
    }));
  }

  function changeGenerationMethod(method: WorkoutGenerationMethod) {
    if (generationMethodMutation.isPending || method === generationMethod) return;
    const previousMethod = generationMethod;
    setGenerationMethod(method);
    setGenerationMethodError(null);
    generationMethodMutation.mutate(method, {
      onError: () => {
        setGenerationMethod(previousMethod);
        setGenerationMethodError("ذخیره روش ساخت برنامه انجام نشد؛ دوباره تلاش کن.");
      },
      onSuccess: (profile) => {
        setGenerationMethod(profile.workout_generation_method ?? method);
      },
    });
  }

  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <View testID="workout-plan-controls" style={styles.planControlsSection}>
        <GenerationMethodSelector
          error={generationMethodError}
          saving={generationMethodMutation.isPending}
          selected={generationMethod}
          onSelect={changeGenerationMethod}
        />
        {canUpdateDisplayedPlan ? (
          <Button
            disabled={generation.isPending}
            label="به‌روزرسانی برنامه"
            loading={generation.isPending}
            onPress={startGeneration}
            style={styles.updateButton}
            variant="primary"
          />
        ) : null}
      </View>

      {displayedPlan !== undefined && displayedPlan !== null ? (
        <PlanOverview historical={isViewingHistorical} plan={displayedPlan} />
      ) : (
        <View style={styles.pageHeader}>
          <View style={styles.pageHeaderCopy}>
            <Text accessibilityRole="header" style={styles.pageTitle}>برنامه تمرینی من</Text>
          </View>
          <View accessibilityLabel={`${formatPersianNumber(profileQuery.data?.plan_duration_weeks ?? 4, { maximumFractionDigits: 0 })} هفته`} style={styles.durationBadge}>
            <Text style={styles.durationValue}>{formatPersianNumber(profileQuery.data?.plan_duration_weeks ?? 4, { maximumFractionDigits: 0 })}</Text>
            <Text style={styles.durationLabel}>هفته</Text>
          </View>
        </View>
      )}

      {connectivityStatus === "offline" && displayedPlan !== undefined ? (
        <PlanInlineNotice message="اتصال اینترنت برقرار نیست؛ آخرین برنامهٔ ذخیره‌شده نمایش داده می‌شود." variant="offline" />
      ) : null}
      {loading ? <PlanSkeleton /> : null}
      {activeLoadError ? (
        <Notice
          actionLabel="تلاش دوباره"
          message="دریافت برنامه تمرینی انجام نشد."
          onAction={retry}
          variant="danger"
        />
      ) : null}
      {activeOffline ? <Notice message="برای دریافت برنامه تمرینی به اینترنت وصل شو." variant="offline" /> : null}
      {activeState.status === "error" && activePlan !== undefined ? (
        <PlanInlineNotice message="به‌روزرسانی برنامه انجام نشد؛ نسخهٔ ذخیره‌شده نمایش داده می‌شود." variant="warning" />
      ) : null}

      {!loading && !activeLoadError && !activeOffline && displayedPlan !== undefined && displayedPlan !== null ? (
        <PlanView
          historical={isViewingHistorical}
          onStartReplacement={startReplacement}
          plan={displayedPlan}
          pending={displayedPlan.status === "pending_review"}
        />
      ) : null}

      {!loading && !activeLoadError && !activeOffline && displayedPlan !== null && displayedPlan !== undefined
        && isWorkoutPlanExecutable(displayedPlan, isViewingHistorical) ? (
        <WorkoutCyclePanel
          expectedCycleId={cycleTargetId}
          plan={displayedPlan}
          replacementRequest={replacementRequest}
        />
      ) : null}

      {pendingPlanId !== null && pendingPlan === undefined && !pendingLoading && selectedPlanId === null ? (
        <Notice
          actionLabel="تلاش دوباره"
          message="یک برنامه در انتظار تأیید مربی است؛ جزئیات آن فعلاً در دسترس نیست."
          onAction={() => void pendingQuery.refetch()}
          variant={pendingState.status === "offline" ? "offline" : "warning"}
        />
      ) : null}

      {!loading && !activeLoadError && !activeOffline && currentPlan === null && pendingPlanId === null ? (
        <EmptyState
          actionLabel={generation.isPending ? "در حال ساخت برنامه" : "ساخت برنامه تمرینی"}
          onAction={startGeneration}
          title="هنوز برنامهٔ فعالی نداری"
        >
          <Text style={styles.emptyBody}>با تکمیل پروفایل تمرینی می‌توانی برنامهٔ متناسب با شرایطت بسازی.</Text>
        </EmptyState>
      ) : null}

      {generationError !== null ? (
        <Notice
          actionLabel={generationError === "cooldown" ? undefined : "تلاش دوباره"}
          message={generationErrorMessages[generationError]}
          onAction={generationError === "cooldown" || generationError === "in_progress" ? undefined : startGeneration}
          variant={generationError === "unsupported" ? "warning" : "danger"}
        />
      ) : null}

      {selectedPlanId !== null && selectedState.status === "loading" ? <Skeleton height={300} /> : null}
      {selectedPlanId !== null && selectedState.status === "error" && selectedPlan === undefined ? (
        <Notice
          actionLabel="تلاش دوباره"
          message="نسخهٔ انتخاب‌شده دریافت نشد."
          onAction={() => void selectedQuery.refetch()}
          variant="danger"
        />
      ) : null}

      {!loading && !activeLoadError && !activeOffline && displayedPlan !== undefined && displayedPlan !== null ? (
        <WorkoutPlanTools
          api={api}
          awaitingCoachApproval={displayedPlan.status === "pending_review"}
          connectivityStatus={connectivityStatus}
          cycleApi={cycleApi}
          fallbackDurationWeeks={displayedPlan.plan_duration_weeks}
          pdfStore={pdfStore}
          plan={displayedPlan}
        />
      ) : null}

      <WorkoutHistory
        currentPlanId={currentPlanId}
        deletionError={deletionError}
        deletingPlanId={deletingPlanId}
        history={history}
        historyState={historyState}
        onDelete={confirmDelete}
        onRetry={() => void historyQuery.refetch()}
        onSelect={selectHistoryVersion}
        isViewingHistorical={isViewingHistorical}
        onReturnToCurrent={() => {
          setReplacementRequest(null);
          setSelectedPlanId(null);
        }}
        selectedPlanId={selectedPlanId}
      />
    </Screen>
  );
}

function PlanOverview({
  historical,
  plan,
}: {
  readonly historical: boolean;
  readonly plan: WorkoutPlan;
}) {
  return (
    <View style={styles.planOverview} testID={`workout-plan-overview-${plan.id}`}>
      <View style={styles.pageHeader}>
        <View style={styles.pageHeaderCopy}>
          <Text accessibilityRole="header" style={styles.pageTitle}>برنامه تمرینی من</Text>
        </View>
        <View accessibilityLabel={`${formatPersianNumber(plan.plan_duration_weeks, { maximumFractionDigits: 0 })} هفته`} style={styles.durationBadge}>
          <Text style={styles.durationValue}>{formatPersianNumber(plan.plan_duration_weeks, { maximumFractionDigits: 0 })}</Text>
          <Text style={styles.durationLabel}>هفته</Text>
        </View>
      </View>
      <PlanContextStrip historical={historical} plan={plan} />
      <CoachReviewBanner historical={historical} plan={plan} />
      {historical ? <Text style={styles.readOnlyNotice}>این نسخه فقط برای مشاهده است.</Text> : null}
    </View>
  );
}

function PlanContextStrip({
  historical,
  plan,
}: {
  readonly historical: boolean;
  readonly plan: WorkoutPlan;
}) {
  const status = getWorkoutPlanSummaryStatus(plan, historical);
  const statusLabel = status === "active" ? "فعال" : status === "pending" ? "در انتظار مربی" : "غیرفعال";
  const statusStyle = status === "active"
    ? styles.contextValueActive
    : status === "pending" ? styles.contextValuePending : styles.contextValueInactive;
  const averageDuration = workoutPlanAverageDuration(plan);
  const cells = [
    { label: "برنامه فعلی", value: statusLabel, valueStyle: statusStyle },
    { label: "پیش‌برنامه", value: workoutGenerationSourceLabel(plan.generation_source), valueStyle: undefined },
    { label: "روزهای تمرین", value: `${formatPersianNumber(plan.days.length, { maximumFractionDigits: 0 })} روز تمرین`, valueStyle: undefined },
    { label: "زمان جلسه", value: averageDuration === null ? "—" : `${formatPersianNumber(averageDuration, { maximumFractionDigits: 0 })} دقیقه`, valueStyle: undefined },
  ];

  return (
    <View accessibilityLabel="خلاصه برنامه" style={styles.contextStrip}>
      {cells.map((cell, index) => (
        <View key={cell.label} style={[styles.contextCell, index > 0 && styles.contextCellDivided]}>
          <Text numberOfLines={2} style={styles.contextLabel}>{cell.label}</Text>
          <Text numberOfLines={2} style={[styles.contextValue, cell.valueStyle]}>{cell.value}</Text>
        </View>
      ))}
    </View>
  );
}

function workoutGenerationSourceLabel(source: WorkoutPlan["generation_source"]): string {
  if (source === "ai") return "هوش مصنوعی";
  if (source === "internal_engine") return "موتور داخلی";
  return "—";
}

function CoachReviewBanner({
  historical,
  plan,
}: {
  readonly historical: boolean;
  readonly plan: WorkoutPlan;
}) {
  const review = plan.coach_review;
  if (historical) {
    return (
      <View accessibilityRole="text" style={[styles.reviewBanner, styles.reviewBannerHistory]}>
        <View style={styles.reviewIndicator} />
        <Text style={styles.reviewText}>در حال مشاهده نسخه قبلی</Text>
      </View>
    );
  }
  if (review?.state === "pending_coach_review" || plan.status === "pending_review") {
    return (
      <View accessibilityRole="text" style={styles.reviewBanner}>
        <View style={styles.reviewIndicator} />
        <Text style={styles.reviewText}>در انتظار تایید مربی</Text>
      </View>
    );
  }
  if (review?.state === "coach_approved") {
    const coach = review.coach_display_name ?? "مربی فیتشو";
    return (
      <View accessibilityRole="text" style={[styles.reviewBanner, styles.reviewBannerApproved]}>
        <Text style={[styles.reviewIndicator, styles.reviewIndicatorApproved]}>✓</Text>
        <View style={styles.reviewCopy}>
          <Text style={styles.reviewText}>تأییدشده توسط {coach}</Text>
          {plan.coach_review?.coach_note ? <Text style={styles.reviewNote}>{plan.coach_review.coach_note}</Text> : null}
        </View>
      </View>
    );
  }
  if (review?.state === "coach_rejected") {
    return (
      <View accessibilityRole="text" style={[styles.reviewBanner, styles.reviewBannerRejected]}>
        <Text style={[styles.reviewIndicator, styles.reviewIndicatorRejected]}>!</Text>
        <View style={styles.reviewCopy}>
          <Text style={styles.reviewText}>نیاز به اصلاح طبق نظر مربی</Text>
          {plan.coach_review?.coach_note ? <Text style={styles.reviewNote}>{plan.coach_review.coach_note}</Text> : null}
        </View>
      </View>
    );
  }
  return (
    <View accessibilityRole="text" style={[styles.reviewBanner, styles.reviewBannerApproved]}>
      <Text style={[styles.reviewIndicator, styles.reviewIndicatorApproved]}>✓</Text>
      <Text style={styles.reviewText}>برنامه آماده اجراست</Text>
    </View>
  );
}

type PlanInlineNoticeVariant = "danger" | "info" | "offline" | "warning";

function PlanInlineNotice({
  message,
  variant,
}: {
  readonly message: string;
  readonly variant: PlanInlineNoticeVariant;
}) {
  const accentStyle = variant === "danger"
    ? styles.inlineNoticeDanger
    : variant === "offline" || variant === "warning" ? styles.inlineNoticeWarning : styles.inlineNoticeInfo;
  return (
    <View style={[styles.inlineNotice, accentStyle]}>
      <Text style={styles.inlineNoticeText}>{message}</Text>
    </View>
  );
}

function GenerationMethodSelector({
  error,
  saving,
  selected,
  onSelect,
}: {
  readonly error: string | null;
  readonly saving: boolean;
  readonly selected: WorkoutGenerationMethod;
  readonly onSelect: (method: WorkoutGenerationMethod) => void;
}) {
  return (
    <View style={styles.generationMethodSection}>
      <Text style={styles.selectorTitle}>چه کسی برنامه‌ات را بنویسد؟</Text>
      <SegmentedControl
        accessibilityLabel="روش ساخت برنامه"
        disabled={saving}
        onChange={(value) => onSelect(value as WorkoutGenerationMethod)}
        options={[
          { label: "موتور داخلی", value: "fitsho_coach" },
          { label: "هوش مصنوعی", value: "ai" },
        ]}
        selectedValue={selected}
      />
      {saving ? <Text style={styles.selectorHint}>در حال ذخیره…</Text> : null}
      {error ? <Text style={styles.selectorError}>{error}</Text> : null}
    </View>
  );
}

function PlanView({
  historical,
  onStartReplacement,
  plan,
  pending,
}: {
  readonly historical: boolean;
  readonly onStartReplacement?: (exerciseId: string) => void;
  readonly plan: WorkoutPlan;
  readonly pending: boolean;
}) {
  const router = useRouter();
  const [expandedDay, setExpandedDay] = useState<number | null>(plan.days[0]?.day_number ?? null);
  const [activePreviewId, setActivePreviewId] = useState<string | null>(null);
  const executable = isWorkoutPlanExecutable(plan, historical);
  const visibleWarnings = getUserVisibleWorkoutWarnings(plan.warnings);

  useEffect(() => {
    setActivePreviewId(null);
  }, [plan.id]);

  function togglePreview(previewId: string): void {
    setActivePreviewId((current) => current === previewId ? null : previewId);
  }

  return (
    <View style={styles.planSection} testID={`workout-plan-view-${plan.id}`}>
      {plan.status === "failed" ? <PlanInlineNotice message="این نسخه با خطا ساخته شده و قابل اجرا نیست." variant="danger" /> : null}
      {!executable && plan.status === "active" && !historical && !pending && plan.coach_review?.state !== "pending_coach_review" ? (
        <PlanInlineNotice message="این برنامه هنوز برای اجرا آزاد نشده است." variant="warning" />
      ) : null}

      {plan.status === "failed" || plan.days.length === 0 ? null : (
        <View style={styles.scheduleSection}>
          <View style={styles.scheduleHeading}>
            <View style={styles.scheduleHeadingCopy}>
              <Text style={styles.sectionEyebrow}>برنامه هفتگی</Text>
              <Text style={styles.scheduleTitle}>روزهای تمرین تو</Text>
            </View>
          </View>
          <View style={styles.daysSection}>
            {plan.days.map((day, dayIndex) => (
              <WorkoutDayCard
                day={day}
                dayIndex={dayIndex}
                activePreviewId={activePreviewId}
                expanded={expandedDay === day.day_number}
                focus={dayIndex === 0}
                key={day.day_number}
                onOpenExercise={(slug) => router.push({ pathname: "/member/exercises/[slug]", params: { slug } })}
                onStartReplacement={executable && !pending ? onStartReplacement : undefined}
                onTogglePreview={togglePreview}
                showNext={dayIndex === 0 && executable && !historical}
                onToggle={() => {
                  setActivePreviewId(null);
                  setExpandedDay((current) => current === day.day_number ? null : day.day_number);
                }}
              />
            ))}
          </View>
        </View>
      )}

      {plan.ai_coach_program_explanation_fa ? (
        <Card style={styles.aiCard}>
          <Text style={styles.aiLabel}>توضیح فیتشو کوچ</Text>
          <Text style={styles.bodyText}>{plan.ai_coach_program_explanation_fa}</Text>
        </Card>
      ) : null}

      {visibleWarnings.map((warning) => (
        <PlanInlineNotice key={warning} message={warning} variant="warning" />
      ))}
      {plan.body_analysis_provenance?.provisional === true ? (
        <PlanInlineNotice message="این برنامه از یافته‌های موقت تحلیل بدن استفاده کرده که هنوز به تأیید هر دو متخصص نرسیده است." variant="warning" />
      ) : null}
    </View>
  );
}

function WorkoutPlanTools({
  api,
  awaitingCoachApproval,
  connectivityStatus,
  cycleApi,
  fallbackDurationWeeks,
  pdfStore,
  plan,
}: {
  readonly api: ReturnType<typeof createWorkoutPlanApi>;
  readonly awaitingCoachApproval: boolean;
  readonly connectivityStatus: ConnectivityStatus;
  readonly cycleApi: ReturnType<typeof createWorkoutCycleApi>;
  readonly fallbackDurationWeeks: number;
  readonly pdfStore: ExpoWorkoutPlanPdfStore;
  readonly plan: WorkoutPlan | null;
}) {
  const router = useRouter();
  const [pdfError, setPdfError] = useState(false);
  const feedbackController = useCompletionFeedbackController({
    api: cycleApi,
    awaitingCoachApproval,
    connectivityStatus,
    fallbackDurationWeeks,
    planId: plan?.id ?? null,
  });
  const toolsRowDirection = { direction: "rtl" as const, flexDirection: "row" as const };
  const toolDividerStyle = {
    borderRightColor: fiticianTokens.colors.line,
    borderRightWidth: 1,
  } as const;

  return (
    <View style={styles.toolsSection} testID="workout-plan-tools">
      <Text style={styles.toolsHeading}>ابزارهای برنامه</Text>
      <View style={styles.toolsContainer}>
        <View style={[styles.toolsRow, toolsRowDirection]} testID="workout-plan-tools-row">
          <WorkoutPdfTool
            api={api}
            onErrorChange={setPdfError}
            pdfStore={pdfStore}
            plan={plan}
          />
          <CompletionFeedbackToolCell controller={feedbackController} />
          <Pressable
            accessibilityLabel="Body Analysis"
            accessibilityRole="button"
            onPress={() => router.push("/member/body-analysis-history")}
            style={({ pressed }) => [styles.toolsCell, toolDividerStyle, pressed && styles.toolPressed]}
            testID="workout-plan-body-analysis-tool"
          >
            <AppIcon color={fiticianTokens.colors.aqua} name="progress" size={fiticianTokens.iconSize.md} />
            <Text style={styles.toolTitleEnglish}>Body Analysis</Text>
          </Pressable>
        </View>
        <CompletionFeedbackDetails controller={feedbackController} />
      </View>
      {pdfError ? (
        <Notice compact message="دانلود PDF انجام نشد. دوباره تلاش کن." variant="danger" />
      ) : null}
    </View>
  );
}

function WorkoutPdfTool({
  api,
  onErrorChange,
  pdfStore,
  plan,
}: {
  readonly api: ReturnType<typeof createWorkoutPlanApi>;
  readonly onErrorChange: (hasError: boolean) => void;
  readonly pdfStore: ExpoWorkoutPlanPdfStore;
  readonly plan: WorkoutPlan | null;
}) {
  const planId = plan?.id ?? null;
  const [pdfStatus, setPdfStatus] = useState<PdfStatus>("idle");
  const [storedPdf, setStoredPdf] = useState<StoredWorkoutPlanPdf | null>(null);
  const storageCheck = useRef<Promise<StoredWorkoutPlanPdf | null> | null>(null);
  const requestVersion = useRef(0);

  useEffect(() => {
    const version = requestVersion.current + 1;
    requestVersion.current = version;
    setStoredPdf(null);
    onErrorChange(false);
    if (planId === null) {
      storageCheck.current = null;
      setPdfStatus("idle");
      return;
    }

    storageCheck.current = pdfStore.get(planId).catch(() => null);
  }, [onErrorChange, pdfStore, planId]);

  async function openPdf(uri: string, version: number) {
    if (requestVersion.current !== version) return;
    await Linking.openURL(uri);
    onErrorChange(false);
    setPdfStatus("ready");
  }

  async function handlePress() {
    if (planId === null || pdfStatus === "downloading") return;
    const version = requestVersion.current;
    onErrorChange(false);
    setPdfStatus("downloading");
    try {
      const checkedPdf = storedPdf ?? (storageCheck.current === null ? null : await storageCheck.current);
      if (requestVersion.current !== version || planId !== plan?.id) return;
      if (checkedPdf !== null) {
        setStoredPdf(checkedPdf);
        await openPdf(checkedPdf.uri, version);
        return;
      }

      const downloaded = await api.downloadPdf(planId);
      const stored = await pdfStore.save(planId, downloaded);
      if (requestVersion.current !== version || planId !== plan?.id) return;
      setStoredPdf(stored);
      await openPdf(stored.uri, version);
    } catch {
      if (requestVersion.current !== version) return;
      setPdfStatus("error");
      onErrorChange(true);
    }
  }

  const downloading = pdfStatus === "downloading";
  return (
    <Pressable
      accessibilityLabel="دانلود PDF"
      accessibilityRole="button"
      accessibilityState={{ busy: downloading, disabled: planId === null || downloading }}
      disabled={planId === null || downloading}
      onPress={() => void handlePress()}
      style={({ pressed }) => [styles.toolsCell, pressed && styles.toolPressed]}
      testID="workout-plan-pdf-tool"
    >
      <AppIcon color={fiticianTokens.colors.aqua} name="document" size={fiticianTokens.iconSize.md} />
      <Text style={styles.toolTitle}>دانلود PDF</Text>
      <Text numberOfLines={2} style={styles.toolSubtitle}>
        {downloading ? "در حال آماده‌سازی PDF…" : "دریافت نسخه فارسی برنامه"}
      </Text>
    </Pressable>
  );
}

export function getWorkoutDayDisplayTitle(day: WorkoutDay): string {
  const title = (day.title_fa || day.title_en).trim();
  return title.replace(/^(?:روز|Day)\s+[0-9۰-۹٠-٩]+\s*:\s*/u, "").trim();
}

function WorkoutDayCard({
  activePreviewId,
  day,
  dayIndex,
  expanded,
  focus,
  onOpenExercise,
  onStartReplacement,
  onTogglePreview,
  showNext,
  onToggle,
}: {
  readonly activePreviewId: string | null;
  readonly day: WorkoutDay;
  readonly dayIndex: number;
  readonly expanded: boolean;
  readonly focus: boolean;
  readonly onOpenExercise: (slug: string) => void;
  readonly onStartReplacement?: (exerciseId: string) => void;
  readonly onTogglePreview: (previewId: string) => void;
  readonly showNext: boolean;
  readonly onToggle: () => void;
}) {
  const mainExercises = day.exercises.filter((item) => item.section !== "core");
  const coreExercises = day.exercises.filter((item) => item.section === "core");
  const leadExercise = mainExercises[0] ?? day.exercises[0];
  const leadName = leadExercise?.exercise.name_fa || leadExercise?.exercise.name_en || "";
  const leadPreviewId = `${day.day_number}:lead`;
  const displayTitle = getWorkoutDayDisplayTitle(day);
  return (
    <Pressable
      accessibilityLabel={`روز ${formatPersianNumber(day.day_number, { maximumFractionDigits: 0 })}: ${displayTitle}`}
      accessibilityRole="button"
      accessibilityState={{ expanded }}
      onPress={onToggle}
      style={({ pressed }) => [
        styles.dayCard,
        focus ? styles.focusDayCard : styles.secondaryDayCard,
        expanded && styles.dayCardExpanded,
        pressed && styles.dayCardPressed,
      ]}
    >
      <View style={[styles.daySummary, focus ? styles.focusDaySummary : styles.secondaryDaySummary]}>
        {focus && dayIndex === 0 && leadExercise ? (
          <Pressable
            accessibilityLabel={leadExercise.exercise.media_type === "video"
              ? `${activePreviewId === leadPreviewId ? "توقف" : "پخش"} پیش‌نمایش جلسه ${leadName}`
              : `باز کردن راهنمای ${leadName}`}
            accessibilityRole="button"
            onPress={(event) => {
              event.stopPropagation();
              if (leadExercise.exercise.media_type === "video") {
                onTogglePreview(leadPreviewId);
              } else {
                onOpenExercise(leadExercise.exercise.slug);
              }
            }}
            style={({ pressed }) => [styles.dayMediaButton, pressed && styles.mediaPressed]}
          >
            <ExerciseMedia
              accessibilityLabel={`پیش‌نمایش ${leadExercise.exercise.name_fa || leadExercise.exercise.name_en}`}
              autoplay={activePreviewId === leadPreviewId}
              compact
              deferVideo
              mediaType={leadExercise.exercise.media_type}
              name={leadExercise.exercise.name_fa || leadExercise.exercise.name_en}
              path={leadExercise.exercise.media_path}
              style={styles.focusDayMedia}
              videoActive={activePreviewId === leadPreviewId}
            />
            {activePreviewId === leadPreviewId ? null : (
              <View pointerEvents="none" style={styles.dayMediaBadge}>
                <AppIcon color={fiticianTokens.colors.ink} name="play" size={fiticianTokens.iconSize.sm} />
              </View>
            )}
          </Pressable>
        ) : null}
        <View style={[styles.dayNumberBox, focus ? styles.focusDayNumber : styles.secondaryDayNumber]}>
          <Text style={styles.dayNumber}>{formatPersianNumber(day.day_number, { maximumFractionDigits: 0, useGrouping: false }).padStart(2, "۰")}</Text>
        </View>
        <View style={styles.dayHeadingCopy}>
          {showNext ? <Text style={styles.nextSessionLabel}>جلسه بعد</Text> : null}
          <Text numberOfLines={focus ? 2 : 1} style={[styles.dayTitle, !focus && styles.secondaryDayTitle]}>
            روز {formatPersianNumber(day.day_number, { maximumFractionDigits: 0 })}: {displayTitle}
          </Text>
          <Text numberOfLines={1} style={styles.dayMeta}>
            {focus && leadExercise ? `${leadName} · ` : ""}{formatPersianNumber(day.estimated_duration_minutes, { maximumFractionDigits: 0 })} دقیقه
          </Text>
        </View>
        <AppIcon
          accessibilityLabel={expanded ? "بستن جزئیات روز" : "باز کردن جزئیات روز"}
          color={fiticianTokens.colors.aqua}
          name={expanded ? "chevronUp" : "chevronDown"}
          size={fiticianTokens.iconSize.md}
        />
      </View>
      {expanded ? (
        <View style={styles.dayDetails}>
          {day.ai_coach_explanation_fa ? (
            <Notice message={day.ai_coach_explanation_fa} title="توضیح این جلسه" variant="info" />
          ) : null}
          {mainExercises.map((exercise) => (
            <WorkoutExerciseRow
              exercise={exercise}
              key={exercise.id}
              onOpen={() => onOpenExercise(exercise.exercise.slug)}
              onOpenAlternative={onOpenExercise}
              onStartReplacement={onStartReplacement}
              onTogglePreview={onTogglePreview}
              videoActive={activePreviewId === exercise.id}
            />
          ))}
          {coreExercises.length > 0 ? (
            <View style={styles.exerciseSection}>
              <Text style={styles.exerciseSectionTitle}>بخش مرکزی بدن</Text>
              {coreExercises.map((exercise) => (
                <WorkoutExerciseRow
                  exercise={exercise}
                  key={exercise.id}
                  onOpen={() => onOpenExercise(exercise.exercise.slug)}
                  onOpenAlternative={onOpenExercise}
                  onStartReplacement={onStartReplacement}
                  onTogglePreview={onTogglePreview}
                  videoActive={activePreviewId === exercise.id}
                />
              ))}
            </View>
          ) : null}
        </View>
      ) : null}
    </Pressable>
  );
}

function formatExerciseNumber(value: number): string {
  return formatPersianNumber(value, { maximumFractionDigits: 0, useGrouping: false });
}

function formatExerciseRange(
  min: number | null | undefined,
  max: number | null | undefined,
  suffix = "",
): string | null {
  const lower = min ?? max;
  if (lower === null || lower === undefined) return null;
  const upper = max ?? lower;
  return `${formatExerciseNumber(lower)}–${formatExerciseNumber(upper)}${suffix}`;
}

function WorkoutExerciseRow({
  exercise,
  onOpen,
  onOpenAlternative,
  onStartReplacement,
  onTogglePreview,
  videoActive,
}: {
  readonly exercise: WorkoutPlanExercise;
  readonly onOpen: () => void;
  readonly onOpenAlternative: (slug: string) => void;
  readonly onStartReplacement?: (exerciseId: string) => void;
  readonly onTogglePreview: (previewId: string) => void;
  readonly videoActive: boolean;
}) {
  const language = languageForDirection();
  const actionCopy = language === "en"
    ? { alternatives: "View alternatives", detail: "View exercise details" }
    : { alternatives: "حرکت جایگزین", detail: "مشاهده جزئیات حرکت" };
  const [alternativesExpanded, setAlternativesExpanded] = useState(false);
  const prescriptionLabel = exercise.prescription_mode === "duration" ? "زمان" : "تکرار";
  const prescriptionValue = exercise.prescription_mode === "duration"
    ? formatExerciseRange(exercise.duration_min_seconds, exercise.duration_max_seconds, "ث")
    : formatExerciseRange(exercise.reps_min, exercise.reps_max);

  return (
    <View style={styles.exerciseRow}>
      <Pressable
        accessibilityLabel={exercise.exercise.media_type === "video"
          ? `${videoActive ? "توقف" : "پخش"} پیش‌نمایش ${exercise.exercise.name_fa || exercise.exercise.name_en}`
          : `باز کردن راهنمای ${exercise.exercise.name_fa || exercise.exercise.name_en}`}
        accessibilityRole="button"
        onPress={(event) => {
          event.stopPropagation();
          if (exercise.exercise.media_type === "video") {
            onTogglePreview(exercise.id);
          } else {
            onOpen();
          }
        }}
        style={({ pressed }) => [styles.exerciseMediaButton, pressed && styles.mediaPressed]}
        testID={`workout-exercise-preview-${exercise.id}`}
      >
        <ExerciseMedia
          accessibilityLabel={`پیش‌نمایش ${exercise.exercise.name_fa || exercise.exercise.name_en}`}
          autoplay={videoActive}
          compact
          deferVideo
          mediaType={exercise.exercise.media_type}
          name={exercise.exercise.name_fa || exercise.exercise.name_en}
          path={exercise.exercise.media_path}
          style={styles.exerciseMedia}
          videoActive={videoActive}
        />
        {videoActive ? null : (
          <View pointerEvents="none" style={styles.exerciseMediaBadge}>
            <AppIcon color={fiticianTokens.colors.ink} name="play" size={fiticianTokens.iconSize.sm} />
          </View>
        )}
      </Pressable>
      <View style={styles.exerciseCopy}>
        <Text style={styles.exerciseTitle}>{exercise.exercise.name_fa || exercise.exercise.name_en}</Text>
        <View style={styles.exerciseStatsRow}>
          {exercise.sets === null || exercise.sets === undefined ? null : (
            <View style={styles.exerciseStat}>
              <Text style={styles.exerciseStatLabel}>ست</Text>
              <Text style={styles.exerciseStatValue}>{formatExerciseNumber(exercise.sets)}</Text>
            </View>
          )}
          {prescriptionValue === null ? null : (
            <View style={styles.exerciseStat}>
              <Text style={styles.exerciseStatLabel}>{prescriptionLabel}</Text>
              <Text style={styles.exerciseStatValue}>{prescriptionValue}</Text>
            </View>
          )}
          {exercise.rest_seconds === null || exercise.rest_seconds === undefined ? null : (
            <View style={styles.exerciseStat}>
              <Text style={styles.exerciseStatLabel}>استراحت</Text>
              <Text style={styles.exerciseStatValue}>{formatExerciseNumber(exercise.rest_seconds)}ث</Text>
            </View>
          )}
          {exercise.rir === null || exercise.rir === undefined ? null : (
            <View style={styles.exerciseStat}>
              <Text style={styles.exerciseStatLabel}>RIR</Text>
              <Text style={styles.exerciseStatValue}>{formatExerciseNumber(exercise.rir)}</Text>
            </View>
          )}
        </View>
        {exercise.notes_fa ? <Text style={styles.exerciseNote}>{exercise.notes_fa}</Text> : null}
        <Pressable
          accessibilityLabel={actionCopy.detail}
          accessibilityRole="link"
          hitSlop={fiticianTokens.spacing[1]}
          onPress={(event) => {
            event.stopPropagation();
            onOpen();
          }}
          style={({ pressed }) => [styles.exerciseAction, pressed && styles.exerciseActionPressed]}
        >
          <Text style={[styles.exerciseActionText, language === "en" && styles.exerciseActionTextEnglish]}>
            {actionCopy.detail}
          </Text>
        </Pressable>
        {exercise.alternatives.length > 0 ? (
          <>
            <Pressable
              accessibilityLabel={actionCopy.alternatives}
              accessibilityRole="button"
              accessibilityState={onStartReplacement ? undefined : { expanded: alternativesExpanded }}
              hitSlop={fiticianTokens.spacing[1]}
              onPress={(event) => {
                event?.stopPropagation();
                if (onStartReplacement) {
                  onStartReplacement(exercise.id);
                  return;
                }
                setAlternativesExpanded((expanded) => !expanded);
              }}
              style={({ pressed }) => [styles.exerciseAction, pressed && styles.exerciseActionPressed]}
            >
              <Text style={[styles.exerciseActionText, language === "en" && styles.exerciseActionTextEnglish]}>
                {actionCopy.alternatives}
              </Text>
              <AppIcon
                color={fiticianTokens.colors.aqua}
                name={onStartReplacement ? "arrowLeft" : alternativesExpanded ? "chevronUp" : "chevronDown"}
                size={fiticianTokens.iconSize.sm}
              />
            </Pressable>
            {!onStartReplacement && alternativesExpanded ? (
              <ReadOnlyAlternativeList
                alternatives={exercise.alternatives}
                language={language}
                onOpenAlternative={onOpenAlternative}
              />
            ) : null}
          </>
        ) : null}
      </View>
    </View>
  );
}

function ReadOnlyAlternativeList({
  alternatives,
  language,
  onOpenAlternative,
}: {
  readonly alternatives: WorkoutPlanExercise["alternatives"];
  readonly language: MobileLanguage;
  readonly onOpenAlternative: (slug: string) => void;
}) {
  return (
    <View style={styles.readOnlyAlternatives} testID="workout-read-only-alternatives">
      {alternatives.map((alternative) => {
        const name = language === "en"
          ? alternative.exercise.name_en || alternative.exercise.name_fa
          : alternative.exercise.name_fa || alternative.exercise.name_en;
        const reason = language === "en" ? alternative.reason_en : alternative.reason_fa;
        return (
          <View key={alternative.exercise.id} style={styles.readOnlyAlternative}>
            <Pressable
              accessibilityLabel={name}
              accessibilityRole="link"
              onPress={(event) => {
                event?.stopPropagation();
                onOpenAlternative(alternative.exercise.slug);
              }}
              style={styles.readOnlyAlternativeLink}
            >
              <Text
                style={[
                  styles.readOnlyAlternativeName,
                  language === "en" && styles.readOnlyAlternativeNameEnglish,
                ]}
              >
                {name}
              </Text>
            </Pressable>
            {reason ? (
              <Text
                style={[
                  styles.readOnlyAlternativeReason,
                  language === "en" && styles.readOnlyAlternativeReasonEnglish,
                ]}
              >
                {reason}
              </Text>
            ) : null}
          </View>
        );
      })}
    </View>
  );
}

function WorkoutHistory({
  currentPlanId,
  deletionError,
  deletingPlanId,
  history,
  historyState,
  onDelete,
  onRetry,
  onReturnToCurrent,
  onSelect,
  isViewingHistorical,
  selectedPlanId,
}: {
  readonly currentPlanId: string | null;
  readonly deletionError: string | null;
  readonly deletingPlanId: string | null;
  readonly history: readonly WorkoutPlanVersionSummary[];
  readonly historyState: MobileViewState<WorkoutPlanVersionSummary[]>;
  readonly onDelete: (version: WorkoutPlanVersionSummary) => void;
  readonly onRetry: () => void;
  readonly onReturnToCurrent: () => void;
  readonly onSelect: (version: WorkoutPlanVersionSummary) => void;
  readonly isViewingHistorical: boolean;
  readonly selectedPlanId: string | null;
}) {
  const versions = history.filter(
    (version) => version.status !== "pending_review" && version.id !== currentPlanId,
  );
  if (historyState.status === "loading") return <Skeleton height={120} />;
  if (historyState.status === "error" && history.length === 0) {
    return <Notice actionLabel="تلاش دوباره" message="تاریخچهٔ برنامه دریافت نشد." onAction={onRetry} variant="danger" />;
  }
  if (historyState.status === "offline" && history.length === 0) {
    return <Notice message="تاریخچهٔ برنامه در حالت آفلاین در دسترس نیست." variant="offline" />;
  }
  if (versions.length === 0 && !isViewingHistorical) return null;

  return (
    <View style={styles.historySection}>
      <View style={styles.historyHeader}>
        <Text style={styles.sectionTitle}>تاریخچهٔ برنامه‌ها</Text>
        {isViewingHistorical ? (
          <Pressable accessibilityRole="button" onPress={onReturnToCurrent} style={styles.returnCurrentButton}>
            <Text style={styles.returnCurrentText}>بازگشت به برنامه فعلی</Text>
          </Pressable>
        ) : null}
      </View>
      {historyState.status === "offline" ? <Notice message="فهرست تاریخچه تازه‌سازی نشده است." variant="offline" /> : null}
      {deletionError !== null ? <Notice message={deletionError} variant="danger" /> : null}
      {versions.map((version) => (
        <View key={version.id} style={styles.historyItem}>
          <Card
            onPress={() => onSelect(version)}
            style={styles.historyCard}
            variant={selectedPlanId === version.id ? "raised" : "interactive"}
          >
            <View style={styles.historyRow}>
              <View style={styles.historyCopy}>
                <Text style={styles.historyTitle}>{historyLabel(version)}</Text>
                <Text style={styles.historyDate}>{formatDate(version.created_at)}</Text>
              </View>
              <Text style={styles.historyState}>{version.is_active ? "فعال" : "آرشیو"}</Text>
            </View>
          </Card>
          {isDeletableWorkoutPlanVersion(version) ? (
            <Pressable
              accessibilityLabel="حذف نسخه قدیمی برنامه"
              accessibilityRole="button"
              accessibilityState={{ busy: deletingPlanId === version.id, disabled: deletingPlanId === version.id }}
              disabled={deletingPlanId === version.id}
              onPress={() => onDelete(version)}
              style={({ pressed }) => [styles.historyDeleteButton, pressed && styles.mediaPressed]}
            >
              <AppIcon color={fiticianTokens.colors.danger} name="delete" size={fiticianTokens.iconSize.sm} />
            </Pressable>
          ) : null}
        </View>
      ))}
    </View>
  );
}

function PlanSkeleton() {
  return (
    <View style={styles.skeletonGroup}>
      <Skeleton height={150} />
      <Skeleton height={110} />
      <Skeleton height={110} />
    </View>
  );
}

function viewData<TData>(state: MobileViewState<TData>): TData | undefined {
  if (state.status === "loading") return undefined;
  return "data" in state ? state.data : undefined;
}

function historyLabel(version: WorkoutPlanVersionSummary): string {
  if (version.coach_review.state === "coach_approved") return "نسخهٔ تأییدشده توسط مربی";
  if (version.coach_review.state === "coach_rejected") return "نسخهٔ برگشت‌داده‌شده برای اصلاح";
  if (version.status === "failed") return "نسخهٔ ناموفق";
  if (version.status === "active") return "نسخهٔ فعال";
  return "نسخهٔ اولیه";
}

function isDeletableWorkoutPlanVersion(version: WorkoutPlanVersionSummary): boolean {
  return version.status === "superseded" || version.status === "failed";
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" }).format(new Date(value));
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

function firstParam(value: string | string[] | undefined): string | undefined {
  const candidate = Array.isArray(value) ? value[0] : value;
  const normalized = candidate?.trim();
  return normalized === "" ? undefined : normalized;
}

const styles = StyleSheet.create({
  aiCard: {
    borderColor: fiticianTokens.colors.aqua,
    gap: fiticianTokens.spacing[2],
  },
  contextCell: {
    alignItems: "center",
    flex: 1,
    gap: 2,
    justifyContent: "center",
    minWidth: 0,
    paddingHorizontal: 4,
    paddingVertical: 10,
  },
  contextCellDivided: {
    borderRightColor: fiticianTokens.colors.line,
    borderRightWidth: 1,
  },
  contextLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    lineHeight: 14,
    textAlign: "center",
    writingDirection: "rtl",
  },
  contextStrip: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    flexDirection: "row",
    minWidth: 0,
    overflow: "hidden",
    width: "100%",
  },
  contextValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 11,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 15,
    textAlign: "center",
    writingDirection: "rtl",
  },
  contextValueActive: {
    color: fiticianTokens.colors.aqua,
  },
  contextValueInactive: {
    color: fiticianTokens.colors.muted,
  },
  contextValuePending: {
    color: fiticianTokens.colors.amber,
  },
  dayCardPressed: {
    opacity: 0.9,
  },
  dayNumberBox: {
    alignItems: "center",
    aspectRatio: 1,
    borderColor: fiticianTokens.colors.line,
    borderRadius: 11,
    borderWidth: 1,
    justifyContent: "center",
    width: 40,
  },
  daySummary: {
    alignItems: "center",
    flexDirection: "row",
    gap: 10,
    minWidth: 0,
  },
  durationBadge: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: 14,
    borderWidth: 1,
    justifyContent: "center",
    minWidth: 60,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  durationLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    lineHeight: 14,
    textAlign: "center",
    writingDirection: "rtl",
  },
  durationValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: 22,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 24,
    textAlign: "center",
    writingDirection: "ltr",
  },
  exerciseSection: {
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
    gap: fiticianTokens.spacing[2],
    paddingTop: fiticianTokens.spacing[2],
  },
  exerciseSectionTitle: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  focusDayCard: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    elevation: fiticianTokens.shadows.focus.elevation,
    shadowColor: fiticianTokens.shadows.focus.color,
    shadowOffset: fiticianTokens.shadows.focus.offset,
    shadowOpacity: fiticianTokens.shadows.focus.opacity,
    shadowRadius: fiticianTokens.shadows.focus.radius,
  },
  focusDayMedia: {
    borderRadius: 11,
    height: 86,
    minHeight: 0,
    width: 94,
  },
  focusDayNumber: {
    backgroundColor: fiticianTokens.colors.surfaceHighlight,
  },
  focusDaySummary: {
    minHeight: 112,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  generationMethodSection: {
    gap: fiticianTokens.spacing[2],
    marginTop: fiticianTokens.spacing[1],
  },
  inlineNotice: {
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  inlineNoticeDanger: {
    borderRightColor: fiticianTokens.colors.coral,
  },
  inlineNoticeInfo: {
    borderRightColor: fiticianTokens.colors.aqua,
  },
  inlineNoticeText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 19,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  inlineNoticeWarning: {
    borderRightColor: fiticianTokens.colors.amber,
  },
  nextSessionLabel: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 14,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  pageHeader: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    marginBottom: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  planControlsSection: {
    gap: fiticianTokens.spacing[2],
    marginBottom: fiticianTokens.spacing[1],
  },
  pageHeaderCopy: {
    flex: 1,
    minWidth: 0,
  },
  pageTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
    lineHeight: 32,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  planOverview: {
    gap: fiticianTokens.spacing[2],
  },
  planSection: {
    gap: fiticianTokens.spacing[3],
  },
  reviewBanner: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: 14,
    borderWidth: 1,
    flexDirection: "row",
    gap: 10,
    minHeight: 52,
    paddingHorizontal: 12,
    paddingVertical: 8,
    width: "100%",
  },
  reviewBannerApproved: {
    borderRightColor: fiticianTokens.colors.aqua,
  },
  reviewBannerHistory: {
    borderRightColor: fiticianTokens.colors.coral,
  },
  reviewBannerRejected: {
    borderRightColor: fiticianTokens.colors.coral,
  },
  reviewCopy: {
    flex: 1,
    gap: 2,
    minWidth: 0,
  },
  reviewIndicator: {
    borderColor: fiticianTokens.colors.coral,
    borderRadius: 999,
    borderWidth: 2,
    flexShrink: 0,
    height: 22,
    width: 22,
  },
  reviewIndicatorApproved: {
    alignItems: "center",
    borderColor: fiticianTokens.colors.success,
    color: fiticianTokens.colors.success,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: 15,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 19,
    textAlign: "center",
    writingDirection: "ltr",
  },
  reviewIndicatorRejected: {
    alignItems: "center",
    borderColor: fiticianTokens.colors.coral,
    color: fiticianTokens.colors.coral,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: 15,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 19,
    textAlign: "center",
    writingDirection: "ltr",
  },
  reviewNote: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  reviewText: {
    color: fiticianTokens.colors.ink,
    flexShrink: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 20,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  readOnlyNotice: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  scheduleHeading: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    marginBottom: fiticianTokens.spacing[2],
    minWidth: 0,
  },
  scheduleHeadingCopy: {
    flex: 1,
    gap: 2,
    minWidth: 0,
  },
  scheduleSection: {
    marginTop: fiticianTokens.spacing[1],
  },
  scheduleTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  updateButton: {
    borderRadius: fiticianTokens.radii.pill,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  secondaryDayCard: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    elevation: fiticianTokens.shadows.card.elevation,
    minHeight: 62,
    shadowColor: fiticianTokens.shadows.card.color,
    shadowOffset: fiticianTokens.shadows.card.offset,
    shadowOpacity: fiticianTokens.shadows.card.opacity,
    shadowRadius: fiticianTokens.shadows.card.radius,
  },
  secondaryDayNumber: {
    backgroundColor: fiticianTokens.colors.surfaceHighlight,
  },
  secondaryDaySummary: {
    minHeight: 62,
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  secondaryDayTitle: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    lineHeight: 20,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  selectorError: {
    color: fiticianTokens.colors.coral,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  selectorHint: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  selectorTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  aiLabel: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  bodyText: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 27,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  dayCard: {
    minWidth: 0,
    overflow: "hidden",
  },
  dayCardExpanded: {
    borderColor: fiticianTokens.colors.lineStrong,
  },
  dayMediaBadge: {
    alignItems: "center",
    backgroundColor: "rgba(2,6,7,0.70)",
    borderRadius: fiticianTokens.radii.pill,
    bottom: 7,
    height: 26,
    justifyContent: "center",
    position: "absolute",
    right: 7,
    width: 26,
  },
  dayMediaButton: {
    borderRadius: fiticianTokens.radii.medium,
    height: 86,
    overflow: "hidden",
    position: "relative",
    width: 94,
  },
  dayDetails: {
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
    gap: fiticianTokens.spacing[3],
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  daysSection: {
    gap: 9,
  },
  dayHeadingCopy: {
    flex: 1,
    gap: 2,
    minWidth: 0,
  },
  dayMeta: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  dayNumber: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  dayTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: 17,
    lineHeight: 24,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  emptyBody: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 26,
    textAlign: "center",
    writingDirection: "rtl",
  },
  exerciseCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  exerciseActionPressed: {
    opacity: 0.78,
  },
  exerciseAction: {
    alignItems: "center",
    alignSelf: "flex-start",
    flexDirection: "row",
    gap: fiticianTokens.spacing[1],
    paddingVertical: 2,
  },
  exerciseActionText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 18,
    textAlign: "auto",
    textDecorationLine: "underline",
    writingDirection: "rtl",
  },
  exerciseActionTextEnglish: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    textAlign: "left",
    writingDirection: "ltr",
  },
  exerciseMedia: {
    borderRadius: fiticianTokens.radii.medium,
    flexShrink: 0,
    height: 68,
    minHeight: 0,
    width: 76,
  },
  exerciseMediaBadge: {
    alignItems: "center",
    backgroundColor: "rgba(2,6,7,0.70)",
    borderRadius: fiticianTokens.radii.pill,
    bottom: 7,
    height: 26,
    justifyContent: "center",
    position: "absolute",
    right: 7,
    width: 26,
  },
  exerciseMediaButton: {
    borderRadius: fiticianTokens.radii.medium,
    flexShrink: 0,
    height: 68,
    overflow: "hidden",
    position: "relative",
    width: 76,
  },
  exerciseNote: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  exerciseRow: {
    alignItems: "flex-start",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    minWidth: 0,
    paddingBottom: fiticianTokens.spacing[3],
    paddingTop: fiticianTokens.spacing[1],
  },
  readOnlyAlternatives: {
    borderRightColor: fiticianTokens.colors.aqua,
    borderRightWidth: 2,
    gap: fiticianTokens.spacing[1],
    marginTop: fiticianTokens.spacing[1],
    paddingRight: fiticianTokens.spacing[2],
  },
  readOnlyAlternative: {
    gap: fiticianTokens.spacing[1],
  },
  readOnlyAlternativeLink: {
    alignSelf: "flex-start",
    paddingVertical: 2,
  },
  readOnlyAlternativeName: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 18,
    textAlign: "auto",
    textDecorationLine: "underline",
    writingDirection: "rtl",
  },
  readOnlyAlternativeNameEnglish: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    textAlign: "left",
    writingDirection: "ltr",
  },
  readOnlyAlternativeReason: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  readOnlyAlternativeReasonEnglish: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    textAlign: "left",
    writingDirection: "ltr",
  },
  exerciseStat: {
    alignItems: "baseline",
    flexDirection: "row",
    flexShrink: 0,
    gap: 2,
  },
  exerciseStatLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 17,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  exerciseStatValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 18,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  exerciseStatsRow: {
    alignItems: "baseline",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
    minWidth: 0,
  },
  exerciseTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.lg,
    lineHeight: 26,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  historyCard: {
    gap: fiticianTokens.spacing[2],
    flex: 1,
  },
  historyDeleteButton: {
    alignItems: "center",
    borderColor: fiticianTokens.colors.danger,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
  },
  historyItem: {
    alignItems: "stretch",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  historyCopy: {
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
  historyRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  historyHeader: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    justifyContent: "space-between",
  },
  historySection: {
    gap: fiticianTokens.spacing[3],
    marginTop: fiticianTokens.spacing[5],
  },
  returnCurrentButton: {
    borderColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  returnCurrentText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "center",
    writingDirection: "rtl",
  },
  historyState: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
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
  mediaPressed: {
    opacity: 0.78,
    transform: [{ scale: fiticianTokens.motion.pressedScale }],
  },
  screen: {
    gap: fiticianTokens.spacing[3],
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[3],
  },
  sectionEyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  sectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  skeletonGroup: {
    gap: fiticianTokens.spacing[3],
  },
  toolPressed: {
    opacity: 0.78,
  },
  toolSubtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    lineHeight: 14,
    textAlign: "center",
    writingDirection: "rtl",
  },
  toolTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 16,
    textAlign: "center",
    writingDirection: "rtl",
  },
  toolTitleEnglish: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 16,
    textAlign: "center",
    writingDirection: "ltr",
  },
  toolsCell: {
    alignItems: "center",
    flex: 1,
    gap: 2,
    justifyContent: "center",
    minHeight: 80,
    minWidth: 0,
    paddingHorizontal: 4,
    paddingVertical: 8,
  },
  toolsContainer: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    overflow: "hidden",
    width: "100%",
  },
  toolsHeading: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  toolsRow: {
    minHeight: 80,
    width: "100%",
  },
  toolsSection: {
    gap: fiticianTokens.spacing[1],
    marginTop: fiticianTokens.spacing[2],
    width: "100%",
  },
});
