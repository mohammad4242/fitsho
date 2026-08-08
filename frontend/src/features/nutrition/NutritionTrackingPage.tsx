import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import * as api from "./api";
import type { DailyTrackingSummary } from "./types";
import "./nutritionEstimate.css";

const today = new Date().toISOString().slice(0, 10);

export function NutritionTrackingPage() {
  const { i18n } = useTranslation();
  const fa = i18n.language === "fa";
  const l = (persian: string, english: string) => (fa ? persian : english);
  const [summary, setSummary] = useState<DailyTrackingSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [calories, setCalories] = useState("");

  const load = () => api.getDailyTracking(today).then(setSummary).catch(() => setError(l("دریافت اطلاعات ممکن نشد.", "Could not load tracking.")));
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function checkIn(status: DailyTrackingSummary["check_in_status"]) {
    setBusy(true); setError(null);
    try { setSummary(await api.saveDailyCheckIn(today, status)); }
    catch { setError(l("برای این گزینه باید برنامه تأییدشده و فعال داشته باشی.", "This option requires an approved active plan.")); }
    finally { setBusy(false); }
  }

  async function addApproximation() {
    const value = Number(calories);
    if (!value) return;
    setBusy(true);
    try {
      await api.addQuickApproximation({ entry_date: today, display_name: l("وعده تقریبی", "Approximate meal"), calories: value, protein_g: null });
      setCalories(""); await load();
    } finally { setBusy(false); }
  }

  return <main className="nutrition-estimate-page" dir={fa ? "rtl" : "ltr"}>
    <section className="nutrition-estimate-hero">
      <p className="nutrition-eyebrow">{l("ثبت ساده، بدون وسواس", "Simple, not obsessive")}</p>
      <h1 className="fitsho-display">{l("امروز چطور پیش رفت؟", "How did today go?")}</h1>
      <p>{l("فقط نزدیک‌ترین گزینه را بزن؛ لازم نیست هر لقمه را ثبت کنی.", "Choose the closest option. You do not need to log every bite.")}</p>
    </section>
    <section className="nutrition-target-grid" aria-label={l("ثبت وضعیت امروز", "Today's check-in")}>
      {([
        ["on_plan", "طبق برنامه بودم", "I followed the plan"],
        ["mostly_on_plan", "تقریباً طبق برنامه بودم", "Mostly on plan"],
        ["off_plan", "امروز برنامه را رعایت نکردم", "Off plan today"],
      ] as const).map(([value, persian, english]) =>
        <button className="nutrition-target-card" disabled={busy} key={value} onClick={() => void checkIn(value)}>{l(persian, english)}</button>
      )}
    </section>
    {error && <p role="alert" className="nutrition-estimate-state">{error}</p>}
    <section className="nutrition-estimate-notes">
      <h2>{l("یک وعده خارج از برنامه", "Food outside the plan")}</h2>
      <p>{l("اگر جزئیات یادت نیست، فقط کالری تقریبی وعده را وارد کن.", "If details are unclear, enter an approximate meal calorie value.")}</p>
      <div className="nutrition-tracking-quick">
        <input aria-label={l("کالری تقریبی", "Approximate calories")} inputMode="numeric" value={calories} onChange={(event) => setCalories(event.target.value)} />
        <button className="primary-button" disabled={busy} onClick={() => void addApproximation()}>{l("ثبت تقریبی", "Add estimate")}</button>
      </div>
    </section>
    <section className="nutrition-estimate-summary">
      <article className="nutrition-calorie-card"><span>{l("کالری ثبت‌شده", "Logged calories")}</span><strong>{Math.round(summary?.actual_totals.energy_kcal ?? 0)}</strong></article>
      <div className="nutrition-confidence-card"><span>{summary?.data_status === "sufficient" ? l("داده کافی", "Sufficient data") : l("داده ناکافی", "Insufficient data")}</span><strong>{summary?.entries.length ?? 0} {l("مورد", "entries")}</strong></div>
    </section>
  </main>;
}
