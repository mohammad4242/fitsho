import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import * as api from "./api";
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
  const load = () => api.listPhysicianReviews().then(setReviews).catch(() => setError(true));
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void api.listSupplementCatalogue().then(setCatalogue); }, []);
  return <main className="nutrition-estimate-page" dir={fa ? "rtl" : "ltr"}>
    <section className="nutrition-estimate-hero"><h1>{l("صف بررسی برنامه‌های تغذیه", "Nutrition review queue")}</h1><p>{l("تأیید فقط برای نسخه دقیق نمایش‌داده‌شده ثبت می‌شود.", "Approval applies only to the exact displayed revision.")}</p></section>
    {error && <p role="alert">{l("دسترسی پزشک لازم است.", "Physician access required.")}</p>}
    <section className="nutrition-target-grid">{reviews.map((review) => <article className="nutrition-target-card" key={review.review_id}><strong>{review.status}</strong><small>{review.plan_id}</small>{review.overdue && <span>{l("گذشته از موعد", "Overdue")}</span>}<button className="primary-button" onClick={() => void api.claimPhysicianReview(review.review_id).then(load)}>{l("شروع بررسی", "Start review")}</button><select value={supplementId} onChange={(event) => setSupplementId(event.target.value)}><option value="">{l("انتخاب مکمل", "Select supplement")}</option>{catalogue.map((item) => <option value={item.id} key={item.id}>{fa ? item.name_fa : item.name_en}</option>)}</select><button disabled={!supplementId} onClick={() => void api.createPhysicianSupplementOrder(review.plan_id, supplementId)}>{l("ثبت دستور مکمل", "Prescribe supplement")}</button></article>)}</section>
  </main>;
}
