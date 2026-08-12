import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { MealThumbnail } from "../../shared/MealThumbnail";
import * as api from "./api";
import type { ShoppingList, WeeklyPlan, WeeklyPlanHistoryItem } from "./types";

type Props = {
  plan: WeeklyPlan;
  language: "fa" | "en";
};

const weekdayFa = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"];
const weekdayEn = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"];

export function WeeklyNutritionPlan({ plan, language }: Props) {
  const [selectedDay, setSelectedDay] = useState(0);
  const [currentPlan, setCurrentPlan] = useState(plan);
  const [shopping, setShopping] = useState<ShoppingList | null>(null);
  const [history, setHistory] = useState<WeeklyPlanHistoryItem[]>([]);
  const [busyMeal, setBusyMeal] = useState<string | null>(null);
  const [preview, setPreview] = useState<({ kind: "remove"; data: Awaited<ReturnType<typeof api.previewMealRemoval>> } | { kind: "meal"; data: api.PlanEditPreview; replacementMealId: string } | { kind: "food"; data: api.PlanEditPreview; foodId: string; replacementFoodId: string }) | null>(null);
  const [actionError, setActionError] = useState(false);
  useEffect(() => { setCurrentPlan(plan); }, [plan]);
  useEffect(() => {
    void Promise.all([api.getShoppingList(currentPlan.id), api.listWeeklyNutritionPlans()])
      .then(([list, revisions]) => { setShopping(list); setHistory(revisions); })
      .catch(() => setActionError(true));
  }, [currentPlan.id]);
  const l = (fa: string, en: string) => language === "en" ? en : fa;
  const number = new Intl.NumberFormat(language === "en" ? "en-US" : "fa-IR", {
    maximumFractionDigits: 1,
  });
  const day = currentPlan.days[selectedDay] ?? currentPlan.days[0];
  const statusClass = currentPlan.physician_approved ? "is-approved" : "is-pending";

  async function toggleLock(mealId: string, locked: boolean) {
    setBusyMeal(mealId); setActionError(false);
    try {
      await api.setMealLock(currentPlan.id, mealId, locked);
      setCurrentPlan({ ...currentPlan, days: currentPlan.days.map((item) => ({ ...item, meals: item.meals.map((meal) => meal.id === mealId ? { ...meal, is_locked: locked } : meal) })) });
    } catch { setActionError(true); } finally { setBusyMeal(null); }
  }

  async function beginRemoval(mealId: string) {
    setBusyMeal(mealId); setActionError(false);
    try { setPreview({ kind: "remove", data: await api.previewMealRemoval(currentPlan.id, mealId) }); }
    catch { setActionError(true); }
    finally { setBusyMeal(null); }
  }

  async function confirmRemoval() {
    if (!preview) return;
    setBusyMeal(String(preview.data.expected_plan_revision_id)); setActionError(false);
    try {
      const next = preview.kind === "remove"
        ? await api.confirmMealRemoval(currentPlan.id, preview.data.meal_id, preview.data.expected_plan_revision_id)
        : preview.kind === "meal"
          ? await api.confirmMealReplacement(currentPlan.id, preview.data.meal_id, preview.replacementMealId)
          : await api.confirmFoodReplacement(currentPlan.id, preview.data.meal_id, preview.foodId, preview.replacementFoodId);
      setCurrentPlan(next); setPreview(null); setSelectedDay(0);
    } catch { setActionError(true); }
    finally { setBusyMeal(null); }
  }

  async function beginMealReplacement(mealId: string, replacementMealId: string) {
    setBusyMeal(mealId); setActionError(false);
    try { setPreview({ kind: "meal", data: await api.previewMealReplacement(currentPlan.id, mealId, replacementMealId), replacementMealId }); }
    catch { setActionError(true); } finally { setBusyMeal(null); }
  }

  async function beginFoodReplacement(mealId: string, foodId: string, replacementFoodId: string) {
    setBusyMeal(mealId); setActionError(false);
    try { setPreview({ kind: "food", data: await api.previewFoodReplacement(currentPlan.id, mealId, foodId, replacementFoodId), foodId, replacementFoodId }); }
    catch { setActionError(true); } finally { setBusyMeal(null); }
  }

  async function regenerateDay() {
    setBusyMeal("regenerate"); setActionError(false);
    try { setCurrentPlan(await api.partialRegeneratePlan(currentPlan.id, [selectedDay])); setSelectedDay(0); }
    catch { setActionError(true); } finally { setBusyMeal(null); }
  }

  return (
    <section className="weekly-plan" aria-labelledby="weekly-plan-title">
      <div className="weekly-plan__heading">
        <div>
          <p className="eyebrow eyebrow--accent">{l("نسخه هفتگی", "Weekly draft")}</p>
          <h2 id="weekly-plan-title">{l("برنامه غذایی تو", "Your nutrition plan")}</h2>
        </div>
        <div className={`weekly-plan__review ${statusClass}`} role="status">
          <strong>
            {currentPlan.physician_approved
              ? l("تأییدشده توسط پزشک", "Physician approved")
              : l("در انتظار بررسی پزشک", "Pending physician review")}
          </strong>
          {!currentPlan.physician_approved && (
            <span>
              {l(
                "این پیش‌نویس قابل مشاهده است اما هنوز برنامه فعال پزشکی نیست.",
                "This draft is visible, but it is not yet an active approved plan.",
              )}
            </span>
          )}
          {currentPlan.physician_approved && currentPlan.physician_approved_at && (
            <span>{l("تاریخ تأیید", "Approved")} {new Intl.DateTimeFormat(language === "en" ? "en-US" : "fa-IR").format(new Date(currentPlan.physician_approved_at))}</span>
          )}
        </div>
      </div>

      <div className="weekly-plan__meta">
        <strong>{l("نسخه", "Revision")} {number.format(currentPlan.revision)}</strong>
        <span>{lifecycleLabel(currentPlan.lifecycle_status, language)}</span>
        <span>{l("قیمت‌های همین نسخه ثابت و قابل ردیابی‌اند.", "Prices are pinned to this exact revision.")}</span>
        <span>{l("وضعیت قیمت", "Price status")}: {currentPlan.price_snapshot.references ? l("قیمت معتبر ثبت‌شده", "Accepted price snapshot") : l("ناموجود", "Unavailable")}</span>
        <span>{l("چیدمان روزانه", "Daily structure")}: {String(currentPlan.input_snapshot.main_meals_per_day ?? "—")} {l("وعده اصلی", "main meals")} + {String(currentPlan.input_snapshot.snacks_per_day ?? "—")} {l("میان‌وعده", "snacks")}</span>
      </div>
      {currentPlan.physician_user_visible_notes && <aside className="weekly-plan__notice"><strong>{l("یادداشت پزشک", "Physician note")}</strong><p>{currentPlan.physician_user_visible_notes}</p></aside>}
      {currentPlan.physician_change_summary.length > 0 && <aside className="weekly-plan__notice"><strong>{l("خلاصه تغییرات پزشک", "Physician change summary")}</strong><ul>{currentPlan.physician_change_summary.map((change, index) => <li key={index}>{String(change.operation ?? change.action ?? l("تغییر برنامه", "Plan change"))}</li>)}</ul></aside>}
      {actionError && <p className="weekly-plan__error" role="alert">{l("عملیات انجام نشد؛ دوباره تلاش کن.", "The action failed. Please try again.")}</p>}

      <div className="weekly-plan__ledger" aria-label={l("بودجه برنامه", "Plan budget")}>
        <div>
          <span>{l("هزینه برآوردی هفته", "Estimated weekly cost")}</span>
          <strong>{number.format(Math.floor(currentPlan.weekly_cost_irr / 10))} {l("تومان", "Toman")}</strong>
        </div>
        <div>
          <span>{l("بودجه هفتگی", "Weekly budget")}</span>
          <strong>{number.format(Math.floor(currentPlan.weekly_budget_irr / 10))} {l("تومان", "Toman")}</strong>
        </div>
        <div>
          <span>{l("وضعیت بودجه", "Budget status")}</span>
          <strong>{budgetLabel(currentPlan.budget_status, language)}</strong>
        </div>
      </div>

      <div className="weekly-plan__days" role="tablist" aria-label={l("روزهای هفته", "Week days")}>
        {currentPlan.days.map((item, index) => (
          <button
            aria-selected={selectedDay === index}
            className={selectedDay === index ? "is-selected" : undefined}
            key={item.plan_date}
            onClick={() => setSelectedDay(index)}
            role="tab"
            type="button"
          >
            <span>{language === "en" ? weekdayEn[index] : weekdayFa[index]}</span>
            <small>{new Intl.DateTimeFormat(language === "en" ? "en-US" : "fa-IR", { day: "numeric", month: "short" }).format(new Date(`${item.plan_date}T12:00:00`))}</small>
          </button>
        ))}
      </div>

      {day && (
        <><div className="weekly-plan__daily-summary"><strong>{l("جمع روز", "Daily total")}: {number.format(day.nutrient_totals.energy_kcal ?? 0)} {l("کیلوکالری", "kcal")}</strong><span>{number.format(Math.floor(day.cost_irr / 10))} {l("تومان", "Toman")}</span><span>{l("پروتئین", "Protein")}: {number.format(day.nutrient_totals.protein_g ?? 0)} g</span><span>{l("کربوهیدرات", "Carbohydrate")}: {number.format(day.nutrient_totals.carbohydrate_g ?? 0)} g</span></div><div className="weekly-plan__day-actions"><button disabled={busyMeal === "regenerate" || day.meals.every((meal) => meal.is_locked)} type="button" onClick={() => void regenerateDay()}>{l("بازسازی وعده‌های باز این روز", "Regenerate unlocked meals for this day")}</button></div><div className="weekly-plan__meals" role="tabpanel">
          {day.meals.map((meal) => (
            meal.slot_role === "free_meal" ? <FreeMealCard key={meal.id} meal={meal} entryDate={day.plan_date} language={language} /> : <article className="weekly-plan__meal" key={meal.id}>
              <header>
                <div className="weekly-plan__meal-heading">
                  <MealThumbnail
                    alt={meal.name_fa && meal.name_en ? (language === "en" ? meal.name_en : meal.name_fa) : mealTitle(meal, language)}
                    className="weekly-plan__meal-image"
                    fallbackLabel={l(`تصویر پیش‌فرض ${mealTitle(meal, language)}`, `Placeholder for ${mealTitle(meal, language)}`)}
                    imageUrl={meal.image_url}
                  />
                  <div>
                    <span>{meal.slot_role === "snack" ? l("میان‌وعده", "Snack") : l("وعده اصلی", "Main meal")}</span>
                    <strong className="weekly-plan__meal-title">{mealTitle(meal, language)}</strong>
                    <small>{number.format(meal.nutrient_totals.energy_kcal ?? 0)} {l("کیلوکالری", "kcal")}</small>
                  </div>
                </div>
                <small>{number.format(Math.floor(meal.cost_irr / 10))} {l("تومان", "Toman")}</small>
              </header>
              <ul>
                {meal.foods.map((food) => (
                  <li key={`${meal.id}-${food.food_id}`}>
                    <span>{language === "en" ? food.name_en : food.name_fa}</span>
                    <strong>{number.format(food.grams)} {l("گرم", "g")}</strong>
                  </li>
                ))}
              </ul>
              <dl className="weekly-plan__meal-totals">
                {mealMetricEntries(meal.nutrient_totals).map(([code, value]) => <div key={code}><dt>{nutrientLabel(code, language)}</dt><dd>{number.format(value)}</dd></div>)}
              </dl>
              <div className="weekly-plan__meal-actions">
                <button disabled={busyMeal === meal.id} type="button" onClick={() => void toggleLock(meal.id, !meal.is_locked)}>{meal.is_locked ? l("بازکردن قفل", "Unlock") : l("قفل وعده", "Lock meal")}</button>
                <button type="button" onClick={() => void api.saveMealFeedback(currentPlan.id, meal.id, "liked")}>{l("پسندیدم", "Liked")}</button>
                <button type="button" onClick={() => void api.saveMealFeedback(currentPlan.id, meal.id, "disliked")}>{l("کمتر پیشنهاد بده", "Suggest less often")}</button>
                <button disabled={meal.is_locked || busyMeal === meal.id} type="button" onClick={() => void beginRemoval(meal.id)}>{l("پیش‌نمایش حذف", "Preview removal")}</button>
                {findMealAlternative(currentPlan, meal.id, meal.slot_role) && <button disabled={meal.is_locked || busyMeal === meal.id} type="button" onClick={() => void beginMealReplacement(meal.id, findMealAlternative(currentPlan, meal.id, meal.slot_role)!.id)}>{l("پیش‌نمایش تعویض وعده", "Preview meal replacement")}</button>}
                {meal.foods[0] && findFoodAlternative(currentPlan, meal.foods[0].food_id) && <button disabled={meal.is_locked || busyMeal === meal.id} type="button" onClick={() => void beginFoodReplacement(meal.id, meal.foods[0].food_id, findFoodAlternative(currentPlan, meal.foods[0].food_id)!.food_id)}>{l("پیش‌نمایش تعویض ماده", "Preview food replacement")}</button>}
              </div>
            </article>
          ))}
        </div></>
      )}

      <div className="weekly-plan__nutrients">
        <h3>{l("هدف در برابر مقدار برنامه", "Target versus planned")}</h3>
        <div>
          {Object.values(currentPlan.nutrients).map((nutrient) => (
            <article key={nutrient.nutrient_code}>
              <span>{nutrientLabel(nutrient.nutrient_code, language)}</span>
              <strong>{number.format(nutrient.planned)} {nutrient.unit}</strong>
              <small data-status={nutrient.status}>{statusLabel(nutrient.status, language)}</small>
              <small>{l("مرجع", "Reference")}: {nutrient.reference_kind ?? l("هدف روزانه", "Daily target")} · {l("اطمینان", "Confidence")}: {nutrient.data_confidence}</small>
              {nutrient.difference_from_preferred !== null && <small>{l("فاصله از مقدار ایده‌آل", "Difference from ideal")}: {number.format(nutrient.difference_from_preferred)}</small>}
            </article>
          ))}
        </div>
      </div>

      {preview && <section className="weekly-plan__confirm" role="dialog" aria-modal="true" aria-labelledby="edit-preview-title"><h3 id="edit-preview-title">{preview.kind === "remove" ? l("تأیید حذف وعده", "Confirm meal removal") : preview.kind === "meal" ? l("تأیید تعویض وعده", "Confirm meal replacement") : l("تأیید تعویض ماده غذایی", "Confirm food replacement")}</h3><p>{l("این تغییر یک نسخه جدید می‌سازد و باید دوباره توسط پزشک بررسی شود.", "This creates a new revision that requires physician review again.")}</p><p>{l("تغییر هزینه", "Cost change")}: {number.format(Math.floor(editPreviewCost(preview.data) / 10))} {l("تومان", "Toman")}</p><button className="primary-button" type="button" onClick={() => void confirmRemoval()}>{l("ساخت نسخه جدید", "Create new revision")}</button><button type="button" onClick={() => setPreview(null)}>{l("انصراف", "Cancel")}</button></section>}

      <section className="weekly-plan__shopping">
        <h3>{l("لیست خرید دقیق", "Exact shopping list")}</h3>
        {!currentPlan.physician_approved && <p className="weekly-plan__warning">{l("تا تأیید پزشک، خرید نهایی را انجام نده.", "Wait for physician approval before making final purchases.")}</p>}
        {shopping === null ? <p role="status">{l("در حال دریافت…", "Loading…")}</p> : <><ul>{shopping.items.map((item) => <li key={item.food_id}><span>{language === "en" ? item.name_en : item.name_fa}</span><strong>{number.format(item.required_quantity)} {item.canonical_unit}</strong><small>{number.format(Math.floor(item.cost_irr / 10))} {l("تومان", "Toman")}</small></li>)}</ul><strong>{l("جمع", "Total")}: {number.format(Math.floor(shopping.total_cost_irr / 10))} {l("تومان", "Toman")}</strong></>}
      </section>

      <section className="weekly-plan__history">
        <h3>{l("تاریخچه نسخه‌ها", "Revision history")}</h3>
        {history.length === 0 ? <p>{l("نسخه دیگری وجود ندارد.", "No other revision exists.")}</p> : <div>{history.map((item) => <button className={item.id === currentPlan.id ? "is-current" : undefined} key={item.id} type="button" onClick={() => void api.getWeeklyNutritionPlan(item.id).then(setCurrentPlan)}>{l("نسخه", "Revision")} {number.format(item.revision)} · {lifecycleLabel(item.lifecycle_status, language)}</button>)}</div>}
      </section>
    </section>
  );
}

