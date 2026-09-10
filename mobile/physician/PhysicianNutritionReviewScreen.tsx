import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";

import { irrToToman, type components } from "@fitician/core";

import { AccountPrivacyLinks } from "../accountDeletion/AccountPrivacyLinks";
import { useMobileAuth } from "../auth/MobileAuthProvider";
import { physicianKeys } from "../data/queryKeys";
import { labReviewStatusLabel, supplementStatusLabel } from "../nutrition/nutritionClinicalModel";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import {
  Button,
  Card,
  DisclosureCard,
  EmptyState,
  MetricStrip,
  Notice,
  PageHeading,
  SegmentedControl,
  Sheet,
  Skeleton,
  TextField,
} from "../ui/components";
import { Screen } from "../ui/layout";
import { formatPersianNumber } from "../ui/locale";
import { getMobileViewState, mobileRequestErrorMessage, type MobileViewState } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import {
  createPhysicianNutritionReviewApi,
  type PhysicianCatalogueFood,
  type PhysicianLabDocument,
  type PhysicianMedicalContextResponse,
  type PhysicianNutritionPlan,
  type PhysicianReviewQueueItem,
  type PhysicianReviewQueueView,
  type PhysicianSupplementCatalogue,
  type PhysicianSupplementOrder,
  type PhysicianSupplementOrderInput,
  type PhysicianSupplementOrderStatus,
} from "./physicianNutritionReviewApi";
import {
  hasRequiredPhysicianDecisionNotes,
  isPhysicianPlanReadOnly,
  physicianReviewStatusLabel,
  samePhysicianPlanRevision,
} from "./physicianNutritionReviewModel";

const queueViews: readonly PhysicianReviewQueueView[] = ["pending", "claimed", "approved"];
const clinicalTabs = ["plan", "labs", "supplements", "notes"] as const;
type ClinicalTab = (typeof clinicalTabs)[number];
type WeeklyPlanMeal = components["schemas"]["WeeklyPlanMealResponse"];
type LabReviewStatus = "reviewed" | "needs_attention";
type SupplementTransitionStatus = Extract<
  PhysicianSupplementOrderStatus,
  "active" | "completed" | "discontinued" | "cancelled"
>;

type SupplementDraft = {
  readonly supplementId: string;
  readonly doseAmount: string;
  readonly doseUnit: string;
  readonly dailyUnits: string;
  readonly frequency: string;
  readonly durationDays: string;
  readonly instructions: string;
  readonly rationale: string;
};

const emptySupplementDraft: SupplementDraft = {
  dailyUnits: "1",
  doseAmount: "1",
  doseUnit: "tablet",
  durationDays: "30",
  frequency: "once_daily",
  instructions: "",
  rationale: "",
  supplementId: "",
};

export function PhysicianNutritionReviewScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const connectivityStatus = useConnectivityStatus();
  const api = useMemo(() => createPhysicianNutritionReviewApi(auth.request), [auth.request]);
  const [view, setView] = useState<PhysicianReviewQueueView>("pending");
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [selectedReview, setSelectedReview] = useState<PhysicianReviewQueueItem | null>(null);
  const [clinicalTab, setClinicalTab] = useState<ClinicalTab>("plan");
  const [quantityDrafts, setQuantityDrafts] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState("");
  const [internalNotes, setInternalNotes] = useState("");
  const [requestedTests, setRequestedTests] = useState("CBC");
  const [labReviewNotes, setLabReviewNotes] = useState("");
  const [supplementDraft, setSupplementDraft] = useState<SupplementDraft>(emptySupplementDraft);
  const [editingSupplementOrderId, setEditingSupplementOrderId] = useState<string | null>(null);
  const [supplementPickerVisible, setSupplementPickerVisible] = useState(false);
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
  const supplementOrdersQuery = useQuery({
    enabled: selectedPlanId !== null,
    queryFn: () => api.listSupplementOrders(selectedPlanId as string),
    queryKey: physicianKeys.detail(`${selectedPlanId ?? "selected"}:supplement-orders`),
  });
  const supplementCatalogueQuery = useQuery({
    enabled: selectedPlanId !== null,
    queryFn: api.listSupplementCatalogue,
    queryKey: ["physician", "supplement-catalogue"],
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
  const supplementOrdersState = getMobileViewState(supplementOrdersQuery, {
    connectivityStatus,
    isEmpty: (data) => data.length === 0,
  });
  const supplementCatalogueState = getMobileViewState(supplementCatalogueQuery, {
    connectivityStatus,
    isEmpty: (data) => data.length === 0,
  });
  const selected = viewData(detailState);
  const offline = connectivityStatus === "offline";
  const readOnly = selected === undefined
    ? offline
    : view === "approved" || selectedReview?.status === "approved"
      ? true
      : isPhysicianPlanReadOnly(selected.review_status, offline);

  useEffect(() => {
    if (selected === undefined) return;
    setQuantityDrafts({});
    setNotes("");
    setInternalNotes("");
    setError(null);
    setMessage(null);
  }, [selected?.id, selected?.revision]);

  function clearSelectedCase(): void {
    setSelectedPlanId(null);
    setSelectedReview(null);
    setClinicalTab("plan");
    setEditingSupplementOrderId(null);
    setSupplementDraft(emptySupplementDraft);
    setSupplementPickerVisible(false);
  }

  function handleBack(): boolean {
    if (selectedPlanId !== null) {
      clearSelectedCase();
      return true;
    }
    router.back();
    return true;
  }

  useAndroidBackHandler("wizard", handleBack, selectedPlanId !== null);

  async function openCase(item: PhysicianReviewQueueItem): Promise<void> {
    if (offline) {
      setError("در حالت آفلاین امکان شروع یا بازخوانی پرونده وجود ندارد.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    setSelectedReview(item);
    setClinicalTab("plan");
    try {
      if (item.status === "pending" || item.status === "changes_requested") {
        await api.claim(item.review_id);
        setView("claimed");
      }
      const plan = await api.getPlan(item.plan_id);
      queryClient.setQueryData(physicianKeys.detail(plan.id), plan);
      setSelectedPlanId(plan.id);
      await queryClient.invalidateQueries({ queryKey: physicianKeys.lists() });
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

  async function requestLabs(): Promise<void> {
    if (selected === undefined || readOnly || offline) return;
    const tests = [...new Set(
      requestedTests
        .split(/[،,\n]/)
        .map((test) => test.trim())
        .filter(Boolean),
    )];
    if (tests.length === 0) {
      setError("حداقل یک آزمایش را وارد کن.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const latest = await revalidateSelected();
      if (latest === null) return;
      await api.requestLabs(
        latest.id,
        latest.id,
        tests,
        notes.trim() || "برای بررسی ایمن‌تر برنامه",
      );
      setMessage("درخواست آزمایش برای پرونده ثبت شد.");
      await labsQuery.refetch();
    } catch (requestError) {
      setError(physicianErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function reviewLab(documentId: string, status: LabReviewStatus): Promise<void> {
    if (selected === undefined || readOnly || offline) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.reviewLab(documentId, status, labReviewNotes.trim() || notes.trim() || null);
      setMessage("وضعیت آزمایش در پرونده ثبت شد.");
      await labsQuery.refetch();
    } catch (requestError) {
      setError(physicianErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  function selectSupplement(supplement: PhysicianSupplementCatalogue): void {
    setSupplementDraft((current) => ({ ...current, supplementId: supplement.id }));
    setSupplementPickerVisible(false);
  }

  function editSupplementOrder(order: PhysicianSupplementOrder): void {
    setEditingSupplementOrderId(order.id);
    setSupplementDraft({
      dailyUnits: String(order.daily_units ?? ""),
      doseAmount: String(order.dose_amount ?? ""),
      doseUnit: order.dose_unit ?? "",
      durationDays: String(order.duration_days ?? ""),
      frequency: order.frequency ?? "",
      instructions: order.instructions ?? "",
      rationale: order.rationale ?? "",
      supplementId: order.supplement_id ?? "",
    });
  }

  function cancelSupplementEdit(): void {
    setEditingSupplementOrderId(null);
    setSupplementDraft(emptySupplementDraft);
  }

  function supplementPayload(): PhysicianSupplementOrderInput | null {
    const doseAmount = Number(supplementDraft.doseAmount);
    const dailyUnits = Number(supplementDraft.dailyUnits);
    const durationDays = Number(supplementDraft.durationDays);
    if (
      !supplementDraft.supplementId ||
      !supplementDraft.doseUnit.trim() ||
      !supplementDraft.frequency.trim() ||
      !supplementDraft.instructions.trim() ||
      !supplementDraft.rationale.trim() ||
      !Number.isFinite(doseAmount) || doseAmount <= 0 ||
      !Number.isFinite(dailyUnits) || dailyUnits <= 0 ||
      !Number.isInteger(durationDays) || durationDays <= 0
    ) {
      return null;
    }
    return {
      daily_units: dailyUnits,
      dose_amount: doseAmount,
      dose_unit: supplementDraft.doseUnit.trim(),
      duration_days: durationDays,
      frequency: supplementDraft.frequency.trim(),
      instructions: supplementDraft.instructions.trim(),
      linked_gap_codes: [],
      linked_lab_document_ids: [],
      rationale: supplementDraft.rationale.trim(),
      rationale_user_visible: true,
      supplement_id: supplementDraft.supplementId,
    };
  }

  async function saveSupplementOrder(): Promise<void> {
    if (selected === undefined || readOnly || offline) return;
    const payload = supplementPayload();
    if (payload === null) {
      setError("مکمل، مقدار دوز، دفعات، مدت، دستور مصرف و دلیل بالینی را کامل کن.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (editingSupplementOrderId === null) {
        await api.createSupplementOrder(selected.id, payload);
      } else {
        await api.updateSupplementOrder(editingSupplementOrderId, payload);
      }
      await supplementOrdersQuery.refetch();
      setEditingSupplementOrderId(null);
      setSupplementDraft(emptySupplementDraft);
      setMessage("دستور مکمل در پرونده ذخیره شد.");
    } catch (requestError) {
      setError(physicianErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function transitionSupplementOrder(
    orderId: string,
    status: SupplementTransitionStatus,
  ): Promise<void> {
    if (selected === undefined || readOnly || offline) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.transitionSupplementOrder(orderId, status);
      await supplementOrdersQuery.refetch();
      setMessage("وضعیت دستور مکمل به‌روزرسانی شد.");
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
      <Card style={styles.heroCard} variant="hero">
        <PageHeading
          action={<Button label={selectedPlanId === null ? "بازگشت" : "بازگشت به صف"} onPress={handleBack} variant="ghost" />}
          compact={false}
          eyebrow="میز کار پزشک"
          supportingText="آزمایش‌ها، مکمل‌ها و نسخه را در یک پرونده بررسی کن."
          title="صف بررسی برنامه‌های تغذیه"
        />
        <MetricStrip
          items={[{
            accent: fiticianTokens.colors.aqua,
            label: "پرونده‌های این صف",
            value: formatNumber(viewData(queueState)?.length ?? 0),
          }]}
        />
      </Card>

      {offline ? <Notice message="حالت آفلاین فعال است؛ پرونده‌های ذخیره‌شده فقط برای مشاهده هستند." variant="offline" /> : null}
      {accessState.status === "offline" ? <Notice message="اعتبار دسترسی پزشک در شبکه تأیید نشده است؛ عملیات ویرایشی قفل است." variant="offline" /> : null}
      {error ? <Notice message={error} variant="danger" /> : null}
      {message ? <Notice message={message} variant="success" /> : null}

      {selectedPlanId === null ? (
        <View style={styles.queue}>
          <SegmentedControl
            accessibilityLabel="صف‌های پزشک"
            onChange={(value) => {
              setView(value as PhysicianReviewQueueView);
              clearSelectedCase();
            }}
            options={queueViews.map((item) => ({ label: queueLabel(item), value: item }))}
            selectedValue={view}
          />
          <Text style={styles.sectionTitle}>صف پرونده‌ها</Text>
          <QueueState
            onRetry={() => void queueQuery.refetch()}
            onSelect={openCase}
            selectedPlanId={selectedPlanId}
            state={queueState}
          />
          <EmptyState title="یک پرونده را از صف انتخاب کن">
            <Text style={styles.body}>نسخه، آزمایش‌ها، مکمل‌ها و یادداشت‌های بالینی بعد از انتخاب پرونده اینجا نمایش داده می‌شوند.</Text>
          </EmptyState>
        </View>
      ) : (
        <View style={styles.detail}>
          {selected === undefined && detailState.status === "loading" ? <Skeleton height={260} /> : null}
          {selected === undefined && detailState.status === "offline" ? (
            <Notice message="جزئیات این پرونده در حافظهٔ فعلی نیست." variant="offline" />
          ) : null}
          {selected === undefined && detailState.status === "error" ? (
            <Notice actionLabel="تلاش دوباره" message="جزئیات پرونده دریافت نشد." onAction={() => void detailQuery.refetch()} variant="danger" />
          ) : null}
          {selected !== undefined ? (
            <PhysicianReviewDetail
              busy={busy}
              clinicalTab={clinicalTab}
              contextState={contextState}
              foodsState={foodsState}
              labsState={labsState}
              labReviewNotes={labReviewNotes}
              notes={notes}
              onApprove={() => void decide("approve")}
              onClinicalTabChange={(value) => setClinicalTab(value as ClinicalTab)}
              onInternalNotesChange={setInternalNotes}
              onLabReviewNotesChange={setLabReviewNotes}
              onNotesChange={setNotes}
              onQuantityDraftChange={(key, value) => setQuantityDrafts((current) => ({ ...current, [key]: value }))}
              onRemoveMeal={confirmRemoveMeal}
              onReplaceFood={replaceFood}
              onRequestChanges={() => void decide("request_changes")}
              onReject={() => void decide("reject")}
              onRequestLabs={requestLabs}
              onReviewLab={reviewLab}
              onRequestedTestsChange={setRequestedTests}
              onSaveQuantity={saveQuantity}
              onSaveSupplementOrder={saveSupplementOrder}
              onCancelSupplementEdit={cancelSupplementEdit}
              onSupplementDraftChange={(key, value) => setSupplementDraft((current) => ({ ...current, [key]: value }))}
              onSupplementPickerOpen={() => setSupplementPickerVisible(true)}
              onTransitionSupplementOrder={transitionSupplementOrder}
              onEditSupplementOrder={editSupplementOrder}
              plan={selected}
              quantityDrafts={quantityDrafts}
              readOnly={readOnly}
              internalNotes={internalNotes}
              requestedTests={requestedTests}
              supplementCatalogueState={supplementCatalogueState}
              supplementDraft={supplementDraft}
              supplementOrdersState={supplementOrdersState}
              editingSupplementOrderId={editingSupplementOrderId}
              selectedReview={selectedReview}
            />
          ) : null}
        </View>
      )}
      <Sheet
        onClose={() => setSupplementPickerVisible(false)}
        title="انتخاب مکمل"
        visible={supplementPickerVisible}
      >
        <SupplementCataloguePicker
          onSelect={selectSupplement}
          state={supplementCatalogueState}
        />
      </Sheet>
      <AccountPrivacyLinks />
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
  clinicalTab,
  contextState,
  foodsState,
  labsState,
  labReviewNotes,
  notes,
  onApprove,
  onClinicalTabChange,
  onNotesChange,
  onInternalNotesChange,
  onLabReviewNotesChange,
  onQuantityDraftChange,
  onRemoveMeal,
  onReplaceFood,
  onRequestChanges,
  onReject,
  onRequestLabs,
  onReviewLab,
  onRequestedTestsChange,
  onSaveQuantity,
  onSaveSupplementOrder,
  onCancelSupplementEdit,
  onSupplementDraftChange,
  onSupplementPickerOpen,
  onTransitionSupplementOrder,
  onEditSupplementOrder,
  plan,
  quantityDrafts,
  readOnly,
  internalNotes,
  requestedTests,
  supplementCatalogueState,
  supplementDraft,
  supplementOrdersState,
  editingSupplementOrderId,
  selectedReview,
}: {
  readonly busy: boolean;
  readonly clinicalTab: ClinicalTab;
  readonly contextState: MobileViewState<PhysicianMedicalContextResponse>;
  readonly foodsState: MobileViewState<PhysicianCatalogueFood[]>;
  readonly labsState: MobileViewState<PhysicianLabDocument[]>;
  readonly labReviewNotes: string;
  readonly notes: string;
  readonly onApprove: () => void;
  readonly onClinicalTabChange: (value: string) => void;
  readonly onNotesChange: (value: string) => void;
  readonly onInternalNotesChange: (value: string) => void;
  readonly onLabReviewNotesChange: (value: string) => void;
  readonly onQuantityDraftChange: (key: string, value: string) => void;
  readonly onRemoveMeal: (meal: WeeklyPlanMeal) => void;
  readonly onReplaceFood: (mealId: string, foodId: string, replacementFoodId: string) => void;
  readonly onRequestChanges: () => void;
  readonly onReject: () => void;
  readonly onRequestLabs: () => void;
  readonly onReviewLab: (documentId: string, status: LabReviewStatus) => void;
  readonly onRequestedTestsChange: (value: string) => void;
  readonly onSaveQuantity: (mealId: string, foodId: string, currentGrams: number) => Promise<void>;
  readonly onSaveSupplementOrder: () => void;
  readonly onCancelSupplementEdit: () => void;
  readonly onSupplementDraftChange: (key: keyof SupplementDraft, value: string) => void;
  readonly onSupplementPickerOpen: () => void;
  readonly onTransitionSupplementOrder: (orderId: string, status: SupplementTransitionStatus) => void;
  readonly onEditSupplementOrder: (order: PhysicianSupplementOrder) => void;
  readonly plan: PhysicianNutritionPlan;
  readonly quantityDrafts: Record<string, string>;
  readonly readOnly: boolean;
  readonly internalNotes: string;
  readonly requestedTests: string;
  readonly supplementCatalogueState: MobileViewState<PhysicianSupplementCatalogue[]>;
  readonly supplementDraft: SupplementDraft;
  readonly supplementOrdersState: MobileViewState<PhysicianSupplementOrder[]>;
  readonly editingSupplementOrderId: string | null;
  readonly selectedReview: PhysicianReviewQueueItem | null;
}) {
  const memberName = selectedReview?.member_display_name ?? "کاربر فیتیشین";
  return (
    <View style={styles.detailContent}>
      <View style={styles.detailHeader}>
        <View style={styles.caseIdentity}>
          <View style={styles.headerCopy}>
            <Text style={styles.eyebrow}>پروندهٔ تغذیه</Text>
            <Text style={styles.detailTitle}>نسخه در حال بررسی {formatPersianNumber(plan.revision, { maximumFractionDigits: 0 })}</Text>
          </View>
          <View accessibilityLabel={`تصویر ${memberName}`} style={styles.memberAvatar}>
            <Text style={styles.memberAvatarText}>{memberInitials(memberName)}</Text>
          </View>
        </View>
        <Text style={[styles.status, readOnly && styles.approvedStatus]}>
          {readOnly ? "تأییدشده" : "در حال بررسی"}
        </Text>
      </View>

      {readOnly ? <Notice message="این پرونده در حالت فقط‌خواندنی نمایش داده می‌شود." variant="info" /> : null}
      <MetricStrip
        items={[
          { label: "هزینه هفتگی", value: `${irrToToman(plan.weekly_cost_irr)} تومان` },
          { label: "مدت", value: `${formatNumber(plan.days.length)} روز` },
          { label: "حالت", value: readOnly ? "فقط‌خواندنی" : "قابل ویرایش" },
        ]}
      />
      <SegmentedControl
        accessibilityLabel="بخش‌های پرونده"
        onChange={onClinicalTabChange}
        options={clinicalTabs.map((tab) => ({ label: clinicalTabLabel(tab), value: tab }))}
        selectedValue={clinicalTab}
      />

      {clinicalTab === "plan" ? (
        <View style={styles.detailContent}>
          <DisclosureCard
            defaultExpanded={false}
            icon="shield"
            summary="داده‌های مبنا و وضعیت کنترل‌های نسخه"
            title="پروفایل، ایمنی، بودجه و منشأ داده"
          >
            <PlanEvidence plan={plan} />
          </DisclosureCard>
          <MedicalContextCard state={contextState} />
          <NutrientValidation plan={plan} />
          <Text style={styles.sectionTitle}>ویرایش نسخه</Text>
          {foodsState.status === "error" && foodsState.data === undefined ? (
            <Notice message="کاتالوگ مواد غذایی برای جایگزینی در دسترس نیست؛ بررسی نسخه ادامه دارد." variant="warning" />
          ) : null}
          {foodsState.status === "offline" && foodsState.data === undefined ? (
            <Notice message="در حالت آفلاین گزینه‌های جایگزینی بارگذاری نمی‌شوند." variant="offline" />
          ) : null}
          {plan.days.map((day) => (
            <Card key={day.plan_date} style={styles.dayCard}>
              <Text style={styles.dayTitle}>روز {formatPersianNumber(day.day_index + 1, { maximumFractionDigits: 0 })} · {formatPhysicianPlanDate(day.plan_date)}</Text>
              {day.meals.map((meal) => (
                <MealEditor
                  busy={busy}
                  foods={viewData(foodsState) ?? []}
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
          <DecisionBar
            busy={busy}
            hasNotes={notes.trim().length > 0}
            onApprove={onApprove}
            onRequestChanges={onRequestChanges}
            onReject={onReject}
            readOnly={readOnly}
          />
        </View>
      ) : null}
      {clinicalTab === "labs" ? (
        <LabsCard
          busy={busy}
          labReviewNotes={labReviewNotes}
          onLabReviewNotesChange={onLabReviewNotesChange}
          onRequestLabs={onRequestLabs}
          onReviewLab={onReviewLab}
          onRequestedTestsChange={onRequestedTestsChange}
          readOnly={readOnly}
          requestedTests={requestedTests}
          state={labsState}
        />
      ) : null}
      {clinicalTab === "supplements" ? (
        <SupplementsCard
          busy={busy}
          catalogueState={supplementCatalogueState}
          draft={supplementDraft}
          editingOrderId={editingSupplementOrderId}
          onDraftChange={onSupplementDraftChange}
          onEditOrder={onEditSupplementOrder}
          onOpenPicker={onSupplementPickerOpen}
          onCancelEdit={onCancelSupplementEdit}
          onSave={onSaveSupplementOrder}
          onTransition={onTransitionSupplementOrder}
          ordersState={supplementOrdersState}
          readOnly={readOnly}
        />
      ) : null}
      {clinicalTab === "notes" ? (
        <NotesSection
          busy={busy}
          internalNotes={internalNotes}
          notes={notes}
          onInternalNotesChange={onInternalNotesChange}
          onNotesChange={onNotesChange}
          readOnly={readOnly}
        />
      ) : null}
    </View>
  );
}

function PlanEvidence({ plan }: { readonly plan: PhysicianNutritionPlan }) {
  return (
    <View style={styles.evidenceContent}>
      <Text style={styles.body}>دادهٔ ورودی نسخه: {formatNumber(Object.keys(plan.input_snapshot).length)} مورد ثبت‌شده</Text>
      <Text style={styles.body}>وضعیت بودجه: {budgetStatusLabel(plan.budget_status)}</Text>
      <Text style={styles.body}>منشأ قیمت: {Object.keys(plan.price_snapshot).length > 0 ? "snapshot ثبت‌شده" : "ثبت نشده"}</Text>
      <Text style={styles.body}>منشأ دادهٔ غذایی: {Object.keys(plan.food_data_manifest).length > 0 ? "manifest معتبر" : "نیازمند بررسی"}</Text>
      <Text style={styles.body}>هشدارهای نسخه: {plan.warning_codes.length > 0 ? `${formatNumber(plan.warning_codes.length)} مورد` : "ندارد"}</Text>
      <Text style={styles.muted}>نسخه‌های فرمول و سیاست علمی در پرونده ثبت شده‌اند.</Text>
    </View>
  );
}

function NutrientValidation({ plan }: { readonly plan: PhysicianNutritionPlan }) {
  const nutrients = Object.values(plan.nutrients);
  return (
    <Card style={styles.contextCard}>
      <Text style={styles.sectionTitle}>وضعیت مواد مغذی</Text>
      {nutrients.length === 0 ? <Text style={styles.muted}>دادهٔ اعتبارسنجی مواد مغذی ثبت نشده است.</Text> : nutrients.map((nutrient) => (
        <View key={nutrient.nutrient_code} style={styles.nutrientRow}>
          <View style={styles.headerCopy}>
            <Text style={styles.body}>{nutrientLabel(nutrient.nutrient_code)}</Text>
            <Text style={styles.muted}>{formatNumber(nutrient.planned)} {nutrient.unit}</Text>
          </View>
          <Text style={[styles.status, nutrient.status === "fail" && styles.warningText]}>
            {nutrientStatusLabel(nutrient.status)}
          </Text>
        </View>
      ))}
    </Card>
  );
}

function DecisionBar({
  busy,
  hasNotes,
  onApprove,
  onRequestChanges,
  onReject,
  readOnly,
}: {
  readonly busy: boolean;
  readonly hasNotes: boolean;
  readonly onApprove: () => void;
  readonly onRequestChanges: () => void;
  readonly onReject: () => void;
  readonly readOnly: boolean;
}) {
  if (readOnly) return null;
  return (
    <Card style={styles.decisionCard} variant="raised">
      <Text style={styles.sectionTitle}>تصمیم نهایی</Text>
      {!hasNotes ? <Text style={styles.muted}>برای درخواست تغییر یا رد، ابتدا یادداشت پرونده را در بخش یادداشت‌ها ثبت کن.</Text> : null}
      <View style={styles.decisionRow}>
        <Button disabled={busy} label="تأیید این نسخه" onPress={onApprove} />
        <Button disabled={busy || !hasNotes} label="درخواست تغییر" onPress={onRequestChanges} variant="secondary" />
        <Button disabled={busy || !hasNotes} label="رد" onPress={onReject} variant="danger" />
      </View>
    </Card>
  );
}

function MedicalContextCard({ state }: { readonly state: MobileViewState<PhysicianMedicalContextResponse> }) {
  if (state.status === "loading") return <Skeleton height={200} />;
  if ((state.status === "offline" || state.status === "error") && state.data === undefined) {
    return <Notice message="زمینهٔ پزشکی این پرونده فعلاً در دسترس نیست؛ تصمیم‌گیری را متوقف کن." variant={state.status === "offline" ? "offline" : "warning"} />;
  }
  const context = state.data;
  if (context === undefined) return null;
  const flags = Object.values(context.flags).some(Boolean);
  return (
    <Card style={styles.contextCard}>
      <Text style={styles.sectionTitle}>زمینهٔ پزشکی</Text>
      <Text style={styles.muted}>نتیجهٔ ایمنی: {safetyOutcomeLabel(context.safety_outcome)}</Text>
      <Text style={styles.muted}>قواعد پزشکی و ایمنی پرونده ثبت شده‌اند.</Text>
      {context.conditions.length > 0 ? (
        <View style={styles.contextGroup}>
          <Text style={styles.contextLabel}>شرایط ثبت‌شده</Text>
          {context.conditions.map((condition) => <Text key={condition.code} style={styles.body}>{medicalConditionLabel(condition.code)}{condition.details ? ` · ${condition.details}` : ""}</Text>)}
        </View>
      ) : null}
      {context.medications.length > 0 ? (
        <View style={styles.contextGroup}>
          <Text style={styles.contextLabel}>داروها</Text>
          {context.medications.map((medication) => <Text key={`${medication.name}-${medication.dosage ?? ""}`} style={styles.body}>{medication.name}{medication.dosage ? ` · ${medication.dosage}` : ""}{medication.notes ? ` · ${medication.notes}` : ""}</Text>)}
        </View>
      ) : null}
      {flags ? <Text style={styles.body}>ملاحظات ایمنی تکمیلی برای این پرونده ثبت شده است.</Text> : null}
      {context.physician_dietary_restrictions ? <Text style={styles.body}>محدودیت غذایی پزشک: {context.physician_dietary_restrictions}</Text> : null}
      {context.other_relevant_condition ? <Text style={styles.body}>شرایط مرتبط دیگر: {context.other_relevant_condition}</Text> : null}
      {context.safety_reason_codes.length > 0 ? <Text style={styles.warningText}>ملاحظات ایمنی نیازمند توجه پزشک است.</Text> : null}
    </Card>
  );
}

function LabsCard({
  busy,
  labReviewNotes,
  onLabReviewNotesChange,
  onRequestLabs,
  onReviewLab,
  onRequestedTestsChange,
  readOnly,
  requestedTests,
  state,
}: {
  readonly busy: boolean;
  readonly labReviewNotes: string;
  readonly onLabReviewNotesChange: (value: string) => void;
  readonly onRequestLabs: () => void;
  readonly onReviewLab: (documentId: string, status: LabReviewStatus) => void;
  readonly onRequestedTestsChange: (value: string) => void;
  readonly readOnly: boolean;
  readonly requestedTests: string;
  readonly state: MobileViewState<PhysicianLabDocument[]>;
}) {
  if (state.status === "loading") return <Skeleton height={150} />;
  const labs = state.data ?? [];
  return (
    <Card style={styles.contextCard}>
      <Text style={styles.sectionTitle}>آزمایش‌های کاربر</Text>
      {state.status === "offline" && state.data === undefined ? (
        <Notice message="پرونده‌های آزمایش در حالت آفلاین در دسترس نیستند." variant="offline" />
      ) : null}
      {state.status === "error" && state.data === undefined ? (
        <Notice message="فهرست آزمایش‌های این پرونده دریافت نشد." variant="warning" />
      ) : null}
      {labs.length === 0 && state.status !== "offline" && state.status !== "error" ? (
        <Text style={styles.muted}>آزمایشی ثبت نشده است.</Text>
      ) : null}
      {labs.map((lab) => (
        <View key={lab.id} style={styles.labRow}>
          <Text style={styles.body}>{lab.original_filename}</Text>
          <Text style={styles.muted}>
            {labReviewStatusLabel(lab.review_status)}{lab.laboratory_name ? ` · ${lab.laboratory_name}` : ""}
          </Text>
          {!readOnly && state.status !== "offline" ? (
            <Button
              disabled={busy}
              label={lab.review_status === "reviewed" ? "ثبت نیازمند توجه" : "ثبت بررسی"}
              onPress={() => onReviewLab(lab.id, lab.review_status === "reviewed" ? "needs_attention" : "reviewed")}
              variant="ghost"
            />
          ) : null}
        </View>
      ))}
      <TextField
        editable={!readOnly && !busy && state.status !== "offline"}
        hint="آزمایش‌ها را با ویرگول فارسی یا انگلیسی جدا کن."
        label="آزمایش‌های درخواستی"
        onChangeText={onRequestedTestsChange}
        value={requestedTests}
      />
      <TextField
        editable={!readOnly && !busy && state.status !== "offline"}
        hint="این توضیح برای درخواست آزمایش یا ثبت بررسی استفاده می‌شود."
        label="یادداشت بررسی آزمایش"
        multiline
        numberOfLines={3}
        onChangeText={onLabReviewNotesChange}
        value={labReviewNotes}
      />
      {!readOnly ? (
        <Button
          disabled={busy || state.status === "offline"}
          label="درخواست آزمایش"
          onPress={onRequestLabs}
          variant="secondary"
        />
      ) : null}
    </Card>
  );
}

function SupplementsCard({
  busy,
  catalogueState,
  draft,
  editingOrderId,
  onDraftChange,
  onEditOrder,
  onOpenPicker,
  onCancelEdit,
  onSave,
  onTransition,
  ordersState,
  readOnly,
}: {
  readonly busy: boolean;
  readonly catalogueState: MobileViewState<PhysicianSupplementCatalogue[]>;
  readonly draft: SupplementDraft;
  readonly editingOrderId: string | null;
  readonly onDraftChange: (key: keyof SupplementDraft, value: string) => void;
  readonly onEditOrder: (order: PhysicianSupplementOrder) => void;
  readonly onOpenPicker: () => void;
  readonly onCancelEdit: () => void;
  readonly onSave: () => void;
  readonly onTransition: (orderId: string, status: SupplementTransitionStatus) => void;
  readonly ordersState: MobileViewState<PhysicianSupplementOrder[]>;
  readonly readOnly: boolean;
}) {
  if (ordersState.status === "loading") return <Skeleton height={260} />;
  const orders = ordersState.data ?? [];
  return (
    <View style={styles.detailContent}>
      <Card style={styles.contextCard}>
        <Text style={styles.sectionTitle}>دستورهای مکمل</Text>
        {ordersState.status === "offline" && ordersState.data === undefined ? (
          <Notice message="دستورهای مکمل در حالت آفلاین در دسترس نیستند." variant="offline" />
        ) : null}
        {ordersState.status === "error" && ordersState.data === undefined ? (
          <Notice message="دستورهای مکمل این پرونده دریافت نشد." variant="warning" />
        ) : null}
        {orders.length === 0 && ordersState.status !== "offline" && ordersState.status !== "error" ? (
          <Text style={styles.muted}>دستوری ثبت نشده است.</Text>
        ) : null}
        {orders.map((order) => (
          <View key={order.id} style={styles.orderCard}>
            <View style={styles.orderHeader}>
              <View style={styles.headerCopy}>
                <Text style={styles.foodName}>{order.name}</Text>
                <Text style={styles.muted}>{supplementStatusLabel(order.status)}</Text>
              </View>
              <Text style={styles.status}>{formatDose(order)}</Text>
            </View>
            {order.instructions ? <Text style={styles.body}>{order.instructions}</Text> : null}
            {order.rationale ? <Text style={styles.muted}>دلیل بالینی: {order.rationale}</Text> : null}
            {order.combined_exposure_safety.hard_blocks.length > 0 ? (
              <Notice message="برای این دستور، مانع ایمنی ثبت شده است؛ قبل از هر تصمیم جزئیات پزشکی را بررسی کن." variant="danger" />
            ) : null}
            {!readOnly && ordersState.status !== "offline" ? (
              <View style={styles.replacementRow}>
                {(order.status === "prescribed" || order.status === "active") ? (
                  <Button label="ویرایش" onPress={() => onEditOrder(order)} variant="ghost" />
                ) : null}
                {order.status === "prescribed" ? (
                  <>
                    <Button disabled={busy} label="فعال‌سازی" onPress={() => onTransition(order.id, "active")} variant="secondary" />
                    <Button disabled={busy} label="لغو" onPress={() => onTransition(order.id, "cancelled")} variant="danger" />
                  </>
                ) : null}
                {order.status === "active" ? (
                  <>
                    <Button disabled={busy} label="تکمیل" onPress={() => onTransition(order.id, "completed")} variant="secondary" />
                    <Button disabled={busy} label="قطع" onPress={() => onTransition(order.id, "discontinued")} variant="danger" />
                  </>
                ) : null}
              </View>
            ) : null}
          </View>
        ))}
      </Card>
      {!readOnly ? (
        <Card style={styles.contextCard}>
          <Text style={styles.sectionTitle}>{editingOrderId === null ? "ثبت دستور مکمل" : "ویرایش دستور مکمل"}</Text>
          <Button
            disabled={busy || catalogueState.status === "offline"}
            label={draftSupplementName(draft.supplementId, catalogueState)}
            onPress={onOpenPicker}
            variant="secondary"
          />
          <TextField
            editable={!busy}
            keyboardType="decimal-pad"
            label="مقدار دوز"
            onChangeText={(value) => onDraftChange("doseAmount", value)}
            value={draft.doseAmount}
          />
          <TextField
            editable={!busy}
            label="واحد دوز"
            onChangeText={(value) => onDraftChange("doseUnit", value)}
            value={draft.doseUnit}
          />
          <TextField
            editable={!busy}
            keyboardType="decimal-pad"
            label="تعداد واحد روزانه"
            onChangeText={(value) => onDraftChange("dailyUnits", value)}
            value={draft.dailyUnits}
          />
          <TextField
            editable={!busy}
            label="دفعات مصرف"
            onChangeText={(value) => onDraftChange("frequency", value)}
            value={draft.frequency}
          />
          <TextField
            editable={!busy}
            keyboardType="number-pad"
            label="مدت به روز"
            onChangeText={(value) => onDraftChange("durationDays", value)}
            value={draft.durationDays}
          />
          <TextField
            editable={!busy}
            hint="دستور دقیق مصرف برای کاربر ثبت می‌شود."
            label="دستور مصرف"
            multiline
            numberOfLines={3}
            onChangeText={(value) => onDraftChange("instructions", value)}
            value={draft.instructions}
          />
          <TextField
            editable={!busy}
            hint="دلیل بالینی قابل مشاهده در پرونده."
            label="دلیل بالینی"
            multiline
            numberOfLines={3}
            onChangeText={(value) => onDraftChange("rationale", value)}
            value={draft.rationale}
          />
          <View style={styles.decisionRow}>
            <Button disabled={busy} label={editingOrderId === null ? "ثبت دستور مکمل" : "ذخیره ویرایش"} onPress={onSave} />
            {editingOrderId !== null ? <Button disabled={busy} label="انصراف از ویرایش" onPress={onCancelEdit} variant="ghost" /> : null}
          </View>
        </Card>
      ) : null}
    </View>
  );
}

function SupplementCataloguePicker({
  onSelect,
  state,
}: {
  readonly onSelect: (supplement: PhysicianSupplementCatalogue) => void;
  readonly state: MobileViewState<PhysicianSupplementCatalogue[]>;
}) {
  if (state.status === "loading") return <Skeleton height={160} />;
  if (state.status === "offline" && state.data === undefined) {
    return <Notice message="کاتالوگ مکمل در حالت آفلاین در دسترس نیست." variant="offline" />;
  }
  if (state.status === "error" && state.data === undefined) {
    return <Notice message="کاتالوگ مکمل دریافت نشد." variant="warning" />;
  }
  const catalogue = state.data ?? [];
  if (catalogue.length === 0) return <EmptyState title="مکمل تأییدشده‌ای در کاتالوگ نیست" />;
  return (
    <View style={styles.catalogueList}>
      {catalogue.map((supplement) => (
        <Button
          key={supplement.id}
          label={supplement.name_fa || supplement.name_en}
          onPress={() => onSelect(supplement)}
          variant="secondary"
        />
      ))}
    </View>
  );
}

function NotesSection({
  busy,
  internalNotes,
  notes,
  onInternalNotesChange,
  onNotesChange,
  readOnly,
}: {
  readonly busy: boolean;
  readonly internalNotes: string;
  readonly notes: string;
  readonly onInternalNotesChange: (value: string) => void;
  readonly onNotesChange: (value: string) => void;
  readonly readOnly: boolean;
}) {
  return (
    <Card style={styles.contextCard}>
      <Text style={styles.sectionTitle}>یادداشت‌های پرونده</Text>
      <TextField
        editable={!readOnly && !busy}
        hint="برای درخواست تغییر یا رد نسخه، این توضیح الزامی است."
        label="یادداشت قابل مشاهده برای کاربر"
        multiline
        numberOfLines={5}
        onChangeText={onNotesChange}
        value={notes}
      />
      <TextField
        editable={!readOnly && !busy}
        hint="این یادداشت فقط برای تیم تخصصی قابل مشاهده است."
        label="یادداشت محرمانه پزشک"
        multiline
        numberOfLines={4}
        onChangeText={onInternalNotesChange}
        value={internalNotes}
      />
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

function clinicalTabLabel(tab: ClinicalTab): string {
  if (tab === "plan") return "بررسی برنامه";
  if (tab === "labs") return "آزمایش‌ها";
  if (tab === "supplements") return "مکمل‌ها";
  return "یادداشت‌ها";
}

function memberInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return parts.slice(0, 2).map((part) => part[0] ?? "ف").join("");
}

function draftSupplementName(
  supplementId: string,
  state: MobileViewState<PhysicianSupplementCatalogue[]>,
): string {
  if (!supplementId) return "انتخاب مکمل";
  const selected = viewData(state)?.find((item) => item.id === supplementId);
  return selected?.name_fa || selected?.name_en || "مکمل انتخاب‌شده";
}

function formatDose(order: PhysicianSupplementOrder): string {
  const amount = order.dose_amount === null ? "—" : formatNumber(order.dose_amount);
  const unit = order.dose_unit ?? "واحد";
  const frequency = order.frequency ?? "دفعات ثبت نشده";
  return `${amount} ${unit} · ${frequency}`;
}

function budgetStatusLabel(status: string): string {
  if (status === "within_budget") return "در محدوده بودجه";
  if (status === "over_budget") return "بیش از بودجه";
  return "در حال بررسی بودجه";
}

function nutrientLabel(code: string): string {
  if (code === "energy_kcal") return "انرژی";
  if (code === "protein_g") return "پروتئین";
  if (code === "carbohydrate_g") return "کربوهیدرات";
  if (code === "total_fat_g") return "چربی";
  if (code === "fibre_g") return "فیبر";
  return "ماده مغذی";
}

function nutrientStatusLabel(status: string): string {
  if (status === "adequate" || status === "pass" || status === "within_range") return "مناسب";
  if (status === "low" || status === "below_minimum") return "کمتر از حد هدف";
  if (status === "high" || status === "above_maximum" || status === "fail") return "بیشتر از حد هدف";
  return "نیازمند بررسی";
}

function safetyOutcomeLabel(status: string): string {
  if (status === "standard_automatic") return "بررسی خودکار استاندارد";
  if (status === "automatic_draft_requires_physician_review") return "پیش‌نویس نیازمند بررسی پزشک";
  if (status === "physician_manual_plan_required") return "نیازمند نسخه‌نویسی پزشک";
  if (status === "unsupported_or_hard_blocked") return "متوقف‌شده برای بررسی ایمنی";
  return "نیازمند بررسی";
}

function medicalConditionLabel(code: string): string {
  const labels: Readonly<Record<string, string>> = {
    controlled_hypertension: "فشار خون کنترل‌شده",
    dialysis: "دیالیز",
    insulin_treated_diabetes: "دیابت با انسولین",
    kidney_disease: "بیماری کلیوی",
    lipid_disorder: "اختلال چربی خون",
    liver_disease: "بیماری کبدی",
    other: "شرایط پزشکی دیگر",
    stable_gastrointestinal: "شرایط گوارشی پایدار",
    type_2_diabetes_non_insulin: "دیابت نوع دو بدون انسولین",
  };
  return labels[code] ?? "شرایط پزشکی ثبت‌شده";
}

function formatNumber(value: number): string {
  return formatPersianNumber(value);
}

function formatPhysicianPlanDate(value: string): string {
  return new Intl.DateTimeFormat("fa-IR", { day: "numeric", month: "short" }).format(
    new Date(`${value}T12:00:00`),
  );
}

function physicianErrorMessage(error: unknown): string {
  const code = error instanceof Error && "code" in error
    ? (error as { readonly code?: unknown }).code
    : null;
  if (code === "STALE_PLAN_REVISION") return "نسخهٔ پرونده تغییر کرده است؛ نسخهٔ تازه را بررسی کن.";
  if (code === "REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN") return "این پرونده در اختیار پزشک دیگری است.";
  if (code === "REVIEW_NOT_IN_PROGRESS") return "این پرونده دیگر در وضعیت بررسی نیست.";
  return mobileRequestErrorMessage(error, "عملیات پزشک انجام نشد؛ اتصال و وضعیت پرونده را بررسی کن.");
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

const styles = StyleSheet.create({
  approvedStatus: { color: fiticianTokens.colors.amber },
  body: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 27,
    textAlign: "auto",
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
  caseIdentity: { alignItems: "center", flex: 1, flexDirection: "row", gap: fiticianTokens.spacing[3], minWidth: 0 },
  catalogueList: { gap: fiticianTokens.spacing[2] },
  contextLabel: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  dayCard: { gap: fiticianTokens.spacing[3] },
  dayTitle: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    textAlign: "auto",
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  decisionCard: { gap: fiticianTokens.spacing[3] },
  eyebrow: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  evidenceContent: { gap: fiticianTokens.spacing[2] },
  foodCopy: { flex: 1, gap: fiticianTokens.spacing[1] },
  foodEditor: { borderTopColor: fiticianTokens.colors.line, borderTopWidth: 1, gap: fiticianTokens.spacing[2], paddingTop: fiticianTokens.spacing[3] },
  foodName: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  heroCard: { gap: fiticianTokens.spacing[4] },
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  memberName: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  memberAvatar: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceHighlight,
    borderColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    height: 48,
    justifyContent: "center",
    width: 48,
  },
  memberAvatarText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "center",
    writingDirection: "rtl",
  },
  muted: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  nutrientRow: { alignItems: "center", borderTopColor: fiticianTokens.colors.line, borderTopWidth: 1, flexDirection: "row", gap: fiticianTokens.spacing[2], paddingTop: fiticianTokens.spacing[2] },
  orderCard: { borderTopColor: fiticianTokens.colors.line, borderTopWidth: 1, gap: fiticianTokens.spacing[2], paddingTop: fiticianTokens.spacing[3] },
  orderHeader: { alignItems: "flex-start", flexDirection: "row", gap: fiticianTokens.spacing[2], justifyContent: "space-between" },
  quantityRow: { alignItems: "center", flexDirection: "row", gap: fiticianTokens.spacing[2] },
  queue: { gap: fiticianTokens.spacing[3] },
  queueItems: { gap: fiticianTokens.spacing[3] },
  queueMeta: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "auto",
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  selectedCard: { borderColor: fiticianTokens.colors.aqua },
  status: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  subtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 26,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  summaryCard: { gap: fiticianTokens.spacing[2] },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 40,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  warningList: { gap: fiticianTokens.spacing[1] },
  warningText: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  warningTitle: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  workspace: { gap: fiticianTokens.spacing[6] },
});
