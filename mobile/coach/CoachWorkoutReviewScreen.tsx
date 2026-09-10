import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { components } from "@fitician/core";

import { AccountPrivacyLinks } from "../accountDeletion/AccountPrivacyLinks";
import { useMobileAuth } from "../auth/MobileAuthProvider";
import { coachKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import {
  Button,
  Card,
  DisclosureCard,
  EmptyState,
  Notice,
  PageHeading,
  SegmentedControl,
  Sheet,
  Skeleton,
  TextField,
} from "../ui/components";
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
type CoachExerciseOption = CoachWorkoutReviewDetail["exercise_options"][number];
type CoachTemplateSelection = NonNullable<CoachWorkoutReviewDetail["template_selection"]>;

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

  function clearSelectedReview() {
    setSelectedId(null);
    setDraft(null);
    setRejectionExplanation("");
  }

  function goBack(): boolean {
    if (selectedId !== null) {
      clearSelectedReview();
      return true;
    }
    router.back();
    return true;
  }

  useAndroidBackHandler("wizard", goBack);

  useEffect(() => {
    if (selected === undefined) return;
    setDraft(getCoachDraft(selected));
    setRejectionExplanation("");
    setError(null);
    setMessage(null);
  }, [selected?.draft_revision, selected?.id]);

  useEffect(() => {
    if (selected?.status !== "claimed" || offline) return undefined;
    const timer = setInterval(() => {
      void api.renew(selected.id)
        .then((updated) => queryClient.setQueryData(coachKeys.detail(selected.id), updated))
        .catch(() => setError("زمان بازبینی منقضی شد؛ پرونده را دوباره باز کن."));
    }, 8 * 60 * 1000);
    return () => clearInterval(timer);
  }, [api, offline, queryClient, selected?.id, selected?.status]);

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
      if (status === "pending") setView("mine");
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

  function updateExerciseSelection(
    dayIndex: number,
    exerciseIndex: number,
    exerciseId: string,
  ) {
    const option = selected?.exercise_options.find((item) => item.id === exerciseId);
    if (option === undefined) return;
    if (option.prescription_mode === "duration") {
      updateExercise(dayIndex, exerciseIndex, {
        duration_min_seconds: option.duration_min_seconds ?? null,
        duration_max_seconds: option.duration_max_seconds ?? null,
        exercise_id: exerciseId,
        prescription_mode: "duration",
        reps_min: null,
        reps_max: null,
        rir: null,
      });
      return;
    }
    updateExercise(dayIndex, exerciseIndex, {
      duration_min_seconds: null,
      duration_max_seconds: null,
      exercise_id: exerciseId,
      prescription_mode: "reps",
      reps_min: 8,
      reps_max: 12,
      rir: 2,
    });
  }

  return (
    <Screen contentWidth="reading">
      <PageHeading
        action={<Button label="بازگشت" onPress={goBack} variant="ghost" />}
        eyebrow="میز کار مربی"
        supportingText="نسخه اولیه فعال می‌ماند تا نسخه تو با اعتبارسنجی کامل تأیید شود."
        title="بازبینی برنامه‌های تمرینی"
      />

      <ReviewLeaseCard leaseExpiresAt={selected?.lease_expires_at ?? null} />

      {offline ? <Notice message="حالت آفلاین فعال است؛ پرونده‌ها فقط برای مشاهده هستند." variant="offline" /> : null}
      {error ? <Notice message={error} variant="danger" /> : null}
      {message ? <Notice message={message} variant="success" /> : null}

      <SegmentedControl
        accessibilityLabel="صف‌های بازبینی"
        disabled={busy}
        onChange={(value) => {
          setView(value as CoachWorkoutReviewView);
          clearSelectedReview();
        }}
        options={queueViews.map((item) => ({ label: queueLabel(item), value: item }))}
        selectedValue={view}
      />

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
              onExerciseSelection={updateExerciseSelection}
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
      <AccountPrivacyLinks />
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
            label={item.status === "pending" ? "شروع بازبینی" : "مشاهده پرونده"}
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
  onExerciseSelection,
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
  readonly onExerciseSelection: (dayIndex: number, exerciseIndex: number, exerciseId: string) => void;
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
          <View style={styles.memberIdentity}>
            <Text style={styles.detailTitle}>{detail.member_display_name ?? "کاربر فیتیشین"}</Text>
            <MemberAvatar label={detail.member_display_name ?? "کاربر فیتیشین"} />
          </View>
        </View>
        <Text style={styles.status}>{coachReviewStatusLabel(detail.status)}</Text>
      </View>

      <View style={styles.profileStrip}>
        <ProfileMetric label="هدف" value={humanize(detail.fitness_goal)} />
        <ProfileMetric label="سابقه" value={humanize(detail.experience_level)} />
        <ProfileMetric label="مدت" value={sourceSummary.durationWeeks === null ? "ثبت نشده" : `${faNumber(sourceSummary.durationWeeks)} هفته`} />
      </View>

      {detail.template_selection ? <TemplateSelectionAudit selection={detail.template_selection} /> : null}

      <View style={styles.versionLabels}>
        <Text style={styles.versionLabel}>نسخه اولیه — فقط خواندنی</Text>
        <Text style={styles.versionLabelActive}>
          {readOnly ? "نسخه تأییدشده" : `پیش‌نویس مربی · نسخه ${faNumber(detail.draft_revision)}`}
        </Text>
      </View>

      <Card style={styles.summaryCard}>
        <Text style={styles.sectionTitle}>خلاصهٔ برنامه</Text>
        <Text style={styles.body}>روزها: {faNumber(sourceSummary.days)} · مدت: {sourceSummary.durationWeeks === null ? "ثبت نشده" : `${faNumber(sourceSummary.durationWeeks)} هفته`}</Text>
        {detail.coach_quality_metrics ? (
          <Text style={styles.muted}>وضعیت اعتبارسنجی: {validationStatusLabel(detail.coach_quality_metrics.hard_validation_status)}</Text>
        ) : null}
      </Card>

      {readOnly ? <Notice message="این پرونده در حالت فقط‌خواندنی نمایش داده می‌شود." variant="info" /> : null}
      <Text style={styles.sectionTitle}>پیش‌نویس مربی · نسخه {faNumber(detail.draft_revision)}</Text>
      {draft.days.length === 0 ? <Notice message="پیش‌نویس برنامه در دسترس نیست." variant="warning" /> : null}
      {draft.days.map((day, dayIndex) => (
        <Card key={day.day_number} style={styles.dayCard}>
          <View style={styles.dayHeader}>
            <Text style={styles.dayTitle}>روز {faNumber(day.day_number)}</Text>
            <Text style={styles.dayNumber}>{faNumber(day.day_number).padStart(2, "۰")}</Text>
          </View>
          {day.exercises.map((exercise, exerciseIndex) => (
            <ReviewExerciseEditor
              disabled={readOnly || busy}
              exercise={exercise}
              key={`${day.day_number}-${exercise.order_index}`}
              options={detail.exercise_options}
              onChange={(patch) => onExerciseChange(dayIndex, exerciseIndex, patch)}
              onSelect={(exerciseId) => onExerciseSelection(dayIndex, exerciseIndex, exerciseId)}
            />
          ))}
        </Card>
      ))}

      <TextField
        editable={!readOnly && !busy}
        label="یادداشت مربی برای کاربر"
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
            <Button disabled={busy} label="برگشت برای اصلاح" onPress={onReject} variant="danger" />
            <Button disabled={busy || draft.days.length === 0} label="تأیید و ارسال برای کاربر" onPress={onApprove} />
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
  onSelect,
  options,
}: {
  readonly disabled: boolean;
  readonly exercise: CoachDraftExercise;
  readonly onChange: (patch: Partial<CoachDraftExercise>) => void;
  readonly onSelect: (exerciseId: string) => void;
  readonly options: readonly CoachExerciseOption[];
}) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const selectedOption = options.find((option) => option.id === exercise.exercise_id);
  const durationMode = exercise.prescription_mode === "duration";

  return (
    <>
      <View style={styles.exerciseEditor}>
        <Text style={styles.exerciseTitle}>حرکت {faNumber(exercise.order_index)}</Text>
        <Pressable
          accessibilityLabel="انتخاب حرکت"
          accessibilityRole="button"
          accessibilityState={{ disabled }}
          disabled={disabled}
          onPress={() => setPickerOpen(true)}
          style={styles.exercisePicker}
        >
          <Text style={styles.fieldLabel}>انتخاب حرکت</Text>
          <Text style={styles.exercisePickerValue}>{selectedOption?.name_fa ?? "حرکت انتخاب نشده"}</Text>
        </Pressable>
        <View style={styles.numberRow}>
          <TextField
            editable={!disabled}
            keyboardType="number-pad"
            label="ست"
            onChangeText={(value) => onChange({ sets: boundedNumber(value, exercise.sets, 1, 10) })}
            value={String(exercise.sets)}
          />
          {durationMode ? (
            <>
              <TextField
                editable={!disabled}
                keyboardType="number-pad"
                label="حداقل ثانیه"
                onChangeText={(value) => onChange({ duration_min_seconds: positiveNumber(value, exercise.duration_min_seconds ?? 1) })}
                value={String(exercise.duration_min_seconds ?? "")}
              />
              <TextField
                editable={!disabled}
                keyboardType="number-pad"
                label="حداکثر ثانیه"
                onChangeText={(value) => onChange({ duration_max_seconds: positiveNumber(value, exercise.duration_max_seconds ?? 1) })}
                value={String(exercise.duration_max_seconds ?? "")}
              />
            </>
          ) : (
            <>
              <TextField
                editable={!disabled}
                keyboardType="number-pad"
                label="تکرار حداقل"
                onChangeText={(value) => onChange({ reps_min: boundedNumber(value, exercise.reps_min ?? 1, 1, 100) })}
                value={String(exercise.reps_min ?? "")}
              />
              <TextField
                editable={!disabled}
                keyboardType="number-pad"
                label="تکرار حداکثر"
                onChangeText={(value) => onChange({ reps_max: boundedNumber(value, exercise.reps_max ?? 1, 1, 100) })}
                value={String(exercise.reps_max ?? "")}
              />
            </>
          )}
        </View>
        <View style={styles.numberRow}>
          {!durationMode ? (
            <TextField
              editable={!disabled}
              keyboardType="number-pad"
              label="RIR"
              onChangeText={(value) => onChange({ rir: boundedNumber(value, exercise.rir ?? 0, 0, 5) })}
              value={String(exercise.rir ?? "")}
            />
          ) : null}
          <TextField
            editable={!disabled}
            keyboardType="number-pad"
            label="استراحت به ثانیه"
            onChangeText={(value) => onChange({ rest_seconds: boundedNumber(value, exercise.rest_seconds, 0, 600) })}
            value={String(exercise.rest_seconds)}
          />
        </View>
        <TextField
          editable={!disabled}
          label="یادداشت فارسی حرکت"
          multiline
          numberOfLines={3}
          onChangeText={(value) => onChange({ notes_fa: value || null })}
          value={exercise.notes_fa ?? ""}
        />
        <TextField
          editable={!disabled}
          label="یادداشت انگلیسی حرکت"
          multiline
          numberOfLines={3}
          onChangeText={(value) => onChange({ notes_en: value || null })}
          textDirection="ltr"
          value={exercise.notes_en ?? ""}
        />
      </View>
      <Sheet
        closeLabel="بستن انتخاب حرکت"
        onClose={() => setPickerOpen(false)}
        title="انتخاب حرکت"
        visible={pickerOpen}
      >
        <Text style={styles.muted}>حرکت جایگزین را از گزینه‌های مجاز انتخاب کن.</Text>
        {options.map((option) => (
          <Pressable
            accessibilityLabel={option.name_fa}
            accessibilityRole="button"
            accessibilityState={{ selected: option.id === exercise.exercise_id }}
            key={option.id}
            onPress={() => {
              onSelect(option.id);
              setPickerOpen(false);
            }}
            style={styles.exerciseOption}
          >
            <Text style={styles.exerciseOptionFa}>{option.name_fa}</Text>
            <Text style={styles.exerciseOptionEn}>{option.name_en}</Text>
          </Pressable>
        ))}
      </Sheet>
    </>
  );
}