function mealTitle(
  meal: WeeklyPlan["days"][number]["meals"][number],
  language: "fa" | "en",
): string {
  const catalogueName = language === "en" ? meal.name_en : meal.name_fa;
  if (catalogueName) return meal.meal_code ? `${meal.meal_code} — ${catalogueName}` : catalogueName;
  const foodNames = meal.foods.map((food) => language === "en" ? food.name_en : food.name_fa);
  return foodNames.join(" + ") || (language === "en" ? "Meal" : "وعده غذایی");
}

function FreeMealCard({ meal, entryDate, language }: { meal: WeeklyPlan["days"][number]["meals"][number]; entryDate: string; language: "fa" | "en" }) {
  const l = (fa: string, en: string) => language === "en" ? en : fa;
  const stored = sessionStorage.getItem(`fitsho-free-meal:${meal.id}`);
  const initial = stored ? JSON.parse(stored) as api.FreeMealMacros : null;
  const [values, setValues] = useState({
    calories: initial?.calories?.toString() ?? "",
    protein_g: initial?.protein_g?.toString() ?? "",
    carbohydrate_g: initial?.carbohydrate_g?.toString() ?? "",
    fat_g: initial?.fat_g?.toString() ?? "",
  });
  const [actualTotal, setActualTotal] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const fields = [
    ["calories", l("کالری", "Calories"), "kcal"],
    ["protein_g", l("پروتئین", "Protein"), "g"],
    ["carbohydrate_g", l("کربو", "Carbs"), "g"],
    ["fat_g", l("چربی", "Fat"), "g"],
  ] as const;
  async function save() {
    if (Object.values(values).some((value) => value === "" || Number(value) < 0)) return;
    setSaving(true);
    try {
      const summary = await api.saveFreeMeal(meal.id, {
        entry_date: entryDate,
        calories: Number(values.calories),
        protein_g: Number(values.protein_g),
        carbohydrate_g: Number(values.carbohydrate_g),
        fat_g: Number(values.fat_g),
      });
      sessionStorage.removeItem(`fitsho-free-meal:${meal.id}`);
      setActualTotal(summary.actual_totals.energy_kcal ?? 0);
    } finally { setSaving(false); }
  }
  return <article className="weekly-plan__meal weekly-plan__free-meal">
    <header><div><span>{l("ناهار جمعه", "Friday lunch")}</span><strong>{l("وعده آزاد", "Free Meal")}</strong></div></header>
    <p>{l("لطفاً جهت محاسبه کالری روزانه از وعده آزاد عکس بگیرید و اطلاعات مهم وعده آزاد را اینجا وارد کنید.", "Optionally take a photo, then enter the Free Meal nutrition details here.")}</p>
    <div className="weekly-plan__free-fields">{fields.map(([key, label, unit]) => <label key={key}><i aria-hidden="true" /><span>{label}</span><input aria-label={label} min="0" type="number" value={values[key]} onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))} /><b>{unit}</b></label>)}</div>
    <div className="weekly-plan__meal-actions"><Link to={`/nutrition-tracking?freeMealId=${meal.id}&entryDate=${entryDate}&return=${encodeURIComponent("/nutrition-estimate")}`}>{l("محاسبه با عکس اختیاری", "Optional photo estimate")}</Link><button disabled={saving} type="button" onClick={() => void save()}>{saving ? l("در حال ثبت…", "Saving…") : l("ثبت وعده آزاد", "Save Free Meal")}</button></div>
    {actualTotal !== null && <strong role="status">{l("جمع مصرف واقعی این روز", "Actual daily total")}: {actualTotal.toLocaleString(language === "fa" ? "fa-IR" : "en-US")} kcal</strong>}
  </article>;
}

