import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";

import type { components } from "@fitician/core";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { physicianKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { Button, Card, EmptyState, Notice, Skeleton, TextField } from "../ui/components";
import { Screen } from "../ui/layout";
import { getMobileViewState, type MobileViewState } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import {
  createPhysicianNutritionReviewApi,
  type PhysicianCatalogueFood,
  type PhysicianMedicalContextResponse,
  type PhysicianNutritionPlan,
  type PhysicianReviewQueueItem,
  type PhysicianReviewQueueView,
} from "./physicianNutritionReviewApi";
import {
  hasRequiredPhysicianDecisionNotes,
  isPhysicianPlanReadOnly,
  physicianReviewStatusLabel,
  samePhysicianPlanRevision,
} from "./physicianNutritionReviewModel";

const queueViews: readonly PhysicianReviewQueueView[] = ["pending", "claimed", "approved"];
type WeeklyPlanMeal = components["schemas"]["WeeklyPlanMealResponse"];

export function PhysicianNutritionReviewScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const connectivityStatus = useConnectivityStatus();
  const api = useMemo(() => createPhysicianNutritionReviewApi(auth.request), [auth.request]);
  const [view, setView] = useState<PhysicianReviewQueueView>("pending");
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [quantityDrafts, setQuantityDrafts] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState("");
  const [internalNotes, setInternalNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const accessQuery = useQuery({
    queryFn: api.getAccess,
    queryKey: ["physician", "access"],
    retry: false,
  });
  const queueQuery = useQuery({
    queryFn: () => api.list(view),
    queryKey: physicianKeys.list(view),
  });
  const detailQuery = useQuery({
    enabled: selectedPlanId !== null,
    queryFn: () => api.getPlan(selectedPlanId as string),
    queryKey: physicianKeys.detail(selectedPlanId ?? "selected"),
  });
  const contextQuery = useQuery({
    enabled: selectedPlanId !== null,
    queryFn: () => api.getMedicalContext(selectedPlanId as string),
    queryKey: physicianKeys.detail(`${selectedPlanId ?? "selected"}:medical-context`),
  });
  const labsQuery = useQuery({
    enabled: selectedPlanId !== null,
    queryFn: () => api.getLabs(selectedPlanId as string),
    queryKey: physicianKeys.detail(`${selectedPlanId ?? "selected"}:labs`),
  });
  const foodsQuery = useQuery({
    enabled: selectedPlanId !== null,
    queryFn: api.listFoods,
    queryKey: ["physician", "foods"],
  });

  const accessState = getMobileViewState(accessQuery, { connectivityStatus });
  const queueState = getMobileViewState(queueQuery, {
    connectivityStatus,
    isEmpty: (data) => data.length === 0,
  });
  const detailState = getMobileViewState(detailQuery, { connectivityStatus });
  const contextState = getMobileViewState(contextQuery, { connectivityStatus });
  const labsState = getMobileViewState(labsQuery, {
    connectivityStatus,
    isEmpty: (data) => data.length === 0,
  });
  const foodsState = getMobileViewState(foodsQuery, {
    connectivityStatus,
    isEmpty: (data) => data.length === 0,
  });
  const selected = viewData(detailState);
  const offline = connectivityStatus === "offline";
  const readOnly = selected === undefined
    ? offline
    : isPhysicianPlanReadOnly(selected.review_status, offline);

  useEffect(() => {
    if (selected === undefined) return;
    setQuantityDrafts({});
    setNotes("");
    setInternalNotes("");
    setError(null);
    setMessage(null);
  }, [selected]);

  async function openCase(item: PhysicianReviewQueueItem): Promise<void> {
    if (offline) {
      setError("در حالت آفلاین امکان شروع یا بازخوانی پرونده وجود ندارد.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (item.status === "pending" || item.status === "changes_requested") {
        await api.claim(item.review_id);
      }
      const plan = await api.getPlan(item.plan_id);
      queryClient.setQueryData(physicianKeys.detail(plan.id), plan);
      setSelectedPlanId(plan.id);
      await queueQuery.refetch();
    } catch (requestError) {
      setError(physicianErrorMessage(requestError));
      await queueQuery.refetch();
    } finally {
      setBusy(false);
    }
  }

  function acceptPlan(plan: PhysicianNutritionPlan): void {
    queryClient.setQueryData(physicianKeys.detail(plan.id), plan);
    setSelectedPlanId(plan.id);
    void queryClient.invalidateQueries({ queryKey: physicianKeys.lists() });
  }

  async function revalidateSelected(): Promise<PhysicianNutritionPlan | null> {
    if (selected === undefined || offline) return null;
    const latest = await api.getPlan(selected.id);
    if (!samePhysicianPlanRevision(selected, latest)) {
      acceptPlan(latest);
      setError("نسخهٔ پرونده تغییر کرده است؛ نسخهٔ تازه را دوباره بررسی کن.");
      return null;
    }
    return latest;
  }

  async function decide(action: "approve" | "request_changes" | "reject"): Promise<void> {
    if (selected === undefined || readOnly) return;
    if ((action === "request_changes" || action === "reject") && !hasRequiredPhysicianDecisionNotes(notes)) {
      setError("برای درخواست اصلاح یا رد برنامه، توضیح الزامی است.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const latest = await revalidateSelected();
      if (latest === null) return;
      const expectedPlanRevisionId = latest.id;
      const updated = await api.action(
        latest.id,
        expectedPlanRevisionId,
        action,
        notes.trim() || null,
        internalNotes.trim() || null,
      );
      acceptPlan(updated);
      setMessage(action === "approve" ? "نسخه با موفقیت تأیید شد." : "تصمیم پزشک ثبت شد.");
      await queueQuery.refetch();
    } catch (requestError) {
      setError(physicianErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function saveQuantity(mealId: string, foodId: string, currentGrams: number): Promise<void> {
    if (selected === undefined || readOnly) return;
    const key = `${mealId}:${foodId}`;
    const grams = Number(quantityDrafts[key] ?? currentGrams);
    if (!Number.isFinite(grams) || grams <= 0 || grams > 5000) {
      setError("مقدار باید بین ۱ تا ۵۰۰۰ گرم باشد.");
      return;
    }
    if (grams === currentGrams) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const latest = await revalidateSelected();
      if (latest === null) return;
      const expectedPlanRevisionId = latest.id;
      const updated = await api.adjustFoodQuantity(latest.id, expectedPlanRevisionId, mealId, foodId, grams);
      acceptPlan(updated);
      setMessage("مقدار ماده غذایی ذخیره شد و نسخهٔ تازه ساخته شد.");
    } catch (requestError) {
      setError(physicianErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function replaceFood(mealId: string, foodId: string, replacementFoodId: string): Promise<void> {
    if (selected === undefined || readOnly || foodId === replacementFoodId) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const latest = await revalidateSelected();
      if (latest === null) return;
      const expectedPlanRevisionId = latest.id;
      const updated = await api.replaceFood(latest.id, expectedPlanRevisionId, mealId, foodId, replacementFoodId);
      acceptPlan(updated);
      setMessage("جایگزینی ماده غذایی ذخیره شد و نسخهٔ تازه ساخته شد.");
    } catch (requestError) {
      setError(physicianErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  function confirmRemoveMeal(meal: WeeklyPlanMeal): void {
    if (selected === undefined || readOnly) return;
    Alert.alert(
      "حذف وعده",
      `آیا وعدهٔ ${meal.name_fa ?? meal.name_en ?? "انتخاب‌شده"} حذف شود؟`,
      [
        { text: "انصراف", style: "cancel" },
        {
          text: "حذف وعده",
          style: "destructive",
          onPress: () => void removeMeal(meal.id),
        },
      ],
    );
  }

  async function removeMeal(mealId: string): Promise<void> {
    if (selected === undefined || readOnly) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const latest = await revalidateSelected();
      if (latest === null) return;
      const expectedPlanRevisionId = latest.id;
      const updated = await api.removeMeal(latest.id, expectedPlanRevisionId, mealId);
      acceptPlan(updated);
      setMessage("وعده حذف شد و نسخهٔ تازه ساخته شد.");
    } catch (requestError) {
      setError(physicianErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  if (accessState.status === "loading") {
    return <Screen contentWidth="reading"><Skeleton height={260} /></Screen>;
  }
  if (accessState.status === "error" && accessState.data === undefined) {
    return (
      <Screen contentWidth="reading">
        <Notice message="این حساب دسترسی پزشک به پرونده‌های تغذیه ندارد." variant="danger" />
      </Screen>
    );
  }

  return (
    <Screen contentWidth="reading">
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <Text style={styles.brand}>FITICIAN</Text>
          <Text accessibilityRole="header" style={styles.title}>صف بررسی برنامه‌های تغذیه</Text>
          <Text style={styles.subtitle}>پرونده، زمینهٔ پزشکی و نسخهٔ قابل ممیزی در یک محل.</Text>
        </View>
        <Button label="بازگشت" onPress={() => router.back()} variant="ghost" />
      </View>

      {offline ? <Notice message="حالت آفلاین فعال است؛ پرونده‌های ذخیره‌شده فقط برای مشاهده هستند." variant="offline" /> : null}
      {accessState.status === "offline" ? <Notice message="اعتبار دسترسی پزشک در شبکه تأیید نشده است؛ عملیات ویرایشی قفل است." variant="offline" /> : null}
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
              setSelectedPlanId(null);
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
            onSelect={openCase}
            selectedPlanId={selectedPlanId}
            state={queueState}
          />
        </View>
        <View style={styles.detail}>
          {selected === undefined && detailState.status === "loading" ? <Skeleton height={260} /> : null}
          {selected === undefined && detailState.status === "offline" ? (
            <Notice message="جزئیات این پرونده در حافظهٔ فعلی نیست." variant="offline" />
          ) : null}
          {selected === undefined && detailState.status === "error" ? (
            <Notice actionLabel="تلاش دوباره" message="جزئیات پرونده دریافت نشد." onAction={() => void detailQuery.refetch()} variant="danger" />
          ) : null}
          {selected === undefined && selectedPlanId === null && detailState.status !== "loading" ? (
            <EmptyState title="یک پرونده را از صف انتخاب کن">
              <Text style={styles.body}>پس از باز کردن پرونده، زمینهٔ پزشکی و ابزار تصمیم‌گیری نمایش داده می‌شود.</Text>
            </EmptyState>
          ) : null}
          {selected !== undefined ? (
            <PhysicianReviewDetail
              busy={busy}
              contextState={contextState}
              foodsState={foodsState}
              labsState={labsState}
              notes={notes}
              onApprove={() => void decide("approve")}
              onNotesChange={setNotes}
              onInternalNotesChange={setInternalNotes}
              onQuantityDraftChange={(key, value) => setQuantityDrafts((current) => ({ ...current, [key]: value }))}
              onRemoveMeal={confirmRemoveMeal}
              onReplaceFood={replaceFood}
              onRequestChanges={() => void decide("request_changes")}
              onReject={() => void decide("reject")}
              onSaveQuantity={saveQuantity}
              plan={selected}
              quantityDrafts={quantityDrafts}
              readOnly={readOnly}
              internalNotes={internalNotes}
            />
          ) : null}
        </View>
      </View>
    </Screen>
  );
}

function QueueState({
  onRetry,
  onSelect,
  selectedPlanId,
  state,
}: {
  readonly onRetry: () => void;
  readonly onSelect: (item: PhysicianReviewQueueItem) => void;
  readonly selectedPlanId: string | null;
  readonly state: MobileViewState<PhysicianReviewQueueItem[]>;
}) {
  if (state.status === "loading") return <Skeleton height={180} />;
  if (state.status === "error" && state.data === undefined) {
    return <Notice actionLabel="تلاش دوباره" message="صف پرونده‌ها دریافت نشد." onAction={onRetry} variant="danger" />;
  }
  if (state.status === "offline" && state.data === undefined) {
    return <Notice message="صف پرونده‌ها در حالت آفلاین در دسترس نیست." variant="offline" />;
  }
  const items = state.data ?? [];
  if (items.length === 0) return <EmptyState title="این صف خالی است" />;
  return (
    <View style={styles.queueItems}>
      {state.status === "offline" ? <Notice message="این فهرست آخرین دادهٔ دریافت‌شده است." variant="offline" /> : null}
      {items.map((item) => (
        <Card
          key={item.review_id}
          style={selectedPlanId === item.plan_id ? styles.selectedCard : undefined}
          variant={selectedPlanId === item.plan_id ? "raised" : "interactive"}
        >
          <Text style={styles.memberName}>{item.member_display_name ?? "کاربر فیتیشین"}</Text>
          <Text style={styles.queueMeta}>{item.overdue ? "گذشته از موعد · " : ""}نسخهٔ تغذیه</Text>
          <Text style={styles.status}>{physicianReviewStatusLabel(item.status)}</Text>
          <Button
            disabled={state.status === "offline"}
            label={item.status === "pending" || item.status === "changes_requested" ? "شروع بررسی" : "باز کردن پرونده"}
            onPress={() => onSelect(item)}
            variant="secondary"
          />
        </Card>
      ))}
    </View>
  );
}

function PhysicianReviewDetail({
  busy,
  contextState,
  foodsState,
  labsState,
  notes,
  onApprove,
  onNotesChange,
  onInternalNotesChange,
  onQuantityDraftChange,
  onRemoveMeal,
  onReplaceFood,
  onRequestChanges,
  onReject,
  onSaveQuantity,
  plan,
  quantityDrafts,
  readOnly,
  internalNotes,
}: {
  readonly busy: boolean;
  readonly contextState: MobileViewState<PhysicianMedicalContextResponse>;
  readonly foodsState: MobileViewState<PhysicianCatalogueFood[]>;
  readonly labsState: MobileViewState<components["schemas"]["NutritionLabDocumentResponse"][]>;
  readonly notes: string;
  readonly onApprove: () => void;
  readonly onNotesChange: (value: string) => void;
  readonly onInternalNotesChange: (value: string) => void;
  readonly onQuantityDraftChange: (key: string, value: string) => void;
  readonly onRemoveMeal: (meal: WeeklyPlanMeal) => void;
  readonly onReplaceFood: (mealId: string, foodId: string, replacementFoodId: string) => void;
  readonly onRequestChanges: () => void;
  readonly onReject: () => void;
  readonly onSaveQuantity: (mealId: string, foodId: string, currentGrams: number) => Promise<void>;
  readonly plan: PhysicianNutritionPlan;
  readonly quantityDrafts: Record<string, string>;
  readonly readOnly: boolean;
  readonly internalNotes: string;
}) {
  const warningCodes = plan.warning_codes;
  const inputSnapshot = plan.input_snapshot;
  const foods = viewData(foodsState) ?? [];
  return (
    <View style={styles.detailContent}>
      <View style={styles.detailHeader}>
        <View style={styles.headerCopy}>
          <Text style={styles.eyebrow}>پروندهٔ تغذیه</Text>
          <Text style={styles.detailTitle}>نسخهٔ {plan.revision}</Text>
        </View>
        <Text style={styles.status}>{physicianReviewStatusLabel(plan.review_status)}</Text>
      </View>

      {readOnly ? <Notice message="این پرونده در حالت فقط‌خواندنی نمایش داده می‌شود." variant="info" /> : null}
      <Card style={styles.summaryCard}>
        <Text style={styles.sectionTitle}>خلاصهٔ نسخه</Text>
        <Text style={styles.body}>هزینهٔ هفتگی: {formatNumber(plan.weekly_cost_irr)} ریال</Text>
        <Text style={styles.body}>بودجه: {plan.budget_status}</Text>
        <Text style={styles.body}>دادهٔ ورودی نسخه: {Object.keys(inputSnapshot).length} مورد ثبت‌شده</Text>
        {warningCodes.length > 0 ? (
          <View style={styles.warningList}>
            <Text style={styles.warningTitle}>هشدارهای نسخه</Text>
            {warningCodes.map((code) => <Text key={code} style={styles.warningText}>{code}</Text>)}
          </View>
        ) : <Text style={styles.muted}>هشدار ثبت‌شده‌ای برای این نسخه وجود ندارد.</Text>}
      </Card>

      <MedicalContextCard state={contextState} />
      <LabsCard state={labsState} />

      <Text style={styles.sectionTitle}>ویرایش نسخه</Text>
      {foodsState.status === "error" && foodsState.data === undefined ? (
        <Notice message="کاتالوگ مواد غذایی برای جایگزینی در دسترس نیست؛ بررسی نسخه ادامه دارد." variant="warning" />
      ) : null}
      {foodsState.status === "offline" && foodsState.data === undefined ? (
        <Notice message="در حالت آفلاین گزینه‌های جایگزینی بارگذاری نمی‌شوند." variant="offline" />
      ) : null}
      {plan.days.map((day) => (
        <Card key={day.plan_date} style={styles.dayCard}>
          <Text style={styles.dayTitle}>روز {day.day_index + 1} · {day.plan_date}</Text>
          {day.meals.map((meal) => (
            <MealEditor
              busy={busy}
              foods={foods}
              key={meal.id}
              meal={meal}
              onQuantityDraftChange={onQuantityDraftChange}
              onRemove={() => onRemoveMeal(meal)}
              onReplaceFood={onReplaceFood}
              onSaveQuantity={onSaveQuantity}
              quantityDrafts={quantityDrafts}
              readOnly={readOnly}
            />
          ))}
        </Card>
      ))}

      <TextField
        editable={!readOnly && !busy}
        hint="برای رد یا درخواست اصلاح، این توضیح برای پرونده ثبت می‌شود."
        label="توضیح تصمیم پزشک"
        multiline
        numberOfLines={4}
        onChangeText={onNotesChange}
        value={notes}
      />
      <TextField
        editable={!readOnly && !busy}
        hint="این یادداشت فقط برای تیم تخصصی قابل مشاهده است."
        label="یادداشت داخلی"
        multiline
        numberOfLines={3}
        onChangeText={onInternalNotesChange}
        value={internalNotes}
      />
      {!readOnly ? (
        <View style={styles.decisionRow}>
          <Button disabled={busy} label="تأیید نسخه" onPress={onApprove} />
          <Button disabled={busy} label="درخواست اصلاح" onPress={onRequestChanges} variant="secondary" />
          <Button disabled={busy} label="رد نسخه" onPress={onReject} variant="danger" />
        </View>
      ) : null}
    </View>
  );
}

function MedicalContextCard({ state }: { readonly state: MobileViewState<PhysicianMedicalContextResponse> }) {
  if (state.status === "loading") return <Skeleton height={200} />;
  if ((state.status === "offline" || state.status === "error") && state.data === undefined) {
    return <Notice message="زمینهٔ پزشکی این پرونده فعلاً در دسترس نیست؛ تصمیم‌گیری را متوقف کن." variant={state.status === "offline" ? "offline" : "warning"} />;
  }
  const context = state.data;
  if (context === undefined) return null;
  const flags = Object.entries(context.flags).filter(([, value]) => value);
  return (
    <Card style={styles.contextCard}>
      <Text style={styles.sectionTitle}>زمینهٔ پزشکی</Text>
      <Text style={styles.muted}>نتیجهٔ ایمنی: {context.safety_outcome}</Text>
      <Text style={styles.muted}>نسخهٔ سیاست: {context.medical_condition_policy_version}</Text>
      {context.conditions.length > 0 ? (
        <View style={styles.contextGroup}>
          <Text style={styles.contextLabel}>شرایط ثبت‌شده</Text>
          {context.conditions.map((condition) => <Text key={condition.code} style={styles.body}>{condition.code}{condition.details ? ` · ${condition.details}` : ""}</Text>)}
        </View>
      ) : null}
      {context.medications.length > 0 ? (
        <View style={styles.contextGroup}>
          <Text style={styles.contextLabel}>داروها</Text>
          {context.medications.map((medication) => <Text key={`${medication.name}-${medication.dosage ?? ""}`} style={styles.body}>{medication.name}{medication.dosage ? ` · ${medication.dosage}` : ""}{medication.notes ? ` · ${medication.notes}` : ""}</Text>)}
        </View>
      ) : null}
      {flags.length > 0 ? <Text style={styles.body}>پرچم‌های ایمنی: {flags.map(([key]) => key).join("، ")}</Text> : null}
      {context.physician_dietary_restrictions ? <Text style={styles.body}>محدودیت غذایی پزشک: {context.physician_dietary_restrictions}</Text> : null}
      {context.other_relevant_condition ? <Text style={styles.body}>شرایط مرتبط دیگر: {context.other_relevant_condition}</Text> : null}
      {context.safety_reason_codes.length > 0 ? <Text style={styles.warningText}>کدهای ایمنی: {context.safety_reason_codes.join("، ")}</Text> : null}
    </Card>
  );
}

function LabsCard({ state }: { readonly state: MobileViewState<components["schemas"]["NutritionLabDocumentResponse"][]> }) {
  if (state.status === "loading") return <Skeleton height={150} />;
  if (state.status === "offline" && state.data === undefined) {
    return <Notice message="پرونده‌های آزمایش در حالت آفلاین در دسترس نیستند." variant="offline" />;
  }
  if (state.status === "error" && state.data === undefined) {
    return <Notice message="فهرست آزمایش‌های این پرونده دریافت نشد." variant="warning" />;
  }
  const labs = state.data ?? [];
  return (
    <Card style={styles.contextCard}>
      <Text style={styles.sectionTitle}>آزمایش‌ها</Text>
      {labs.length === 0 ? <Text style={styles.muted}>آزمایش ثبت‌شده‌ای در این پرونده وجود ندارد.</Text> : labs.map((lab) => (
        <View key={lab.id} style={styles.labRow}>
          <Text style={styles.body}>{lab.original_filename}</Text>
          <Text style={styles.muted}>{lab.review_status}{lab.laboratory_name ? ` · ${lab.laboratory_name}` : ""}</Text>
        </View>
      ))}
    </Card>
  );
}

function MealEditor({
  busy,
  foods,
  meal,
  onQuantityDraftChange,
  onRemove,
  onReplaceFood,
  onSaveQuantity,
  quantityDrafts,
  readOnly,
}: {
  readonly busy: boolean;
  readonly foods: PhysicianCatalogueFood[];
  readonly meal: WeeklyPlanMeal;
  readonly onQuantityDraftChange: (key: string, value: string) => void;
  readonly onRemove: () => void;
  readonly onReplaceFood: (mealId: string, foodId: string, replacementFoodId: string) => void;
  readonly onSaveQuantity: (mealId: string, foodId: string, currentGrams: number) => Promise<void>;
  readonly quantityDrafts: Record<string, string>;
  readonly readOnly: boolean;
}) {
  return (
    <View style={styles.mealEditor}>
      <View style={styles.mealHeader}>
        <View style={styles.headerCopy}>
          <Text style={styles.mealTitle}>{meal.name_fa ?? meal.name_en ?? "وعده غذایی"}</Text>
          {meal.name_en && meal.name_en !== meal.name_fa ? <Text style={styles.muted}>{meal.name_en}</Text> : null}
        </View>
        <Button disabled={readOnly || busy} label="حذف وعده" onPress={onRemove} variant="ghost" />
      </View>
      {meal.foods.map((food) => {
        const foodId = food.food_id;
        const key = foodId === null ? null : `${meal.id}:${foodId}`;
        const replacementFoods = foodId === null ? [] : foods.filter((candidate) => candidate.id !== foodId).slice(0, 4);
        return (
          <View key={`${meal.id}-${food.slug}`} style={styles.foodEditor}>
            <View style={styles.foodCopy}>
              <Text style={styles.foodName}>{food.name_fa || food.name_en}</Text>
              <Text style={styles.muted}>{formatNumber(food.grams)} گرم · {formatNumber(food.cost_irr)} ریال</Text>
            </View>
            {foodId !== null && key !== null ? (
              <View style={styles.quantityRow}>
                <TextField
                  editable={!readOnly && !busy}
                  keyboardType="decimal-pad"
                  label="گرم"
                  onChangeText={(value) => onQuantityDraftChange(key, value)}
                  value={quantityDrafts[key] ?? String(food.grams)}
                />
                <Button
                  disabled={readOnly || busy}
                  label="ذخیره مقدار"
                  onPress={() => void onSaveQuantity(meal.id, foodId, food.grams)}
                  variant="secondary"
                />
              </View>
            ) : null}
            {foodId !== null && replacementFoods.length > 0 ? (
              <View style={styles.replacementGroup}>
                <Text style={styles.muted}>جایگزین‌های تأییدشده:</Text>
                <View style={styles.replacementRow}>
                  {replacementFoods.map((candidate) => (
                    <Button
                      disabled={readOnly || busy}
                      key={candidate.id}
                      label={candidate.name_fa}
                      onPress={() => onReplaceFood(meal.id, foodId, candidate.id)}
                      variant="ghost"
                    />
                  ))}
                </View>
              </View>
            ) : null}
          </View>
        );
      })}
    </View>
  );
}

function viewData<TData>(state: MobileViewState<TData>): TData | undefined {
  return state.status === "loading" ? undefined : "data" in state ? state.data : undefined;
}

function queueLabel(view: PhysicianReviewQueueView): string {
  if (view === "pending") return "در انتظار";
  if (view === "claimed") return "در بررسی من";
  return "تأییدشده";
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("fa-IR").format(value);
}

function physicianErrorMessage(error: unknown): string {
  const code = error instanceof Error && "code" in error
    ? (error as { readonly code?: unknown }).code
    : null;
  if (code === "STALE_PLAN_REVISION") return "نسخهٔ پرونده تغییر کرده است؛ نسخهٔ تازه را بررسی کن.";
  if (code === "REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN") return "این پرونده در اختیار پزشک دیگری است.";
  if (code === "REVIEW_NOT_IN_PROGRESS") return "این پرونده دیگر در وضعیت بررسی نیست.";
  return error instanceof Error && error.message ? error.message : "عملیات پزشک انجام نشد؛ اتصال و وضعیت پرونده را بررسی کن.";
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
  contextCard: { gap: fiticianTokens.spacing[3] },
  contextGroup: { gap: fiticianTokens.spacing[1] },
  contextLabel: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  dayCard: { gap: fiticianTokens.spacing[3] },
  dayTitle: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    textAlign: "right",
    writingDirection: "rtl",
  },
  decisionRow: { flexDirection: "row", flexWrap: "wrap", gap: fiticianTokens.spacing[2] },
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
  eyebrow: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  foodCopy: { flex: 1, gap: fiticianTokens.spacing[1] },
  foodEditor: { borderTopColor: fiticianTokens.colors.line, borderTopWidth: 1, gap: fiticianTokens.spacing[2], paddingTop: fiticianTokens.spacing[3] },
  foodName: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  header: { alignItems: "flex-start", flexDirection: "row", gap: fiticianTokens.spacing[3], justifyContent: "space-between" },
  headerCopy: { flex: 1, gap: fiticianTokens.spacing[2] },
  labRow: { borderTopColor: fiticianTokens.colors.line, borderTopWidth: 1, gap: fiticianTokens.spacing[1], paddingTop: fiticianTokens.spacing[2] },
  mealEditor: { gap: fiticianTokens.spacing[3] },
  mealHeader: { alignItems: "center", flexDirection: "row", gap: fiticianTokens.spacing[2], justifyContent: "space-between" },
  mealTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
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
  quantityRow: { alignItems: "flex-end", flexDirection: "row", gap: fiticianTokens.spacing[2] },
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
  replacementGroup: { gap: fiticianTokens.spacing[2] },
  replacementRow: { flexDirection: "row", flexWrap: "wrap", gap: fiticianTokens.spacing[2] },
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
  warningList: { gap: fiticianTokens.spacing[1] },
  warningText: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  warningTitle: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  workspace: { gap: fiticianTokens.spacing[6] },
});
