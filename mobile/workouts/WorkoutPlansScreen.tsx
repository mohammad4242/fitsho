import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { Linking, StyleSheet, Text, View } from "react-native";
import { useEffect, useMemo, useState } from "react";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { workoutKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { Button, Card, EmptyState, Notice, Skeleton } from "../ui/components";
import { Screen } from "../ui/layout";
import { getMobileViewState, type MobileViewState } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import {
  createWorkoutPlanApi,
  type WorkoutDay,
  type WorkoutPlan,
  type WorkoutPlanExercise,
  type WorkoutPlanVersionSummary,
} from "./workoutApi";
import {
  classifyWorkoutGenerationError,
  findPendingWorkoutPlanId,
  formatWorkoutPrescription,
  getWorkoutPlanSummaryStatus,
  isWorkoutPlanExecutable,
  workoutPlanAverageDuration,
} from "./workoutModel";
import {
  ExpoWorkoutPlanPdfStore,
  type StoredWorkoutPlanPdf,
} from "./workoutPdfStore";
import { WorkoutCyclePanel } from "./WorkoutCyclePanel";
import type { WorkoutGenerationErrorKind } from "./workoutModel";

type PdfStatus = "checking" | "downloading" | "error" | "idle" | "ready";

const generationErrorMessages: Record<WorkoutGenerationErrorKind, string> = {
  cooldown: "ساخت برنامه به‌تازگی انجام شده است؛ کمی بعد دوباره تلاش کن.",
  failed: "ساخت برنامه انجام نشد. وضعیت پروفایل و اتصال اینترنت را بررسی کن.",
  in_progress: "ساخت یک برنامهٔ دیگر در حال انجام است؛ کمی بعد وضعیت برنامه را بررسی کن.",
  unsupported: "با تنظیمات فعلی، برنامه امن و قابل ساختی پیدا نشد. پروفایل تمرینی را بررسی کن.",
};

export function WorkoutPlansScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const connectivityStatus = useConnectivityStatus();
  const api = useMemo(
    () => createWorkoutPlanApi(auth.request, auth.download),
    [auth.download, auth.request],
  );
  const pdfStore = useMemo(() => new ExpoWorkoutPlanPdfStore(), []);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [generationError, setGenerationError] = useState<WorkoutGenerationErrorKind | null>(null);

  const activeQuery = useQuery({
    queryFn: api.getActive,
    queryKey: workoutKeys.plan("active"),
  });
  const historyQuery = useQuery({
    queryFn: api.getHistory,
    queryKey: workoutKeys.plans(),
  });
  const history = historyQuery.data ?? [];
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
  const displayedPlan = selectedPlanId === null ? activePlan : selectedPlan;
  const isViewingHistorical = selectedPlanId !== null;
  const generation = useMutation({
    mutationFn: () => api.generate(),
    onError: (error: unknown) => setGenerationError(classifyWorkoutGenerationError(error)),
    onSuccess: async (result) => {
      setGenerationError(null);
      setSelectedPlanId(null);
      if (result.plan.status === "active") {
        queryClient.setQueryData(workoutKeys.plan("active"), result.plan);
      }
      await Promise.all([activeQuery.refetch(), historyQuery.refetch()]);
    },
  });

  const loading = activeState.status === "loading"
    || (activePlan === undefined && historyState.status === "loading");
  const activeLoadError = activeState.status === "error" && activePlan === undefined;
  const activeOffline = activeState.status === "offline" && activePlan === undefined;
  const pendingLoading = pendingPlanId !== null && pendingState.status === "loading";

  function retry() {
    void Promise.all([activeQuery.refetch(), historyQuery.refetch()]);
  }

  function startGeneration() {
    if (generation.isPending) return;
    setGenerationError(null);
    generation.mutate();
  }

  function selectHistoryVersion(version: WorkoutPlanVersionSummary) {
    if (version.id === activePlan?.id) {
      setSelectedPlanId(null);
      return;
    }
    setSelectedPlanId(version.id);
  }

  return (
    <Screen contentWidth="reading">
      <View style={styles.header}>
        <Text style={styles.brand}>FITICIAN</Text>
        <Text accessibilityRole="header" style={styles.title}>برنامه تمرینی</Text>
        <Text style={styles.intro}>
          برنامه‌ات را ببین، توضیح مربی را بخوان و نسخه‌ای را که برای تمرین آماده است نگه دار.
        </Text>
        <Button
          label="کتابخانه حرکات"
          onPress={() => router.push("/member/exercises")}
          variant="secondary"
        />
      </View>

      {connectivityStatus === "offline" && displayedPlan !== undefined ? (
        <Notice message="اتصال اینترنت برقرار نیست؛ آخرین برنامهٔ ذخیره‌شده نمایش داده می‌شود." variant="offline" />
      ) : null}
      {activeState.status === "stale" && activePlan !== undefined ? (
        <Notice message="این برنامه از حافظهٔ آفلاین خوانده شده و ممکن است تازه‌ترین نسخه نباشد." variant="info" />
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
        <Notice message="به‌روزرسانی برنامه انجام نشد؛ نسخهٔ ذخیره‌شده نمایش داده می‌شود." variant="warning" />
      ) : null}

      {!loading && !activeLoadError && !activeOffline && displayedPlan !== undefined && displayedPlan !== null ? (
        <PlanView
          api={api}
          historical={isViewingHistorical}
          pdfStore={pdfStore}
          plan={displayedPlan}
          pending={displayedPlan.status === "pending_review"}
        />
      ) : null}

      {!loading && !activeLoadError && !activeOffline && activePlan !== null && activePlan !== undefined
        && selectedPlanId === null && isWorkoutPlanExecutable(activePlan) ? (
        <WorkoutCyclePanel plan={activePlan} />
      ) : null}

      {!loading && !activeLoadError && !activeOffline && pendingPlan !== undefined && pendingPlan.id !== displayedPlan?.id ? (
        <PlanView
          api={api}
          historical={false}
          pdfStore={pdfStore}
          plan={pendingPlan}
          pending
        />
      ) : null}

      {pendingPlanId !== null && pendingPlan === undefined && !pendingLoading ? (
        <Notice
          actionLabel="تلاش دوباره"
          message="یک برنامه در انتظار تأیید مربی است؛ جزئیات آن فعلاً در دسترس نیست."
          onAction={() => void pendingQuery.refetch()}
          variant={pendingState.status === "offline" ? "offline" : "warning"}
        />
      ) : null}

      {!loading && !activeLoadError && !activeOffline && activePlan === null && pendingPlan === undefined && pendingPlanId === null ? (
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

      {activePlan !== null && activePlan !== undefined && selectedPlanId === null ? (
        <View style={styles.generateSection}>
          <Button
            disabled={generation.isPending || pendingPlanId !== null}
            label={pendingPlanId === null ? "ساخت نسخهٔ جدید" : "در انتظار تأیید مربی"}
            loading={generation.isPending}
            onPress={startGeneration}
            variant="secondary"
          />
        </View>
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

      <WorkoutHistory
        activePlanId={activePlan?.id ?? null}
        history={history}
        historyState={historyState}
        onRetry={() => void historyQuery.refetch()}
        onSelect={selectHistoryVersion}
        selectedPlanId={selectedPlanId}
      />
    </Screen>
  );
}

function PlanView({
  api,
  historical,
  pdfStore,
  plan,
  pending,
}: {
  readonly api: ReturnType<typeof createWorkoutPlanApi>;
  readonly historical: boolean;
  readonly pdfStore: ExpoWorkoutPlanPdfStore;
  readonly plan: WorkoutPlan;
  readonly pending: boolean;
}) {
  const router = useRouter();
  const [expandedDay, setExpandedDay] = useState<number | null>(plan.days[0]?.day_number ?? null);
  const [pdfStatus, setPdfStatus] = useState<PdfStatus>("checking");
  const [storedPdf, setStoredPdf] = useState<StoredWorkoutPlanPdf | null>(null);
  const executable = isWorkoutPlanExecutable(plan, historical);
  const averageDuration = workoutPlanAverageDuration(plan);
  const summaryStatus = getWorkoutPlanSummaryStatus(plan, historical);

  useEffect(() => {
    let active = true;
    setPdfStatus("checking");
    setStoredPdf(null);
    void pdfStore.get(plan.id).then((stored) => {
      if (!active) return;
      setStoredPdf(stored);
      setPdfStatus(stored === null ? "idle" : "ready");
    }).catch(() => {
      if (active) setPdfStatus("idle");
    });
    return () => {
      active = false;
    };
  }, [pdfStore, plan.id]);

  async function downloadPdf() {
    setPdfStatus("downloading");
    try {
      const downloaded = await api.downloadPdf(plan.id);
      const stored = await pdfStore.save(plan.id, downloaded);
      setStoredPdf(stored);
      setPdfStatus("ready");
    } catch {
      setPdfStatus("error");
    }
  }

  async function openPdf() {
    if (storedPdf === null) return;
    try {
      await Linking.openURL(storedPdf.uri);
    } catch {
      setPdfStatus("error");
    }
  }

  return (
    <View style={styles.planSection}>
      <Card style={styles.overviewCard}>
        <View style={styles.planHeading}>
          <View style={styles.planHeadingCopy}>
            <Text style={styles.sectionEyebrow}>{historical ? "نسخهٔ قبلی" : "برنامهٔ فعلی"}</Text>
            <Text style={styles.planTitle}>{plan.status === "failed" ? "ساخت برنامه ناموفق بود" : "برنامهٔ تمرینی هفتگی"}</Text>
          </View>
          <StatusPill status={summaryStatus} />
        </View>
        <View style={styles.statsRow}>
          <Stat label="مدت برنامه" value={`${plan.plan_duration_weeks} هفته`} />
          <Stat label="روزهای تمرین" value={`${plan.days.length} روز`} />
          {averageDuration !== null ? <Stat label="میانگین جلسه" value={`${averageDuration} دقیقه`} /> : null}
        </View>
      </Card>

      {historical ? <Notice message="این نسخه فقط برای مشاهدهٔ تاریخچه است و قابل اجرا نیست." variant="info" /> : null}
      {pending || plan.coach_review?.state === "pending_coach_review" ? (
        <Notice
          message="این برنامه تا تأیید مربی قابل اجرا نیست؛ جزئیات آن فقط برای بررسی نمایش داده می‌شود."
          variant="warning"
        />
      ) : null}
      {plan.status === "failed" ? (
        <Notice message="این نسخه با خطا ساخته شده و قابل اجرا نیست." variant="danger" />
      ) : null}
      {plan.is_stale ? <Notice message="اطلاعات این برنامه قدیمی است؛ قبل از اجرا وضعیت آنلاین را بررسی کن." variant="warning" /> : null}
      {plan.coach_review?.state === "coach_approved" ? (
        <Notice
          message={plan.coach_review.coach_note ?? "این برنامه توسط مربی تأیید شده است."}
          title={`تأیید مربی${plan.coach_review.coach_display_name ? `: ${plan.coach_review.coach_display_name}` : ""}`}
          variant="success"
        />
      ) : null}
      {!executable && plan.status === "active" && !historical && !pending ? (
        <Notice message="این برنامه هنوز برای اجرا آزاد نشده است." variant="warning" />
      ) : null}

      {plan.ai_coach_program_explanation_fa ? (
        <Card style={styles.aiCard}>
          <Text style={styles.aiLabel}>توضیح فیتشو کوچ</Text>
          <Text style={styles.bodyText}>{plan.ai_coach_program_explanation_fa}</Text>
        </Card>
      ) : null}

      {plan.warnings !== undefined && plan.warnings.length > 0 ? (
        <Notice message={plan.warnings.join("\n")} title="نکات ایمنی برنامه" variant="warning" />
      ) : null}

      {plan.status === "failed" || plan.days.length === 0 ? null : (
        <View style={styles.daysSection}>
          <Text style={styles.sectionTitle}>روزهای برنامه</Text>
          {plan.days.map((day) => (
            <WorkoutDayCard
              day={day}
              expanded={expandedDay === day.day_number}
              key={day.day_number}
              onOpenExercise={(slug) => router.push({ pathname: "/member/exercises/[slug]", params: { slug } })}
              onToggle={() => setExpandedDay((current) => current === day.day_number ? null : day.day_number)}
            />
          ))}
        </View>
      )}

      <Card style={styles.pdfCard}>
        <Text style={styles.sectionTitle}>نسخهٔ PDF</Text>
        <Text style={styles.bodyText}>فایل PDF در فضای پایدار برنامه ذخیره می‌شود و بعد از باز کردن دوبارهٔ اپ هم باقی می‌ماند.</Text>
        {pdfStatus === "checking" ? <Skeleton height={52} /> : null}
        {pdfStatus !== "checking" && storedPdf === null ? (
          <Button
            disabled={pdfStatus === "downloading"}
            label="ذخیرهٔ PDF برای استفاده آفلاین"
            loading={pdfStatus === "downloading"}
            onPress={() => void downloadPdf()}
            variant="secondary"
          />
        ) : null}
        {storedPdf !== null ? (
          <View style={styles.pdfActions}>
            <Button label="باز کردن PDF" onPress={() => void openPdf()} />
            <Button label="دریافت دوباره" onPress={() => void downloadPdf()} variant="ghost" />
          </View>
        ) : null}
        {pdfStatus === "error" ? (
          <Notice message="دریافت یا باز کردن PDF انجام نشد؛ دوباره تلاش کن." variant="danger" />
        ) : null}
      </Card>
    </View>
  );
}

function WorkoutDayCard({
  day,
  expanded,
  onOpenExercise,
  onToggle,
}: {
  readonly day: WorkoutDay;
  readonly expanded: boolean;
  readonly onOpenExercise: (slug: string) => void;
  readonly onToggle: () => void;
}) {
  return (
    <Card onPress={onToggle} style={styles.dayCard} variant={expanded ? "raised" : "interactive"}>
      <View style={styles.dayHeader}>
        <View style={styles.dayHeadingCopy}>
          <Text style={styles.dayNumber}>روز {day.day_number}</Text>
          <Text style={styles.dayTitle}>{day.title_fa || day.title_en}</Text>
          <Text style={styles.dayMeta}>{day.estimated_duration_minutes} دقیقه · {day.total_exercise_count} حرکت</Text>
        </View>
        <Text accessibilityLabel={expanded ? "بستن جزئیات روز" : "باز کردن جزئیات روز"} style={styles.chevron}>
          {expanded ? "⌃" : "⌄"}
        </Text>
      </View>
      {expanded ? (
        <View style={styles.dayDetails}>
          {day.ai_coach_explanation_fa ? (
            <Notice message={day.ai_coach_explanation_fa} title="توضیح این جلسه" variant="info" />
          ) : null}
          {day.exercises.map((exercise) => (
            <WorkoutExerciseRow
              exercise={exercise}
              key={exercise.id}
              onOpen={() => onOpenExercise(exercise.exercise.slug)}
            />
          ))}
        </View>
      ) : null}
    </Card>
  );
}

function WorkoutExerciseRow({
  exercise,
  onOpen,
}: {
  readonly exercise: WorkoutPlanExercise;
  readonly onOpen: () => void;
}) {
  return (
    <View style={styles.exerciseRow}>
      <View style={styles.exerciseCopy}>
        <Text style={styles.exerciseTitle}>{exercise.exercise.name_fa || exercise.exercise.name_en}</Text>
        <Text style={styles.exerciseSecondary}>{exercise.exercise.name_en}</Text>
        <View style={styles.exerciseStats}>
          <Text style={styles.exerciseStat}>{exercise.sets} ست</Text>
          <Text style={styles.exerciseStat}>{formatWorkoutPrescription(exercise)}</Text>
          <Text style={styles.exerciseStat}>{exercise.rest_seconds} ثانیه استراحت</Text>
          {exercise.rir !== null ? <Text style={styles.exerciseStat}>RIR {exercise.rir}</Text> : null}
        </View>
        {exercise.notes_fa ? <Text style={styles.exerciseNote}>{exercise.notes_fa}</Text> : null}
        {exercise.load_guidance ? <Text style={styles.exerciseNote}>{exercise.load_guidance}</Text> : null}
        {exercise.alternatives.length > 0 ? (
          <Text style={styles.exerciseAlternative}>
            {exercise.alternatives.length} جایگزین امن در دسترس است.
          </Text>
        ) : null}
      </View>
      <Button label="راهنما" onPress={onOpen} variant="ghost" />
    </View>
  );
}

function WorkoutHistory({
  activePlanId,
  history,
  historyState,
  onRetry,
  onSelect,
  selectedPlanId,
}: {
  readonly activePlanId: string | null;
  readonly history: readonly WorkoutPlanVersionSummary[];
  readonly historyState: MobileViewState<WorkoutPlanVersionSummary[]>;
  readonly onRetry: () => void;
  readonly onSelect: (version: WorkoutPlanVersionSummary) => void;
  readonly selectedPlanId: string | null;
}) {
  const versions = history.filter((version) => version.status !== "pending_review");
  if (historyState.status === "loading") return <Skeleton height={120} />;
  if (historyState.status === "error" && history.length === 0) {
    return <Notice actionLabel="تلاش دوباره" message="تاریخچهٔ برنامه دریافت نشد." onAction={onRetry} variant="danger" />;
  }
  if (historyState.status === "offline" && history.length === 0) {
    return <Notice message="تاریخچهٔ برنامه در حالت آفلاین در دسترس نیست." variant="offline" />;
  }
  if (versions.length === 0) return null;

  return (
    <View style={styles.historySection}>
      <Text style={styles.sectionTitle}>تاریخچهٔ برنامه‌ها</Text>
      {historyState.status === "offline" ? <Notice message="فهرست تاریخچه تازه‌سازی نشده است." variant="offline" /> : null}
      {versions.map((version) => (
        <Card
          key={version.id}
          onPress={() => onSelect(version)}
          style={styles.historyCard}
          variant={selectedPlanId === version.id || activePlanId === version.id ? "raised" : "interactive"}
        >
          <View style={styles.historyRow}>
            <View style={styles.historyCopy}>
              <Text style={styles.historyTitle}>{historyLabel(version)}</Text>
              <Text style={styles.historyDate}>{formatDate(version.created_at)}</Text>
            </View>
            <Text style={styles.historyState}>{version.is_active ? "فعال" : "آرشیو"}</Text>
          </View>
        </Card>
      ))}
    </View>
  );
}

function StatusPill({ status }: { readonly status: ReturnType<typeof getWorkoutPlanSummaryStatus> }) {
  const label = status === "active" ? "فعال" : status === "pending" ? "در انتظار تأیید" : "آرشیو";
  return <Text style={[styles.statusPill, status === "active" ? styles.statusActive : styles.statusPending]}>{label}</Text>;
}

function Stat({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
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
  if (version.status === "failed") return "نسخهٔ ناموفق";
  if (version.status === "active") return "نسخهٔ فعال";
  return "نسخهٔ اولیه";
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" }).format(new Date(value));
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

const styles = StyleSheet.create({
  aiCard: {
    borderColor: fiticianTokens.colors.aqua,
    gap: fiticianTokens.spacing[2],
  },
  aiLabel: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  bodyText: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 27,
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
  chevron: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
  },
  dayCard: {
    gap: fiticianTokens.spacing[3],
  },
  dayDetails: {
    gap: fiticianTokens.spacing[3],
  },
  daysSection: {
    gap: fiticianTokens.spacing[3],
  },
  dayHeader: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  dayHeadingCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  dayMeta: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  dayNumber: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  dayTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
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
  exerciseAlternative: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 19,
    textAlign: "right",
    writingDirection: "rtl",
  },
  exerciseCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  exerciseNote: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  exerciseRow: {
    alignItems: "flex-start",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    paddingBottom: fiticianTokens.spacing[3],
  },
  exerciseSecondary: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "ltr",
  },
  exerciseStat: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  exerciseStats: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  exerciseTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.lg,
    lineHeight: 26,
    textAlign: "right",
    writingDirection: "rtl",
  },
  generateSection: {
    marginTop: fiticianTokens.spacing[3],
  },
  header: {
    alignItems: "flex-end",
    gap: fiticianTokens.spacing[2],
    marginBottom: fiticianTokens.spacing[4],
  },
  historyCard: {
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
    textAlign: "right",
    writingDirection: "rtl",
  },
  historyRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  historySection: {
    gap: fiticianTokens.spacing[3],
    marginTop: fiticianTokens.spacing[5],
  },
  historyState: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  historyTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  intro: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 27,
    textAlign: "right",
    writingDirection: "rtl",
  },
  overviewCard: {
    gap: fiticianTokens.spacing[4],
  },
  pdfActions: {
    gap: fiticianTokens.spacing[2],
  },
  pdfCard: {
    gap: fiticianTokens.spacing[3],
    marginTop: fiticianTokens.spacing[4],
  },
  planHeading: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  planHeadingCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  planSection: {
    gap: fiticianTokens.spacing[3],
  },
  planTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
    lineHeight: 32,
    textAlign: "right",
    writingDirection: "rtl",
  },
  sectionEyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
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
  skeletonGroup: {
    gap: fiticianTokens.spacing[3],
  },
  stat: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  statLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  statValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  statsRow: {
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
  },
  statusActive: {
    backgroundColor: "rgba(102,200,159,0.16)",
    color: fiticianTokens.colors.success,
  },
  statusPending: {
    backgroundColor: "rgba(242,184,91,0.16)",
    color: fiticianTokens.colors.amber,
  },
  statusPill: {
    borderRadius: fiticianTokens.radii.pill,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    overflow: "hidden",
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[1],
    textAlign: "center",
    writingDirection: "rtl",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 40,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
