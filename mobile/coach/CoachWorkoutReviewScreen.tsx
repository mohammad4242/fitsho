import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { components } from "@fitician/core";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { coachKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { Button, Card, EmptyState, Notice, Skeleton, TextField } from "../ui/components";
import { Screen } from "../ui/layout";
import { getMobileViewState, type MobileViewState } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import {
  createCoachWorkoutReviewApi,
  type CoachWorkoutReviewDetail,
  type CoachWorkoutReviewView,
} from "./coachWorkoutReviewApi";
import {
  coachReviewErrorMessage,
  coachReviewStatusLabel,
  getCoachDraft,
  hasRequiredRejectionExplanation,
  isCoachReviewReadOnly,
} from "./coachWorkoutReviewModel";

type CoachDraft = ReturnType<typeof getCoachDraft>;
type CoachDraftDay = CoachDraft["days"][number];
type CoachDraftExercise = CoachDraftDay["exercises"][number];

const queueViews: readonly CoachWorkoutReviewView[] = ["pending", "mine", "approved"];

export function CoachWorkoutReviewScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const connectivityStatus = useConnectivityStatus();
  const api = useMemo(() => createCoachWorkoutReviewApi(auth.request), [auth.request]);
  const [view, setView] = useState<CoachWorkoutReviewView>("pending");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<CoachDraft | null>(null);
  const [rejectionExplanation, setRejectionExplanation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const queueQuery = useQuery({
    queryFn: () => api.list(view),
    queryKey: coachKeys.list(view),
  });
  const detailQuery = useQuery({
    enabled: selectedId !== null,
    queryFn: () => api.get(selectedId as string),
    queryKey: coachKeys.detail(selectedId ?? "selected"),
  });
  const queueState = getMobileViewState(queueQuery, {
    connectivityStatus,
    isEmpty: (data) => data.length === 0,
  });
  const detailState = getMobileViewState(detailQuery, { connectivityStatus });
  const selected = viewData(detailState);
  const offline = connectivityStatus === "offline";
  const readOnly = selected === undefined
    ? offline
    : isCoachReviewReadOnly(selected.status, offline);

  useEffect(() => {
    if (selected === undefined) return;
    setDraft(getCoachDraft(selected));
    setRejectionExplanation("");
    setError(null);
    setMessage(null);
  }, [selected]);

  async function openReview(reviewId: string, status: CoachWorkoutReviewView | "claimed") {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const detail = status === "pending"
        ? await api.claim(reviewId)
        : await api.get(reviewId);
      queryClient.setQueryData(coachKeys.detail(reviewId), detail);
      setSelectedId(reviewId);
      if (status === "pending") await queueQuery.refetch();
    } catch (requestError) {
      setError(coachReviewErrorMessage(requestError));
      await queueQuery.refetch();
    } finally {
      setBusy(false);
    }
  }

  async function saveDraft() {
    if (selected === undefined || draft === null || readOnly) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await api.saveDraft(selected.id, draft);
      queryClient.setQueryData(coachKeys.detail(selected.id), updated);
      setMessage("پیش‌نویس با موفقیت ذخیره شد.");
    } catch (requestError) {
      setError(coachReviewErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function decide(decision: "approve" | "reject") {
    if (selected === undefined || readOnly) return;
    if (decision === "reject" && !hasRequiredRejectionExplanation(rejectionExplanation)) {
      setError("برای رد برنامه، توضیح اصلاحات الزامی است.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const latest = await api.get(selected.id);
      if (latest.draft_revision !== selected.draft_revision) {
        queryClient.setQueryData(coachKeys.detail(selected.id), latest);
        setError("نسخهٔ پرونده تغییر کرده است؛ پیش‌نویس جدید را بررسی کن.");
        return;
      }
      const updated = decision === "approve"
        ? await api.approve(selected.id, latest.draft_revision)
        : await api.reject(selected.id, latest.draft_revision, rejectionExplanation.trim());
      queryClient.setQueryData(coachKeys.detail(selected.id), updated);
      setMessage(decision === "approve" ? "برنامه تأیید شد." : "برنامه برای اصلاح برگشت داده شد.");
      await queueQuery.refetch();
    } catch (requestError) {
      setError(coachReviewErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  function updateExercise(
    dayIndex: number,
    exerciseIndex: number,
    patch: Partial<CoachDraftExercise>,
  ) {
    setDraft((current) => current === null ? current : {
      ...current,
      days: current.days.map((day, currentDayIndex) => currentDayIndex !== dayIndex
        ? day
        : {
            ...day,
            exercises: day.exercises.map((exercise, currentExerciseIndex) =>
              currentExerciseIndex === exerciseIndex ? { ...exercise, ...patch } : exercise,
            ),
          }),
    });
  }

  return (
    <Screen contentWidth="reading">
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <Text style={styles.brand}>FITICIAN</Text>
          <Text accessibilityRole="header" style={styles.title}>بازبینی برنامه‌های تمرینی</Text>
          <Text style={styles.subtitle}>نسخه اولیه تا تأیید مربی فعال باقی می‌ماند.</Text>
        </View>
        <Button label="بازگشت" onPress={() => router.back()} variant="ghost" />
      </View>

      {offline ? <Notice message="حالت آفلاین فعال است؛ پرونده‌ها فقط برای مشاهده هستند." variant="offline" /> : null}
      {error ? <Notice message={error} variant="danger" /> : null}
      {message ? <Notice message={message} variant="success" /> : null}

      <View style={styles.queueTabs} accessibilityRole="tablist">
        {queueViews.map((item) => (
          <Pressable
            accessibilityRole="tab"
            accessibilityState={{ selected: view === item }}
            key={item}
            onPress={() => {
              setView(item);
              setSelectedId(null);
              setDraft(null);
            }}
            style={[styles.queueTab, view === item && styles.queueTabActive]}
          >
            <Text style={styles.queueTabText}>{queueLabel(item)}</Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.workspace}>
        <View style={styles.queue}>
          <Text style={styles.sectionTitle}>صف پرونده‌ها</Text>
          <QueueState
            onRetry={() => void queueQuery.refetch()}
            onSelect={openReview}
            selectedId={selectedId}
            state={queueState}
            view={view}
          />
        </View>
        <View style={styles.detail}>
          {selected === undefined && detailState.status === "loading" ? <Skeleton height={240} /> : null}
          {selected === undefined && detailState.status === "offline" ? (
            <Notice message="جزئیات این پرونده در حافظهٔ فعلی نیست." variant="offline" />
          ) : null}
          {selected === undefined && detailState.status === "error" ? (
            <Notice actionLabel="تلاش دوباره" message="جزئیات پرونده دریافت نشد." onAction={() => void detailQuery.refetch()} variant="danger" />
          ) : null}
          {selected !== undefined && draft !== null ? (
            <CoachReviewDetail
              busy={busy}
              detail={selected}
              draft={draft}
              onApprove={() => void decide("approve")}
              onDraftChange={setDraft}
              onExerciseChange={updateExercise}
              onReject={() => void decide("reject")}
              onRejectionExplanationChange={setRejectionExplanation}
              onSave={() => void saveDraft()}
              readOnly={readOnly}
              rejectionExplanation={rejectionExplanation}
            />
          ) : null}
          {selected === undefined && detailState.status !== "loading" && selectedId === null ? (
            <EmptyState title="یک پرونده را از صف انتخاب کن">
              <Text style={styles.body}>پس از باز کردن پرونده، خلاصهٔ برنامه و ابزار بررسی نمایش داده می‌شود.</Text>
            </EmptyState>
          ) : null}
        </View>
      </View>
    </Screen>
  );
}

function QueueState({
  onRetry,
  onSelect,
  selectedId,
  state,
  view,
}: {
  readonly onRetry: () => void;
  readonly onSelect: (reviewId: string, status: CoachWorkoutReviewView | "claimed") => void;
  readonly selectedId: string | null;
  readonly state: MobileViewState<components["schemas"]["WorkoutReviewQueueItemResponse"][]>;
  readonly view: CoachWorkoutReviewView;
}) {
  if (state.status === "loading") return <Skeleton height={180} />;
  if (state.status === "error" && state.data === undefined) {
    return <Notice actionLabel="تلاش دوباره" message="صف بازبینی دریافت نشد." onAction={onRetry} variant="danger" />;
  }
  if (state.status === "offline" && state.data === undefined) {
    return <Notice message="صف بازبینی در این حالت آفلاین در دسترس نیست." variant="offline" />;
  }
  const items = state.data ?? [];
  if (items.length === 0) return <EmptyState title="این صف خالی است" />;
  return (
    <View style={styles.queueItems}>
      {state.status === "offline" ? <Notice message="فهرست نمایش‌داده‌شده آخرین دادهٔ دریافت‌شده است." variant="offline" /> : null}
      {items.map((item) => (
        <Card key={item.id} style={selectedId === item.id ? styles.selectedCard : undefined} variant={selectedId === item.id ? "raised" : "interactive"}>
          <Text style={styles.memberName}>{item.member_display_name ?? "کاربر فیتیشین"}</Text>
          <Text style={styles.queueMeta}>{humanize(item.fitness_goal)} · {humanize(item.experience_level)}</Text>
          <Text style={styles.status}>{coachReviewStatusLabel(item.status)}</Text>
          <Button
            disabled={state.status === "offline"}
            label={item.status === "pending" ? "شروع بررسی" : "باز کردن پرونده"}
            onPress={() => onSelect(item.id, item.status === "pending" ? "pending" : view)}
            variant="secondary"
          />
        </Card>
      ))}
    </View>
  );
}

function CoachReviewDetail({
  busy,
  detail,
  draft,
  onApprove,
  onDraftChange,
  onExerciseChange,
  onReject,
  onRejectionExplanationChange,
  onSave,
  readOnly,
  rejectionExplanation,
}: {
  readonly busy: boolean;
  readonly detail: CoachWorkoutReviewDetail;
  readonly draft: CoachDraft;
  readonly onApprove: () => void;
  readonly onDraftChange: (draft: CoachDraft) => void;
  readonly onExerciseChange: (dayIndex: number, exerciseIndex: number, patch: Partial<CoachDraftExercise>) => void;
  readonly onReject: () => void;
  readonly onRejectionExplanationChange: (value: string) => void;
  readonly onSave: () => void;
  readonly readOnly: boolean;
  readonly rejectionExplanation: string;
}) {
  const sourceSummary = sourcePlanSummary(detail.source_plan);
  return (
    <View style={styles.detailContent}>
      <View style={styles.detailHeader}>
        <View style={styles.headerCopy}>
          <Text style={styles.eyebrow}>پروندهٔ برنامه</Text>
          <Text style={styles.detailTitle}>{detail.member_display_name ?? "کاربر فیتیشین"}</Text>
        </View>
        <Text style={styles.status}>{coachReviewStatusLabel(detail.status)}</Text>
      </View>
      <Card style={styles.summaryCard}>
        <Text style={styles.sectionTitle}>خلاصهٔ برنامه</Text>
        <Text style={styles.body}>هدف: {humanize(detail.fitness_goal)}</Text>
        <Text style={styles.body}>سطح: {humanize(detail.experience_level)}</Text>
        <Text style={styles.body}>روزها: {sourceSummary.days} · مدت: {sourceSummary.durationWeeks ?? "—"} هفته</Text>
        {detail.template_selection ? <Text style={styles.body}>{detail.template_selection.explanation_fa}</Text> : null}
        {detail.coach_quality_metrics ? <Text style={styles.muted}>وضعیت اعتبارسنجی: {detail.coach_quality_metrics.hard_validation_status}</Text> : null}
      </Card>

      {readOnly ? <Notice message="این پرونده در حالت فقط‌خواندنی نمایش داده می‌شود." variant="info" /> : null}
      <Text style={styles.sectionTitle}>پیش‌نویس مربی · نسخه {detail.draft_revision}</Text>
      {draft.days.length === 0 ? <Notice message="پیش‌نویس برنامه در دسترس نیست." variant="warning" /> : null}
      {draft.days.map((day, dayIndex) => (
        <Card key={day.day_number} style={styles.dayCard}>
          <Text style={styles.dayTitle}>روز {day.day_number}</Text>
          {day.exercises.map((exercise, exerciseIndex) => (
            <ReviewExerciseEditor
              disabled={readOnly || busy}
              exercise={exercise}
              key={`${day.day_number}-${exercise.order_index}`}
              onChange={(patch) => onExerciseChange(dayIndex, exerciseIndex, patch)}
            />
          ))}
        </Card>
      ))}

      <TextField
        editable={!readOnly && !busy}
        label="یادداشت مربی"
        multiline
        numberOfLines={4}
        onChangeText={(value) => onDraftChange({ ...draft, coach_note: value.trim() || null })}
        value={draft.coach_note ?? ""}
      />
      {!readOnly ? (
        <>
          <Button disabled={busy || draft.days.length === 0} label="ذخیرهٔ پیش‌نویس" loading={busy} onPress={onSave} variant="secondary" />
          <TextField
            editable={!busy}
            hint="برای رد برنامه، دلیل قابل اقدام برای اصلاح را بنویس."
            label="توضیح اصلاحات الزامی برای رد"
            multiline
            numberOfLines={4}
            onChangeText={onRejectionExplanationChange}
            value={rejectionExplanation}
          />
          <View style={styles.decisionRow}>
            <Button disabled={busy} label="رد و درخواست اصلاح" onPress={onReject} variant="danger" />
            <Button disabled={busy || draft.days.length === 0} label="تأیید برنامه" onPress={onApprove} />
          </View>
        </>
      ) : null}
    </View>
  );
}

function ReviewExerciseEditor({
  disabled,
  exercise,
  onChange,
}: {
  readonly disabled: boolean;
  readonly exercise: CoachDraftExercise;
  readonly onChange: (patch: Partial<CoachDraftExercise>) => void;
}) {
  return (
    <View style={styles.exerciseEditor}>
      <Text style={styles.exerciseTitle}>حرکت {exercise.order_index}</Text>
      <View style={styles.numberRow}>
        <TextField
          editable={!disabled}
          keyboardType="number-pad"
          label="ست"
          onChangeText={(value) => onChange({ sets: positiveNumber(value, exercise.sets) })}
          value={String(exercise.sets)}
        />
        <TextField
          editable={!disabled}
          keyboardType="number-pad"
          label="تکرار حداقل"
          onChangeText={(value) => onChange({ reps_min: positiveNumber(value, exercise.reps_min ?? 1) })}
          value={String(exercise.reps_min ?? "")}
        />
        <TextField
          editable={!disabled}
          keyboardType="number-pad"
          label="تکرار حداکثر"
          onChangeText={(value) => onChange({ reps_max: positiveNumber(value, exercise.reps_max ?? 1) })}
          value={String(exercise.reps_max ?? "")}
        />
      </View>
      <Text style={styles.muted}>استراحت: {exercise.rest_seconds} ثانیه · RIR: {exercise.rir ?? "—"}</Text>
      {exercise.notes_fa ? <Text style={styles.body}>{exercise.notes_fa}</Text> : null}
    </View>
  );
}

function sourcePlanSummary(value: Record<string, unknown>): { readonly days: number; readonly durationWeeks: number | null } {
  const days = value.days;
  const duration = value.plan_duration_weeks;
  return {
    days: Array.isArray(days) ? days.length : 0,
    durationWeeks: typeof duration === "number" ? duration : null,
  };
}

function viewData<TData>(state: MobileViewState<TData>): TData | undefined {
  return state.status === "loading" ? undefined : "data" in state ? state.data : undefined;
}

function positiveNumber(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function queueLabel(view: CoachWorkoutReviewView): string {
  if (view === "pending") return "در انتظار";
  if (view === "mine") return "در حال بررسی من";
  return "تأییدشده";
}

function humanize(value: string | null): string {
  if (!value) return "ثبت نشده";
  return value.replaceAll("_", " ");
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

const styles = StyleSheet.create({
  body: {
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
    writingDirection: "ltr",
  },
  dayCard: { gap: fiticianTokens.spacing[3] },
  dayTitle: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    textAlign: "right",
    writingDirection: "rtl",
  },
  decisionRow: { flexDirection: "row", gap: fiticianTokens.spacing[2] },
  detail: { gap: fiticianTokens.spacing[4] },
  detailContent: { gap: fiticianTokens.spacing[4] },
  detailHeader: { alignItems: "center", flexDirection: "row", justifyContent: "space-between" },
  detailTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
    textAlign: "right",
    writingDirection: "rtl",
  },
  exerciseEditor: { borderTopColor: fiticianTokens.colors.line, borderTopWidth: 1, gap: fiticianTokens.spacing[2], paddingTop: fiticianTokens.spacing[3] },
  exerciseTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  eyebrow: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  header: { alignItems: "flex-start", flexDirection: "row", gap: fiticianTokens.spacing[3], justifyContent: "space-between" },
  headerCopy: { flex: 1, gap: fiticianTokens.spacing[2] },
  memberName: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  muted: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  numberRow: { flexDirection: "row", gap: fiticianTokens.spacing[2] },
  queue: { gap: fiticianTokens.spacing[3] },
  queueItems: { gap: fiticianTokens.spacing[3] },
  queueMeta: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  queueTab: {
    alignItems: "center",
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flex: 1,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    justifyContent: "center",
    paddingHorizontal: fiticianTokens.spacing[2],
  },
  queueTabActive: { backgroundColor: fiticianTokens.colors.aqua, borderColor: fiticianTokens.colors.aqua },
  queueTabText: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "center",
    writingDirection: "rtl",
  },
  queueTabs: { flexDirection: "row", gap: fiticianTokens.spacing[2] },
  sectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    textAlign: "right",
    writingDirection: "rtl",
  },
  selectedCard: { borderColor: fiticianTokens.colors.aqua },
  status: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  subtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 26,
    textAlign: "right",
    writingDirection: "rtl",
  },
  summaryCard: { gap: fiticianTokens.spacing[2] },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 40,
    textAlign: "right",
    writingDirection: "rtl",
  },
  workspace: { gap: fiticianTokens.spacing[6] },
});
