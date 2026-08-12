import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import foodAccent from "../../assets/landing/food.webp";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import {
  archiveAdminNutritionProgram,
  getAdminNutritionPrograms,
  restoreAdminNutritionProgram,
} from "./api";
import type {
  AdminNutritionProgramPage,
  NutritionDietStyle,
  NutritionProgramLifecycle,
} from "./types";
import "./admin.css";

const dietStyles: Array<NutritionDietStyle | "all"> = [
  "all",
  "economy",
  "balanced_iranian",
  "high_protein_gym",
  "quick_easy",
  "premium_varied",
];
const lifecycles: NutritionProgramLifecycle[] = ["active", "archived", "all"];

export function AdminNutritionProgramsPage() {
  const { i18n, t } = useTranslation();
  const [dietStyle, setDietStyle] = useState<NutritionDietStyle | "all">("all");
  const [lifecycle, setLifecycle] = useState<NutritionProgramLifecycle>("active");
  const [page, setPage] = useState<AdminNutritionProgramPage | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [retry, setRetry] = useState(0);
  const english = i18n.resolvedLanguage === "en";

  useEffect(() => {
    let active = true;
    setState("loading");
    void getAdminNutritionPrograms({ dietStyle, lifecycle })
      .then((result) => {
        if (!active) return;
        setPage(result);
        setState("ready");
      })
      .catch(() => { if (active) setState("error"); });
    return () => { active = false; };
  }, [dietStyle, lifecycle, retry]);

  async function changeLifecycle(programId: string, active: boolean) {
    try {
      if (active) await archiveAdminNutritionProgram(programId);
      else await restoreAdminNutritionProgram(programId);
      setRetry((value) => value + 1);
    } catch {
      setState("error");
    }
  }

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={foodAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--templates admin-main--nutrition-programs">
        <header className="admin-hero">
          <div>
            <p className="eyebrow eyebrow--accent">{t("admin.nutritionPrograms.eyebrow")}</p>
            <h1 className="fitsho-display">{t("admin.nutritionPrograms.title")}</h1>
            <p>{t("admin.nutritionPrograms.intro")}</p>
          </div>
        </header>

        <div className="admin-template-filters">
          <div className="admin-template-filter-group">
            <span>{t("admin.nutritionPrograms.dietFilter")}</span>
            <div className="admin-template-tabs admin-program-diet-tabs" role="tablist" aria-label={t("admin.nutritionPrograms.dietFilter")}>
              {dietStyles.map((style) => (
                <button key={style} type="button" role="tab" aria-selected={style === dietStyle} onClick={() => setDietStyle(style)}>
                  {t(`admin.nutritionPrograms.dietStyles.${style}`)}
                </button>
              ))}
            </div>
          </div>
          <div className="admin-template-filter-group">
            <span>{t("admin.nutritionPrograms.lifecycleFilter")}</span>
            <div className="admin-template-tabs" role="tablist" aria-label={t("admin.nutritionPrograms.lifecycleFilter")}>
              {lifecycles.map((item) => (
                <button key={item} type="button" role="tab" aria-selected={item === lifecycle} onClick={() => setLifecycle(item)}>
                  {t(`admin.nutritionPrograms.lifecycle.${item}`)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {state === "loading" && <p className="admin-status" role="status">{t("admin.nutritionPrograms.loading")}</p>}
        {state === "error" && <div className="admin-status" role="alert"><p>{t("admin.nutritionPrograms.loadError")}</p><button type="button" onClick={() => setRetry((value) => value + 1)}>{t("common.retry")}</button></div>}
        {state === "ready" && page?.items.length === 0 && <p className="admin-status">{t("admin.nutritionPrograms.empty")}</p>}
        {state === "ready" && page !== null && page.items.length > 0 && (
          <section className="admin-template-list">
            {page.items.map((program) => {
              const name = english ? program.name_en : program.name_fa;
              return (
                <article className={`admin-template-card admin-program-card${program.is_active ? "" : " is-archived"}`} key={program.id}>
                  <header>
                    <div>
                      <p className="eyebrow">{t(`admin.nutritionPrograms.dietStyles.${program.diet_style}`)}</p>
                      <h2>{program.code ? <>{program.code} — </> : null}<span>{name}</span></h2>
                      <p>{english ? program.description_en : program.description_fa}</p>
                    </div>
                    <span className="admin-template-level">{t(`admin.nutritionPrograms.lifecycle.${program.is_active ? "active" : "archived"}`)}</span>
                  </header>
                  <div className="admin-program-week">
                    {program.days.map((day) => (
                      <section className="admin-program-day" key={day.id}>
                        <strong>{t("admin.nutritionPrograms.day", { number: day.day_number })}</strong>
                        <ul>{day.slots.map((slot) => <li key={slot.id}><span>{t(`admin.meals.categories.${slot.category}`)}</span>{slot.kind === "free_meal" || slot.meal === null ? <b>وعده آزاد</b> : <b>{slot.meal.code ? <>{slot.meal.code} — </> : null}{slot.meal.name_fa}<small>{slot.meal.name_en}</small></b>}</li>)}</ul>
                      </section>
                    ))}
                  </div>
                  <footer>
                    <Link aria-label={t("admin.nutritionPrograms.editAria", { name })} to={`/admin/nutrition-programs/${program.id}/edit`}>{t("admin.nutritionPrograms.edit")}</Link>
                    <button type="button" aria-label={t(`admin.nutritionPrograms.${program.is_active ? "archiveAria" : "restoreAria"}`, { name })} onClick={() => void changeLifecycle(program.id, program.is_active)}>
                      {t(`admin.nutritionPrograms.${program.is_active ? "archive" : "restore"}`)}
                    </button>
                  </footer>
                </article>
              );
            })}
          </section>
        )}
        <div className="admin-template-add-program"><Link className="admin-primary-link" to="/admin/nutrition-programs/new">{t("admin.nutritionPrograms.add")}</Link></div>
      </main>
    </div>
  );
}