function ReviewLeaseCard({ leaseExpiresAt }: { readonly leaseExpiresAt: string | null }) {
  return (
    <Card accessibilityLabel="زمان قفل بازبینی" style={styles.leaseCard} variant="hero">
      <View style={styles.leaseCopy}>
        <Text style={styles.eyebrow}>قفل بازبینی تا</Text>
        <Text style={styles.leaseValue}>{reviewLeaseLabel(leaseExpiresAt)}</Text>
      </View>
      <View style={styles.leaseIndicator} />
    </Card>
  );
}

function MemberAvatar({ label }: { readonly label: string }) {
  return (
    <View accessibilityLabel={`تصویر ${label}`} style={styles.avatar}>
      <Text style={styles.avatarText}>{label.trim().slice(0, 1) || "ف"}</Text>
    </View>
  );
}

function ProfileMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.profileMetric}>
      <Text style={styles.profileMetricLabel}>{label}</Text>
      <Text style={styles.profileMetricValue}>{value}</Text>
    </View>
  );
}

function TemplateSelectionAudit({ selection }: { readonly selection: CoachTemplateSelection }) {
  const scores = [
    ["اولویت عضلانی", selection.score.priority],
    ["آنالیز بدن", selection.score.body_analysis],
    ["هدف", selection.score.goal],
    ["پیش‌فرض جنسیتی", selection.score.sex],
    ["ساختار متعادل", selection.score.fallback],
    ["مجموع", selection.score.total],
  ] as const;

  return (
    <DisclosureCard
      icon="training"
      summary={selection.explanation_fa}
      title="علت انتخاب برنامه"
    >
      <Text style={styles.body}>{selection.explanation_fa}</Text>
      <View style={styles.templateSlug}>
        <Text style={styles.muted}>قالب منتخب</Text>
        <Text style={styles.templateSlugValue}>{selection.selected_template}</Text>
      </View>
      <View style={styles.scoreGrid}>
        {scores.map(([label, value]) => (
          <View key={label} style={[styles.scoreItem, label === "مجموع" && styles.scoreItemTotal]}>
            <Text style={styles.scoreLabel}>{label}</Text>
            <Text style={styles.scoreValue}>{formatPersianNumber(value)}</Text>
          </View>
        ))}
      </View>
    </DisclosureCard>
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

function boundedNumber(value: string, fallback: number, minimum: number, maximum: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed)
    ? Math.min(maximum, Math.max(minimum, parsed))
    : fallback;
}

function queueLabel(view: CoachWorkoutReviewView): string {
  if (view === "pending") return "در انتظار بررسی";
  if (view === "mine") return "در حال بررسی من";
  return "تأییدشده";
}

function humanize(value: string | null): string {
  const labels: Record<string, string> = {
    advanced: "پیشرفته",
    beginner: "مبتدی",
    build_muscle: "عضله‌سازی",
    intermediate: "متوسط",
    lose_weight: "کاهش وزن",
  };
  return value === null ? "ثبت نشده" : labels[value] ?? "ثبت نشده";
}

function validationStatusLabel(value: components["schemas"]["ValidationStatus"]): string {
  if (value === "VALID") return "تأییدشده";
  if (value === "VALID_WITH_CONSTRAINTS") return "تأییدشده با محدودیت";
  return "نیازمند بررسی";
}

function reviewLeaseLabel(value: string | null): string {
  if (value === null) return "بدون قفل فعال";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "بدون قفل فعال";
  return new Intl.DateTimeFormat("fa-IR", { hour: "2-digit", minute: "2-digit" }).format(date);
}

function formatPersianNumber(value: number): string {
  return value.toLocaleString("fa-IR", { useGrouping: false });
}

function faNumber(value: number): string {
  return formatPersianNumber(value);
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

const styles = StyleSheet.create({
  avatar: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 48,
    justifyContent: "center",
    width: 48,
  },
  avatarText: {
    color: fiticianTokens.colors.canvas,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
  },
  body: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 27,
    textAlign: "right",
    writingDirection: "rtl",
  },
  dayCard: { gap: fiticianTokens.spacing[3] },
  dayHeader: { alignItems: "center", flexDirection: "row", gap: fiticianTokens.spacing[3] },
  dayNumber: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.h3,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    writingDirection: "ltr",
  },
  dayTitle: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    textAlign: "right",
    writingDirection: "rtl",
  },
  decisionRow: { flexDirection: "column", gap: fiticianTokens.spacing[2] },
  detail: { gap: fiticianTokens.spacing[4] },
  detailContent: { gap: fiticianTokens.spacing[4] },
  detailHeader: { alignItems: "center", flexDirection: "row", gap: fiticianTokens.spacing[3], justifyContent: "space-between" },
  detailTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
    textAlign: "right",
    writingDirection: "rtl",
  },
  exerciseEditor: {
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
    gap: fiticianTokens.spacing[3],
    paddingTop: fiticianTokens.spacing[3],
  },
  exerciseOption: {
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    gap: fiticianTokens.spacing[1],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingVertical: fiticianTokens.spacing[3],
  },
  exerciseOptionEn: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "left",
    writingDirection: "ltr",
  },
  exerciseOptionFa: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    textAlign: "right",
    writingDirection: "rtl",
  },
  exercisePicker: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[1],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[4],
    paddingVertical: fiticianTokens.spacing[2],
  },
  exercisePickerValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
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
  headerCopy: { flex: 1, gap: fiticianTokens.spacing[2] },
  fieldLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  leaseCard: {
    alignItems: "stretch",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    minHeight: 72,
  },
  leaseCopy: { flex: 1, gap: fiticianTokens.spacing[1] },
  leaseIndicator: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    width: 8,
  },
  leaseValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.h3,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "right",
    writingDirection: "ltr",
  },
  memberIdentity: { alignItems: "center", flexDirection: "row", gap: fiticianTokens.spacing[3] },
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
  profileMetric: {
    borderBottomColor: fiticianTokens.colors.line,
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 96,
    paddingVertical: fiticianTokens.spacing[3],
  },
  profileMetricLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  profileMetricValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  profileStrip: { flexDirection: "row", flexWrap: "wrap", gap: fiticianTokens.spacing[2] },
  queue: { gap: fiticianTokens.spacing[3] },
  queueItems: { gap: fiticianTokens.spacing[3] },
  queueMeta: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  sectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    textAlign: "right",
    writingDirection: "rtl",
  },
  scoreGrid: { flexDirection: "row", flexWrap: "wrap", gap: fiticianTokens.spacing[2] },
  scoreItem: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderRadius: fiticianTokens.radii.small,
    flexBasis: "30%",
    flexGrow: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 84,
    padding: fiticianTokens.spacing[2],
  },
  scoreItemTotal: { backgroundColor: fiticianTokens.colors.amber },
  scoreLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  scoreValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "right",
    writingDirection: "ltr",
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
  summaryCard: { gap: fiticianTokens.spacing[2] },
  templateSlug: {
    alignItems: "center",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  templateSlugValue: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "left",
    writingDirection: "ltr",
  },
  versionLabel: {
    color: fiticianTokens.colors.muted,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  versionLabelActive: {
    color: fiticianTokens.colors.aqua,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  versionLabels: { flexDirection: "row", flexWrap: "wrap", gap: fiticianTokens.spacing[2] },
  workspace: { gap: fiticianTokens.spacing[6] },
});
