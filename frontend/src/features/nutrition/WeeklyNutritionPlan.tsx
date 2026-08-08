import { useState } from "react";

import type { WeeklyPlan } from "./types";

type Props = {
  plan: WeeklyPlan;
  language: "fa" | "en";
};

const weekdayFa = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"];
const weekdayEn = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"];

export function WeeklyNutritionPlan({ plan, language }: Props) {
  const [selectedDay, setSelectedDay] = useState(0);
  const l = (fa: string, en: string) => language === "en" ? en : fa;
  const number = new Intl.NumberFormat(language === "en" ? "en-US" : "fa-IR", {
    maximumFractionDigits: 1,
  });
  const day = plan.days[selectedDay] ?? plan.days[0];
  const statusClass = plan.physician_approved ? "is-approved" : "is-pending";

  return (
    <section className="weekly-plan" aria-labelledby="weekly-plan-title">
      <div className="weekly-plan__heading">
        <div>
          <p className="eyebrow eyebrow--accent">{l("نسخه هفتگی", "Weekly draft")}</p>
          <h2 id="weekly-plan-title">{l("برنامه غذایی تو", "Your nutrition plan")}</h2>
        </div>
        <div className={`weekly-plan__review ${statusClass}`} role="status">
          <strong>
            {plan.physician_approved
              ? l("تأییدشده توسط پزشک", "Physician approved")
              : l("در انتظار بررسی پزشک", "Pending physician review")}
          </strong>
          {!plan.physician_approved && (
            <span>
              {l(
                "این پیش‌نویس قابل مشاهده است اما هنوز برنامه فعال پزشکی نیست.",
                "This draft is visible, but it is not yet an active approved plan.",
              )}
            </span>
          )}
        </div>
      </div>

      <div className="weekly-plan__ledger" aria-label={l("بودجه برنامه", "Plan budget")}>
        <div>
          <span>{l("هزینه برآوردی هفته", "Estimated weekly cost")}</span>
          <strong>{number.format(plan.weekly_cost_irr)} {l("ریال", "IRR")}</strong>
        </div>
        <div>
          <span>{l("بودجه هفتگی", "Weekly budget")}</span>
          <strong>{number.format(plan.weekly_budget_irr)} {l("ریال", "IRR")}</strong>
        </div>
        <div>
          <span>{l("وضعیت بودجه", "Budget status")}</span>
          <strong>{budgetLabel(plan.budget_status, language)}</strong>
        </div>
      </div>

      <div className="weekly-plan__days" role="tablist" aria-label={l("روزهای هفته", "Week days")}>
        {plan.days.map((item, index) => (
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
        <div className="weekly-plan__meals" role="tabpanel">
          {day.meals.map((meal) => (
            <article className="weekly-plan__meal" key={meal.id}>
              <header>
                <div>
                  <span>{meal.slot_role === "snack" ? l("میان‌وعده", "Snack") : l("وعده اصلی", "Main meal")}</span>
                  <strong>{number.format(meal.nutrient_totals.energy_kcal ?? 0)} {l("کیلوکالری", "kcal")}</strong>
                </div>
                <small>{number.format(meal.cost_irr)} {l("ریال", "IRR")}</small>
              </header>
              <ul>
                {meal.foods.map((food) => (
                  <li key={`${meal.id}-${food.food_id}`}>
                    <span>{language === "en" ? food.name_en : food.name_fa}</span>
                    <strong>{number.format(food.grams)} {l("گرم", "g")}</strong>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      )}

      <div className="weekly-plan__nutrients">
        <h3>{l("هدف در برابر مقدار برنامه", "Target versus planned")}</h3>
        <div>
          {Object.values(plan.nutrients).map((nutrient) => (
            <article key={nutrient.nutrient_code}>
              <span>{nutrientLabel(nutrient.nutrient_code, language)}</span>
              <strong>{number.format(nutrient.planned)} {nutrient.unit}</strong>
              <small data-status={nutrient.status}>{statusLabel(nutrient.status, language)}</small>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
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
