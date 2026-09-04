import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../shared/apiClient";
import { MealThumbnail } from "../../shared/MealThumbnail";
import * as api from "./api";
import type { MealFeedbackType, ShoppingList, WeeklyPlan, WeeklyPlanHistoryItem, WeeklyPlanFood } from "./types";

type Props = {
  plan: WeeklyPlan;
  language: "fa" | "en";
};

const weekdayFa = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"];
const weekdayEn = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"];
type PlanMeal = WeeklyPlan["days"][number]["meals"][number];
type ActionKind = "lock" | "feedback" | "remove-preview" | "meal-replacement-preview" | "food-replacement-preview" | "confirm" | "regenerate";
type BusyAction = { mealId: string; action: ActionKind };
type PreviewState =
  | { kind: "remove"; data: Awaited<ReturnType<typeof api.previewMealRemoval>>; meal: PlanMeal }
  | { kind: "meal"; data: api.PlanEditPreview; meal: PlanMeal; replacement: api.MealReplacementOption }
  | { kind: "food"; data: api.PlanEditPreview; meal: PlanMeal; food: WeeklyPlanFood; replacement: api.FoodReplacementOption };
type ReplacementSelector =
  | { kind: "meal"; mealId: string; options: api.MealReplacementOption[] | null; selectedId: string | null }
  | { kind: "food"; mealId: string; targetFoodId: string | null; options: api.FoodReplacementOption[] | null; selectedId: string | null };

