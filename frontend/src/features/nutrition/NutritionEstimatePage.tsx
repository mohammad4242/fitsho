import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { AppIcon } from "../../shared/AppIcon";
import { DualProgressRing } from "../../shared/DualProgressRing";
import { ProgressRing } from "../../shared/ProgressRing";
import * as nutritionApi from "./api";
import type {
  DailyTrackingSummary,
  NutritionEstimate,
  NutritionTarget,
  PlanComparison,
  WeeklyPlan,
  WeeklyPlanGeneration,
} from "./types";
import { useSynchronizedProgress } from "./useSynchronizedProgress";
import { WeeklyNutritionPlan } from "./WeeklyNutritionPlan";
import "./nutritionEstimate.css";

type ViewState = "loading" | "ready" | "empty" | "error";

export function NutritionEstimatePage() {
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage === "en" ? "en" : "fa";
  const [state, setState] = useState<ViewState>("loading");
  const [estimate, setEstimate] = useState<NutritionEstimate | null>(null);
  const [plan, setPlan] = useState<WeeklyPlan | null>(null);
  const [budgetPlan, setBudgetPlan] = useState<WeeklyPlan | null>(null);
  const [idealPlan, setIdealPlan] = useState<WeeklyPlan | null>(null);
  const [bundleId, setBundleId] = useState<string | null>(null);
  const [selectedPlanRole, setSelectedPlanRole] = useState<"budget" | "ideal" | null>(null);
  const [isSelectingPlan, setIsSelectingPlan] = useState(false);
  const [comparison, setComparison] = useState<PlanComparison | null>(null);
  const [tracking, setTracking] = useState<DailyTrackingSummary | null>(null);
  const [planOutcome, setPlanOutcome] = useState<WeeklyPlanGeneration | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const l = (fa: string, en: string) => language === "en" ? en : fa;

  useEffect(() => {
    let active = true;
    void Promise.all([
      nutritionApi.getCurrentNutritionEstimate(),
      nutritionApi.getLatestWeeklyNutritionPlan(),
      nutritionApi.getDailyTracking(new Date().toISOString().slice(0, 10)).catch(() => null),
      nutritionApi.getLatestPlanBundle().catch(() => null),
    ])
      .then(([result, latestPlan, dailyTracking, latestBundle]) => {
        if (!active) return;
        setEstimate(result);
        setTracking(dailyTracking);

        if (
          latestBundle &&
          latestBundle.bundle_id &&
          !latestBundle.selected_plan_id &&
          latestBundle.comparison?.show_ideal_plan &&
          latestBundle.ideal_plan &&
          latestBundle.budget_plan
        ) {
          setBundleId(latestBundle.bundle_id);
          setBudgetPlan(latestBundle.budget_plan);
          setIdealPlan(latestBundle.ideal_plan);
          setComparison(latestBundle.comparison);
          setSelectedPlanRole(null);
          setPlan(latestBundle.budget_plan);
        } else {
          setPlan(latestPlan);
        }
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

  function handleSelectPlan(role: "budget" | "ideal") {
    if (!bundleId) return;
    setIsSelectingPlan(true);
    void nutritionApi.selectBundlePlan(bundleId, { selected_plan_role: role })
      .then((resp) => {
        setSelectedPlanRole(role);
        setPlan(resp.plan);
        setComparison(null);
        setBudgetPlan(null);
        setIdealPlan(null);
        setFeedbackMessage(
          role === "ideal"
            ? l("برنامه ایده‌آل برای شما فعال و اجرا شد.", "Ideal plan activated and set as your active plan.")
            : l("برنامه با بودجه شما فعال و اجرا شد.", "Budget plan activated and set as your active plan.")
        );
      })
      .catch((err) => {
        console.error("Failed to select plan:", err);
      })
      .finally(() => setIsSelectingPlan(false));
  }

  function generatePlan() {
    if (generatingPlan) return;
    setGeneratingPlan(true);
    setPlanOutcome(null);
    setFeedbackMessage(null);
    void nutritionApi.createWeeklyNutritionPlan()
      .then((result) => {
        setPlanOutcome(result);
        const resolvedPlan = result.budget_plan ?? result.plan ?? null;
        if (result.outcome === "success" && resolvedPlan !== null) {
          setBundleId(result.bundle_id ?? null);
          const isTwoPlan = Boolean(result.comparison?.show_ideal_plan && result.ideal_plan);
          const resolvedRole = (result.selected_plan_role as "budget" | "ideal" | null) ?? (isTwoPlan ? null : "budget");
          setSelectedPlanRole(resolvedRole);
          setBudgetPlan(result.budget_plan ?? result.plan ?? null);
          setIdealPlan(result.ideal_plan ?? null);
          setPlan(result.plan ?? resolvedPlan);
          setComparison(result.comparison ?? null);
          setFeedbackMessage(l("برنامه با اطلاعات جدیدت ساخته شد.", "Plan rebuilt with your latest details."));
          void nutritionApi.getCurrentNutritionEstimate()
            .then((updatedEstimate) => {
              if (updatedEstimate !== null) {
                setEstimate(updatedEstimate);
              }
            })
            .catch(() => {});
        }
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
        <div><p className="eyebrow eyebrow--accent">{l("امروز", "Today")}</p><h1 className="fitsho-display">{l("تغذیه", "Nutrition")}</h1></div>
        <nav className="nutrition-estimate-tools" aria-label={l("ابزارهای تغذیه", "Nutrition tools")}>
          <Link className="nutrition-tool-link nutrition-tool-link--primary" to="/nutrition-tracking"><strong>{l("ثبت تغذیه", "Track food")}</strong><small>{l("دستی یا با عکس", "Manual or photo")}</small></Link>
          <Link className="nutrition-tool-link" to="/food-catalogue"><strong>{l("کاتالوگ", "Catalogue")}</strong><small>{l("مرجع مواد غذایی", "Food reference")}</small></Link>
        </nav>
      </section>

      {state === "loading" && <p className="nutrition-estimate-state" role="status">{calculating ? l("در حال محاسبه…", "Calculating…") : l("در حال دریافت برآورد…", "Loading estimate…")}</p>}
      {state === "empty" && <section className="nutrition-estimate-state"><h2>{l("هنوز برآوردی ثبت نشده", "No estimate yet")}</h2><p>{l("اطلاعات پروفایل فعلی را به یک برآورد شفاف تبدیل کن.", "Turn your current profile into a transparent estimate.")}</p><button className="primary-button" type="button" onClick={calculate}>{l("محاسبه هدف‌ها", "Calculate targets")}</button></section>}
      {state === "error" && <section className="nutrition-estimate-state" role="alert"><h2>{l("محاسبه انجام نشد", "Estimate unavailable")}</h2><p>{l("اطلاعات ضروری یا وضعیت ایمنی را در پروفایل بررسی کن.", "Review required profile details and your safety status.")}</p><Link className="secondary-button" to="/profile">{l("رفتن به پروفایل", "Open profile")}</Link></section>}
      {state === "ready" && estimate !== null && (
        <>
          <EstimateContent estimate={estimate} language={language} onRefresh={calculate} plan={plan} tracking={tracking} />
          <DoctorSupervision language={language} plan={plan} />
          <PlanArea
            bundleId={bundleId}
            budgetPlan={budgetPlan}
            comparison={comparison}
            feedbackMessage={feedbackMessage}
            generating={generatingPlan}
            idealPlan={idealPlan}
            isSelectingPlan={isSelectingPlan}
            language={language}
            onGenerate={generatePlan}
            onSelectPlan={handleSelectPlan}
            outcome={planOutcome}
            plan={plan}
            selectedPlanRole={selectedPlanRole}
          />
        </>
      )}
    </main>
  );
}

function PlanArea({
  bundleId,
  budgetPlan,
  comparison,
  feedbackMessage,
  generating,
  idealPlan,
  isSelectingPlan,
  language,
  onGenerate,
  onSelectPlan,
  outcome,
  plan,
  selectedPlanRole = null,
}: {
  bundleId?: string | null;
  budgetPlan?: WeeklyPlan | null;
  comparison: PlanComparison | null;
  feedbackMessage?: string | null;
  generating: boolean;
  idealPlan: WeeklyPlan | null;
  isSelectingPlan?: boolean;
  language: "fa" | "en";
  onGenerate: () => void;
  onSelectPlan?: (role: "budget" | "ideal") => void;
  outcome: WeeklyPlanGeneration | null;
  plan: WeeklyPlan | null;
  selectedPlanRole?: "budget" | "ideal" | null;
}) {
  const l = (fa: string, en: string) => language === "en" ? en : fa;
  const number = new Intl.NumberFormat(language === "en" ? "en-US" : "fa-IR", {
    maximumFractionDigits: 1,
  });

  if (plan !== null) {
    const isTwoPlan = comparison?.show_ideal_plan && idealPlan !== null;
    const activeBudgetPlan = budgetPlan ?? plan;
    return (
      <div className="weekly-plan-area-container">
        {comparison && (
          <PlanComparisonSection
            bundleId={bundleId}
            comparison={comparison}
            isSelectingPlan={isSelectingPlan}
            language={language}
            onSelectPlan={onSelectPlan}
            selectedPlanRole={selectedPlanRole}
          />
        )}
        {isTwoPlan ? (
          <div className="weekly-plans-dual-container">
            <details className="weekly-plan-accordion" open={selectedPlanRole === "budget" || selectedPlanRole === null}>
              <summary className="weekly-plan-accordion__summary">
                <span>
                  {l("برنامه پیشنهادی با بودجه شما", "Recommended Plan with Your Budget")}
                  {selectedPlanRole === "budget" && ` (${l("برنامه فعال شما", "Active Plan")})`}
                </span>
                <span className="weekly-plan-accordion__chevron" aria-hidden="true">▾</span>
              </summary>
              <WeeklyNutritionPlan
                isReferencePlan={selectedPlanRole === "ideal"}
                language={language}
                plan={activeBudgetPlan}
                title={l("برنامه پیشنهادی با بودجه شما", "Recommended Plan with Your Budget")}
              />
            </details>
            <details className="weekly-plan-accordion" open={selectedPlanRole === "ideal"}>
              <summary className="weekly-plan-accordion__summary">
                <span>
                  {l("برنامه ایده‌آل", "Ideal Plan")}
                  {selectedPlanRole === "ideal" && ` (${l("برنامه فعال شما", "Active Plan")})`}
                </span>
                <span className="weekly-plan-accordion__chevron" aria-hidden="true">▾</span>
              </summary>
              <WeeklyNutritionPlan
                isReferencePlan={selectedPlanRole !== "ideal"}
                language={language}
                plan={idealPlan}
                title={l("برنامه ایده‌آل", "Ideal Plan")}
              />
            </details>
          </div>
        ) : (
          <WeeklyNutritionPlan
            language={language}
            plan={plan}
            title={plan.plan_role === "ideal" ? l("برنامه ایده‌آل", "Ideal Plan") : (comparison ? l("برنامه پیشنهادی با بودجه شما", "Recommended Plan with Your Budget") : undefined)}
          />
        )}
        <PlanRegenerateAction
          feedbackMessage={feedbackMessage}
          generating={generating}
          language={language}
          onGenerate={onGenerate}
          outcome={outcome}
        />
      </div>
    );
  }

  const generation = outcome === null
    ? null
    : generationMessage(outcome.outcome, outcome.reason_codes, language);
  return (
    <section className="weekly-plan-empty" aria-label={l("ساخت برنامه تغذیه هفتگی", "Build weekly nutrition plan")}>
      {generation !== null && <p className="weekly-plan-empty__message" role="status">{generation.message}</p>}
      {generation !== null && generation.reasons.length > 0 && (
        <ul>
          {generation.reasons.map((reason) => <li key={reason}>{reason}</li>)}
        </ul>
      )}
      {outcome?.comparison?.minimum_feasible_monthly_cost_irr != null && (
        <div className="weekly-plan-budget-infeasible-details">
          <p>
            {l("بودجه شما: ", "Your budget: ")}
            <strong>{formatTomanOrMillion(outcome.comparison.user_monthly_budget_irr, language, number)}</strong>
          </p>
          <p>
            {l("حداقل هزینه تخمینی برنامه قابل‌اجرا: حدود ", "Estimated minimum feasible plan cost: approximately ")}
            <strong>{formatTomanOrMillion(outcome.comparison.minimum_feasible_monthly_cost_irr, language, number)}</strong>
          </p>
        </div>
      )}
      <button className="primary-button" disabled={generating} onClick={onGenerate} type="button">
        {generating ? l("در حال ساخت برنامه…", "Building plan…") : l("ساخت برنامه تغذیه هفتگی", "Build weekly nutrition plan")}
      </button>
    </section>
  );
}

function PlanRegenerateAction({
  feedbackMessage,
  generating,
  language,
  onGenerate,
  outcome,
}: {
  feedbackMessage?: string | null;
  generating: boolean;
  language: "fa" | "en";
  onGenerate: () => void;
  outcome: WeeklyPlanGeneration | null;
}) {
  const l = (fa: string, en: string) => (language === "en" ? en : fa);
  const isFailed = outcome !== null && outcome.outcome !== "success";
  const failureInfo = isFailed
    ? generationMessage(outcome.outcome, outcome.reason_codes, language)
    : null;

  return (
    <section
      className="nutrition-plan-regenerate"
      aria-label={l("ساخت مجدد برنامه غذایی", "Rebuild weekly nutrition plan")}
    >
      <div className="nutrition-plan-regenerate__content">
        <div className="nutrition-plan-regenerate__header">
          <span className="nutrition-plan-regenerate__icon-wrap" aria-hidden="true">
            <AppIcon
              name="refresh"
              className={`nutrition-plan-regenerate__icon ${generating ? "is-spinning" : ""}`}
            />
          </span>
          <div className="nutrition-plan-regenerate__text">
            <h3>{l("ساخت مجدد برنامه غذایی", "Rebuild weekly nutrition plan")}</h3>
            <p>
              {l(
                "اگر اطلاعاتت را تغییر داده‌ای، برنامه با اطلاعات جدیدت دوباره ساخته می‌شود.",
                "If you updated your details, the plan will be rebuilt with your latest information.",
              )}
            </p>
          </div>
        </div>
        <button
          className={`nutrition-plan-regenerate__button ${generating ? "is-loading" : ""}`}
          disabled={generating}
          onClick={onGenerate}
          type="button"
          aria-busy={generating}
        >
          <AppIcon
            name="refresh"
            className={`nutrition-plan-regenerate__btn-icon ${generating ? "is-spinning" : ""}`}
          />
          <span>
            {generating
              ? l("در حال ساخت مجدد برنامه…", "Rebuilding plan…")
              : l("ساخت مجدد برنامه", "Rebuild plan")}
          </span>
        </button>
      </div>

      {feedbackMessage && (
        <p className="nutrition-plan-regenerate__feedback" role="status">
          {feedbackMessage}
        </p>
      )}

      {isFailed && (
        <div className="nutrition-plan-regenerate__error" role="alert">
          <p className="nutrition-plan-regenerate__error-notice">
            {l(
              "ساخت برنامه جدید کامل نشد؛ برنامه فعلی شما تغییری نکرد.",
              "Could not complete new plan; your current plan remains unchanged.",
            )}
          </p>
          {failureInfo?.message && (
            <p className="nutrition-plan-regenerate__error-message">{failureInfo.message}</p>
          )}
          {failureInfo && failureInfo.reasons.length > 0 && (
            <ul className="nutrition-plan-regenerate__reasons">
              {failureInfo.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

function formatTomanOrMillion(
  irr: number,
  language: "fa" | "en",
  numberFormatter: Intl.NumberFormat,
): string {
  const toman = irr / 10;
  if (toman >= 1_000_000) {
    const millions = toman / 1_000_000;
    const formatted = numberFormatter.format(millions);
    return language === "en" ? `${formatted} million Toman` : `${formatted} میلیون تومان`;
  }
  return language === "en" ? `${numberFormatter.format(toman)} Toman` : `${numberFormatter.format(toman)} تومان`;
}

function PlanComparisonSection({
  bundleId,
  comparison,
  isSelectingPlan,
  language,
  onSelectPlan,
  selectedPlanRole = null,
}: {
  bundleId?: string | null;
  comparison: PlanComparison;
  isSelectingPlan?: boolean;
  language: "fa" | "en";
  onSelectPlan?: (role: "budget" | "ideal") => void;
  selectedPlanRole?: "budget" | "ideal" | null;
}) {
  const l = (fa: string, en: string) => language === "en" ? en : fa;
  const number = new Intl.NumberFormat(language === "en" ? "en-US" : "fa-IR", {
    maximumFractionDigits: 1,
  });

  const proteinDifference = comparison.protein_gap?.difference
    ?? (comparison.protein_gap_g_per_day != null ? Number(comparison.protein_gap_g_per_day) : null);
  const proteinBudgetVal = comparison.protein_gap?.budget_value;
  const proteinIdealVal = comparison.protein_gap?.ideal_value;
  const proteinTargetVal = comparison.protein_gap?.target_value;

  return (
    <section className="nutrition-plan-comparison-card" aria-label={l("مقایسه برنامه‌ها", "Plan comparison")}>
      <header className="nutrition-plan-comparison-header">
        <div className="nutrition-plan-comparison-title-wrap">
          <span className="nutrition-plan-comparison-icon" aria-hidden="true">📊</span>
          <h3>{l("خلاصه بودجه و مقایسه", "Budget summary and comparison")}</h3>
        </div>
        {comparison.show_ideal_plan && (
          <span className="nutrition-plan-comparison-badge">
            {l("۲ برنامه محاسبه‌شده", "2 Computed Plans")}
          </span>
        )}
      </header>

      {comparison.show_ideal_plan && Boolean(bundleId) && Boolean(onSelectPlan) && (
        <div className="nutrition-bundle-selection-area">
          {selectedPlanRole === null && (
            <div className="nutrition-bundle-selection-prompt" role="status">
              <span className="nutrition-bundle-selection-prompt__icon" aria-hidden="true">👉</span>
              <strong>
                {l(
                  "دو نسخه برنامه برای شما آماده شده است؛ لطفاً یکی از دو گزینه زیر را برای فعال‌سازی انتخاب کنید:",
                  "Two plan versions are ready. Please select one of the options below to activate it:"
                )}
              </strong>
            </div>
          )}
          <div className="nutrition-bundle-selection-cards">
            <div
              className={`nutrition-bundle-card ${selectedPlanRole === "budget" ? "is-selected" : ""}`}
            >
              <div className="nutrition-bundle-card__header">
                <div className="nutrition-bundle-card__title-group">
                  <h4 className="nutrition-bundle-card__title">{l("برنامه بودجه‌ای", "Budget Plan")}</h4>
                  <p className="nutrition-bundle-card__subtitle">
                    {l("بهترین کیفیت در محدوده بودجه شما", "Best quality within your budget")}
                  </p>
                </div>
                {selectedPlanRole === "budget" ? (
                  <span className="nutrition-bundle-card__badge">
                    <span className="nutrition-bundle-card__badge-dot" aria-hidden="true" />
                    {l("فعال", "Active")}
                  </span>
                ) : null}
              </div>
              <div className="nutrition-bundle-card__cost-row">
                <span className="nutrition-bundle-card__cost-label">{l("هزینه ماهانه: ", "Monthly cost: ")}</span>
                <strong className="nutrition-bundle-card__cost-val">
                  {comparison.budget_plan_monthly_cost_irr != null
                    ? formatTomanOrMillion(comparison.budget_plan_monthly_cost_irr, language, number)
                    : "—"}
                </strong>
              </div>
              <div className="nutrition-bundle-card__pills">
                {proteinBudgetVal != null && (
                  <span className="nutrition-bundle-card__pill">
                    {number.format(proteinBudgetVal)} g {l("پروتئین/روز", "protein/day")}
                  </span>
                )}
                {comparison.unique_meal_count_budget != null && (
                  <span className="nutrition-bundle-card__pill">
                    {number.format(comparison.unique_meal_count_budget)} {l("وعده", "meals")}
                  </span>
                )}
                {comparison.unique_protein_sources_budget != null && (
                  <span className="nutrition-bundle-card__pill">
                    {number.format(comparison.unique_protein_sources_budget)} {l("منبع پروتئین", "protein sources")}
                  </span>
                )}
              </div>
              <button
                className={selectedPlanRole === "budget" ? "secondary-button is-active nutrition-bundle-card__action" : "primary-button nutrition-bundle-card__action"}
                disabled={selectedPlanRole === "budget" || isSelectingPlan}
                onClick={() => onSelectPlan?.("budget")}
                type="button"
              >
                {selectedPlanRole === "budget" ? l("برنامه فعال شما", "Active Plan") : l("انتخاب این برنامه", "Select this plan")}
              </button>
            </div>

            <div
              className={`nutrition-bundle-card ${selectedPlanRole === "ideal" ? "is-selected" : ""}`}
            >
              <div className="nutrition-bundle-card__header">
                <div className="nutrition-bundle-card__title-group">
                  <h4 className="nutrition-bundle-card__title">{l("برنامه ایده‌آل", "Ideal Plan")}</h4>
                  <p className="nutrition-bundle-card__subtitle">
                    {l("پروتئین بالاتر، تنوع بیشتر، هدف‌محور", "Higher protein, more variety, goal-first")}
                  </p>
                </div>
                {selectedPlanRole === "ideal" ? (
                  <span className="nutrition-bundle-card__badge">
                    <span className="nutrition-bundle-card__badge-dot" aria-hidden="true" />
                    {l("فعال", "Active")}
                  </span>
                ) : null}
              </div>
              <div className="nutrition-bundle-card__cost-row">
                <span className="nutrition-bundle-card__cost-label">{l("هزینه ماهانه: ", "Monthly cost: ")}</span>
                <strong className="nutrition-bundle-card__cost-val">
                  {comparison.ideal_plan_monthly_cost_irr != null
                    ? formatTomanOrMillion(comparison.ideal_plan_monthly_cost_irr, language, number)
                    : "—"}
                </strong>
              </div>
              <div className="nutrition-bundle-card__pills">
                {proteinIdealVal != null && (
                  <span className="nutrition-bundle-card__pill">
                    {number.format(proteinIdealVal)} g {l("پروتئین/روز", "protein/day")}
                  </span>
                )}
                {comparison.unique_meal_count_ideal != null && (
                  <span className="nutrition-bundle-card__pill">
                    {number.format(comparison.unique_meal_count_ideal)} {l("وعده", "meals")}
                  </span>
                )}
                {comparison.unique_protein_sources_ideal != null && (
                  <span className="nutrition-bundle-card__pill">
                    {number.format(comparison.unique_protein_sources_ideal)} {l("منبع پروتئین", "protein sources")}
                  </span>
                )}
              </div>
              <button
                className={selectedPlanRole === "ideal" ? "secondary-button is-active nutrition-bundle-card__action" : "primary-button nutrition-bundle-card__action"}
                disabled={selectedPlanRole === "ideal" || isSelectingPlan}
                onClick={() => onSelectPlan?.("ideal")}
                type="button"
              >
                {selectedPlanRole === "ideal" ? l("برنامه فعال شما", "Active Plan") : l("انتخاب این برنامه", "Select this plan")}
              </button>
            </div>
          </div>
        </div>
      )}

      {comparison.show_ideal_plan ? (
        <div className="nutrition-plan-comparison-dual-content">
          <div className="nutrition-plan-comparison-table-wrap">
            <h4 className="nutrition-plan-comparison-section-subtitle">
              {l("جدول مقایسه برنامه‌ها", "Plan Comparison Table")}
            </h4>
            <table className="nutrition-plan-comparison-table">
              <thead>
                <tr>
                  <th scope="col">{l("شاخص", "Metric")}</th>
                  <th scope="col">{l("هدف / بودجه شما", "Your Target / Budget")}</th>
                  <th scope="col">{l("برنامه با بودجه شما", "Plan with Your Budget")}</th>
                  <th scope="col">{l("برنامه ایده‌آل", "Ideal Plan")}</th>
                </tr>
              </thead>
              <tbody>
                {/* Row 1: Monthly Cost */}
                <tr>
                  <td className="nutrition-comparison-table__metric-cell">
                    <span className="metric-icon" aria-hidden="true">💰</span>
                    <span>{l("هزینه ماهیانه", "Monthly Cost")}</span>
                  </td>
                  <td>
                    <span className="comparison-table__target-badge">
                      {formatTomanOrMillion(comparison.user_monthly_budget_irr, language, number)}
                    </span>
                  </td>
                  <td>
                    <strong className="comparison-table__val">
                      {comparison.budget_plan_monthly_cost_irr != null
                        ? formatTomanOrMillion(comparison.budget_plan_monthly_cost_irr, language, number)
                        : "—"}
                    </strong>
                  </td>
                  <td>
                    <strong className="comparison-table__val comparison-table__val--ideal">
                      {comparison.ideal_plan_monthly_cost_irr != null
                        ? formatTomanOrMillion(comparison.ideal_plan_monthly_cost_irr, language, number)
                        : "—"}
                    </strong>
                  </td>
                </tr>

                {/* Row 2: Daily Protein */}
                <tr>
                  <td className="nutrition-comparison-table__metric-cell">
                    <span className="metric-icon" aria-hidden="true">🥩</span>
                    <span>{l("پروتئین روزانه", "Daily Protein")}</span>
                  </td>
                  <td>
                    <span className="comparison-table__target-badge">
                      {proteinTargetVal != null
                        ? `${number.format(proteinTargetVal)} ${l("گرم/روز", "g/day")}`
                        : (proteinIdealVal != null ? `${number.format(proteinIdealVal)} ${l("گرم/روز", "g/day")}` : "—")}
                    </span>
                  </td>
                  <td>
                    <strong className="comparison-table__val">
                      {proteinBudgetVal != null ? `${number.format(proteinBudgetVal)} ${l("گرم/روز", "g/day")}` : "—"}
                    </strong>
                  </td>
                  <td>
                    <strong className="comparison-table__val comparison-table__val--ideal">
                      {proteinIdealVal != null ? `${number.format(proteinIdealVal)} ${l("گرم/روز", "g/day")}` : "—"}
                    </strong>
                  </td>
                </tr>

                {/* Row 3: Meal Variety (if available) */}
                {(comparison.unique_meal_count_budget != null || comparison.unique_meal_count_ideal != null) && (
                  <tr>
                    <td className="nutrition-comparison-table__metric-cell">
                      <span className="metric-icon" aria-hidden="true">🥗</span>
                      <span>{l("تنوع وعده‌ها", "Meal Variety")}</span>
                    </td>
                    <td>
                      <span className="comparison-table__muted">—</span>
                    </td>
                    <td>
                      <strong className="comparison-table__val">
                        {comparison.unique_meal_count_budget != null
                          ? `${number.format(comparison.unique_meal_count_budget)} ${l("وعده", "meals")}`
                          : "—"}
                      </strong>
                    </td>
                    <td>
                      <strong className="comparison-table__val comparison-table__val--ideal">
                        {comparison.unique_meal_count_ideal != null
                          ? `${number.format(comparison.unique_meal_count_ideal)} ${l("وعده", "meals")}`
                          : "—"}
                      </strong>
                    </td>
                  </tr>
                )}

                {/* Row 4: Protein Sources (if available) */}
                {(comparison.unique_protein_sources_budget != null || comparison.unique_protein_sources_ideal != null) && (
                  <tr>
                    <td className="nutrition-comparison-table__metric-cell">
                      <span className="metric-icon" aria-hidden="true">🐟</span>
                      <span>{l("منابع پروتئینی", "Protein Sources")}</span>
                    </td>
                    <td>
                      <span className="comparison-table__muted">—</span>
                    </td>
                    <td>
                      <strong className="comparison-table__val">
                        {comparison.unique_protein_sources_budget != null
                          ? `${number.format(comparison.unique_protein_sources_budget)} ${l("منبع", "sources")}`
                          : "—"}
                      </strong>
                    </td>
                    <td>
                      <strong className="comparison-table__val comparison-table__val--ideal">
                        {comparison.unique_protein_sources_ideal != null
                          ? `${number.format(comparison.unique_protein_sources_ideal)} ${l("منبع", "sources")}`
                          : "—"}
                      </strong>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="nutrition-comparison-detailed-explanation">
            <div className="comparison-detail-card comparison-detail-card--budget">
              <div className="comparison-detail-card__header">
                <span className="comparison-detail-card__icon" aria-hidden="true">🛡️</span>
                <h4>{l("رعایت استانداردها و حداقل‌های علمی در برنامه بودجه‌ای", "Safety Baselines & Minimums in Budget Plan")}</h4>
              </div>
              <p>
                {l(
                  `برنامه با بودجه با دقت داخل سقف ${formatTomanOrMillion(comparison.user_monthly_budget_irr, language, number)} شما بهینه شده است. در این برنامه تمامی حداقل‌های علمی و بیولوژیک ضروری (شامل کف استاندارد پروتئین روزانه${proteinBudgetVal != null ? ` به میزان ${number.format(proteinBudgetVal)} گرم` : ""}، کالری مورد نیاز پایه و نیازهای ضروری سوخت‌وساز) کاملاً رعایت شده‌اند تا بدون هرگونه ریسک سلامتی یا افت کیفیت بیولوژیک، برنامه‌ای سالم، پایدار و اقتصادی داشته باشید.`,
                  `The budget plan is precisely optimized within your ${formatTomanOrMillion(comparison.user_monthly_budget_irr, language, number)} ceiling. All essential scientific baselines—including the required daily protein floor${proteinBudgetVal != null ? ` of ${number.format(proteinBudgetVal)} g` : ""}, baseline caloric demand, and metabolic safety needs—are strictly satisfied, ensuring a healthy, sustainable, and risk-free nutritional foundation without financial strain.`
                )}
              </p>
            </div>

            <div className="comparison-detail-card comparison-detail-card--ideal">
              <div className="comparison-detail-card__header">
                <span className="comparison-detail-card__icon" aria-hidden="true">🚀</span>
                <h4>{l("تفاوت‌ها و مزیت‌های برنامه ایده‌آل (مرجع)", "Advantages & Differences in Ideal Plan")}</h4>
              </div>
              <p>
                {l(
                  `برنامه ایده‌آل با هزینه ماهانه حدود ${comparison.ideal_plan_monthly_cost_irr != null ? formatTomanOrMillion(comparison.ideal_plan_monthly_cost_irr, language, number) : "—"} (حدود ${comparison.monthly_cost_gap_irr != null ? formatTomanOrMillion(comparison.monthly_cost_gap_irr, language, number) : "—"} تفاوت با بودجه شما)، روی اوج بهره‌وری و شتاب ورزشی تمرکز دارد. این برنامه پروتئین روزانه را به ${proteinIdealVal != null ? `${number.format(proteinIdealVal)} گرم` : "—"}${proteinTargetVal != null ? ` (منطبق بر هدف کامل ${number.format(proteinTargetVal)} گرم)` : ""}${proteinDifference != null && proteinDifference > 0 ? ` و حدود ${number.format(proteinDifference)} گرم بیشتر از برنامه بودجه‌ای` : ""} می‌رساند و با بهره‌گیری از منابع پروتئینی مرغوب‌تر و تنوع بیشتر وعده‌ها، مسیر دستیابی به هدف را سریع‌تر و پایبندی غذایی را لذت‌بخش‌تر می‌کند.`,
                  `The ideal reference plan costs ~${comparison.ideal_plan_monthly_cost_irr != null ? formatTomanOrMillion(comparison.ideal_plan_monthly_cost_irr, language, number) : "—"} (a ~${comparison.monthly_cost_gap_irr != null ? formatTomanOrMillion(comparison.monthly_cost_gap_irr, language, number) : "—"} monthly difference), focusing on optimal athletic velocity. It lifts daily protein intake to ${proteinIdealVal != null ? `${number.format(proteinIdealVal)} g` : "—"}${proteinTargetVal != null ? ` (fully matching your target of ${number.format(proteinTargetVal)} g)` : ""}${proteinDifference != null && proteinDifference > 0 ? ` (~${number.format(proteinDifference)} g more than budget plan)` : ""}, using premium protein sources and broader variety to accelerate recovery and make long-term consistency effortless.`
                )}
              </p>
            </div>

            <div className="comparison-detail-card comparison-detail-card--guidance">
              <div className="comparison-detail-card__header">
                <span className="comparison-detail-card__icon" aria-hidden="true">💡</span>
                <h4>{l("راهنمای انتخاب برای شما", "Decision Guidance for You")}</h4>
              </div>
              <p>
                {l(
                  "اگر حفظ دقیق سقف بودجه اولویت اصلی شماست، برنامه با بودجه کاملاً پاسخگوی نیازهای فیزیکی و ورزشی شما خواهد بود و جای نگرانی ندارد. در صورتی که امکان افزایش بودجه را دارید و به دنبال ریکاوری سریع‌تر، حداکثر رشد عضلانی و تنوع بالاتر غذایی هستید، می‌توانید برنامه ایده‌آل را انتخاب نمایید.",
                  "If budget predictability is your primary priority, the budget plan completely satisfies your physiological and training requirements. If your financial leeway allows higher investment and you aim for accelerated recovery, maximal muscle synthesis, and richer variety, you can choose the ideal plan with confidence."
                )}
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="nutrition-plan-comparison-bottom-row">
          <div className="nutrition-plan-comparison-metrics-col">
            <div className="nutrition-plan-comparison-grid">
              <div className="nutrition-plan-comparison-item">
                <span className="comparison-item-label">{l("بودجه ماهانه شما", "Your monthly budget")}</span>
                <strong className="comparison-item-val">{formatTomanOrMillion(comparison.user_monthly_budget_irr, language, number)}</strong>
              </div>
              <div className="nutrition-plan-comparison-item">
                <span className="comparison-item-label">{l("هزینه تقریبی برنامه", "Estimated plan cost")}</span>
                <strong className="comparison-item-val">
                  {comparison.budget_plan_monthly_cost_irr != null
                    ? formatTomanOrMillion(comparison.budget_plan_monthly_cost_irr, language, number)
                    : "—"}
                </strong>
              </div>
            </div>
          </div>

          <div className="plan-comparison-explanation">
            <div className="plan-comparison-explanation__header">
              <span className="plan-comparison-explanation__icon" aria-hidden="true">⚡</span>
              <h4>{l("تفاوت برنامه‌ها", "Plan difference")}</h4>
            </div>
            {comparison.monthly_cost_gap_irr != null && comparison.monthly_cost_gap_irr < 10_000_000 ? (
              <p className="plan-comparison-explanation__body">
                {l(
                  "بودجه شما با برنامه ایده‌آل فاصله کمی دارد؛ یک برنامه نمایش داده می‌شود.",
                  "Your budget is close to the ideal plan cost — only one plan shown.",
                )}
              </p>
            ) : (
              <p className="plan-comparison-explanation__body">
                {l(
                  "اختلاف کیفیت چشمگیر نبود؛ بهترین گزینه با بودجه شما نمایش داده می‌شود.",
                  "No meaningful quality gap — the best option within your budget is shown.",
                )}
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function DoctorSupervision({ language, plan }: { language: "fa" | "en"; plan: WeeklyPlan | null }) {
  const l = (fa: string, en: string) => language === "en" ? en : fa;
  const pendingStatuses = new Set(["pending", "pending_physician_review", "physician_review_in_progress", "awaiting_lab_information"]);
  const isPending = plan !== null
    && !plan.physician_approved
    && (pendingStatuses.has(plan.review_status) || pendingStatuses.has(plan.lifecycle_status));
  const isApproved = plan?.physician_approved === true || ["physician_approved", "active"].includes(plan?.lifecycle_status ?? "");
  const approvalCopy = plan === null
    ? l("پس از ساخت برنامه", "After plan creation")
    : isPending
      ? l("در انتظار تأیید پزشک", "Pending physician approval")
      : isApproved
        ? l("تأییدشده توسط پزشک", "Physician approved")
        : l("نیازمند بررسی", "Review required");
  const guidanceCopy = plan?.physician_user_visible_notes
    ?? (isPending
      ? l("پس از بررسی پزشک", "After physician review")
      : l("راهنمایی ثبت نشده", "No guidance recorded"));

  return (
    <section className="nutrition-doctor-supervision" aria-labelledby="nutrition-doctor-title">
      <details className="nutrition-doctor-accordion">
        <summary className="nutrition-doctor-accordion__summary">
          <div className="nutrition-doctor-accordion__lead">
            <span className="nutrition-doctor-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="7" r="3" />
                <path d="M7 21v-3a5 5 0 0 1 10 0v3M4 13v3a3 3 0 0 0 6 0v-3M4 13V9M10 13V9M18 13v3" />
                <circle cx="18" cy="18" r="2" />
              </svg>
            </span>
            <div className="nutrition-doctor-accordion__titles">
              <h2 id="nutrition-doctor-title">{l("تحت نظر پزشک", "Doctor supervision")}</h2>
              <p>{l("خدمات و وضعیت بررسی پزشکی در یک نگاه", "Medical services and review status at a glance")}</p>
            </div>
          </div>
          <div className="nutrition-doctor-accordion__trailing">
            {isPending && (
              <span className="nutrition-doctor-header-status">
                <i />{l("در انتظار پزشک", "Pending physician")}
              </span>
            )}
            <span className="nutrition-doctor-accordion__chevron" aria-hidden="true">▾</span>
          </div>
        </summary>
        <div className="nutrition-doctor-grid">
          <Link className="nutrition-doctor-item nutrition-doctor-item--link nutrition-doctor-item--supplements" to="/nutrition-supplements">
            <span className="nutrition-doctor-item__symbol nutrition-doctor-item__symbol--supplements" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                <path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z" />
                <path d="m8.5 8.5 7 7" />
              </svg>
            </span>
            <span className="nutrition-doctor-item__content">
              <span className="nutrition-doctor-item__header-row">
                <strong>{l("مکمل‌های من", "My supplements")}</strong>
                <span className="nutrition-doctor-item__tag">{l("تجویز و پیگیری", "Prescription")}</span>
              </span>
              <small>{l("دستورها و پیگیری مکمل‌ها", "Supplement orders and tracking")}</small>
            </span>
            <b className="nutrition-doctor-item__chevron" aria-hidden="true">‹</b>
          </Link>

          <article className="nutrition-doctor-item">
            <span className="nutrition-doctor-item__symbol nutrition-doctor-item__symbol--approved" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6 9 17l-5-5" />
              </svg>
            </span>
            <span className="nutrition-doctor-item__content">
              <strong>{l("تأیید برنامه غذایی", "Nutrition plan approval")}</strong>
              <small className={isPending ? "nutrition-doctor-status--pending" : undefined}>
                {isPending && <i />}
                {approvalCopy}
              </small>
            </span>
          </article>

          <Link className="nutrition-doctor-item nutrition-doctor-item--link" to="/nutrition-labs">
            <span className="nutrition-doctor-item__symbol nutrition-doctor-item__symbol--labs" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 2v7.31a2 2 0 0 1-.37 1.17l-4.26 6.39A2 2 0 0 0 7 20h10a2 2 0 0 0 1.63-3.13l-4.26-6.39A2 2 0 0 1 14 9.31V2" />
                <path d="M8.5 2h7" />
                <path d="M7 16h10" />
              </svg>
            </span>
            <span className="nutrition-doctor-item__content">
              <strong>{l("آزمایشات من", "My lab tests")}</strong>
              <small>{l("نتایج و سابقه بررسی", "Results and review history")}</small>
            </span>
            <b className="nutrition-doctor-item__chevron" aria-hidden="true">‹</b>
          </Link>

          <article className="nutrition-doctor-item">
            <span className="nutrition-doctor-item__symbol nutrition-doctor-item__symbol--guidance" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <path d="M14 2v6h6" />
                <path d="M16 13H8" />
                <path d="M16 17H8" />
                <path d="M10 9H8" />
              </svg>
            </span>
            <span className="nutrition-doctor-item__content">
              <strong>{l("راهنمایی‌های پزشک", "Physician guidance")}</strong>
              <small>{guidanceCopy}</small>
            </span>
          </article>
        </div>
      </details>
    </section>
  );
}

type LocalizedGenerationMessage = readonly [string, string];

const generationReasonMessages: Record<string, LocalizedGenerationMessage> = {
  STRICT_BUDGET_EXCEEDED: [
    "هزینه برنامه‌ای که با شرایط فعلی ساخته شد از بودجه غذایی تعیین‌شده بیشتر است. بودجه را افزایش بده یا حالت بودجه را از سخت‌گیرانه به انعطاف‌پذیر تغییر بده.",
    "The generated plan exceeds your current strict food budget. Increase the budget or switch to flexible budget mode.",
  ],
  FLEXIBLE_BUDGET_CAP_EXCEEDED: [
    "حتی با محدوده انعطاف‌پذیر بودجه، هزینه برنامه از سقف مجاز بیشتر شده است. بودجه غذایی را کمی افزایش بده.",
    "Even the flexible budget limit is not enough for the current plan. Increase your food budget.",
  ],
  NUTRIENT_UPPER_LIMIT_EXCEEDED: [
    "برنامه ساخته‌شده از سقف ایمن یکی از ریزمغذی‌ها عبور کرده است، بنابراین فیتشو آن را قبول نکرد.",
    "The generated plan exceeds the safe upper limit for at least one micronutrient, so it was rejected.",
  ],
  INSUFFICIENT_PRICE_COVERAGE: [
    "برای تعداد کافی از مواد غذایی، قیمت معتبر در دسترس نیست و بدون قیمت قابل اعتماد امکان ساخت برنامه وجود ندارد.",
    "Reliable prices are unavailable for enough foods to build the plan.",
  ],
  GOAL_RESELECTION_REQUIRED: [
    "هدف فعلی با شرایط تمرینی ثبت‌شده قابل برنامه‌ریزی نیست. هدف یا اطلاعات تمرینت را بررسی کن.",
    "The current goal is not compatible with the recorded training conditions. Review your goal or exercise information.",
  ],
  STRUCTURED_EXERCISE_REQUIRED: [
    "اطلاعات تمرین برای محاسبه و ساخت برنامه تغذیه کامل نیست.",
    "Exercise information is required before the nutrition plan can be generated.",
  ],
  NUTRITION_PROFILE_REQUIRED: [
    "اطلاعات پروفایل تغذیه کامل نیست. ابتدا پروفایل تغذیه را تکمیل کن.",
    "Your nutrition profile is incomplete. Complete it before generating a plan.",
  ],
  NUTRITION_PRODUCT_MODE_REQUIRED: [
    "مسیر تغذیه برای این پروفایل فعال نیست.",
    "Nutrition mode is not enabled for this profile.",
  ],
  PROTEIN_MINIMUM_EXCEEDS_CALORIE_BUDGET: [
    "حداقل پروتئین موردنیاز با کالری هدف فعلی قابل جمع نیست.",
    "The minimum protein requirement cannot fit within the current calorie target.",
  ],
  CARBOHYDRATE_MINIMUM_EXCEEDS_CALORIE_BUDGET: [
    "حداقل کربوهیدرات موردنیاز با کالری هدف فعلی قابل جمع نیست.",
    "The minimum carbohydrate requirement cannot fit within the current calorie target.",
  ],
  FAT_MINIMUM_EXCEEDS_CALORIE_BUDGET: [
    "حداقل چربی موردنیاز با کالری هدف فعلی قابل جمع نیست.",
    "The minimum fat requirement cannot fit within the current calorie target.",
  ],
  PHYSICIAN_MANUAL_PLAN_REQUIRED: [
    "با توجه به شرایط ثبت‌شده، ساخت خودکار برنامه مناسب نیست و برنامه باید توسط پزشک تنظیم یا بررسی شود.",
    "Based on the recorded conditions, an automatic plan is not appropriate and physician involvement is required.",
  ],
  UNSUPPORTED_OR_HARD_BLOCKED: [
    "با شرایط فعلی، ساخت خودکار برنامه تغذیه مجاز نیست.",
    "Automatic nutrition planning is unavailable under the current safety conditions.",
  ],
  USER_BUDGET_BELOW_MINIMUM_FEASIBLE: [
    "با بودجه فعلی، ساخت برنامه‌ای که حداقل‌های تعیین‌شده برای هدف شما را رعایت کند ممکن نشد.",
    "With your current budget, generating a plan that satisfies the required minimums for your goal was not possible.",
  ],
  NO_BUDGET_FEASIBLE_PLAN_FOUND: [
    "با قیمت‌ها و کاتالوگ فعلی، برنامه سازگار در این بودجه پیدا نشد.",
    "With current prices and catalogue, no compatible plan was found in this budget.",
  ],
  REQUEST_FAILED: [
    "درخواست ساخت برنامه انجام نشد. اتصال یا سرویس را بررسی کن و دوباره تلاش کن.",
    "The plan request failed. Check the connection or service and try again.",
  ],
};

const unknownGenerationReason: LocalizedGenerationMessage = [
  "ساخت برنامه با یکی از محدودیت‌های فعلی کامل نشد.",
  "The plan could not be generated because of one of the current constraints.",
];

function generationMessage(
  outcome: WeeklyPlanGeneration["outcome"],
  reasonCodes: string[],
  language: "fa" | "en",
) {
  const languageIndex = language === "en" ? 1 : 0;
  const reasons = [...new Set(reasonCodes.filter((code) => code.trim() !== ""))]
    .map((code) => generationReasonMessages[code]?.[languageIndex] ?? unknownGenerationReason[languageIndex])
    .filter((message, index, allMessages) => allMessages.indexOf(message) === index);

  if (reasons.length === 0) {
    return { message: generationOutcomeMessage(outcome, language), reasons: [] };
  }
  if (reasons.length === 1) return { message: reasons[0], reasons: [] };
  return {
    message: language === "en"
      ? "Several constraints prevented the plan from being generated:"
      : "چند محدودیت همزمان مانع ساخت برنامه شدند:",
    reasons,
  };
}

function generationOutcomeMessage(outcome: WeeklyPlanGeneration["outcome"], language: "fa" | "en") {
  const values: Record<WeeklyPlanGeneration["outcome"], LocalizedGenerationMessage> = {
    success: ["برنامه ساخته شد.", "Plan generated."],
    failed: ["ساخت برنامه انجام نشد. اطلاعات پروفایل را بررسی کن.", "Plan generation failed. Review your profile."],
    safety_blocked: ["ساخت خودکار این برنامه به‌دلیل وضعیت ایمنی مجاز نیست.", "Automatic planning is unavailable because of the current safety status."],
    infeasible: ["با محدودیت‌های فعلی برنامه ایمن و شدنی پیدا نشد.", "No safe feasible plan was found under the current constraints."],
    target_infeasible: ["هدف‌های فعلی با حداقل‌های علمی قابل جمع نیستند.", "The current targets cannot satisfy the scientific minimums."],
    live_price_unavailable: ["پوشش قیمت معتبر برای ساخت برنامه کافی نیست.", "Reliable price coverage is insufficient to build a plan."],
  };
  return values[outcome][language === "en" ? 1 : 0];
}

function EstimateContent({ estimate, language, onRefresh, plan, tracking }: { estimate: NutritionEstimate; language: "fa" | "en"; onRefresh: () => void; plan: WeeklyPlan | null; tracking: DailyTrackingSummary | null }) {
  const l = (fa: string, en: string) => language === "en" ? en : fa;
  const number = new Intl.NumberFormat(language === "en" ? "en-US" : "fa-IR", { maximumFractionDigits: 1 });
  const target = (metric: string) => estimate.targets[metric];
  const preferred = (metric: string) => formatValue(target(metric)?.preferred, target(metric)?.unit, number, language);
  const range = (metric: string) => formatRange(target(metric), number, language);
  const maximum = (metric: string) => formatValue(target(metric)?.maximum, target(metric)?.unit, number, language);
  const confidence = { high: l("اطمینان بالا", "High confidence"), medium: l("اطمینان متوسط", "Medium confidence"), low: l("اطمینان پایین", "Low confidence") }[estimate.confidence];
  const currentDate = new Date().toISOString().slice(0, 10);
  const todayPlan = plan?.days.find((day) => day.plan_date === currentDate) ?? plan?.days[0];
  const energyTarget = todayPlan?.nutrient_totals.energy_kcal ?? target("goal_calories")?.preferred ?? null;
  const tdeeTarget = target("tdee")?.preferred ?? target("tdee")?.minimum ?? null;
  const bmrTarget = target("bmr")?.preferred ?? target("bmr")?.minimum ?? null;
  const activityTarget = tdeeTarget !== null && bmrTarget !== null ? Math.max(0, tdeeTarget - bmrTarget) : null;
  const animationProgress = useSynchronizedProgress();
  const animatedEnergyTarget = energyTarget === null ? null : energyTarget * animationProgress;
  const animatedTdee = tdeeTarget === null ? null : tdeeTarget * animationProgress;
  const animatedBmr = bmrTarget === null ? null : bmrTarget * animationProgress;
  const animatedActivity = activityTarget === null ? null : activityTarget * animationProgress;
  const tracked = tracking?.actual_totals;
  const hasTrackedData = tracked !== undefined && (
    tracking?.data_status === "sufficient"
    || (tracking?.entries.length ?? 0) > 0
    || Object.values(tracked).some((value) => value > 0)
  );
  const macro = (key: string, estimateMetric: string) => hasTrackedData && tracked[key] !== undefined
    ? formatValue(tracked[key], "g/day", number, language)
    : preferred(estimateMetric) !== (language === "en" ? "Not set" : "تعیین نشده")
      ? preferred(estimateMetric)
      : range(estimateMetric);

  return <>
    <section className="nutrition-today-panel" aria-label={l("خلاصه هدف‌ها", "Target summary")}>
      <div className="nutrition-today-panel__top">
        <div className="nutrition-calorie-group">
          <div className="nutrition-calorie-item">
            <article className="nutrition-calorie-card" aria-label={l("کالری هدف روزانه", "Daily calorie goal")} role="region">
              <span>{l("کالری هدف", "Calorie goal")}</span>
              <strong>{animatedEnergyTarget === null ? l("تعیین نشده", "Not set") : number.format(animatedEnergyTarget)}</strong>
              <small>{hasTrackedData ? l(`دریافت امروز ${number.format(tracked?.energy_kcal ?? 0)} کیلوکالری`, `Consumed today ${number.format(tracked?.energy_kcal ?? 0)} kcal`) : l("کیلوکالری روزانه", "daily kcal")}</small>
            </article>
            {energyTarget !== null && <ProgressRing value={animatedEnergyTarget ?? 0} max={energyTarget} label={l("پیشرفت کالری هدف", "Calorie goal progress")} />}
          </div>

          {tdeeTarget !== null && (
            <div className="nutrition-calorie-item nutrition-calorie-item--tdee">
              <article className="nutrition-calorie-card nutrition-calorie-card--tdee" aria-label={l("کل مصرف روزانه انرژی (TDEE)", "Total daily energy expenditure (TDEE)")} role="region">
                <span>{l("TDEE (کل مصرف روزانه)", "TDEE (Daily expenditure)")}</span>
                <strong>{animatedTdee === null ? l("تعیین نشده", "Not set") : number.format(animatedTdee)}</strong>
                <div className="nutrition-breakdown-legend" aria-label={l("تفکیک متابولیسم پایه و فعالیت", "BMR and activity breakdown")}>
                  <span className="nutrition-breakdown-pill nutrition-breakdown-pill--bmr">
                    <i className="nutrition-breakdown-dot nutrition-breakdown-dot--bmr" />
                    {l("پایه", "BMR")}: {animatedBmr === null ? "—" : number.format(animatedBmr)}
                  </span>
                  <span className="nutrition-breakdown-pill nutrition-breakdown-pill--activity">
                    <i className="nutrition-breakdown-dot nutrition-breakdown-dot--activity" />
                    {l("فعالیت", "Activity")}: {animatedActivity === null ? "—" : number.format(animatedActivity)}
                  </span>
                </div>
              </article>
              <DualProgressRing
                primaryValue={animatedBmr ?? 0}
                secondaryValue={animatedActivity ?? 0}
                total={tdeeTarget}
                label={l("تفکیک مصرف انرژی روزانه", "Daily energy expenditure breakdown")}
              />
            </div>
          )}
        </div>
        <div className="nutrition-confidence-card">
          <span className={`nutrition-confidence nutrition-confidence--${estimate.confidence}`}>{confidence}</span>
          {estimate.is_stale && <button className="text-button" type="button" onClick={onRefresh}>{l("به‌روزرسانی", "Refresh")}</button>}
        </div>
      </div>
      <div className="nutrition-target-grid nutrition-target-grid--primary fitsho-metric-strip" aria-label={l("درشت‌مغذی‌های اصلی", "Primary macronutrient targets")}>
        <TargetCard title={l("پروتئین", "Protein")} value={macro("protein_g", "protein")} note="" />
        <TargetCard title={l("کربوهیدرات", "Carbohydrate")} value={macro("carbohydrate_g", "carbohydrate")} note="" />
        <TargetCard title={l("چربی", "Fat")} value={macro("total_fat_g", "total_fat")} note="" />
      </div>
    </section>

    <WeightRateCard estimate={estimate} language={language} onRefresh={onRefresh} />

    {todayPlan && <section className="nutrition-meal-summary" aria-label={l("وعده‌های امروز", "Today's meals")}>
      <header><h2>{l("وعده‌های امروز", "Today's meals")}</h2><Link to="/nutrition-tracking">{l("ثبت وعده", "Track meal")}</Link></header>
      <div>{todayPlan.meals.map((meal) => <article key={meal.id}><span>{mealLabel(meal.slot_role, meal.slot_index, language)}</span><strong>{meal.nutrient_totals.energy_kcal === undefined ? "—" : `${number.format(meal.nutrient_totals.energy_kcal)} ${l("کیلوکالری", "kcal")}`}</strong></article>)}</div>
    </section>}

    <details className="nutrition-science-details">
      <summary>{l("جزئیات علمی و حدود ایمنی", "Scientific details and safety limits")}</summary>
      <nav className="nutrition-science-links" aria-label={l("ابزارهای علمی تغذیه", "Scientific nutrition tools")}>
        <Link to="/nutrition-labs">{l("آزمایش‌ها", "Labs")}</Link>
        <Link to="/nutrition-supplements">{l("مکمل‌ها", "Supplements")}</Link>
      </nav>
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

function mealLabel(role: "main_meal" | "snack" | "free_meal" | "post_workout", index: number, language: "fa" | "en") {
  if (role === "free_meal") return language === "en" ? "Free Meal" : "وعده آزاد";
  if (role === "post_workout") return language === "en" ? "Post-workout" : "پس از تمرین";
  if (role === "snack") return language === "en" ? `Snack ${index + 1}` : `میان‌وعده ${new Intl.NumberFormat("fa-IR").format(index + 1)}`;
  const labels = language === "en" ? ["Breakfast", "Lunch", "Dinner"] : ["صبحانه", "ناهار", "شام"];
  return labels[index] ?? (language === "en" ? `Meal ${index + 1}` : `وعده ${new Intl.NumberFormat("fa-IR").format(index + 1)}`);
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

function WeightRateCard({
  estimate,
  language,
  onRefresh,
}: {
  estimate: NutritionEstimate;
  language: "fa" | "en";
  onRefresh?: () => void;
}) {
  const [switching, setSwitching] = useState(false);
  const l = (fa: string, en: string) => (language === "en" ? en : fa);
  const number = new Intl.NumberFormat(language === "en" ? "en-US" : "fa-IR", {
    maximumFractionDigits: 1,
  });
  const snapshot = estimate.input_snapshot;
  if (!snapshot) return null;

  const requested = snapshot["requested_weight_change_kg_per_week"] != null
    ? Number(snapshot["requested_weight_change_kg_per_week"])
    : null;
  const recommended = snapshot["recommended_weight_change_kg_per_week"] != null
    ? Number(snapshot["recommended_weight_change_kg_per_week"])
    : null;
  const applied = snapshot["applied_weight_change_kg_per_week"] != null
    ? Number(snapshot["applied_weight_change_kg_per_week"])
    : null;

  if (requested == null && recommended == null && applied == null) {
    return null;
  }

  const rateMode: "safe" | "user_override" =
    snapshot["weight_rate_mode"] === "user_override" ? "user_override" : "safe";
  const isOverride =
    rateMode === "user_override" ||
    estimate.confidence_reasons.includes("WEIGHT_RATE_USER_OVERRIDE_APPLIED");
  const isClamped =
    !isOverride &&
    estimate.confidence_reasons.includes("WEIGHT_RATE_CLAMPED_FOR_AUTOMATIC_SAFETY");

  async function handleSwitchMode(newMode: "safe" | "user_override") {
    if (newMode === rateMode || switching) return;
    setSwitching(true);
    try {
      const profile = await nutritionApi.getNutritionProfile();
      if (profile) {
        await nutritionApi.saveNutritionProfile({
          ...profile,
          weight_rate_mode: newMode,
        });
        await nutritionApi.createNutritionEstimate();
        onRefresh?.();
      }
    } catch (err) {
      console.error("Failed to switch weight rate mode", err);
    } finally {
      setSwitching(false);
    }
  }

  return (
    <section className="nutrition-weight-rate-card" aria-label={l("نرخ تغییر وزن هفتگی", "Weekly weight change rate")}>
      <header className="nutrition-weight-rate-card__header">
        <div className="nutrition-weight-rate-card__title-group">
          <span className="nutrition-weight-rate-card__icon" aria-hidden="true">⚖️</span>
          <h3 className="nutrition-weight-rate-card__title">{l("نرخ تغییر وزن هفتگی", "Weekly Weight Change Rate")}</h3>
          {isOverride ? (
            <span className="nutrition-rate-badge--override">
              {l("نرخ دلخواه من", "User Override")}
            </span>
          ) : isClamped ? (
            <span className="nutrition-rate-badge--clamped">
              {l("تنظیم‌شده برای ایمنی خودکار", "Adjusted for safety")}
            </span>
          ) : (
            <span className="nutrition-rate-badge--safe">
              {l("تنظیم ایمن پیشنهادی", "Safe Recommended")}
            </span>
          )}
        </div>
        <div className="nutrition-weight-rate-modes">
          <button
            type="button"
            className={`nutrition-weight-rate-mode-btn ${rateMode === "safe" ? "is-active" : ""}`}
            onClick={() => void handleSwitchMode("safe")}
            disabled={switching}
          >
            <span>🛡️</span>
            <span>{l("تنظیم ایمن پیشنهادی", "Safe")}</span>
          </button>
          <button
            type="button"
            className={`nutrition-weight-rate-mode-btn ${rateMode === "user_override" ? "is-active is-override" : ""}`}
            onClick={() => void handleSwitchMode("user_override")}
            disabled={switching}
          >
            <span>⚡</span>
            <span>{l("اعمال نرخ دلخواه من", "Override")}</span>
          </button>
        </div>
      </header>
      <div className="nutrition-weight-rate-grid">
        <div className="nutrition-weight-rate-item nutrition-weight-rate-item--requested">
          <span className="nutrition-weight-rate-label">{l("درخواست شما", "Your request")}</span>
          <strong className="nutrition-weight-rate-val">
            {requested != null ? `${number.format(requested)} ${l("کیلوگرم/هفته", "kg/week")}` : "—"}
          </strong>
        </div>
        <div className="nutrition-weight-rate-item nutrition-weight-rate-item--recommended">
          <span className="nutrition-weight-rate-label">{l("مقدار پیشنهادی", "Recommended")}</span>
          <strong className="nutrition-weight-rate-val">
            {recommended != null ? `${number.format(recommended)} ${l("کیلوگرم/هفته", "kg/week")}` : "—"}
          </strong>
        </div>
        <div
          className={`nutrition-weight-rate-item nutrition-weight-rate-item--applied ${
            isOverride
              ? "nutrition-weight-rate-item--override"
              : isClamped
                ? "nutrition-weight-rate-item--clamped"
                : ""
          }`}
        >
          <span className="nutrition-weight-rate-label">
            {isOverride
              ? l("مقدار اعمال‌شده (نرخ مستقیم)", "Applied (user override)")
              : isClamped
                ? l("مقدار اعمال‌شده (تنظیم ایمنی)", "Applied (safety clamped)")
                : l("مقدار اعمال‌شده", "Applied")}
          </span>
          <strong className="nutrition-weight-rate-val">
            {applied != null ? `${number.format(applied)} ${l("کیلوگرم/هفته", "kg/week")}` : "—"}
          </strong>
        </div>
      </div>
    </section>
  );
}

