import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import * as api from "./api";
import type { WeeklyPlan } from "./types";
import "./nutritionEstimate.css";

type Review = Awaited<ReturnType<typeof api.listPhysicianReviews>>[number];

export function PhysicianNutritionReviewPage() {
  const { i18n } = useTranslation();
  const fa = i18n.language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const [reviews, setReviews] = useState<Review[]>([]);
  const [error, setError] = useState(false);
  const [catalogue, setCatalogue] = useState<Awaited<ReturnType<typeof api.listSupplementCatalogue>>>([]);
  const [supplementId, setSupplementId] = useState("");
  const [selectedPlan, setSelectedPlan] = useState<WeeklyPlan | null>(null);
  const [notes, setNotes] = useState("");
  const [tests, setTests] = useState("CBC");
  const load = () => api.listPhysicianReviews().then(setReviews).catch(() => setError(true));
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void api.listSupplementCatalogue().then(setCatalogue); }, []);
  return <main className="nutrition-estimate-page" dir={fa ? "rtl" : "ltr"}>
    <section className="nutrition-estimate-hero"><h1>{l("صف بررسی برنامه‌های تغذیه", "Nutrition review queue")}</h1><p>{l("تأیید فقط برای نسخه دقیق نمایش‌داده‌شده ثبت می‌شود.", "Approval applies only to the exact displayed revision.")}</p></section>
    {error && <p role="alert">{l("دسترسی پزشک لازم است.", "Physician access required.")}</p>}
    <section className="nutrition-target-grid">{reviews.map((review) => <article className="nutrition-target-card" key={review.review_id}><strong>{review.status}</strong><small>{review.plan_id}</small>{review.overdue && <span>{l("گذشته از موعد", "Overdue")}</span>}<button onClick={() => void api.getPhysicianPlan(review.plan_id).then(setSelectedPlan)}>{l("مشاهده نسخه", "View exact revision")}</button><button className="primary-button" onClick={() => void api.claimPhysicianReview(review.review_id).then(load)}>{l("شروع بررسی", "Start review")}</button></article>)}</section>
    {selectedPlan && <section className="nutrition-estimate-notes"><h2>{l("نسخه در حال بررسی", "Revision under review")} {selectedPlan.revision}</h2><p>{l("هزینه هفتگی", "Weekly cost")}: {selectedPlan.weekly_cost_irr.toLocaleString()} IRR · {selectedPlan.days.length} {l("روز", "days")}</p><div className="physician-plan-days">{selectedPlan.days.map((day) => <article key={day.plan_date}><strong>{day.plan_date}</strong>{day.meals.map((meal) => <p key={meal.id}>{meal.foods.map((food) => `${fa ? food.name_fa : food.name_en} ${food.grams}g`).join(" + ")}</p>)}</article>)}</div><label>{l("یادداشت قابل مشاهده برای کاربر", "User-visible note")}<textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></label><div className="weekly-plan__meal-actions"><button onClick={() => void api.actOnPhysicianPlan(selectedPlan.id, "approve", notes || null).then(setSelectedPlan)}>{l("تأیید این نسخه", "Approve this revision")}</button><button onClick={() => void api.actOnPhysicianPlan(selectedPlan.id, "request_changes", notes || null).then(setSelectedPlan)}>{l("درخواست تغییر", "Request changes")}</button><button onClick={() => void api.actOnPhysicianPlan(selectedPlan.id, "reject", notes || null).then(setSelectedPlan)}>{l("رد", "Reject")}</button></div><label>{l("آزمایش‌های درخواستی", "Requested tests")}<input value={tests} onChange={(event) => setTests(event.target.value)} /></label><button onClick={() => void api.requestPhysicianLabs(selectedPlan.id, tests.split(",").map((item) => item.trim()).filter(Boolean), notes || l("برای بررسی ایمن‌تر برنامه", "For a safer plan review"))}>{l("درخواست آزمایش", "Request labs")}</button><hr /><select value={supplementId} onChange={(event) => setSupplementId(event.target.value)}><option value="">{l("انتخاب مکمل", "Select supplement")}</option>{catalogue.map((item) => <option value={item.id} key={item.id}>{fa ? item.name_fa : item.name_en}</option>)}</select><button disabled={!supplementId} onClick={() => void api.createPhysicianSupplementOrder(selectedPlan.id, supplementId)}>{l("ثبت دستور مکمل", "Prescribe supplement")}</button></section>}
  </main>;
}