export function WeeklyNutritionPlan({ plan, language }: Props) {
  const [selectedDay, setSelectedDay] = useState(0);
  const [currentPlan, setCurrentPlan] = useState(plan);
  const [shopping, setShopping] = useState<ShoppingList | null>(null);
  const [history, setHistory] = useState<WeeklyPlanHistoryItem[]>([]);
  const [busyAction, setBusyAction] = useState<BusyAction | null>(null);
  const [feedback, setFeedback] = useState<Record<string, MealFeedbackType>>({});
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const [selector, setSelector] = useState<ReplacementSelector | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  useEffect(() => { setCurrentPlan(plan); }, [plan]);
  useEffect(() => {
    void Promise.all([
      api.getShoppingList(currentPlan.id),
      api.listWeeklyNutritionPlans(),
      api.getMealFeedback(currentPlan.id),
    ])
      .then(([list, revisions, savedFeedback]) => {
        setShopping(list);
        setHistory(revisions);
        setFeedback(savedFeedback?.feedback ?? {});
      })
      .catch((error: unknown) => setActionError(actionErrorMessage(error, language)));
  }, [currentPlan.id, language]);
  useEffect(() => {
    if (preview === null && selector === null) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && busyAction?.action !== "confirm") {
        setPreview(null);
        setSelector(null);
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [busyAction?.action, preview, selector]);
  const l = (fa: string, en: string) => language === "en" ? en : fa;
  const number = new Intl.NumberFormat(language === "en" ? "en-US" : "fa-IR", {
    maximumFractionDigits: 1,
  });
  const day = currentPlan.days[selectedDay] ?? currentPlan.days[0];
  const statusClass = currentPlan.physician_approved ? "is-approved" : "is-pending";

  const isBusy = (mealId: string, action?: ActionKind) => busyAction?.mealId === mealId && (action === undefined || busyAction.action === action);
  const runError = (error: unknown) => setActionError(actionErrorMessage(error, language));

  async function toggleLock(mealId: string, locked: boolean) {
    setBusyAction({ mealId, action: "lock" }); setActionError(null);
    try {
      const result = await api.setMealLock(currentPlan.id, mealId, locked);
      setCurrentPlan({ ...currentPlan, days: currentPlan.days.map((item) => ({ ...item, meals: item.meals.map((meal) => meal.id === mealId ? { ...meal, is_locked: result.is_locked } : meal) })) });
    } catch (error: unknown) { runError(error); } finally { setBusyAction(null); }
  }

  async function beginRemoval(mealId: string) {
    const meal = findMeal(currentPlan, mealId);
    if (!meal || meal.is_locked) return;
    setBusyAction({ mealId, action: "remove-preview" }); setActionError(null);
    try { setPreview({ kind: "remove", data: await api.previewMealRemoval(currentPlan.id, mealId), meal }); }
    catch (error: unknown) { runError(error); }
    finally { setBusyAction(null); }
  }

  async function saveFeedback(mealId: string, feedbackType: "liked" | "disliked") {
    if (isBusy(mealId, "feedback")) return;
    setBusyAction({ mealId, action: "feedback" }); setActionError(null);
    try {
      const saved = await api.saveMealFeedback(currentPlan.id, mealId, feedbackType);
      setFeedback((current) => ({ ...current, [mealId]: saved.feedback_type }));
    } catch (error: unknown) { runError(error); }
    finally { setBusyAction(null); }
  }

  async function confirmPlanEdit() {
    if (!preview) return;
    setBusyAction({ mealId: preview.data.meal_id, action: "confirm" }); setActionError(null);
    try {
      const next = preview.kind === "remove"
        ? await api.confirmMealRemoval(currentPlan.id, preview.data.meal_id, preview.data.expected_plan_revision_id)
        : preview.kind === "meal"
          ? await api.confirmMealReplacement(currentPlan.id, preview.data.meal_id, preview.replacement.id)
          : await api.confirmFoodReplacement(currentPlan.id, preview.data.meal_id, preview.food.food_id!, preview.replacement.food_id);
      setCurrentPlan(next); setPreview(null); setSelector(null); setSelectedDay(0);
    } catch (error: unknown) { runError(error); }
    finally { setBusyAction(null); }
  }

  async function beginMealReplacement(mealId: string) {
    setSelector({ kind: "meal", mealId, options: null, selectedId: null });
    setBusyAction({ mealId, action: "meal-replacement-preview" }); setActionError(null);
    try {
      const result = await api.getMealReplacementOptions(currentPlan.id, mealId);
      setSelector({ kind: "meal", mealId, options: result.options, selectedId: null });
    } catch (error: unknown) { setSelector(null); runError(error); }
    finally { setBusyAction(null); }
  }

  async function chooseMealReplacement() {
    if (!selector || selector.kind !== "meal" || !selector.selectedId) return;
    const meal = findMeal(currentPlan, selector.mealId);
    const replacement = selector.options?.find((option) => option.id === selector.selectedId);
    if (!meal || !replacement) return;
    setBusyAction({ mealId: meal.id, action: "meal-replacement-preview" }); setActionError(null);
    try {
      const data = await api.previewMealReplacement(currentPlan.id, meal.id, replacement.id);
      setPreview({ kind: "meal", data, meal, replacement }); setSelector(null);
    } catch (error: unknown) { runError(error); }
    finally { setBusyAction(null); }
  }

  function beginFoodReplacement(mealId: string) {
    setSelector({ kind: "food", mealId, targetFoodId: null, options: null, selectedId: null });
    setActionError(null);
  }

  async function chooseFoodTarget(foodId: string) {
    if (!selector || selector.kind !== "food") return;
    const meal = findMeal(currentPlan, selector.mealId);
    if (!meal) return;
    setBusyAction({ mealId: meal.id, action: "food-replacement-preview" }); setActionError(null);
    try {
      const result = await api.getFoodReplacementOptions(currentPlan.id, meal.id, foodId);
      setSelector({ ...selector, targetFoodId: foodId, options: result.options, selectedId: null });
    } catch (error: unknown) { runError(error); }
    finally { setBusyAction(null); }
  }

  async function chooseFoodReplacement() {
    if (!selector || selector.kind !== "food" || !selector.targetFoodId || !selector.selectedId) return;
    const meal = findMeal(currentPlan, selector.mealId);
    const food = meal?.foods.find((item) => item.food_id === selector.targetFoodId);
    const replacement = selector.options?.find((option) => option.food_id === selector.selectedId);
    if (!meal || !food || !replacement || !food.food_id) return;
    setBusyAction({ mealId: meal.id, action: "food-replacement-preview" }); setActionError(null);
    try {
      const data = await api.previewFoodReplacement(currentPlan.id, meal.id, food.food_id, replacement.food_id);
      setPreview({ kind: "food", data, meal, food, replacement }); setSelector(null);
    } catch (error: unknown) { runError(error); }
    finally { setBusyAction(null); }
  }

  async function regenerateDay() {
    setBusyAction({ mealId: "regenerate", action: "regenerate" }); setActionError(null);
    try { setCurrentPlan(await api.partialRegeneratePlan(currentPlan.id, [selectedDay])); setSelectedDay(0); }
    catch (error: unknown) { runError(error); } finally { setBusyAction(null); }
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
      {actionError && <p className="weekly-plan__error" role="alert">{actionError}</p>}

      <details className="weekly-plan__section">
        <summary>
          <span>{l("برنامه تغذیه", "Nutrition plan")}</span>
          <span aria-hidden="true" className="weekly-plan__section-chevron" />
        </summary>
        <div className="weekly-plan__section-content">
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
        <><div className="weekly-plan__daily-summary"><strong>{l("جمع روز", "Daily total")}: {number.format(day.nutrient_totals.energy_kcal ?? 0)} {l("کیلوکالری", "kcal")}</strong><span>{number.format(Math.floor(day.cost_irr / 10))} {l("تومان", "Toman")}</span><span>{l("پروتئین", "Protein")}: {number.format(day.nutrient_totals.protein_g ?? 0)} g</span><span>{l("کربوهیدرات", "Carbohydrate")}: {number.format(day.nutrient_totals.carbohydrate_g ?? 0)} g</span></div><div className="weekly-plan__day-actions"><button disabled={isBusy("regenerate", "regenerate") || day.meals.every((meal) => meal.is_locked)} type="button" onClick={() => void regenerateDay()}>{l("بازسازی وعده‌های باز این روز", "Regenerate unlocked meals for this day")}</button></div><div className="weekly-plan__meals" role="tabpanel">
          {day.meals.map((meal) => (
            meal.slot_role === "free_meal" ? <FreeMealCard key={meal.id} meal={meal} entryDate={day.plan_date} language={language} /> : <details className="weekly-plan__meal" key={meal.id}>
              <summary className="weekly-plan__meal-summary">
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
                  </div>
                </div>
                <div className="weekly-plan__meal-summary-metrics">
                  <span>{number.format(meal.nutrient_totals.energy_kcal ?? 0)} kcal</span>
                  <span>{number.format(Math.floor(meal.cost_irr / 10))} {l("تومان", "Toman")}</span>
                  <span aria-hidden="true" className="weekly-plan__meal-chevron" />
                </div>
              </summary>
              <div className="weekly-plan__meal-content">
              <ul>
                {meal.foods.map((food) => (
                  <li key={`${meal.id}-${food.food_id ?? food.slug}`}>
                    <span>{language === "en" ? food.name_en : food.name_fa}</span>
                    <strong>{number.format(food.grams)} {l("گرم", "g")}</strong>
                  </li>
                ))}
              </ul>
              {meal.foods.map((food) => food.item_kind === "prepared_recipe" && food.prepared_recipe ? (
                <aside className="weekly-plan__prepared-recipe" key={`${meal.id}-${food.slug}-summary`}>
                  <div>
                    <strong>{number.format(food.prepared_recipe.nutrients_per_100g.energy_kcal ?? 0)} {l("کیلوکالری در ۱۰۰ گرم", "kcal per 100 g")}</strong>
                    {food.prepared_recipe.status === "estimated" && <span>تخمینی</span>}
                  </div>
                  <dl>
                    {preparedRecipeMacroEntries(food.prepared_recipe.nutrients_per_100g).map(([code, value]) => (
                      <div key={code}><dt>{nutrientLabel(code, language)}</dt><dd>{number.format(value)}</dd></div>
                    ))}
                  </dl>
                  <small>{number.format(Math.floor(food.prepared_recipe.cost_irr_per_100g / 10))} {l("تومان در ۱۰۰ گرم", "Toman per 100 g")}</small>
                </aside>
              ) : null)}
              <dl className="weekly-plan__meal-totals">
                {mealMetricEntries(meal.nutrient_totals).map(([code, value]) => <div key={code}><dt>{nutrientLabel(code, language)}</dt><dd>{number.format(value)}</dd></div>)}
              </dl>
              <div className="weekly-plan__meal-actions">
                <button aria-busy={isBusy(meal.id, "lock")} disabled={isBusy(meal.id, "lock")} type="button" onClick={() => void toggleLock(meal.id, !meal.is_locked)}>{meal.is_locked ? l("بازکردن قفل", "Unlock") : l("قفل وعده", "Lock meal")}</button>
                <button aria-pressed={feedback[meal.id] === "liked"} className={feedback[meal.id] === "liked" ? "is-selected" : undefined} aria-busy={isBusy(meal.id, "feedback")} disabled={isBusy(meal.id, "feedback")} type="button" onClick={() => void saveFeedback(meal.id, "liked")}>{isBusy(meal.id, "feedback") ? l("در حال ثبت…", "Saving…") : l("پسندیدم", "Liked")}{feedback[meal.id] === "liked" && !isBusy(meal.id, "feedback") ? " ✓" : ""}</button>
                <button aria-pressed={feedback[meal.id] === "disliked"} className={feedback[meal.id] === "disliked" ? "is-selected" : undefined} aria-busy={isBusy(meal.id, "feedback")} disabled={isBusy(meal.id, "feedback")} type="button" onClick={() => void saveFeedback(meal.id, "disliked")}>{isBusy(meal.id, "feedback") ? l("در حال ثبت…", "Saving…") : l("کمتر پیشنهاد بده", "Suggest less often")}{feedback[meal.id] === "disliked" && !isBusy(meal.id, "feedback") ? " ✓" : ""}</button>
                <button disabled={meal.is_locked || isBusy(meal.id, "remove-preview") || isBusy(meal.id, "confirm")} type="button" onClick={() => void beginRemoval(meal.id)}>{l("حذف وعده", "Remove meal")}</button>
                <button disabled={meal.is_locked || isBusy(meal.id, "meal-replacement-preview") || isBusy(meal.id, "confirm")} type="button" onClick={() => void beginMealReplacement(meal.id)}>{l("تعویض وعده", "Replace meal")}</button>
                {meal.foods.some((food) => food.food_id !== null) && <button disabled={meal.is_locked || isBusy(meal.id, "food-replacement-preview") || isBusy(meal.id, "confirm")} type="button" onClick={() => beginFoodReplacement(meal.id)}>{l("تعویض ماده غذایی", "Replace ingredient")}</button>}
              </div>
              </div>
            </details>
          ))}
        </div></>
      )}

      <section className="weekly-plan__history">
        <h3>{l("تاریخچه نسخه‌ها", "Revision history")}</h3>
        {history.length === 0 ? <p>{l("نسخه دیگری وجود ندارد.", "No other revision exists.")}</p> : <div>{history.map((item) => <button className={item.id === currentPlan.id ? "is-current" : undefined} key={item.id} type="button" onClick={() => void api.getWeeklyNutritionPlan(item.id).then(setCurrentPlan)}>{l("نسخه", "Revision")} {number.format(item.revision)} · {lifecycleLabel(item.lifecycle_status, language)}</button>)}</div>}
      </section>

      </div>
      </details>

      <details className="weekly-plan__section weekly-plan__nutrients">
        <summary>
          <span>{l("هدف در برابر مقدار برنامه", "Target versus planned")}</span>
          <span aria-hidden="true" className="weekly-plan__section-chevron" />
        </summary>
        <div className="weekly-plan__section-content">
        <div className="weekly-plan__nutrient-grid">
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
      </details>

      {selector && <div className="weekly-plan__modal-backdrop">
        <div className="weekly-plan__modal" role="dialog" aria-modal="true" aria-labelledby="replacement-selector-title">
          <button className="weekly-plan__modal-close" type="button" onClick={() => setSelector(null)}>{l("بستن", "Close")}</button>
          {selector.kind === "meal" ? <>
            <h3 id="replacement-selector-title">{l("انتخاب وعده جایگزین", "Choose a replacement meal")}</h3>
            {actionError && <p className="weekly-plan__error" role="alert">{actionError}</p>}
            {selector.options === null ? <p role="status">{l("در حال دریافت گزینه‌ها…", "Loading options…")}</p> : selector.options.length === 0 ? <p>{l("گزینه سازگار دیگری در این نسخه وجود ندارد.", "No other compatible meal exists in this revision.")}</p> : <div className="weekly-plan__replacement-options">
              {selector.options.map((option) => <button aria-pressed={selector.selectedId === option.id} className={selector.selectedId === option.id ? "is-selected" : undefined} key={option.id} type="button" onClick={() => setSelector({ ...selector, selectedId: option.id })}>
                <MealThumbnail alt={language === "en" ? option.name_en : option.name_fa} className="weekly-plan__replacement-image" fallbackLabel={l("تصویر وعده جایگزین", "Replacement meal placeholder")} imageUrl={option.image_url} />
                <span><strong>{option.meal_code ? `${option.meal_code} — ` : ""}{language === "en" ? option.name_en : option.name_fa}</strong><small>{number.format(option.nutrient_totals.energy_kcal ?? 0)} kcal · {l("پروتئین", "Protein")} {number.format(option.nutrient_totals.protein_g ?? 0)} g · {number.format(Math.floor(option.cost_irr / 10))} {l("تومان", "Toman")}</small></span>
              </button>)}
            </div>}
            <div className="weekly-plan__modal-actions"><button className="primary-button" disabled={!selector.selectedId || isBusy(selector.mealId, "meal-replacement-preview")} type="button" onClick={() => void chooseMealReplacement()}>{l("پیش‌نمایش تعویض وعده", "Preview meal replacement")}</button><button type="button" onClick={() => setSelector(null)}>{l("انصراف", "Cancel")}</button></div>
          </> : <>
            <h3 id="replacement-selector-title">{l("انتخاب ماده غذایی برای تعویض", "Choose an ingredient to replace")}</h3>
            {(() => { const targetMeal = findMeal(currentPlan, selector.mealId); return targetMeal ? <>
              <p>{l("ابتدا ماده غذایی موردنظر را انتخاب کن.", "First choose the ingredient you want to replace.")}</p>
              <div className="weekly-plan__food-targets">{targetMeal.foods.filter((food) => food.food_id !== null).map((food) => <button aria-pressed={selector.targetFoodId === food.food_id} className={selector.targetFoodId === food.food_id ? "is-selected" : undefined} key={food.food_id} type="button" onClick={() => void chooseFoodTarget(food.food_id!)}>{language === "en" ? food.name_en : food.name_fa} — {number.format(food.grams)} {l("گرم", "g")}</button>)}</div>
              {selector.targetFoodId && <><h4>{l("جایگزین‌های قابل انتخاب", "Eligible replacements")}</h4>{selector.options === null ? <p role="status">{l("در حال دریافت گزینه‌ها…", "Loading options…")}</p> : selector.options.length === 0 ? <p>{l("گزینه سازگار دیگری در این نسخه وجود ندارد.", "No other compatible ingredient exists in this revision.")}</p> : <div className="weekly-plan__replacement-options">{selector.options.map((option) => <button aria-pressed={selector.selectedId === option.food_id} className={selector.selectedId === option.food_id ? "is-selected" : undefined} key={option.food_id} type="button" onClick={() => setSelector({ ...selector, selectedId: option.food_id })}><MealThumbnail alt={language === "en" ? option.name_en : option.name_fa} className="weekly-plan__replacement-image" fallbackLabel={l("تصویر ماده غذایی جایگزین", "Replacement ingredient placeholder")} imageUrl={option.image_url} /><span><strong>{language === "en" ? option.name_en : option.name_fa}</strong><small>{number.format(option.grams)} {l("گرم", "g")} · {number.format(option.nutrients.energy_kcal ?? 0)} kcal · {l("پروتئین", "Protein")} {number.format(option.nutrients.protein_g ?? 0)} g · {number.format(Math.floor(option.cost_irr / 10))} {l("تومان", "Toman")}</small></span></button>)}</div>}</>}
              <div className="weekly-plan__modal-actions"><button className="primary-button" disabled={!selector.targetFoodId || !selector.selectedId || isBusy(selector.mealId, "food-replacement-preview")} type="button" onClick={() => void chooseFoodReplacement()}>{l("پیش‌نمایش تعویض ماده غذایی", "Preview ingredient replacement")}</button><button type="button" onClick={() => setSelector(null)}>{l("انصراف", "Cancel")}</button></div>
            </> : null; })()}
          </>}
        </div>
      </div>}

      {preview && <div className="weekly-plan__modal-backdrop">
        <div className="weekly-plan__modal" role="dialog" aria-modal="true" aria-labelledby="edit-preview-title">
          <button className="weekly-plan__modal-close" type="button" onClick={() => setPreview(null)}>{l("بستن", "Close")}</button>
          <h3 id="edit-preview-title">{preview.kind === "remove" ? l("پیش‌نمایش حذف وعده", "Preview meal removal") : preview.kind === "meal" ? l("پیش‌نمایش تعویض وعده", "Preview meal replacement") : l("پیش‌نمایش تعویض ماده غذایی", "Preview ingredient replacement")}</h3>
          {actionError && <p className="weekly-plan__error" role="alert">{actionError}</p>}
          <p><strong>{l("وعده هدف", "Target meal")}: </strong>{mealTitle(preview.meal, language)}</p>
          {preview.kind === "meal" && <p><strong>{l("وعده جدید", "New meal")}: </strong>{preview.replacement.meal_code ? `${preview.replacement.meal_code} — ` : ""}{language === "en" ? preview.replacement.name_en : preview.replacement.name_fa}</p>}
          {preview.kind === "food" && <><p><strong>{l("ماده قدیمی", "Old ingredient")}: </strong>{language === "en" ? preview.food.name_en : preview.food.name_fa} — {number.format(preview.food.grams)} {l("گرم", "g")}</p><p><strong>{l("ماده جدید", "New ingredient")}: </strong>{language === "en" ? preview.replacement.name_en : preview.replacement.name_fa} — {number.format(preview.replacement.grams)} {l("گرم", "g")}</p></>}
          {previewImpact(preview.data, language, number).length > 0 && <ul className="weekly-plan__preview-impact">{previewImpact(preview.data, language, number).map((item) => <li key={item.label}>{item.label}: {item.value}</li>)}</ul>}
          <p>{l("تغییر هزینه", "Cost change")}: {number.format(Math.floor(editPreviewCost(preview.data) / 10))} {l("تومان", "Toman")}</p>
          <p className="weekly-plan__warning">{l("این عملیات هنوز اعمال نشده است. تأیید آن یک نسخه جدید می‌سازد و بررسی پزشک دوباره لازم خواهد بود.", "This operation has not been applied. Confirming creates a new revision and requires physician review again.")}</p>
          <div className="weekly-plan__modal-actions"><button className="primary-button" disabled={isBusy(preview.data.meal_id, "confirm")} type="button" onClick={() => void confirmPlanEdit()}>{l("ساخت نسخه جدید", "Create new revision")}</button><button type="button" onClick={() => setPreview(null)}>{l("انصراف", "Cancel")}</button></div>
        </div>
      </div>}

      <details className="weekly-plan__section weekly-plan__shopping">
        <summary>
          <span>{l("لیست خرید دقیق", "Exact shopping list")}</span>
          <span aria-hidden="true" className="weekly-plan__section-chevron" />
        </summary>
        <div className="weekly-plan__section-content">
          {!currentPlan.physician_approved && <p className="weekly-plan__warning">{l("تا تأیید پزشک، خرید نهایی را انجام نده.", "Wait for physician approval before making final purchases.")}</p>}
          {shopping === null ? <p role="status">{l("در حال دریافت…", "Loading…")}</p> : <><ul>{shopping.items.map((item) => <li key={item.food_id}><span>{language === "en" ? item.name_en : item.name_fa}</span><strong>{number.format(item.required_quantity)} {item.canonical_unit}</strong><small>{number.format(Math.floor(item.cost_irr / 10))} {l("تومان", "Toman")}</small></li>)}</ul><strong>{l("جمع", "Total")}: {number.format(Math.floor(shopping.total_cost_irr / 10))} {l("تومان", "Toman")}</strong></>}
        </div>
      </details>

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
  const plannedCalories = meal.nutrient_totals.energy_kcal;
  return <details className="weekly-plan__meal weekly-plan__free-meal">
    <summary className="weekly-plan__meal-summary">
      <div className="weekly-plan__meal-heading">
        <div><span>{l("ناهار جمعه", "Friday lunch")}</span><strong className="weekly-plan__meal-title">{l("وعده آزاد", "Free Meal")}</strong></div>
      </div>
      <div className="weekly-plan__meal-summary-metrics">
        <span>{plannedCalories === undefined ? "—" : new Intl.NumberFormat(language === "en" ? "en-US" : "fa-IR").format(plannedCalories)} kcal</span>
        <span>{new Intl.NumberFormat(language === "en" ? "en-US" : "fa-IR").format(Math.floor(meal.cost_irr / 10))} {l("تومان", "Toman")}</span>
        <span aria-hidden="true" className="weekly-plan__meal-chevron" />
      </div>
    </summary>
    <div className="weekly-plan__meal-content">
      <p>{l("لطفاً جهت محاسبه کالری روزانه از وعده آزاد عکس بگیرید و اطلاعات مهم وعده آزاد را اینجا وارد کنید.", "Optionally take a photo, then enter the Free Meal nutrition details here.")}</p>
      <div className="weekly-plan__free-fields">{fields.map(([key, label, unit]) => <label key={key}><i aria-hidden="true" /><span>{label}</span><input aria-label={label} min="0" type="number" value={values[key]} onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))} /><b>{unit}</b></label>)}</div>
      <div className="weekly-plan__meal-actions"><Link to={`/nutrition-tracking?freeMealId=${meal.id}&entryDate=${entryDate}&return=${encodeURIComponent("/nutrition-estimate")}`}>{l("محاسبه با عکس اختیاری", "Optional photo estimate")}</Link><button disabled={saving} type="button" onClick={() => void save()}>{saving ? l("در حال ثبت…", "Saving…") : l("ثبت وعده آزاد", "Save Free Meal")}</button></div>
      {actualTotal !== null && <strong role="status">{l("جمع مصرف واقعی این روز", "Actual daily total")}: {actualTotal.toLocaleString(language === "fa" ? "fa-IR" : "en-US")} kcal</strong>}
    </div>
  </details>;
}