function findMealAlternative(plan: WeeklyPlan, mealId: string, role: "main_meal" | "snack" | "free_meal" | "post_workout") {
  return plan.days.flatMap((day) => day.meals).find((meal) => meal.id !== mealId && meal.slot_role === role);
}

function findFoodAlternative(plan: WeeklyPlan, foodId: string) {
  return plan.days.flatMap((day) => day.meals).flatMap((meal) => meal.foods).find((food) => food.food_id !== foodId);
}

function editPreviewCost(data: api.PlanEditPreview | Awaited<ReturnType<typeof api.previewMealRemoval>>) {
  if ("weekly_cost_delta_irr" in data && typeof data.weekly_cost_delta_irr === "number") return data.weekly_cost_delta_irr;
  return "cost_delta_irr" in data && typeof data.cost_delta_irr === "number" ? data.cost_delta_irr : 0;
}

function mealMetricEntries(values: Record<string, number>): Array<[string, number]> {
  const ordered = ["energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "fibre_g", "sodium_mg", "free_sugar_g", "saturated_fat_g"];
  return ordered.flatMap((code) => typeof values[code] === "number" ? [[code, values[code]] as [string, number]] : []);
}

function lifecycleLabel(status: string, language: "fa" | "en") {
  const values: Record<string, [string, string]> = {
    pending_physician_review: ["در انتظار بررسی", "Pending review"], physician_review_in_progress: ["در حال بررسی پزشک", "Physician review in progress"], awaiting_lab_information: ["در انتظار اطلاعات آزمایش", "Awaiting lab information"], physician_approved: ["تأییدشده", "Approved"], active: ["فعال", "Active"], archived: ["بایگانی‌شده", "Archived"], changes_requested: ["نیازمند تغییر", "Changes requested"], rejected: ["ردشده", "Rejected"],
  };
  return values[status]?.[language === "en" ? 1 : 0] ?? status;
}

function budgetLabel(status: string, language: "fa" | "en") {
  const values: Record<string, [string, string]> = {
    within_budget: ["در محدوده بودجه", "Within budget"],
    flexible_overage: ["کمی بالاتر از بودجه انعطاف‌پذیر", "Flexible overage"],
    over_budget: ["بالاتر از بودجه", "Over budget"],
  };
  return values[status]?.[language === "en" ? 1 : 0] ?? status;
}

function nutrientLabel(code: string, language: "fa" | "en") {
  const values: Record<string, [string, string]> = {
    goal_calories: ["انرژی", "Energy"],
    protein: ["پروتئین", "Protein"],
    carbohydrate: ["کربوهیدرات", "Carbohydrate"],
    total_fat: ["چربی کل", "Total fat"],
    fibre: ["فیبر", "Fibre"],
    calcium_mg: ["کلسیم", "Calcium"],
    sodium_mg: ["سدیم", "Sodium"],
    energy_kcal: ["انرژی", "Energy"],
    protein_g: ["پروتئین", "Protein"],
    carbohydrate_g: ["کربوهیدرات", "Carbohydrate"],
    fat_g: ["چربی", "Fat"],
    fibre_g: ["فیبر", "Fibre"],
    free_sugar_g: ["قند آزاد", "Free sugar"],
    saturated_fat_g: ["چربی اشباع", "Saturated fat"],
  };
  return values[code]?.[language === "en" ? 1 : 0] ?? code.replaceAll("_", " ");
}

function statusLabel(status: string, language: "fa" | "en") {
  const values: Record<string, [string, string]> = {
    within_target: ["در محدوده", "Within target"],
    below_minimum: ["کمتر از حداقل", "Below minimum"],
    below_preferred_but_acceptable: ["کمتر از ترجیح، قابل‌قبول", "Below preferred, acceptable"],
    below_reference_target: ["شکاف نسبت به مرجع غذایی", "Dietary reference gap"],
    above_applicable_limit: ["بالاتر از حد مجاز", "Above applicable limit"],
    data_incomplete: ["داده ناکامل", "Incomplete data"],
  };
  return values[status]?.[language === "en" ? 1 : 0] ?? status;
}
