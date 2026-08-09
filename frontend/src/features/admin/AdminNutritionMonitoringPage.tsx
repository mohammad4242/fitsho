import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import * as api from "../nutrition/api";
import "../nutrition/nutritionEstimate.css";

export function AdminNutritionMonitoringPage() {
  const { i18n } = useTranslation();
  const fa = i18n.resolvedLanguage !== "en";
  const l = (persian: string, english: string) => fa ? persian : english;
  const [data, setData] = useState<api.NutritionMonitoring | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { void api.getNutritionMonitoring().then(setData).catch(() => setFailed(true)); }, []);
  return <main className="nutrition-estimate-page" dir={fa ? "rtl" : "ltr"}>
    <section className="nutrition-estimate-hero"><Link to="/dashboard">{l("بازگشت", "Back")}</Link><h1>{l("پایش تغذیه", "Nutrition monitoring")}</h1><p>{l("تمرکز این صفحه روی استثناها، سلامت کاتالوگ و اجرای قیمت‌گذاری است.", "This workspace focuses on exceptions, catalogue health, and pricing runs.")}</p></section>
    {failed && <p className="nutrition-estimate-state" role="alert">{l("داده‌های پایش دریافت نشد.", "Monitoring data could not be loaded.")}</p>}
    {data === null && !failed ? <p className="nutrition-estimate-state" role="status">{l("در حال دریافت…", "Loading…")}</p> : data && <>
      <section className="nutrition-target-grid" aria-label={l("شاخص‌ها", "Metrics")}>
        {Object.entries(data.counts).map(([key, value]) => <article className="nutrition-target-card" key={key}><span>{metricLabel(key, fa)}</span><strong>{new Intl.NumberFormat(fa ? "fa-IR" : "en-US").format(value)}</strong></article>)}
      </section>
      <section className="nutrition-estimate-notes"><h2>{l("اجرای قیمت‌های اخیر", "Recent price runs")}</h2>{data.recent_price_runs.length === 0 ? <p>{l("هنوز اجرایی ثبت نشده است.", "No run has been recorded yet.")}</p> : <div className="nutrition-admin-runs">{data.recent_price_runs.map((run) => <article key={run.id}><strong>{run.status}</strong><span>{new Intl.DateTimeFormat(fa ? "fa-IR" : "en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(run.started_at))}</span><small>{l("به‌روز", "Updated")}: {run.foods_updated} · {l("نیازمند بررسی", "Review")}: {run.foods_needing_review} · {l("خطای منبع", "Provider failures")}: {run.provider_failures}</small></article>)}</div>}</section>
    </>}
  </main>;
}

function metricLabel(key: string, fa: boolean) {
  const labels: Record<string, [string, string]> = { foods: ["مواد غذایی", "Foods"], meals: ["وعده‌های آماده", "Meals"], accepted_price_references: ["قیمت معتبر", "Accepted prices"], price_reviews: ["استثنای قیمت", "Price exceptions"], supplements: ["مکمل‌ها", "Supplements"] };
  return labels[key]?.[fa ? 0 : 1] ?? key;
}