function findMeal(plan: WeeklyPlan, mealId: string): PlanMeal | undefined {
  return plan.days.flatMap((day) => day.meals).find((meal) => meal.id === mealId);
}

function actionErrorMessage(error: unknown, language: "fa" | "en"): string {
  const code = error instanceof ApiError ? error.code : null;
  const messages: Record<string, [string, string]> = {
    PLAN_REVIEW_IN_PROGRESS: ["این نسخه در حال بررسی پزشک است و تا پایان بررسی نمی‌توان وعده‌های آن را تغییر داد.", "This revision is under physician review and cannot be changed until the review is complete."],
    STALE_PLAN_REVISION: ["نسخه برنامه تغییر کرده است. صفحه را به‌روزرسانی کن و دوباره تلاش کن.", "The plan revision changed. Refresh the page and try again."],
    MEAL_NOT_FOUND: ["وعده موردنظر دیگر در این نسخه وجود ندارد.", "This meal is no longer available in this revision."],
    MEAL_LOCKED: ["این وعده قفل است و ابتدا باید قفل آن را باز کنی.", "This meal is locked. Unlock it before editing."],
    INCOMPATIBLE_MEAL_REPLACEMENT: ["این وعده جایگزین با نقش وعده سازگار نیست.", "That meal is not compatible with this meal slot."],
    FOOD_REPLACEMENT_NOT_FOUND: ["ماده غذایی انتخاب‌شده دیگر برای این جایگزینی در دسترس نیست.", "That ingredient replacement is no longer available."],
  };
  return code && messages[code] ? messages[code][language === "en" ? 1 : 0] : l10n("عملیات انجام نشد؛ دوباره تلاش کن.", "The action failed. Please try again.", language);
}

