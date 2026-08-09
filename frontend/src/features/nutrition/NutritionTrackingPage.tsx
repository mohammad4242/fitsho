import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import * as api from "./api";
import type { DailyTrackingSummary } from "./types";
import type { NutritionAdherence } from "./types";
import "./nutritionEstimate.css";

const today = new Date().toISOString().slice(0, 10);
const weekAgo = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10);

export function NutritionTrackingPage() {
  const { i18n } = useTranslation();
  const fa = i18n.language === "fa";
  const l = (persian: string, english: string) => (fa ? persian : english);
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DailyTrackingSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [calories, setCalories] = useState("");
  const [photoConsent, setPhotoConsent] = useState(false);
  const [photoEstimate, setPhotoEstimate] = useState<Awaited<ReturnType<typeof api.estimateFoodPhoto>> | null>(null);
  const [adherence, setAdherence] = useState<NutritionAdherence | null>(null);
  const [rangeStart, setRangeStart] = useState(weekAgo);
  const [foods, setFoods] = useState<api.CatalogueFood[]>([]);
  const [foodId, setFoodId] = useState("");
  const [grams, setGrams] = useState("100");
  const [loading, setLoading] = useState(true);
  const [sourceFilter, setSourceFilter] = useState("all");
  const [recentFoods, setRecentFoods] = useState<Awaited<ReturnType<typeof api.listRecentFoods>>>([]);
  const [history, setHistory] = useState<DailyTrackingSummary[]>([]);

  const load = () => api.getDailyTracking(today).then(setSummary).catch(() => setError(l("دریافت اطلاعات ممکن نشد.", "Could not load tracking."))).finally(() => setLoading(false));
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void api.getNutritionAdherence(rangeStart, today).then(setAdherence); }, [rangeStart]);
  useEffect(() => { void api.listCatalogueFoods().then((items) => { setFoods(items); setFoodId(items[0]?.id ?? ""); }); }, []);
  useEffect(() => { void api.listRecentFoods().then(setRecentFoods); }, []);
  useEffect(() => { void api.getTrackingHistory(rangeStart, today).then(setHistory); }, [rangeStart]);

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

  async function analyzePhoto(file: File | undefined) {
    if (!file || !photoConsent) return;
    setBusy(true); setError(null);
    try { setPhotoEstimate(await api.estimateFoodPhoto(file)); }
    catch { setError(l("برآورد عکس فعلاً در دسترس نیست؛ ثبت دستی همچنان کار می‌کند.", "Photo estimation is unavailable; manual tracking still works.")); }
    finally { setBusy(false); }
  }

  async function addCatalogueFood() {
    if (!foodId || Number(grams) <= 0) return;
    setBusy(true);
    try { await api.addCatalogueFoodEntry({ entry_date: today, food_id: foodId, grams: Number(grams), note: null }); await load(); }
    finally { setBusy(false); }
  }

  async function addRecentFood(item: Awaited<ReturnType<typeof api.listRecentFoods>>[number]) {
    setBusy(true);
    try {
      await api.addCatalogueFoodEntry({ entry_date: today, food_id: item.food_id, grams: item.last_quantity_grams ?? 100, note: null });
      await load();
    } finally { setBusy(false); }
  }

  async function confirmPhoto() {
    if (!photoEstimate) return;
    setBusy(true);
    try { await api.confirmFoodPhoto(photoEstimate.id, today); setPhotoEstimate(null); await load(); }
    catch { setError(l("موارد نامشخص را اول ویرایش کن.", "Resolve uncertain items before confirming.")); }
    finally { setBusy(false); }
  }

  async function correctPhotoAmount(itemId: string, amount: number) {
    if (!photoEstimate || amount <= 0) return;
    setBusy(true);
    try { setPhotoEstimate(await api.correctFoodPhotoItem(photoEstimate.id, itemId, { estimated_amount: amount })); }
    catch { setError(l("اصلاح عکس ذخیره نشد.", "Photo correction was not saved.")); }
    finally { setBusy(false); }
  }

  async function removePhotoItem(itemId: string) {
    if (!photoEstimate) return;
    setBusy(true);
    try { setPhotoEstimate(await api.correctFoodPhotoItem(photoEstimate.id, itemId, { remove: true })); }
    catch { setError(l("حذف مورد انجام نشد.", "The item could not be removed.")); }
    finally { setBusy(false); }
  }

  async function editEntry(entry: DailyTrackingSummary["entries"][number], nextGrams: number) {
    if (nextGrams <= 0) return;
    setBusy(true);
    try { await api.editTrackingEntry(entry.id, { grams: nextGrams }); await load(); }
    catch { setError(l("ویرایش ثبت نشد.", "The edit was not saved.")); }
    finally { setBusy(false); }
  }

  async function adjustPlanned(entry: DailyTrackingSummary["entries"][number], status: "adjusted" | "skipped") {
    if (!entry.planned_meal_id) return;
    setBusy(true);
    try { setSummary(await api.adjustPlannedMeal(entry.planned_meal_id, { entry_date: today, status, portion_ratio: status === "adjusted" ? 0.5 : null })); }
    catch { setError(l("وضعیت وعده تغییر نکرد.", "The planned meal was not changed.")); }
    finally { setBusy(false); }
  }

  const todayAdherence = adherence?.days.find((day) => day.date === today);
  const visibleEntries = summary?.entries.filter((entry) => sourceFilter === "all" || entry.source === sourceFilter) ?? [];

  return <main className="nutrition-estimate-page" dir={fa ? "rtl" : "ltr"}>
    <section className="nutrition-estimate-hero">
      <button className="secondary-button" type="button" onClick={() => navigate(-1)}>{l("بازگشت", "Back")}</button>
      <p className="nutrition-eyebrow">{l("ثبت ساده، بدون وسواس", "Simple, not obsessive")}</p>
      <h1 className="fitsho-display">{l("امروز چطور پیش رفت؟", "How did today go?")}</h1>
      <p>{l("فقط نزدیک‌ترین گزینه را بزن؛ لازم نیست هر لقمه را ثبت کنی.", "Choose the closest option. You do not need to log every bite.")}</p>
    </section>
    {loading && <p role="status" className="nutrition-estimate-state">{l("در حال دریافت ثبت‌های امروز…", "Loading today's entries…")}</p>}
    <section className="nutrition-target-grid" aria-label={l("ثبت وضعیت امروز", "Today's check-in")}>
      {([
        ["on_plan", "طبق برنامه بودم", "I followed the plan"],
        ["mostly_on_plan", "تقریباً طبق برنامه بودم", "Mostly on plan"],
        ["off_plan", "امروز برنامه را رعایت نکردم", "Off plan today"],
        ["not_recorded", "امروز ثبت نمی‌کنم", "Not recording today"],
      ] as const).map(([value, persian, english]) =>
        <button className="nutrition-target-card" disabled={busy} key={value} onClick={() => void checkIn(value)}>{l(persian, english)}</button>
      )}
    </section>
    {error && <p role="alert" className="nutrition-estimate-state">{error}</p>}
    <section className="nutrition-estimate-notes">
      <h2>{l("یک وعده خارج از برنامه", "Food outside the plan")}</h2>
      <p>{l("از کاتالوگ معتبر انتخاب کن؛ اگر جزئیات یادت نیست ثبت تقریبی هم در دسترس است.", "Choose from the verified catalogue, or use an approximation when details are unclear.")}</p>
      {recentFoods.length > 0 && <div className="nutrition-tracking-quick" aria-label={l("غذاهای اخیر", "Recent foods")}>{recentFoods.map((item) => <button disabled={busy} key={item.food_id} onClick={() => void addRecentFood(item)}>{item.display_name} · {item.last_quantity_grams ?? 100} g</button>)}</div>}
      <div className="nutrition-tracking-quick"><select aria-label={l("ماده غذایی", "Food")} value={foodId} onChange={(event) => setFoodId(event.target.value)}>{foods.map((food) => <option key={food.id} value={food.id}>{fa ? food.name_fa : food.name_en}</option>)}</select><input aria-label={l("مقدار به گرم", "Amount in grams")} min="1" max="5000" type="number" value={grams} onChange={(event) => setGrams(event.target.value)} /><button disabled={busy || !foodId} onClick={() => void addCatalogueFood()}>{l("ثبت از کاتالوگ", "Add catalogue food")}</button></div>
      <div className="nutrition-tracking-quick">
        <input aria-label={l("کالری تقریبی", "Approximate calories")} inputMode="numeric" value={calories} onChange={(event) => setCalories(event.target.value)} />
        <button className="primary-button" disabled={busy} onClick={() => void addApproximation()}>{l("ثبت تقریبی", "Add estimate")}</button>
      </div>
    </section>
    <section className="nutrition-estimate-notes">
      <h2>{l("برآورد از عکس غذا", "Estimate from a food photo")}</h2>
      <p>{l("عکس برای شناسایی تقریبی غذا به OpenRouter فرستاده می‌شود؛ اطلاعات حساب یا پزشکی ارسال نمی‌شود.", "The image is sent to OpenRouter only for approximate food identification; account and medical data are not sent.")}</p>
      <label><input type="checkbox" checked={photoConsent} onChange={(event) => setPhotoConsent(event.target.checked)} /> {l("با پردازش عکس توسط سرویس ثالث موافقم", "I consent to third-party image processing")}</label>
      <input aria-label={l("انتخاب عکس غذا", "Choose food photo")} type="file" accept="image/jpeg,image/png,image/webp" disabled={!photoConsent || busy} onChange={(event) => void analyzePhoto(event.target.files?.[0])} />
      {photoEstimate && <div>
        <p>{l("این نتیجه تقریبی است و فقط بعد از تأیید تو ثبت می‌شود.", "This is approximate and is saved only after your confirmation.")}</p>
        <ul>{photoEstimate.items.map((item) => <li key={item.item_id}><span>{item.name_guess} ({item.mapping_status})</span><input aria-label={l(`مقدار ${item.name_guess}`, `${item.name_guess} amount`)} type="number" min="1" max="10000" defaultValue={item.estimated_amount} onBlur={(event) => void correctPhotoAmount(item.item_id, Number(event.target.value))} /> {item.unit}<button type="button" onClick={() => void removePhotoItem(item.item_id)}>{l("حذف", "Remove")}</button></li>)}</ul>
        <button className="primary-button" disabled={busy} onClick={() => void confirmPhoto()}>{l("تأیید و ثبت", "Confirm and log")}</button>
      </div>}
    </section>
    <section className="nutrition-estimate-summary" aria-label={l("برنامه در برابر مصرف واقعی", "Planned versus actual")}>
      <article className="nutrition-calorie-card"><span>{l("کالری ثبت‌شده", "Logged calories")}</span><strong>{Math.round(summary?.actual_totals.energy_kcal ?? 0)}</strong></article>
      <article className="nutrition-calorie-card"><span>{l("کالری برنامه", "Planned calories")}</span><strong>{Math.round(todayAdherence?.planned.energy_kcal ?? 0)}</strong></article>
      <article className="nutrition-calorie-card"><span>{l("پروتئین واقعی / برنامه", "Actual / planned protein")}</span><strong>{Math.round(summary?.actual_totals.protein_g ?? 0)} / {Math.round(todayAdherence?.planned.protein_g ?? 0)} g</strong></article>
      <div className="nutrition-confidence-card"><span>{summary?.data_status === "sufficient" ? l("داده کافی", "Sufficient data") : l("داده ناکافی", "Insufficient data")}</span><strong>{summary?.entries.length ?? 0} {l("مورد", "entries")}</strong></div>
    </section>
    {summary && summary.entries.length > 0 && <section className="nutrition-estimate-notes"><h2>{l("ثبت‌های امروز", "Today's entries")}</h2><label>{l("نوع ثبت", "Entry source")} <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)}><option value="all">{l("همه", "All")}</option><option value="catalogue_manual">{l("دقیق از کاتالوگ", "Exact catalogue")}</option><option value="quick_approximation">{l("تقریبی", "Approximate")}</option><option value="photo_estimated_confirmed">{l("عکس تأییدشده", "Confirmed photo")}</option><option value="planned_confirmed">{l("طبق برنامه", "Planned")}</option><option value="planned_adjusted">{l("برنامه اصلاح‌شده", "Adjusted plan")}</option></select></label><ul>{visibleEntries.map((entry) => <li key={entry.id}><span>{entry.display_name} · {entry.confidence} · {entry.source}</span>{entry.quantity_grams && !entry.planned_meal_id ? <input aria-label={l(`ویرایش مقدار ${entry.display_name}`, `Edit ${entry.display_name} amount`)} type="number" min="1" defaultValue={entry.quantity_grams} onBlur={(event) => void editEntry(entry, Number(event.target.value))} /> : null}{entry.planned_meal_id && <><button disabled={busy} onClick={() => void adjustPlanned(entry, "adjusted")}>{l("نصف مقدار", "Half portion")}</button><button disabled={busy} onClick={() => void adjustPlanned(entry, "skipped")}>{l("نخوردم", "Skipped")}</button></>}<button disabled={busy} onClick={() => void api.deleteTrackingEntry(entry.id).then(load)}>{l("حذف", "Delete")}</button></li>)}</ul></section>}
    <section className="nutrition-estimate-notes">
      <h2>{l("روند پایبندی", "Adherence trend")}</h2>
      <label>{l("از تاریخ", "From")} <input type="date" value={rangeStart} max={today} onChange={(event) => setRangeStart(event.target.value)} /></label>
      <div className="nutrition-adherence-chart" aria-label={l("نمودار کالری و پروتئین", "Calories and protein chart")}>
        {adherence?.days.map((day) => <article key={day.date}>
          <small>{day.date.slice(5)}</small>
          {day.status === "insufficient_data" ? <span>{l("داده ناکافی", "No data")}</span> : <>
            <label>{l("کالری", "Calories")} <progress max="100" value={day.calorie_adherence ?? 0} /></label>
            <label>{l("پروتئین", "Protein")} <progress max="100" value={day.protein_adherence ?? 0} /></label>
            <small>{l("کامل بودن ثبت", "Completeness")}: {Math.round(day.tracking_completeness)}٪</small>
          </>}
        </article>)}
      </div>
      {adherence?.weight_trend.length ? <p>{l("روند وزن کنار پایبندی نمایش داده می‌شود و به‌تنهایی رابطه علت و معلولی را ثابت نمی‌کند.", "Weight is shown beside adherence and does not imply causation.")}</p> : null}
      <details><summary>{l("تاریخچه ثبت‌ها", "Entry history")}</summary>{history.length === 0 ? <p>{l("در این بازه ثبتی وجود ندارد.", "There are no entries in this range.")}</p> : history.map((day) => <article key={day.entry_date}><strong>{day.entry_date}</strong><span>{day.entries.length} {l("مورد", "entries")}</span></article>)}</details>
    </section>
  </main>;
}
