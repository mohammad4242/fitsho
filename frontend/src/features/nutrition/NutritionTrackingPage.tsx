import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import * as api from "./api";
import type { FoodPhotoEstimate, FoodPhotoEstimateItem } from "./api";
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
  const [searchParams] = useSearchParams();
  const freeMealId = searchParams.get("freeMealId");
  const entryDate = searchParams.get("entryDate") ?? today;
  const returnPath = searchParams.get("return") ?? "/nutrition-estimate";
  const [summary, setSummary] = useState<DailyTrackingSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [calories, setCalories] = useState("");
  const [photoConsent, setPhotoConsent] = useState(false);
  const [photoEstimate, setPhotoEstimate] = useState<FoodPhotoEstimate | null>(null);
  const [adherence, setAdherence] = useState<NutritionAdherence | null>(null);
  const [rangeStart, setRangeStart] = useState(weekAgo);
  const [foods, setFoods] = useState<api.CatalogueFood[]>([]);
  const [foodId, setFoodId] = useState("");
  const [grams, setGrams] = useState("100");
  const [loading, setLoading] = useState(true);
  const [sourceFilter, setSourceFilter] = useState("all");
  const [recentFoods, setRecentFoods] = useState<Awaited<ReturnType<typeof api.listRecentFoods>>>([]);
  const [history, setHistory] = useState<DailyTrackingSummary[]>([]);
  const [photoOpen, setPhotoOpen] = useState(freeMealId !== null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [adherenceOpen, setAdherenceOpen] = useState(false);
  const [itemFoodSelections, setItemFoodSelections] = useState<Record<string, string>>({});
  const [itemGramInputs, setItemGramInputs] = useState<Record<string, string>>({});

  const load = () => api.getDailyTracking(entryDate).then(setSummary).catch(() => setError(l("دریافت اطلاعات ممکن نشد.", "Could not load tracking."))).finally(() => setLoading(false));
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
    setPhotoEstimate(null);
    setError(null);
    setItemFoodSelections({});
    setItemGramInputs({});
    const reader = new FileReader();
    reader.addEventListener("load", () => setPhotoPreview(typeof reader.result === "string" ? reader.result : null), { once: true });
    reader.readAsDataURL(file);
    setBusy(true);
    try { setPhotoEstimate(await api.estimateFoodPhoto(file, fa ? "fa" : "en")); }
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
    try {
      if (freeMealId) {
        const macros = await api.confirmFreeMealPhotoPreview(photoEstimate.id);
        sessionStorage.setItem(`fitsho-free-meal:${freeMealId}`, JSON.stringify(macros));
        navigate(`${returnPath}?freeMealId=${freeMealId}`);
      } else {
        await api.confirmFoodPhoto(photoEstimate.id, entryDate); setPhotoEstimate(null); await load();
      }
    }
    catch { setError(l("موارد نامشخص را اول ویرایش یا حذف کن.", "Review or remove the unresolved items before confirming.")); }
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
    try {
      const updated = await api.correctFoodPhotoItem(photoEstimate.id, itemId, { remove: true });
      setPhotoEstimate(updated);
      setItemFoodSelections((prev) => { const n = { ...prev }; delete n[itemId]; return n; });
      setItemGramInputs((prev) => { const n = { ...prev }; delete n[itemId]; return n; });
    }
    catch { setError(l("حذف مورد انجام نشد.", "The item could not be removed.")); }
    finally { setBusy(false); }
  }

  async function resolvePhotoItem(itemId: string) {
    if (!photoEstimate) return;
    const selectedFoodId = itemFoodSelections[itemId];
    const gramStr = itemGramInputs[itemId];
    if (!selectedFoodId || !gramStr || Number(gramStr) <= 0) return;
    setBusy(true);
    try {
      const updated = await api.correctFoodPhotoItem(photoEstimate.id, itemId, {
        food_id: selectedFoodId,
        estimated_amount: Number(gramStr),
      });
      setPhotoEstimate(updated);
      setItemFoodSelections((prev) => { const n = { ...prev }; delete n[itemId]; return n; });
      setItemGramInputs((prev) => { const n = { ...prev }; delete n[itemId]; return n; });
    }
    catch { setError(l("اصلاح مورد ذخیره نشد.", "Item correction was not saved.")); }
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

  const isItemReady = (item: FoodPhotoEstimateItem) =>
    (Boolean(item.food_id) && item.unit === "g") ||
    ((item.calories ?? 0) > 0 ||
      (item.protein_g ?? 0) > 0 ||
      (item.carbohydrate_g ?? 0) > 0 ||
      (item.fat_g ?? 0) > 0);
  const fmt = (n: number) => Math.round(n).toLocaleString(fa ? "fa-IR" : "en-US");

  return <main className="nutrition-estimate-page nutrition-tracking-page" dir={fa ? "rtl" : "ltr"}>
    <section className="nutrition-estimate-hero nutrition-tracking-header">
      <div><p className="nutrition-eyebrow">{l("امروز", "Today")}</p><h1 className="fitsho-display">{l("ثبت تغذیه", "Nutrition tracking")}</h1></div>
    </section>
    {loading && <p role="status" className="nutrition-estimate-state">{l("در حال دریافت ثبت‌های امروز…", "Loading today's entries…")}</p>}
    <section className="nutrition-daily-panel" aria-label={l("برنامه در برابر مصرف واقعی", "Planned versus actual")}>
      <div className="nutrition-daily-panel__calories"><span>{l("کالری ثبت‌شده", "Logged calories")}</span><strong>{Math.round(summary?.actual_totals.energy_kcal ?? 0).toLocaleString(fa ? "fa-IR" : "en-US")}</strong><small><b>{l("کالری برنامه", "Planned calories")}</b> · {Math.round(todayAdherence?.planned.energy_kcal ?? 0).toLocaleString(fa ? "fa-IR" : "en-US")} kcal</small></div>
      <div className="fitsho-metric-strip">
        <span><strong>{Math.round(summary?.actual_totals.protein_g ?? 0)}g</strong><small>{l("پروتئین", "Protein")}</small></span>
        <span><strong>{summary?.entries.length ?? 0}</strong><small>{l("ثبت امروز", "Entries")}</small></span>
        <span><strong>{summary?.data_status === "sufficient" ? l("کافی", "Good") : "—"}</strong><small>{l("کیفیت داده", "Data")}</small></span>
      </div>
    </section>
    <section className="nutrition-photo-entry"><button type="button" onClick={() => setPhotoOpen((open) => !open)} aria-expanded={photoOpen}><span className="nutrition-photo-entry__icon" aria-hidden="true">⌾</span><span><strong>{l("عکس وعده", "Food photo")}</strong><small>{l("تخمین از روی عکس غذا", "Estimate from a meal photo")}</small></span><b aria-hidden="true">+</b></button></section>
    {photoOpen && <section className="nutrition-photo-panel">
      <header><div><p className="eyebrow eyebrow--accent">{l("تخمین تصویری", "Photo estimate")}</p><h2>{l("عکس وعده", "Meal photo")}</h2></div></header>
      <div className="nutrition-photo-stage">
        {photoPreview ? <img alt={l("پیش‌نمایش عکس وعده", "Meal photo preview")} src={photoPreview} /> : <div><span aria-hidden="true">⌾</span><strong>{l("عکس غذا را انتخاب کن", "Choose a meal photo")}</strong></div>}
        {busy && <span className="nutrition-photo-stage__busy" role="status">{l("در حال تحلیل…", "Analyzing…")}</span>}
      </div>
      <p className="nutrition-photo-disclosure">{l(
        "عکس فقط برای شناسایی تقریبی غذا از طریق سرویس هوش مصنوعی تنظیم‌شده پردازش می‌شود؛ اطلاعات حساب یا پزشکی همراه آن ارسال نمی‌شود.",
        "The image is sent only for approximate food recognition through the configured AI service. Account and medical information are not included."
      )}</p>
      <label className="nutrition-photo-consent"><input type="checkbox" checked={photoConsent} onChange={(event) => setPhotoConsent(event.target.checked)} /> {l("با پردازش عکس توسط سرویس ثالث موافقم", "I consent to third-party image processing")}</label>
      <label className={`nutrition-photo-picker${photoConsent ? " is-enabled" : ""}`}><span>{photoPreview ? l("تغییر عکس", "Change photo") : l("انتخاب عکس", "Choose photo")}</span><input aria-label={l("انتخاب عکس غذا", "Choose food photo")} type="file" accept="image/jpeg,image/png,image/webp" disabled={!photoConsent || busy} onChange={(event) => void analyzePhoto(event.target.files?.[0])} /></label>
      {photoEstimate && (() => {
        const macroTotals = photoEstimate.macro_totals ?? { calories: 0, protein_g: 0, carbohydrate_g: 0, fat_g: 0 };
        return <>
        <div className="nutrition-photo-summary">
          <div className="nutrition-photo-calories">
            <span className="nutrition-photo-calories__label">{l("کالری تخمینی", "Estimated calories")}</span>
            <strong className="nutrition-photo-calories__value">≈ {fmt(macroTotals.calories)} kcal</strong>
            <span className="nutrition-photo-summary-note">
              {l("تخمینی", "Estimated")}
            </span>
          </div>
          <div className="nutrition-photo-macros" role="list" aria-label={l("درشت‌مغذی‌ها", "Macronutrients")}>
            <div className="nutrition-photo-macro" role="listitem">
              <span>{l("پروتئین", "Protein")}</span>
              <strong>≈ {fmt(macroTotals.protein_g)} g</strong>
            </div>
            <div className="nutrition-photo-macro" role="listitem">
              <span>{l("کربوهیدرات", "Carbs")}</span>
              <strong>≈ {fmt(macroTotals.carbohydrate_g)} g</strong>
            </div>
            <div className="nutrition-photo-macro" role="listitem">
              <span>{l("چربی", "Fat")}</span>
              <strong>≈ {fmt(macroTotals.fat_g)} g</strong>
            </div>
          </div>
          {!photoEstimate.macro_totals_complete && (
            <p className="nutrition-photo-partial-note" role="alert">
              {l(
                "برآورد فعلاً ناقص است؛ موارد نیازمند بررسی را در جزئیات اصلاح کن.",
                "Partial estimate — review the items below to complete the result."
              )}
            </p>
          )}
        </div>

        <details className="nutrition-photo-details">
          <summary className="nutrition-photo-details__summary">
            <span>{l("جزئیات تشخیص", "Detection details")} · {photoEstimate.items.length} {l("مورد", "items")}</span>
            <i className="nutrition-photo-details__chevron" aria-hidden="true" />
          </summary>
          <ul className="nutrition-photo-details__list">
            {photoEstimate.items.map((item) => {
              const ready = isItemReady(item);
              const needsReview = !ready;
              const isNonGramUnit = item.unit !== "g";
              return <li key={item.item_id} className={`nutrition-photo-item${needsReview ? " nutrition-photo-item--unresolved" : ""}`}>
                <div className="nutrition-photo-item__identity">
                  <strong>{item.name_guess}</strong>
                  {needsReview
                    ? <span className="nutrition-photo-item__status nutrition-photo-item__status--review">{l("نیاز به بررسی", "Needs review")}</span>
                    : <span className="nutrition-photo-item__status nutrition-photo-item__status--ok">{item.food_id ? l("تطبیق‌یافته", "Matched") : l("تخمین هوش مصنوعی", "AI estimated")}</span>
                  }
                </div>

                {ready && (
                  <div className="nutrition-photo-item__amount">
                    <label>
                      <span className="visually-hidden">{l(`مقدار ${item.name_guess}`, `${item.name_guess} amount`)}</span>
                      <input
                        aria-label={l(`مقدار ${item.name_guess}`, `${item.name_guess} amount`)}
                        type="number"
                        min="1"
                        max="10000"
                        defaultValue={item.estimated_amount}
                        onBlur={(event) => void correctPhotoAmount(item.item_id, Number(event.target.value))}
                      />
                      <span>{l("گرم", "g")}</span>
                    </label>
                  </div>
                )}

                {needsReview && (
                  <div className="nutrition-photo-item__review">
                    {isNonGramUnit && item.unit !== "unknown" && (
                      <p className="nutrition-photo-item__ai-hint">
                        {l(`برآورد هوش مصنوعی: ${item.estimated_amount} ${item.unit}`, `AI estimate: ${item.estimated_amount} ${item.unit}`)}
                      </p>
                    )}
                    <label className="nutrition-photo-item__review-label">
                      {l("غذای فیتشو", "Fitsho food")}
                      <span className="nutrition-off-plan-control nutrition-off-plan-control--select">
                        <select
                          aria-label={l(`انتخاب غذا برای ${item.name_guess}`, `Choose food for ${item.name_guess}`)}
                          value={itemFoodSelections[item.item_id] ?? ""}
                          onChange={(e) => setItemFoodSelections((prev) => ({ ...prev, [item.item_id]: e.target.value }))}
                        >
                          <option value="">{l("انتخاب کن…", "Choose…")}</option>
                          {foods.map((food) => (
                            <option key={food.id} value={food.id}>{fa ? food.name_fa : food.name_en}</option>
                          ))}
                        </select>
                        <i aria-hidden="true" />
                      </span>
                    </label>
                    <label className="nutrition-photo-item__review-label">
                      {l("مقدار به گرم", "Amount in grams")}
                      <input
                        aria-label={l(`مقدار ${item.name_guess} به گرم`, `${item.name_guess} amount in grams`)}
                        type="number"
                        min="1"
                        max="10000"
                        value={itemGramInputs[item.item_id] ?? ""}
                        onChange={(e) => setItemGramInputs((prev) => ({ ...prev, [item.item_id]: e.target.value }))}
                        placeholder={l("گرم", "grams")}
                      />
                    </label>
                    <div className="nutrition-photo-item__actions">
                      <button
                        type="button"
                        disabled={busy || !itemFoodSelections[item.item_id] || !itemGramInputs[item.item_id] || Number(itemGramInputs[item.item_id]) <= 0}
                        onClick={() => void resolvePhotoItem(item.item_id)}
                        className="nutrition-photo-item__apply"
                      >
                        {l("اعمال", "Apply")}
                      </button>
                      <button type="button" className="nutrition-photo-item__remove" onClick={() => void removePhotoItem(item.item_id)}>
                        {l("حذف", "Remove")}
                      </button>
                    </div>
                  </div>
                )}

                {ready && (
                  <div className="nutrition-photo-item__actions">
                    <button type="button" className="nutrition-photo-item__remove" onClick={() => void removePhotoItem(item.item_id)}>
                      {l("حذف", "Remove")}
                    </button>
                  </div>
                )}
              </li>;
            })}
          </ul>
        </details>

        <div className="nutrition-photo-confirm">
          <button
            className="primary-button"
            disabled={busy || !photoEstimate.macro_totals_complete}
            onClick={() => void confirmPhoto()}
          >
            {freeMealId ? l("تأیید و بازگشت به وعده آزاد", "Confirm and return to Free Meal") : l("تأیید و ثبت", "Confirm and log")}
          </button>
          {!photoEstimate.macro_totals_complete && (
            <p className="nutrition-photo-confirm__hint">
              {l("قبل از تأیید، موارد نیازمند بررسی را اصلاح یا حذف کن.", "Review or remove the unresolved items before confirming.")}
            </p>
          )}
        </div>
      </>;
      })()}
    </section>}
    <section className="nutrition-checkin" aria-label={l("ثبت وضعیت امروز", "Today's check-in")}>
      {([ ["on_plan", "طبق برنامه", "On plan"], ["mostly_on_plan", "تقریباً طبق برنامه", "Mostly on plan"], ["off_plan", "خارج از برنامه", "Off plan"], ["not_recorded", "ثبت نمی‌کنم", "Skip"] ] as const).map(([value, persian, english]) => <button className={summary?.check_in_status === value ? "is-active" : undefined} disabled={busy} key={value} onClick={() => void checkIn(value)}>{l(persian, english)}</button>)}
    </section>
    {error && <p role="alert" className="nutrition-estimate-state">{error}</p>}
    {recentFoods.length > 0 && <div className="nutrition-tracking-quick nutrition-recent-foods" aria-label={l("غذاهای اخیر", "Recent foods")}>{recentFoods.map((item) => <button disabled={busy} key={item.food_id} onClick={() => void addRecentFood(item)}>{item.display_name} · {item.last_quantity_grams ?? 100} g</button>)}</div>}
    <details className="nutrition-manual-entry">
      <summary><span>{l("ثبت دستی وعده", "Log food manually")}</span><i aria-hidden="true" /></summary>
      <section className="nutrition-off-plan-card">
        <header><h2>{l("وعده خارج از برنامه", "Food outside the plan")}</h2><p>{l("غذا را دقیق از کاتالوگ ثبت کن یا فقط یک برآورد سریع وارد کن.", "Log an exact catalogue food or enter a quick estimate.")}</p></header>
        <fieldset className="nutrition-off-plan-group" aria-label={l("ثبت دقیق از کاتالوگ", "Exact catalogue entry")}>
          <legend>{l("ثبت دقیق از کاتالوگ", "Exact catalogue entry")}</legend>
          <div className="nutrition-off-plan-fields nutrition-off-plan-fields--catalogue">
            <label className="nutrition-off-plan-field nutrition-off-plan-field--food">
              <span>{l("انتخاب ماده غذایی", "Choose food")}</span>
              <span className="nutrition-off-plan-control nutrition-off-plan-control--select">
                <select aria-label={l("ماده غذایی", "Food")} value={foodId} onChange={(event) => setFoodId(event.target.value)}>{foods.map((food) => <option key={food.id} value={food.id}>{fa ? food.name_fa : food.name_en}</option>)}</select>
                <i aria-hidden="true" />
              </span>
            </label>
            <label className="nutrition-off-plan-field">
              <span>{l("مقدار", "Amount")}</span>
              <span className="nutrition-off-plan-control">
                <input aria-label={l("مقدار به گرم", "Amount in grams")} min="1" max="5000" type="number" value={grams} onChange={(event) => setGrams(event.target.value)} />
                <b>{l("گرم", "g")}</b>
              </span>
            </label>
            <button className="nutrition-catalogue-submit" disabled={busy || !foodId} onClick={() => void addCatalogueFood()} type="button">{l("ثبت از کاتالوگ", "Add catalogue food")}</button>
          </div>
        </fieldset>
        <fieldset className="nutrition-off-plan-group nutrition-off-plan-group--estimate" aria-label={l("ثبت تقریبی سریع", "Quick estimate")}>
          <legend>{l("ثبت تقریبی سریع", "Quick estimate")}</legend>
          <div className="nutrition-off-plan-fields nutrition-off-plan-fields--estimate">
            <label className="nutrition-off-plan-field">
              <span>{l("کالری تقریبی", "Approximate calories")}</span>
              <span className="nutrition-off-plan-control">
                <input aria-label={l("کالری تقریبی", "Approximate calories")} inputMode="numeric" value={calories} onChange={(event) => setCalories(event.target.value)} />
                <b>{l("کیلوکالری", "kcal")}</b>
              </span>
            </label>
            <button className="primary-button nutrition-off-plan-primary" disabled={busy} onClick={() => void addApproximation()} type="button">{l("ثبت تقریبی", "Add estimate")}</button>
          </div>
        </fieldset>
      </section>
    </details>
    {summary && summary.entries.length > 0 && <section className="nutrition-estimate-notes"><h2>{l("ثبت‌های امروز", "Today's entries")}</h2><label>{l("نوع ثبت", "Entry source")} <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)}><option value="all">{l("همه", "All")}</option><option value="catalogue_manual">{l("دقیق از کاتالوگ", "Exact catalogue")}</option><option value="quick_approximation">{l("تقریبی", "Approximate")}</option><option value="photo_estimated_confirmed">{l("عکس تأییدشده", "Confirmed photo")}</option><option value="planned_confirmed">{l("طبق برنامه", "Planned")}</option><option value="planned_adjusted">{l("برنامه اصلاح‌شده", "Adjusted plan")}</option></select></label><ul>{visibleEntries.map((entry) => <li key={entry.id}><span>{entry.display_name} · {entry.confidence} · {entry.source}</span>{entry.quantity_grams && !entry.planned_meal_id ? <input aria-label={l(`ویرایش مقدار ${entry.display_name}`, `Edit ${entry.display_name} amount`)} type="number" min="1" defaultValue={entry.quantity_grams} onBlur={(event) => void editEntry(entry, Number(event.target.value))} /> : null}{entry.planned_meal_id && <><button disabled={busy} onClick={() => void adjustPlanned(entry, "adjusted")}>{l("نصف مقدار", "Half portion")}</button><button disabled={busy} onClick={() => void adjustPlanned(entry, "skipped")}>{l("نخوردم", "Skipped")}</button></>}<button disabled={busy} onClick={() => void api.deleteTrackingEntry(entry.id).then(load)}>{l("حذف", "Delete")}</button></li>)}</ul></section>}
    <section className={`nutrition-adherence-card${adherenceOpen ? " is-open" : ""}`}>
      <header className="nutrition-adherence-header">
        <h2><button aria-controls="nutrition-adherence-content" aria-expanded={adherenceOpen} onClick={() => setAdherenceOpen((open) => !open)} type="button"><span>{l("روند پایبندی", "Adherence trend")}</span><i aria-hidden="true" /></button></h2>
        <label className="nutrition-adherence-date"><span>{l("از تاریخ", "From")}</span><input type="date" value={rangeStart} max={today} onChange={(event) => setRangeStart(event.target.value)} /></label>
      </header>
      <div aria-hidden={!adherenceOpen} className="nutrition-adherence-content" id="nutrition-adherence-content" inert={!adherenceOpen}>
        <div className="nutrition-adherence-content__inner">
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
          <details className="nutrition-adherence-history"><summary>{l("تاریخچه ثبت‌ها", "Entry history")}</summary>{history.length === 0 ? <p>{l("در این بازه ثبتی وجود ندارد.", "There are no entries in this range.")}</p> : history.map((day) => <article key={day.entry_date}><strong>{day.entry_date}</strong><span>{day.entries.length} {l("مورد", "entries")}</span></article>)}</details>
        </div>
      </div>
    </section>
  </main>;
}
