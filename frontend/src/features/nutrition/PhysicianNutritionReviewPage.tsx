import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import * as api from "./api";
import type { PhysicianSupplementOrderInput, SupplementOrder } from "./api";
import type { WeeklyPlan } from "./types";
import "./nutritionEstimate.css";

type Review = Awaited<ReturnType<typeof api.listPhysicianReviews>>[number];
type QueueView = api.PhysicianQueueView;
type ClinicalTab = "plan" | "labs" | "supplements" | "notes";

const emptyOrder = {
  supplementId: "",
  doseAmount: "1",
  doseUnit: "tablet",
  dailyUnits: "1",
  frequency: "once_daily",
  durationDays: "30",
  instructions: "",
  rationale: "",
};

export function PhysicianNutritionReviewPage() {
  const { i18n } = useTranslation();
  const fa = i18n.language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const navigate = useNavigate();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [queues, setQueues] = useState<Record<QueueView, Review[]>>({ pending: [], claimed: [], approved: [] });
  const [activeView, setActiveView] = useState<QueueView>("pending");
  const [clinicalTab, setClinicalTab] = useState<ClinicalTab>("plan");
  const [readOnly, setReadOnly] = useState(false);
  const [error, setError] = useState(false);
  const [supplementCatalogue, setSupplementCatalogue] = useState<Awaited<ReturnType<typeof api.listSupplementCatalogue>>>([]);
  const [foodCatalogue, setFoodCatalogue] = useState<api.CatalogueFood[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<WeeklyPlan | null>(null);
  const [notes, setNotes] = useState("");
  const [internalNotes, setInternalNotes] = useState("");
  const [tests, setTests] = useState("CBC");
  const [loading, setLoading] = useState(true);
  const [labs, setLabs] = useState<api.LabDocument[]>([]);
  const [orders, setOrders] = useState<SupplementOrder[]>([]);
  const [orderForm, setOrderForm] = useState(emptyOrder);
  const [editingOrderId, setEditingOrderId] = useState<string | null>(null);

  const load = (view: QueueView = activeView) => api.listPhysicianReviews(view)
    .then((items) => { setReviews(items); setQueues((current) => ({ ...current, [view]: items })); setError(false); })
    .catch(() => setError(true))
    .finally(() => setLoading(false));

  useEffect(() => {
    void Promise.all(([
      "pending", "claimed", "approved",
    ] as QueueView[]).map((view) => api.listPhysicianReviews(view)))
      .then(([pending, claimed, approved]) => {
        setQueues({ pending, claimed, approved });
        setReviews(pending);
        setError(false);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    void Promise.all([api.listSupplementCatalogue(), api.listCatalogueFoods()])
      .then(([supplements, foods]) => {
        setSupplementCatalogue(supplements);
        setFoodCatalogue(foods);
      })
      .catch(() => setError(true));
  }, []);

  async function claimAndOpen(review: Review) {
    setError(false);
    try {
      if (activeView === "pending") await api.claimPhysicianReview(review.review_id);
      const [plan, documents, planOrders] = await Promise.all([
        api.getPhysicianPlan(review.plan_id),
        api.listPhysicianLabs(review.plan_id),
        api.listPhysicianSupplementOrders(review.plan_id),
      ]);
      setSelectedPlan(plan);
      setLabs(documents);
      setOrders(planOrders);
      setReadOnly(activeView === "approved");
      await load(activeView);
    } catch { setError(true); }
  }

  async function act(action: "approve" | "request_changes" | "reject") {
    if (!selectedPlan || ((action === "request_changes" || action === "reject") && !notes.trim())) return;
    try {
      setSelectedPlan(await api.actOnPhysicianPlan(
        selectedPlan.id,
        action,
        notes.trim() || null,
        internalNotes.trim() || null,
      ));
      await load(activeView);
    } catch { setError(true); }
  }

  function orderPayload(): PhysicianSupplementOrderInput | null {
    if (!orderForm.supplementId || !orderForm.instructions.trim() || !orderForm.rationale.trim()) return null;
    return {
      supplement_id: orderForm.supplementId,
      dose_amount: Number(orderForm.doseAmount),
      dose_unit: orderForm.doseUnit,
      daily_units: Number(orderForm.dailyUnits),
      frequency: orderForm.frequency,
      duration_days: Number(orderForm.durationDays),
      instructions: orderForm.instructions,
      rationale: orderForm.rationale,
      rationale_user_visible: true,
      linked_gap_codes: [],
      linked_lab_document_ids: [],
    };
  }

  async function saveOrder() {
    if (!selectedPlan) return;
    const payload = orderPayload();
    if (!payload) return;
    try {
      if (editingOrderId) await api.updatePhysicianSupplementOrder(editingOrderId, payload);
      else await api.createPhysicianSupplementOrder(selectedPlan.id, payload);
      setOrders(await api.listPhysicianSupplementOrders(selectedPlan.id));
      setEditingOrderId(null);
      setOrderForm(emptyOrder);
    } catch { setError(true); }
  }

  function editOrder(order: SupplementOrder) {
    setEditingOrderId(order.id);
    setOrderForm({
      supplementId: order.supplement_id,
      doseAmount: String(order.dose_amount),
      doseUnit: order.dose_unit,
      dailyUnits: String(order.daily_units),
      frequency: order.frequency,
      durationDays: String(order.duration_days),
      instructions: order.instructions,
      rationale: order.rationale ?? "",
    });
  }

  async function transitionOrder(orderId: string, status: "active" | "completed" | "discontinued" | "cancelled") {
    if (!selectedPlan) return;
    try {
      await api.transitionPhysicianSupplementOrder(orderId, status);
      setOrders(await api.listPhysicianSupplementOrders(selectedPlan.id));
    } catch { setError(true); }
  }

  const tabTitle = (tab: ClinicalTab) => tab === "plan" ? l("بررسی برنامه", "Plan review") : tab === "labs" ? l("آزمایش‌ها", "Laboratory review") : tab === "supplements" ? l("مکمل‌ها", "Supplements") : l("یادداشت‌ها", "Notes");

  return <div className="physician-review-shell" dir={fa ? "rtl" : "ltr"}>
    <main className="physician-review-page">
      <header className="physician-review-hero">
        <button className="physician-review-back" type="button" onClick={() => navigate(-1)}>{l("بازگشت", "Back")}</button>
        <div><p>{l("میز کار پزشک", "Physician desk")}</p><h1 className="fitsho-display">{l("صف بررسی برنامه‌های تغذیه", "Nutrition plan reviews")}</h1><span>{l("آزمایش‌ها، مکمل‌ها و نسخه را در یک پرونده بررسی کن.", "Review the plan, lab documents, and supplements in one case.")}</span></div>
        <aside className="physician-review-summary"><strong>{queues.pending.length}</strong><small>{l("پرونده در انتظار", "pending cases")}</small></aside>
      </header>
      {error && <p className="physician-review-error" role="alert">{l("عملیات پزشک انجام نشد.", "The physician operation failed.")}</p>}
      <div className="physician-review-workspace">
        <aside className="physician-review-queue">
          <div className="physician-queue-tabs" role="tablist" aria-label={l("صف‌های پزشک", "Physician queues")}>
            {(["pending", "claimed", "approved"] as QueueView[]).map((view) => <button key={view} type="button" role="tab" aria-selected={activeView === view} onClick={() => { setActiveView(view); setReviews(queues[view]); setSelectedPlan(null); setReadOnly(view === "approved"); }}>{view === "pending" ? l("در انتظار", "Pending") : view === "claimed" ? l("در بررسی", "Claimed") : l("تأییدشده", "Approved")} ({queues[view].length})</button>)}
          </div>
          {loading && <p role="status">{l("در حال دریافت پرونده‌ها…", "Loading cases…")}</p>}
          {!loading && reviews.length === 0 && <p className="physician-review-empty">{l("پرونده‌ای در این صف نیست.", "This queue is clear.")}</p>}
          <div className="physician-review-cases">{reviews.map((review) => <article key={review.review_id} className={selectedPlan?.id === review.plan_id ? "is-selected" : undefined}><small>{review.member_display_name ?? l("کاربر فیتشو", "Fitsho member")}</small><strong>{review.status}</strong><span>{review.overdue ? l("گذشته از موعد", "Overdue") : l("نسخه تغذیه", "Nutrition plan")}</span><button type="button" onClick={() => void claimAndOpen(review)}>{activeView === "pending" ? l("شروع بررسی", "Claim and view revision") : l("مشاهده پرونده", "View revision")}</button></article>)}</div>
        </aside>
        <section className="physician-review-canvas" aria-live="polite">
          {!selectedPlan && <div className="physician-review-placeholder"><span aria-hidden="true">✦</span><h2>{l("یک پرونده را انتخاب کن", "Choose a case from the queue")}</h2><p>{l("نسخه، آزمایش‌ها، مکمل‌ها و یادداشت‌های بالینی اینجا نمایش داده می‌شوند.", "The plan, lab documents, supplements, and clinical notes will appear here.")}</p></div>}
          {selectedPlan && <>
            <header className="physician-review-case-header"><div><small>{l("پرونده تغذیه", "Nutrition case")}</small><h2>{l("نسخه در حال بررسی", "Revision under review")} {selectedPlan.revision}</h2></div><span data-status={readOnly ? "approved" : "claimed"}>{readOnly ? l("تأییدشده", "Approved") : l("در حال بررسی", "In review")}</span></header>
            <div className="physician-review-profile-strip"><span>{l("هزینه هفتگی", "Weekly cost")}<strong>{selectedPlan.weekly_cost_irr.toLocaleString()} IRR</strong></span><span>{l("مدت", "Duration")}<strong>{selectedPlan.days.length} {l("روز", "days")}</strong></span><span>{l("حالت", "Mode")}<strong>{readOnly ? l("فقط‌خواندنی", "Read only") : l("قابل ویرایش", "Editable")}</strong></span></div>
            <div className="physician-clinical-tabs" role="tablist" aria-label={l("بخش‌های پرونده", "Case sections")}>{(["plan", "labs", "supplements", "notes"] as ClinicalTab[]).map((tab) => <button key={tab} type="button" role="tab" aria-selected={clinicalTab === tab} onClick={() => setClinicalTab(tab)}>{tabTitle(tab)}</button>)}</div>
            {clinicalTab === "plan" && <section className="physician-review-section">
              <details><summary>{l("پروفایل، ایمنی، بودجه و منشأ داده", "Profile, safety, budget, and provenance")}</summary><pre>{JSON.stringify({ input_snapshot: selectedPlan.input_snapshot, budget: selectedPlan.budget_status, price_snapshot: selectedPlan.price_snapshot, food_data_manifest: selectedPlan.food_data_manifest }, null, 2)}</pre></details>
              <section><h3>{l("وضعیت مواد مغذی", "Nutrient validation")}</h3>{Object.values(selectedPlan.nutrients).map((nutrient) => <p key={nutrient.nutrient_code}>{nutrient.nutrient_code}: {nutrient.planned} {nutrient.unit} · {nutrient.status}</p>)}</section>
              <div className="physician-plan-days">{selectedPlan.days.map((day) => <article key={day.plan_date}><strong>{day.plan_date}</strong>{day.meals.map((meal) => <div key={meal.id}>{meal.foods.map((food) => <p key={food.food_id}><span>{fa ? food.name_fa : food.name_en}</span><input disabled={readOnly} aria-label={l(`مقدار ${food.name_fa}`, `${food.name_en} quantity`)} type="number" min="1" max="5000" defaultValue={food.grams} onBlur={(event) => { const grams = Number(event.target.value); if (!readOnly && grams !== food.grams) void api.adjustPhysicianFoodQuantity(selectedPlan.id, meal.id, food.food_id, grams).then(setSelectedPlan).catch(() => setError(true)); }} /><select disabled={readOnly} aria-label={l(`جایگزین ${food.name_fa}`, `Replace ${food.name_en}`)} value={food.food_id} onChange={(event) => { if (!readOnly && event.target.value !== food.food_id) void api.replacePhysicianFood(selectedPlan.id, meal.id, food.food_id, event.target.value).then(setSelectedPlan).catch(() => setError(true)); }}><option value={food.food_id}>{fa ? food.name_fa : food.name_en}</option>{foodCatalogue.filter((candidate) => candidate.id !== food.food_id).map((candidate) => <option key={candidate.id} value={candidate.id}>{fa ? candidate.name_fa : candidate.name_en}</option>)}</select></p>)}</div>)}</article>)}</div>
              {!readOnly && <div className="weekly-plan__meal-actions"><button onClick={() => void act("approve")}>{l("تأیید این نسخه", "Approve this revision")}</button><button disabled={!notes.trim()} onClick={() => void act("request_changes")}>{l("درخواست تغییر", "Request changes")}</button><button disabled={!notes.trim()} onClick={() => void act("reject")}>{l("رد", "Reject")}</button></div>}
            </section>}
            {clinicalTab === "notes" && <section className="physician-review-section physician-review-notes"><label>{l("یادداشت قابل مشاهده برای کاربر", "User-visible note")}<textarea disabled={readOnly} value={notes} onChange={(event) => setNotes(event.target.value)} /></label><label>{l("یادداشت محرمانه پزشک", "Private physician note")}<textarea disabled={readOnly} value={internalNotes} onChange={(event) => setInternalNotes(event.target.value)} /></label></section>}
            {clinicalTab === "labs" && <section className="physician-review-section"><h3>{l("آزمایش‌های کاربر", "Member lab documents")}</h3>{labs.length === 0 ? <p>{l("آزمایشی ثبت نشده است.", "No lab documents are available.")}</p> : labs.map((lab) => <article key={lab.id}><strong>{lab.original_filename}</strong><span>{lab.review_status}</span>{!readOnly && <button onClick={() => void api.reviewPhysicianLab(lab.id, "reviewed", notes || null).then((updated) => setLabs((items) => items.map((item) => item.id === updated.id ? updated : item)))}>{l("ثبت بررسی", "Mark reviewed")}</button>}</article>)}<label>{l("آزمایش‌های درخواستی", "Requested tests")}<input disabled={readOnly} value={tests} onChange={(event) => setTests(event.target.value)} /></label>{!readOnly && <button onClick={() => void api.requestPhysicianLabs(selectedPlan.id, tests.split(",").map((item) => item.trim()).filter(Boolean), notes || l("برای بررسی ایمن‌تر برنامه", "For a safer plan review"))}>{l("درخواست آزمایش", "Request labs")}</button>}</section>}
            {clinicalTab === "supplements" && <section className="physician-review-section"><h3>{l("دستورهای مکمل", "Supplement orders")}</h3>{orders.length === 0 ? <p>{l("دستوری ثبت نشده است.", "No order has been recorded.")}</p> : orders.map((order) => <article key={order.id}><strong>{order.name}</strong><span>{order.dose_amount} {order.dose_unit} · {order.frequency} · {order.status}</span>{!readOnly && ["prescribed", "active"].includes(order.status) && <button onClick={() => editOrder(order)}>{l("ویرایش", "Edit")}</button>}{!readOnly && order.status === "prescribed" && <><button onClick={() => void transitionOrder(order.id, "active")}>{l("فعال‌سازی", "Activate")}</button><button onClick={() => void transitionOrder(order.id, "cancelled")}>{l("لغو", "Cancel")}</button></>}{!readOnly && order.status === "active" && <><button onClick={() => void transitionOrder(order.id, "completed")}>{l("تکمیل", "Complete")}</button><button onClick={() => void transitionOrder(order.id, "discontinued")}>{l("قطع", "Discontinue")}</button></>}</article>)}<fieldset disabled={readOnly} className="food-admin-form">
              <label>{l("مکمل", "Supplement")}<select value={orderForm.supplementId} onChange={(event) => setOrderForm((value) => ({ ...value, supplementId: event.target.value }))}><option value="">{l("انتخاب مکمل", "Select supplement")}</option>{supplementCatalogue.map((item) => <option value={item.id} key={item.id}>{fa ? item.name_fa : item.name_en}</option>)}</select></label>
              <label>{l("مقدار دوز", "Dose amount")}<input type="number" min="0.01" value={orderForm.doseAmount} onChange={(event) => setOrderForm((value) => ({ ...value, doseAmount: event.target.value }))} /></label>
              <label>{l("واحد دوز", "Dose unit")}<input value={orderForm.doseUnit} onChange={(event) => setOrderForm((value) => ({ ...value, doseUnit: event.target.value }))} /></label>
              <label>{l("تعداد واحد روزانه", "Daily units")}<input type="number" min="0.01" value={orderForm.dailyUnits} onChange={(event) => setOrderForm((value) => ({ ...value, dailyUnits: event.target.value }))} /></label>
              <label>{l("دفعات مصرف", "Frequency")}<input value={orderForm.frequency} onChange={(event) => setOrderForm((value) => ({ ...value, frequency: event.target.value }))} /></label>
              <label>{l("مدت به روز", "Duration in days")}<input type="number" min="1" value={orderForm.durationDays} onChange={(event) => setOrderForm((value) => ({ ...value, durationDays: event.target.value }))} /></label>
              <label>{l("دستور مصرف", "Instructions")}<textarea value={orderForm.instructions} onChange={(event) => setOrderForm((value) => ({ ...value, instructions: event.target.value }))} /></label>
              <label>{l("دلیل بالینی", "Clinical rationale")}<textarea value={orderForm.rationale} onChange={(event) => setOrderForm((value) => ({ ...value, rationale: event.target.value }))} /></label>
              {!readOnly && <button disabled={!orderPayload()} onClick={() => void saveOrder()}>{editingOrderId ? l("ذخیره ویرایش", "Save changes") : l("ثبت دستور مکمل", "Prescribe supplement")}</button>}
            </fieldset></section>}
          </>}
        </section>
      </div>
    </main>
  </div>;
}
