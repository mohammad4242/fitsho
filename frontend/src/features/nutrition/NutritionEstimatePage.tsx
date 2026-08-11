import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import * as nutritionApi from "./api";
import type {
  NutritionEstimate,
  NutritionTarget,
  WeeklyPlan,
  WeeklyPlanGeneration,
} from "./types";
import { WeeklyNutritionPlan } from "./WeeklyNutritionPlan";
import "./nutritionEstimate.css";

type ViewState = "loading" | "ready" | "empty" | "error";

export function NutritionEstimatePage() {
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage === "en" ? "en" : "fa";
  const [state, setState] = useState<ViewState>("loading");
  const [estimate, setEstimate] = useState<NutritionEstimate | null>(null);
  const [plan, setPlan] = useState<WeeklyPlan | null>(null);
  const [planOutcome, setPlanOutcome] = useState<WeeklyPlanGeneration | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const l = (fa: string, en: string) => language === "en" ? en : fa;

  useEffect(() => {
    let active = true;
    void Promise.all([
      nutritionApi.getCurrentNutritionEstimate(),
      nutritionApi.getLatestWeeklyNutritionPlan(),
    ])
      .then(([result, latestPlan]) => {
        if (!active) return;
        setEstimate(result);
        setPlan(latestPlan);
        setState(result === null ? "empty" : "ready");
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => { active = false; };
  }, []);

  function calculate() {
    setCalculating(true);
    setState("loading");
    void nutritionApi.createNutritionEstimate()
      .then((result) => {
        setEstimate(result);
        setState("ready");
      })
      .catch(() => setState("error"))
      .finally(() => setCalculating(false));
  }

  function generatePlan() {
    setGeneratingPlan(true);
    setPlanOutcome(null);
    void nutritionApi.createWeeklyNutritionPlan()
      .then((result) => {
        setPlanOutcome(result);
        if (result.plan !== null) setPlan(result.plan);
      })
      .catch(() => {
        setPlanOutcome({
          generation_id: "",
          outcome: "failed",
          reason_codes: ["REQUEST_FAILED"],
          warning_codes: [],
          plan: null,
        });
      })
      .finally(() => setGeneratingPlan(false));
  }

  return (
    <main className="nutrition-estimate-page fitsho-page" dir={language === "fa" ? "rtl" : "ltr"}>
      <section className="nutrition-estimate-hero">
        <div><p className="eyebrow eyebrow--accent">{l("امروز", "Today")}</p><h1 className="fitsho-display">{l("هدف روزانه تغذیه", "Daily nutrition targets")}</h1></div>
        <nav className="nutrition-estimate-tools" aria-label={l("ابزارهای تغذیه", "Nutrition tools")}>
          <Link className="nutrition-tool-link nutrition-tool-link--primary" to="/nutrition-tracking"><strong>{l("ثبت تغذیه", "Track food")}</strong><small>{l("دستی یا با عکس", "Manual or photo")}</small></Link>
          <Link className="nutrition-tool-link" to="/food-catalogue"><strong>{l("کاتالوگ", "Catalogue")}</strong><small>{l("مرجع مواد غذایی", "Food reference")}</small></Link>
          <Link className="nutrition-tool-link" to="/nutrition-labs"><strong>{l("آزمایش‌ها", "Labs")}</strong></Link>
          <Link className="nutrition-tool-link" to="/nutrition-supplements"><strong>{l("مکمل‌ها", "Supplements")}</strong></Link>
        </nav>
      </section>

      {state === "loading" && <p className="nutrition-estimate-state" role="status">{calculating ? l("در حال محاسبه…", "Calculating…") : l("در حال دریافت برآورد…", "Loading estimate…")}</p>}
      {state === "empty" && <section className="nutrition-estimate-state"><h2>{l("هنوز برآوردی ثبت نشده", "No estimate yet")}</h2><p>{l("اطلاعات پروفایل فعلی را به یک برآورد شفاف تبدیل کن.", "Turn your current profile into a transparent estimate.")}</p><button className="primary-button" type="button" onClick={calculate}>{l("محاسبه هدف‌ها", "Calculate targets")}</button></section>}
      {state === "error" && <section className="nutrition-estimate-state" role="alert"><h2>{l("محاسبه انجام نشد", "Estimate unavailable")}</h2><p>{l("اطلاعات ضروری یا وضعیت ایمنی را در پروفایل بررسی کن.", "Review required profile details and your safety status.")}</p><Link className="secondary-button" to="/profile">{l("رفتن به پروفایل", "Open profile")}</Link></section>}
      {state === "ready" && estimate !== null && (
        <>
          <EstimateContent estimate={estimate} language={language} onRefresh={calculate} />
          <PlanArea
            generating={generatingPlan}
            language={language}
            onGenerate={generatePlan}
            outcome={planOutcome}
            plan={plan}
          />
        </>
      )}
    </main>
  );
}

function PlanArea({
  generating,
  language,
  onGenerate,
  outcome,
  plan,
}: {
  generating: boolean;
  language: "fa" | "en";
  onGenerate: () => void;
  outcome: WeeklyPlanGeneration | null;
  plan: WeeklyPlan | null;
}) {
  const l = (fa: string, en: string) => language === "en" ? en : fa;
  if (plan !== null) return <WeeklyNutritionPlan language={language} plan={plan} />;
  const message = outcome === null ? null : generationMessage(outcome.outcome, language);
  return (
    <section className="weekly-plan-empty" aria-labelledby="weekly-plan-empty-title">
      <p className="eyebrow eyebrow--accent">{l("گام بعد", "Next step")}</p>
      <h2 id="weekly-plan-empty-title">{l("برنامه هفتگی شخصی‌ات را بساز", "Build your personal weekly plan")}</h2>
      <p>
        {message ?? l(
          "فیتشو هدف‌های علمی، محدودیت‌های غذایی و بودجه هفتگی را در یک پیش‌نویس هفت‌روزه ترکیب می‌کند.",
          "Fitsho combines your scientific targets, food constraints, and weekly budget into a seven-day draft.",
        )}
      </p>
      {outcome?.reason_codes.includes("INSUFFICIENT_PRICE_COVERAGE") && (
        <small>
          {l(
            "قیمت معتبر برای مواد کافی در دسترس نیست؛ هیچ قیمت زنده‌ای ساخته یا حدس زده نشد.",
            "Reliable prices are unavailable for enough foods; no live price was fabricated or guessed.",
          )}
        </small>
      )}
      <button className="primary-button" disabled={generating} onClick={onGenerate} type="button">
        {generating ? l("در حال ساخت برنامه…", "Building plan…") : l("ساخت برنامه هفتگی", "Build weekly plan")}
      </button>
    </section>
  );
}

function generationMessage(outcome: WeeklyPlanGeneration["outcome"], language: "fa" | "en") {
  const values: Record<WeeklyPlanGeneration["outcome"], [string, string]> = {
    success: ["برنامه ساخته شد.", "Plan generated."],
    failed: ["ساخت برنامه انجام نشد. اطلاعات پروفایل را بررسی کن.", "Plan generation failed. Review your profile."],
    safety_blocked: ["ساخت خودکار این برنامه به‌دلیل وضعیت ایمنی مجاز نیست.", "Automatic planning is unavailable because of the current safety status."],
    infeasible: ["با محدودیت‌های فعلی برنامه ایمن و شدنی پیدا نشد.", "No safe feasible plan was found under the current constraints."],
    target_infeasible: ["هدف‌های فعلی با حداقل‌های علمی قابل جمع نیستند.", "The current targets cannot satisfy the scientific minimums."],
    live_price_unavailable: ["پوشش قیمت معتبر برای ساخت برنامه کافی نیست.", "Reliable price coverage is insufficient to build a plan."],
  };
  return values[outcome][language === "en" ? 1 : 0];
}

function EstimateContent({ estimate, language, onRefresh }: { estimate: NutritionEstimate; language: "fa" | "en"; onRefresh: () => void }) {
  const l = (fa: string, en: string) => language === "en" ? en : fa;
  const number = new Intl.NumberFormat(language === "en" ? "en-US" : "fa-IR", { maximumFractionDigits: 1 });
  const target = (metric: string) => estimate.targets[metric];
  const preferred = (metric: string) => formatValue(target(metric)?.preferred, target(metric)?.unit, number, language);
  const range = (metric: string) => formatRange(target(metric), number, language);
  const maximum = (metric: string) => formatValue(target(metric)?.maximum, target(metric)?.unit, number, language);
  const confidence = { high: l("اطمینان بالا", "High confidence"), medium: l("اطمینان متوسط", "Medium confidence"), low: l("اطمینان پایین", "Low confidence") }[estimate.confidence];

  return <>
    <section className="nutrition-estimate-summary" aria-label={l("خلاصه هدف‌ها", "Target summary")}>
      <article className="nutrition-calorie-card" aria-label={l("هدف انرژی روزانه", "Daily energy target")} role="region">
        <span>{l("هدف انرژی", "Energy target")}</span>
        <strong>{preferred("goal_calories")}</strong>
        <small>{l("میانگین روزانه", "daily average")}</small>
      </article>
      <div className="nutrition-confidence-card">
        <span className={`nutrition-confidence nutrition-confidence--${estimate.confidence}`}>{confidence}</span>
        <p>{l("هر تغییر مهم در وزن، فعالیت یا تمرین یک نسخه جدید می‌سازد.", "A material change in weight, activity, or exercise creates a new revision.")}</p>
        {estimate.is_stale && <button className="text-button" type="button" onClick={onRefresh}>{l("به‌روزرسانی برآورد", "Refresh estimate")}</button>}
      </div>
    </section>

    <section className="nutrition-target-grid nutrition-target-grid--primary fitsho-metric-strip" aria-label={l("درشت‌مغذی‌های اصلی", "Primary macronutrient targets")}>
      <TargetCard title={l("پروتئین", "Protein")} value={preferred("protein")} note={l(`حداقل ${formatValue(target("protein")?.minimum, target("protein")?.unit, number, language)}`, `Minimum ${formatValue(target("protein")?.minimum, target("protein")?.unit, number, language)}`)} />
      <TargetCard title={l("کربوهیدرات", "Carbohydrate")} value={range("carbohydrate")} note={l("بازه علمی روزانه", "Scientific daily range")} />
      <TargetCard title={l("چربی کل", "Total fat")} value={range("total_fat")} note={l("بازه علمی روزانه", "Scientific daily range")} />
    </section>

    <details className="nutrition-science-details">
      <summary>{l("جزئیات علمی و حدود ایمنی", "Scientific details and safety limits")}</summary>
      <div className="nutrition-target-grid nutrition-target-grid--secondary" aria-label={l("هدف‌های تغذیه تکمیلی", "Secondary nutrition targets")}>
        <TargetCard title={l("فیبر", "Fibre")} value={preferred("fibre")} note={l(`حداقل مطلق ${formatValue(target("fibre")?.minimum, target("fibre")?.unit, number, language)}`, `Absolute minimum ${formatValue(target("fibre")?.minimum, target("fibre")?.unit, number, language)}`)} />
        <TargetCard title={l("قند آزاد", "Free sugar")} value={maximum("free_sugar")} note={l(`حد ترجیحی ${formatValue(target("free_sugar")?.preferred_maximum, target("free_sugar")?.unit, number, language)}`, `Preferred limit ${formatValue(target("free_sugar")?.preferred_maximum, target("free_sugar")?.unit, number, language)}`)} />
        <TargetCard title={l("چربی اشباع", "Saturated fat")} value={maximum("saturated_fat")} note={l("حداکثر روزانه", "Daily maximum")} />
        <TargetCard title={l("چربی ترانس", "Trans fat")} value={maximum("trans_fat")} note={l("حداکثر روزانه", "Daily maximum")} />
        <TargetCard title={l("سدیم", "Sodium")} value={maximum("sodium")} note={l("حداکثر روزانه", "Daily maximum")} />
      </div>

      {estimate.micronutrients && Object.keys(estimate.micronutrients).length > 0 && <section className="nutrition-estimate-notes"><h2>{l("مرجع ریزمغذی‌ها", "Micronutrient references")}</h2><p>{l("کمتر بودن دریافت غذایی از مقدار مرجع، تشخیص کمبود بالینی نیست؛ این بخش فقط برای سنجش کفایت رژیم و ترمیم برنامه است.", "Dietary intake below a reference is not a clinical deficiency diagnosis; it is used only to assess diet adequacy and guide plan repair.")}</p><div className="nutrition-micronutrient-grid">{Object.entries(estimate.micronutrients).map(([code, item]) => <article key={code}><strong>{nutrientDisplayName(code, language)}</strong><span>{number.format(item.target_value)} {item.unit}</span><small>{item.reference_kind} · {l("اطمینان", "Confidence")}: {item.confidence}</small></article>)}</div></section>}

      <section className="nutrition-estimate-notes">
        <h2>{l("این اعداد چه معنایی دارند؟", "What these numbers mean")}</h2>
        <p>{l("این یک برآورد علمی است، نه تشخیص یا نسخه پزشکی. نتیجه واقعی با پایش وزن، انرژی و عملکرد اصلاح می‌شود.", "This is a scientific estimate, not a diagnosis or medical prescription. Real outcomes should refine it through weight, energy, and performance monitoring.")}</p>
        <p>{l("هدف انرژی با توجه به هدف بدنی انتخاب‌شده و سهم فعالیت روزانه و تمرین ساختاریافته تنظیم می‌شود؛ پروتئین و درشت‌مغذی‌ها سپس در همان محدوده علمی هماهنگ می‌شوند.", "Energy is adjusted for the selected body goal, daily activity, and structured exercise; protein and other macronutrients are then coordinated within scientific bounds.")}</p>
        <p>{l("قند افزوده جداگانه ردیابی می‌شود؛ برای محدودیت سلامتی، سقف قند آزاد معیار کنترل است.", "Added sugar is tracked separately; the free-sugar ceiling is the controlling health limit.")}</p>
        <dl><div><dt>{l("نسخه سیاست", "Policy version")}</dt><dd>{estimate.policy_version}</dd></div><div><dt>{l("نسخه فرمول", "Formula version")}</dt><dd>{estimate.formula_version}</dd></div><div><dt>{l("بازبینی", "Revision")}</dt><dd>{new Intl.NumberFormat(language === "en" ? "en-US" : "fa-IR").format(estimate.revision)}</dd></div></dl>
      </section>
    </details>
  </>;
}

function nutrientDisplayName(code: string, language: "fa" | "en") {
  const labels: Record<string, [string, string]> = { calcium_mg: ["کلسیم", "Calcium"], iron_mg: ["آهن", "Iron"], zinc_mg: ["روی", "Zinc"], vitamin_d_mcg: ["ویتامین D", "Vitamin D"], vitamin_b12_mcg: ["ویتامین B12", "Vitamin B12"], folate_mcg_dfe: ["فولات", "Folate"], potassium_mg: ["پتاسیم", "Potassium"], magnesium_mg: ["منیزیم", "Magnesium"] };
  return labels[code]?.[language === "en" ? 1 : 0] ?? code.replaceAll("_", " ");
}

function TargetCard({ title, value, note }: { title: string; value: string; note: string }) {
  return <article className="nutrition-target-card"><span>{title}</span><strong>{value}</strong><small>{note}</small></article>;
}

function formatValue(value: number | null | undefined, unit: string | undefined, number: Intl.NumberFormat, language: "fa" | "en"): string {
  if (value === null || value === undefined) return language === "en" ? "Not set" : "تعیین نشده";
  const localizedUnit = unit === "kcal/day" ? (language === "en" ? "kcal" : "کیلوکالری") : unit === "g/day" ? (language === "en" ? "g" : "گرم") : unit === "mg/day" ? (language === "en" ? "mg" : "میلی‌گرم") : unit ?? "";
  return `${number.format(value)} ${localizedUnit}`;
}

function formatRange(target: NutritionTarget | undefined, number: Intl.NumberFormat, language: "fa" | "en"): string {
  if (target?.minimum === null || target?.minimum === undefined || target.maximum === null) return language === "en" ? "Not set" : "تعیین نشده";
  const unit = target.unit === "g/day" ? (language === "en" ? "g" : "گرم") : target.unit;
  return `${number.format(target.minimum)}–${number.format(target.maximum)} ${unit}`;
}
