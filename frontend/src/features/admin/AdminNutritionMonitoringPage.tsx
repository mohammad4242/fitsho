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
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState("");
  useEffect(() => { void api.getNutritionMonitoring().then(setData).catch(() => setFailed(true)); }, []);
  async function refreshPrices() {
    setRefreshing(true);
    setRefreshMessage("");
    try {
      await api.triggerNutritionPriceRefresh();
      setRefreshMessage(l("اجرای دستی ثبت شد.", "Manual refresh was recorded."));
    } catch {
      setRefreshMessage(l("اجرای دستی ناموفق بود.", "Manual refresh failed."));
    } finally {
      setRefreshing(false);
    }
  }
  return <main className="nutrition-estimate-page" dir={fa ? "rtl" : "ltr"}>
    <section className="nutrition-estimate-hero"><Link to="/dashboard">{l("بازگشت", "Back")}</Link><h1>{l("پایش تغذیه", "Nutrition monitoring")}</h1><p>{l("تمرکز این صفحه روی استثناها، سلامت کاتالوگ و اجرای قیمت‌گذاری است.", "This workspace focuses on exceptions, catalogue health, and pricing runs.")}</p><button type="button" disabled={refreshing} onClick={() => void refreshPrices()}>{refreshing ? l("در حال اجرا…", "Running…") : l("به‌روزرسانی دستی قیمت‌ها", "Refresh prices manually")}</button>{refreshMessage && <p role="status">{refreshMessage}</p>}</section>
    {failed && <p className="nutrition-estimate-state" role="alert">{l("داده‌های پایش دریافت نشد.", "Monitoring data could not be loaded.")}</p>}
    {data === null && !failed ? <p className="nutrition-estimate-state" role="status">{l("در حال دریافت…", "Loading…")}</p> : data && <>
      <section className="nutrition-target-grid" aria-label={l("شاخص‌ها", "Metrics")}>
        {Object.entries(data.counts).map(([key, value]) => <article className="nutrition-target-card" key={key}><span>{metricLabel(key, fa)}</span><strong>{new Intl.NumberFormat(fa ? "fa-IR" : "en-US").format(value)}</strong></article>)}
      </section>
      {data.coverage_warning && <p className="nutrition-estimate-state" role="alert">{l("پوشش قیمت کافی نیست؛ قیمت زنده ساخته یا حدس زده نمی‌شود.", "Price coverage is insufficient; no live price is fabricated or guessed.")}</p>}
      <section className="nutrition-estimate-notes"><h2>{l("سلامت منابع", "Provider health")}</h2><div className="nutrition-admin-runs">{data.provider_health.map((provider) => <article key={provider.code}><strong>{provider.code}</strong><span>{provider.enabled ? l("فعال", "Enabled") : l("غیرفعال", "Disabled")}</span><small>{provider.last_error ?? l("بدون خطای ثبت‌شده", "No recorded error")} · {provider.parser_version ?? "—"}</small></article>)}</div></section>
      <section className="nutrition-estimate-notes"><h2>{l("استثناهای قیمت", "Price exceptions")}</h2>{data.price_reviews.length === 0 ? <p>{l("استثنایی ثبت نشده است.", "No exception is recorded.")}</p> : <div className="nutrition-admin-runs">{data.price_reviews.map((review) => <article key={review.id} className="nutrition-price-review"><strong>{review.food_slug}</strong><small>{review.reason_codes.join(" · ")}</small><p role="alert">{l("اطمینان کافی برای به‌روزرسانی خودکار قیمت وجود ندارد. منابع را بررسی کنید و در صورت نیاز قیمت را به‌صورت دستی اصلاح کنید.", "There is not enough confidence to update this price automatically. Review the sources and apply a manual price override if needed.")}</p>{review.candidate_reference_price_toman && <span>{l("قیمت پیشنهادی", "Candidate reference")}: {formatToman(review.candidate_reference_price_toman, fa)} {l("تومان", "Toman")}</span>}{review.quotes.length > 0 && <div className="nutrition-admin-runs">{review.quotes.map((quote) => <div key={quote.id} className="nutrition-price-quote">{quote.source_url ? <a href={quote.source_url} target="_blank" rel="noopener noreferrer">{quote.source_name} · {quote.source_domain}</a> : <span>{quote.source_name} · {quote.source_domain}</span>}<strong>{quote.product_title}</strong><span>{l("قیمت عادی", "Normal")}: {formatToman(quote.normal_price_toman, fa)} {l("تومان", "Toman")}</span>{quote.promotional_price_toman && <span>{l("قیمت تخفیفی", "Promotion")}: {formatToman(quote.promotional_price_toman, fa)} {l("تومان", "Toman")}</span>}<small>{l("بسته", "Package")}: {quote.package_quantity} {quote.package_unit}</small></div>)}</div>}</article>)}</div>}</section>
      {data.broken_mappings.length > 0 && <section className="nutrition-estimate-notes"><h2>{l("نگاشت‌های خراب", "Broken mappings")}</h2><div className="nutrition-admin-runs">{data.broken_mappings.map((mapping) => <article key={mapping.id}><strong>{mapping.food_slug}</strong><small>{mapping.provider_code} · {mapping.provider_product_id}</small></article>)}</div></section>}
      <section className="nutrition-estimate-notes"><h2>{l("اجرای قیمت‌های اخیر", "Recent price runs")}</h2>{data.recent_price_runs.length === 0 ? <p>{l("هنوز اجرایی ثبت نشده است.", "No run has been recorded yet.")}</p> : <div className="nutrition-admin-runs">{data.recent_price_runs.map((run) => <article key={run.id}><strong>{run.status}</strong><span>{new Intl.DateTimeFormat(fa ? "fa-IR" : "en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(run.started_at))}</span><small>{l("به‌روز", "Updated")}: {run.foods_updated} · {l("نیازمند بررسی", "Review")}: {run.foods_needing_review} · {l("خطای منبع", "Provider failures")}: {run.provider_failures}</small></article>)}</div>}</section>
    </>}
  </main>;
}

function metricLabel(key: string, fa: boolean) {
  const labels: Record<string, [string, string]> = { foods: ["مواد غذایی", "Foods"], meals: ["وعده‌های آماده", "Meals"], accepted_price_references: ["قیمت معتبر", "Accepted prices"], price_reviews: ["استثنای قیمت", "Price exceptions"], supplements: ["مکمل‌ها", "Supplements"] };
  return labels[key]?.[fa ? 0 : 1] ?? key;
}

function formatToman(value: string | null, fa: boolean): string {
  if (value === null) return "—";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return value;
  return new Intl.NumberFormat(fa ? "fa-IR" : "en-US").format(amount);
}
