import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import * as api from "./api";
import type { WeeklyPlan } from "./types";
import "./nutritionEstimate.css";

type Review = Awaited<ReturnType<typeof api.listPhysicianReviews>>[number];

export function PhysicianNutritionReviewPage() {
  const { i18n } = useTranslation();
  const fa = i18n.language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const navigate = useNavigate();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [error, setError] = useState(false);
  const [catalogue, setCatalogue] = useState<Awaited<ReturnType<typeof api.listSupplementCatalogue>>>([]);
  const [foodCatalogue, setFoodCatalogue] = useState<api.CatalogueFood[]>([]);
  const [supplementId, setSupplementId] = useState("");
  const [selectedPlan, setSelectedPlan] = useState<WeeklyPlan | null>(null);
  const [notes, setNotes] = useState("");
  const [tests, setTests] = useState("CBC");
  const [loading, setLoading] = useState(true);
  const [labs, setLabs] = useState<api.LabDocument[]>([]);
  const load = () => api.listPhysicianReviews().then((items) => { setReviews(items); setError(false); }).catch(() => setError(true)).finally(() => setLoading(false));
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    void Promise.all([api.listSupplementCatalogue(), api.listCatalogueFoods()])
      .then(([supplements, foods]) => { setCatalogue(supplements); setFoodCatalogue(foods); })
      .catch(() => setError(true));
  }, []);

  async function claimAndOpen(review: Review) {
    setError(false);
    try {
      await api.claimPhysicianReview(review.review_id);
      const [plan, documents] = await Promise.all([
        api.getPhysicianPlan(review.plan_id),
        api.listPhysicianLabs(review.plan_id),
      ]);
      setSelectedPlan(plan);
      setLabs(documents);
      await load();
    } catch { setError(true); }
  }

  async function act(action: "approve" | "request_changes" | "reject") {
    if (!selectedPlan || ((action === "request_changes" || action === "reject") && !notes.trim())) return;
    try { setSelectedPlan(await api.actOnPhysicianPlan(selectedPlan.id, action, notes.trim() || null)); await load(); }
    catch { setError(true); }
  }

  return <main className="nutrition-estimate-page" dir={fa ? "rtl" : "ltr"}>
    <section className="nutrition-estimate-hero"><button className="secondary-button" type="button" onClick={() => navigate(-1)}>{l("بازگشت", "Back")}</button><h1>{l("صف بررسی برنامه‌های تغذیه", "Nutrition review queue")}</h1><p>{l("تأیید فقط برای نسخه دقیق نمایش‌داده‌شده ثبت می‌شود.", "Approval applies only to the exact displayed revision.")}</p></section>
    {loading && <p role="status">{l("در حال دریافت صف بررسی…", "Loading review queue…")}</p>}
    {error && <p role="alert">{l("دسترسی پزشک لازم است.", "Physician access required.")}</p>}
    {!loading && reviews.length === 0 && <p>{l("پرونده‌ای در صف نیست.", "The queue is empty.")}</p>}
    <section className="nutrition-target-grid">{reviews.map((review) => <article className="nutrition-target-card" key={review.review_id}><strong>{review.status}</strong><small>{review.plan_id}</small>{review.overdue && <span>{l("گذشته از موعد", "Overdue")}</span>}<button className="primary-button" onClick={() => void claimAndOpen(review)}>{l("ثبت مسئولیت و مشاهده نسخه", "Claim and view revision")}</button></article>)}</section>
    {selectedPlan && <section className="nutrition-estimate-notes"><h2>{l("نسخه در حال بررسی", "Revision under review")} {selectedPlan.revision}</h2><p>{l("هزینه هفتگی", "Weekly cost")}: {selectedPlan.weekly_cost_irr.toLocaleString()} IRR · {selectedPlan.days.length} {l("روز", "days")}</p><details><summary>{l("ایمنی، بودجه و منشأ داده", "Safety, budget, and provenance")}</summary><pre>{JSON.stringify({ safety: selectedPlan.input_snapshot.safety_reason_codes, budget: selectedPlan.budget_status, price_snapshot: selectedPlan.price_snapshot, food_data_manifest: selectedPlan.food_data_manifest }, null, 2)}</pre></details><section><h3>{l("وضعیت مواد مغذی", "Nutrient validation")}</h3>{Object.values(selectedPlan.nutrients).map((nutrient) => <p key={nutrient.nutrient_code}>{nutrient.nutrient_code}: {nutrient.planned} {nutrient.unit} · {nutrient.status}</p>)}</section><div className="physician-plan-days">{selectedPlan.days.map((day) => <article key={day.plan_date}><strong>{day.plan_date}</strong>{day.meals.map((meal) => <div key={meal.id}>{meal.foods.map((food) => <p key={food.food_id}><span>{fa ? food.name_fa : food.name_en}</span><input aria-label={l(`مقدار ${food.name_fa}`, `${food.name_en} quantity`)} type="number" min="1" max="5000" defaultValue={food.grams} onBlur={(event) => { const grams = Number(event.target.value); if (grams !== food.grams) void api.adjustPhysicianFoodQuantity(selectedPlan.id, meal.id, food.food_id, grams).then(setSelectedPlan).catch(() => setError(true)); }} /><select aria-label={l(`جایگزین ${food.name_fa}`, `Replace ${food.name_en}`)} value={food.food_id} onChange={(event) => { if (event.target.value !== food.food_id) void api.replacePhysicianFood(selectedPlan.id, meal.id, food.food_id, event.target.value).then(setSelectedPlan).catch(() => setError(true)); }}><option value={food.food_id}>{fa ? food.name_fa : food.name_en}</option>{foodCatalogue.filter((candidate) => candidate.id !== food.food_id).map((candidate) => <option key={candidate.id} value={candidate.id}>{fa ? candidate.name_fa : candidate.name_en}</option>)}</select></p>)}</div>)}</article>)}</div><label>{l("یادداشت قابل مشاهده برای کاربر", "User-visible note")}<textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></label><div className="weekly-plan__meal-actions"><button onClick={() => void act("approve")}>{l("تأیید این نسخه", "Approve this revision")}</button><button disabled={!notes.trim()} onClick={() => void act("request_changes")}>{l("درخواست تغییر", "Request changes")}</button><button disabled={!notes.trim()} onClick={() => void act("reject")}>{l("رد", "Reject")}</button></div><section><h3>{l("آزمایش‌های کاربر", "Member lab documents")}</h3>{labs.length === 0 ? <p>{l("آزمایشی ثبت نشده است.", "No lab documents are available.")}</p> : labs.map((lab) => <article key={lab.id}><strong>{lab.original_filename}</strong><span>{lab.review_status}</span><button onClick={() => void api.reviewPhysicianLab(lab.id, "reviewed", notes || null).then((updated) => setLabs((items) => items.map((item) => item.id === updated.id ? updated : item)))}>{l("ثبت بررسی", "Mark reviewed")}</button></article>)}</section><label>{l("آزمایش‌های درخواستی", "Requested tests")}<input value={tests} onChange={(event) => setTests(event.target.value)} /></label><button onClick={() => void api.requestPhysicianLabs(selectedPlan.id, tests.split(",").map((item) => item.trim()).filter(Boolean), notes || l("برای بررسی ایمن‌تر برنامه", "For a safer plan review"))}>{l("درخواست آزمایش", "Request labs")}</button><hr /><select value={supplementId} onChange={(event) => setSupplementId(event.target.value)}><option value="">{l("انتخاب مکمل", "Select supplement")}</option>{catalogue.map((item) => <option value={item.id} key={item.id}>{fa ? item.name_fa : item.name_en}</option>)}</select><button disabled={!supplementId} onClick={() => void api.createPhysicianSupplementOrder(selectedPlan.id, supplementId)}>{l("ثبت دستور مکمل", "Prescribe supplement")}</button></section>}
  </main>;
}