function l10n(fa: string, en: string, language: "fa" | "en") {
  return language === "en" ? en : fa;
}

function editPreviewCost(data: api.PlanEditPreview | Awaited<ReturnType<typeof api.previewMealRemoval>>) {
  if ("weekly_cost_delta_irr" in data && typeof data.weekly_cost_delta_irr === "number") return data.weekly_cost_delta_irr;
  return "cost_delta_irr" in data && typeof data.cost_delta_irr === "number" ? data.cost_delta_irr : 0;
}

function previewImpact(data: api.PlanEditPreview | Awaited<ReturnType<typeof api.previewMealRemoval>>, language: "fa" | "en", number: Intl.NumberFormat): Array<{ label: string; value: string }> {
  const delta = "daily_delta" in data && data.daily_delta ? data.daily_delta : "meal_delta" in data && data.meal_delta ? data.meal_delta : {};
  return Object.entries(delta).map(([code, value]) => ({ label: nutrientLabel(code, language), value: `${value > 0 ? "+" : ""}${number.format(value)}` }));
}

function mealMetricEntries(values: Record<string, number>): Array<[string, number]> {
  const ordered = ["energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "fibre_g", "sodium_mg", "free_sugar_g", "saturated_fat_g"];
  return ordered.flatMap((code) => typeof values[code] === "number" ? [[code, values[code]] as [string, number]] : []);
}

function preparedRecipeMacroEntries(values: Record<string, number>): Array<[string, number]> {
  return ["protein_g", "carbohydrate_g", "total_fat_g", "fibre_g"]
    .flatMap((code) => typeof values[code] === "number" ? [[code, values[code]] as [string, number]] : []);
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
    total_fat_g: ["چربی کل", "Total fat"],
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
