import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import appTrainingAccent from "../../assets/landing/app-training-accent.jpg";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import { getAdminTrainingProgramTemplates } from "./api";
import type { AdminTrainingProgramTemplatesResponse } from "./types";
import "./admin.css";

const trainingDays = [2, 3, 4, 5, 6] as const;
const trainingLevels = ["all", "first_month", "beginner", "intermediate", "advanced"] as const;

export function AdminTrainingTemplatesPage() {
  const { i18n, t } = useTranslation();
  const [daysPerWeek, setDaysPerWeek] = useState<(typeof trainingDays)[number]>(2);
  const [trainingLevel, setTrainingLevel] = useState<(typeof trainingLevels)[number]>("all");
  const [page, setPage] = useState<AdminTrainingProgramTemplatesResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [retry, setRetry] = useState(0);
  const [expandedPrograms, setExpandedPrograms] = useState<Set<string>>(() => new Set());
  const [expandedDays, setExpandedDays] = useState<Set<string>>(() => new Set());
  const english = i18n.resolvedLanguage === "en";
  const visibleTemplates = page?.items.filter(
    (template) => trainingLevel === "all" || template.training_level === trainingLevel,
  ) ?? [];
  const newProgramLevel = trainingLevel === "all" ? "beginner" : trainingLevel;
  const newProgramPath = `/admin/training-program-templates/new?days=${daysPerWeek}&level=${newProgramLevel}`;

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

        <div className="admin-template-filters">
          <div className="admin-template-filter-group">
            <span>{t("admin.templates.dayFilter")}</span>
            <div className="admin-template-tabs" role="tablist" aria-label={t("admin.templates.dayFilter")}>
              {trainingDays.map((days) => (
                <button
                  aria-selected={days === daysPerWeek}
                  id={`template-tab-${days}`}
                  key={days}
                  onClick={() => {
                    setDaysPerWeek(days);
                    setTrainingLevel("all");
                  }}
                  role="tab"
                  type="button"
                >
                  {t("admin.templates.days", { count: days })}
                </button>
              ))}
            </div>
          </div>
          <div className="admin-template-filter-group">
            <span>{t("admin.templates.levelFilter")}</span>
            <div className="admin-template-tabs admin-template-tabs--levels" role="tablist" aria-label={t("admin.templates.levelFilter")}>
              {trainingLevels.map((level) => (
                <button
                  aria-selected={level === trainingLevel}
                  key={level}
                  onClick={() => setTrainingLevel(level)}
                  role="tab"
                  type="button"
                >
                  {level === "all"
                    ? t("admin.templates.allLevels")
                    : level === "first_month"
                      ? <><span aria-hidden="true">◇</span> {t("admin.templates.firstMonth")}</>
                      : t(`catalog.difficulty.${level}`)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {state === "loading" && <p className="admin-status" role="status">{t("admin.templates.loading")}</p>}
        {state === "error" && (
          <div className="admin-status" role="alert">
            <p>{t("admin.templates.loadError")}</p>
            <button type="button" onClick={() => setRetry((value) => value + 1)}>{t("common.retry")}</button>
          </div>
        )}
        {state === "ready" && visibleTemplates.length === 0 && (
          <p className="admin-status">{t("admin.templates.empty")}</p>
        )}
        {state === "ready" && page !== null && visibleTemplates.length > 0 && (
          <section className="admin-template-list" role="tabpanel" aria-labelledby={`template-tab-${daysPerWeek}`}>
            {visibleTemplates.map((template) => {
              const name = english ? template.name_en : template.name_fa;
              const programExpanded = expandedPrograms.has(template.id);
              const programPanelId = `training-program-${template.id}`;
              return (
                <article className="admin-template-card" data-expanded={programExpanded} key={template.id}>
                  <header className="admin-accordion-header">
                    <button
                      aria-controls={programPanelId}
                      aria-expanded={programExpanded}
                      aria-label={t(`admin.templates.${programExpanded ? "collapseProgramAria" : "expandProgramAria"}`, { name })}
                      className="admin-program-accordion-trigger"
                      onClick={() => {
                        setExpandedPrograms((current) => {
                          const next = new Set(current);
                          if (programExpanded) next.delete(template.id);
                          else next.add(template.id);
                          return next;
                        });
                        if (programExpanded) {
                          const dayIds = new Set(template.days.map((day) => day.id));
                          setExpandedDays((current) => new Set([...current].filter((id) => !dayIds.has(id))));
                        }
                      }}
                      type="button"
                    >
                      <span className="admin-program-accordion-copy">
                        <span className="eyebrow">{t("admin.templates.days", { count: template.days_per_week })}</span>
                        <span className="admin-program-accordion-title">{name}</span>
                        <span className="admin-program-accordion-description">{english ? template.description_en : template.description_fa}</span>
                      </span>
                      <span className="admin-program-accordion-meta">
                        <span className="admin-template-level">
                          {template.training_level === "first_month"
                            ? t("admin.templates.firstMonth")
                            : t(`catalog.difficulty.${template.training_level}`)}
                        </span>
                        <span aria-hidden="true" className="admin-accordion-chevron">⌄</span>
                      </span>
                    </button>
                  </header>
                  <div className="admin-template-tags" aria-label={t("admin.templates.labels")}>
                    {template.focus_tags.map((tag) => <span key={tag}>{t(`admin.templates.tags.${tag}`)}</span>)}
                    {template.intensity_methods.filter((method) => method !== "standard").map((method) => (
                      <span key={method}>{t(`admin.templates.methods.${method}`)}</span>
                    ))}
                  </div>
                  {programExpanded && (
                    <div className="admin-program-accordion-panel" id={programPanelId}>
                      <div className="admin-template-days">
                        {template.days.map((day) => {
                          const dayName = english ? day.title_en : day.title_fa;
                          const dayExpanded = expandedDays.has(day.id);
                          const dayPanelId = `training-day-${day.id}`;
                          return (
                            <section className="admin-template-day" data-expanded={dayExpanded} key={day.id}>
                              <header>
                                <button
                                  aria-controls={dayPanelId}
                                  aria-expanded={dayExpanded}
                                  aria-label={t(`admin.templates.${dayExpanded ? "collapseDayAria" : "expandDayAria"}`, { name: dayName, number: day.day_number })}
                                  className="admin-day-accordion-trigger"
                                  onClick={() => setExpandedDays((current) => {
                                    const next = new Set(current);
                                    if (dayExpanded) next.delete(day.id);
                                    else next.add(day.id);
                                    return next;
                                  })}
                                  type="button"
                                >
                                  <span>{t("admin.templates.dayNumber", { number: day.day_number })}</span>
                                  <strong>{dayName}</strong>
                                  <span aria-hidden="true" className="admin-accordion-chevron">⌄</span>
                                </button>
                              </header>
                              {dayExpanded && (
                                <ol className="admin-day-accordion-panel" id={dayPanelId}>
                                  {day.slots.map((slot) => {
                                    const exerciseName = slot.exercise === null
                                      ? (english ? slot.placeholder_name_en : slot.placeholder_name_fa)
                                      : (english ? slot.exercise.name_en : slot.exercise.name_fa);
                                    return (
                                      <li className={slot.exercise === null || slot.exercise.needs_review ? "is-placeholder" : ""} key={slot.id}>
                                        <div>
                                          <strong>{exerciseName ?? slot.exercise_slug_hint}</strong>
                                          {slot.exercise === null && <small>{t("admin.templates.placeholder")}</small>}
                                          {slot.exercise !== null && (
                                            <Link
                                              aria-label={t("admin.templates.exerciseDetailAria", { name: exerciseName })}
                                              className="admin-template-exercise-detail"
                                              to={`/exercises/${slot.exercise.slug}`}
                                            >
                                              <span aria-hidden="true">↗</span>
                                              {t("admin.templates.exerciseDetail")}
                                            </Link>
                                          )}
                                          {slot.exercise?.needs_review && <small>{t("admin.templates.reviewMedia")}</small>}
                                        </div>
                                        <span dir="ltr">
                                          {slot.sets} × {slot.rep_min}–{slot.rep_max} · RIR {slot.target_rir}
                                        </span>
                                      </li>
                                    );
                                  })}
                                </ol>
                              )}
                            </section>
                          );
                        })}
                      </div>
                      <section className="admin-template-rationale" aria-label={t("admin.templates.rationaleTitle")}>
                        <h3>{t("admin.templates.rationaleTitle")}</h3>
                        <ol>
                          {template.programming_rationale.map((rationale) => (
                            <li key={rationale.title_en}>
                              <strong>{english ? rationale.title_en : rationale.title_fa}</strong>
                              <p>{english ? rationale.detail_en : rationale.detail_fa}</p>
                            </li>
                          ))}
                        </ol>
                      </section>
                    </div>
                  )}
                  <footer>
                    <Link
                      aria-label={t("admin.templates.editProgramAria", { name })}
                      to={`/admin/training-program-templates/${template.id}/edit`}
                    >
                      {t("admin.templates.editProgram")}
                    </Link>
                    <span>{t("admin.templates.source")}: {template.source_name}</span>
                    <a href={template.source_url} rel="noreferrer" target="_blank">{t("admin.templates.reference")}</a>
                  </footer>
                </article>
              );
            })}
          </section>
        )}
        {state === "ready" && (
          <div className="admin-template-add-program">
            <Link className="admin-primary-link" to={newProgramPath}>{t("admin.templates.addProgram")}</Link>
          </div>
        )}
      </main>
    </div>
  );
}
