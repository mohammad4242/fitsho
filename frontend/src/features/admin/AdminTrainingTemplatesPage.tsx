import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import appTrainingAccent from "../../assets/landing/app-training-accent.jpg";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import { getAdminTrainingProgramTemplates } from "./api";
import type { AdminTrainingProgramTemplatesResponse } from "./types";
import "./admin.css";

const trainingDays = [2, 3, 4, 5, 6] as const;

export function AdminTrainingTemplatesPage() {
  const { i18n, t } = useTranslation();
  const [daysPerWeek, setDaysPerWeek] = useState<(typeof trainingDays)[number]>(2);
  const [page, setPage] = useState<AdminTrainingProgramTemplatesResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [retry, setRetry] = useState(0);
  const english = i18n.resolvedLanguage === "en";

  useEffect(() => {
    let active = true;
    setState("loading");
    void getAdminTrainingProgramTemplates(daysPerWeek)
      .then((result) => {
        if (!active) return;
        setPage(result);
        setState("ready");
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => { active = false; };
  }, [daysPerWeek, retry]);

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={appTrainingAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--templates">
        <header className="admin-hero">
          <div>
            <p className="eyebrow eyebrow--accent">{t("admin.templates.eyebrow")}</p>
            <h1 className="fitsho-display">{t("admin.templates.title")}</h1>
            <p>{t("admin.templates.intro")}</p>
          </div>
        </header>

        <div className="admin-template-tabs" role="tablist" aria-label={t("admin.templates.dayFilter")}>
          {trainingDays.map((days) => (
            <button
              aria-selected={days === daysPerWeek}
              id={`template-tab-${days}`}
              key={days}
              onClick={() => setDaysPerWeek(days)}
              role="tab"
              type="button"
            >
              {t("admin.templates.days", { count: days })}
            </button>
          ))}
        </div>

        {state === "loading" && <p className="admin-status" role="status">{t("admin.templates.loading")}</p>}
        {state === "error" && (
          <div className="admin-status" role="alert">
            <p>{t("admin.templates.loadError")}</p>
            <button type="button" onClick={() => setRetry((value) => value + 1)}>{t("common.retry")}</button>
          </div>
        )}
        {state === "ready" && page?.items.length === 0 && (
          <p className="admin-status">{t("admin.templates.empty")}</p>
        )}
        {state === "ready" && page !== null && page.items.length > 0 && (
          <section className="admin-template-list" role="tabpanel" aria-labelledby={`template-tab-${daysPerWeek}`}>
            {page.items.map((template) => (
              <article className="admin-template-card" key={template.id}>
                <header>
                  <div>
                    <p className="eyebrow">{t("admin.templates.days", { count: template.days_per_week })}</p>
                    <h2>{english ? template.name_en : template.name_fa}</h2>
                    <p>{english ? template.description_en : template.description_fa}</p>
                  </div>
                  <span className="admin-template-level">
                    {t(`catalog.difficulty.${template.training_level}`)}
                  </span>
                </header>
                <div className="admin-template-tags" aria-label={t("admin.templates.labels")}>
                  {template.focus_tags.map((tag) => <span key={tag}>{t(`admin.templates.tags.${tag}`)}</span>)}
                  {template.intensity_methods.filter((method) => method !== "standard").map((method) => (
                    <span key={method}>{t(`admin.templates.methods.${method}`)}</span>
                  ))}
                </div>
                <div className="admin-template-days">
                  {template.days.map((day) => (
                    <section className="admin-template-day" key={day.id}>
                      <header>
                        <span>{t("admin.templates.dayNumber", { number: day.day_number })}</span>
                        <h3>{english ? day.title_en : day.title_fa}</h3>
                      </header>
                      <ol>
                        {day.slots.map((slot) => {
                          const name = slot.exercise === null
                            ? (english ? slot.placeholder_name_en : slot.placeholder_name_fa)
                            : (english ? slot.exercise.name_en : slot.exercise.name_fa);
                          return (
                            <li className={slot.exercise === null ? "is-placeholder" : ""} key={slot.id}>
                              <div>
                                <strong>{name ?? slot.exercise_slug_hint}</strong>
                                {slot.exercise === null && <small>{t("admin.templates.placeholder")}</small>}
                              </div>
                              <span dir="ltr">
                                {slot.sets} × {slot.rep_min}–{slot.rep_max} · RIR {slot.target_rir}
                              </span>
                            </li>
                          );
                        })}
                      </ol>
                    </section>
                  ))}
                </div>
                <footer>
                  <span>{t("admin.templates.source")}: {template.source_name}</span>
                  <a href={template.source_url} rel="noreferrer" target="_blank">{t("admin.templates.reference")}</a>
                </footer>
              </article>
            ))}
          </section>
        )}
      </main>
    </div>
  );
}
