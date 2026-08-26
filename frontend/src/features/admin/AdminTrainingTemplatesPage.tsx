import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import appTrainingAccent from "../../assets/landing/app-training-accent.jpg";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import { AdminTrainingTemplateSlotEditModal } from "./AdminTrainingTemplateSlotEditModal";
import {
  getAdminTrainingProgramStructures,
  getAdminTrainingProgramTemplates,
} from "./api";
import type {
  AdminTrainingProgramStructure,
  AdminTrainingProgramTemplatesResponse,
  AdminTrainingTemplateSlot,
  StructureFamily,
} from "./types";
import "./admin.css";

const trainingDays = [2, 3, 4, 5, 6] as const;
const trainingLevels = ["all", "first_month", "beginner", "intermediate", "advanced"] as const;
const structureFamilies: StructureFamily[] = ["upper_lower", "split"];
const persianDayNumerals = ["", "", "۲", "۳", "۴", "۵", "۶"] as const;
const persianDayWords = ["", "", "دو", "سه", "چهار", "پنج", "شش"] as const;
const englishDayWords = ["", "", "two", "three", "four", "five", "six"] as const;

function displayProgramTitle(title: string, daysPerWeek: number, english: boolean): string {
  const dayToken = english
    ? `(?:${daysPerWeek}|${englishDayWords[daysPerWeek] ?? ""})`
    : `(?:${daysPerWeek}|${persianDayNumerals[daysPerWeek] ?? ""}|${persianDayWords[daysPerWeek] ?? ""})`;
  const dayPhrase = english
    ? `${dayToken}\\s*[-–—]?\\s*days?\\b`
    : `${dayToken}(?:\\u200c|\\s)*روزه`;
  const prefix = new RegExp(`^\\s*${dayPhrase}\\s*(?:[؛;:،,-]\\s*)?`, english ? "i" : "u");
  const suffix = new RegExp(`\\s+${dayPhrase}\\s*$`, english ? "i" : "u");
  const infix = new RegExp(`\\s+${dayPhrase}(?=\\s|$)`, english ? "i" : "u");
  const displayed = title.replace(prefix, "").replace(suffix, "").replace(infix, "").trim();
  return displayed || title;
}

export function AdminTrainingTemplatesPage() {
  const { i18n, t } = useTranslation();
  const [daysPerWeek, setDaysPerWeek] = useState<(typeof trainingDays)[number]>(2);
  const [structureId, setStructureId] = useState<string>("all");
  const [family, setFamily] = useState<StructureFamily | null>(null);
  const [structures, setStructures] = useState<AdminTrainingProgramStructure[]>([]);
  const [trainingLevel, setTrainingLevel] = useState<(typeof trainingLevels)[number]>("all");
  const [page, setPage] = useState<AdminTrainingProgramTemplatesResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [expandedPrograms, setExpandedPrograms] = useState<Set<string>>(() => new Set());
  const [expandedDays, setExpandedDays] = useState<Set<string>>(() => new Set());
  const [editingSlot, setEditingSlot] = useState<{
    templateId: string;
    dayId: string;
    slot: AdminTrainingTemplateSlot;
    noviceDefaults: boolean;
  } | null>(null);
  const english = i18n.resolvedLanguage === "en";
  const visibleTemplates = page?.items ?? [];
  const newProgramLevel = trainingLevel === "all" ? "beginner" : trainingLevel;
  const newProgramPath = `/admin/training-program-templates/new?days=${daysPerWeek}&level=${newProgramLevel}${structureId !== "all" ? `&structure_id=${structureId}` : ""}`;
  const usesFamilyFilter = daysPerWeek >= 4;
  const structureName = (structure: AdminTrainingProgramStructure) => english ? structure.name_en : structure.name_fa;
  const familyLabel = (value: StructureFamily) => value === "upper_lower"
    ? t("admin.templates.upperLowerFamily")
    : t("admin.templates.splitFamily");
  const structuresForFamily = (value: StructureFamily) => structures.filter((structure) => structure.family === value);

  useEffect(() => {
    let active = true;
    getAdminTrainingProgramStructures(daysPerWeek)
      .then((res) => {
        if (!active) return;
        setStructures(res.items);
      })
      .catch(() => {
        if (active) setStructures([]);
      });
    return () => { active = false; };
  }, [daysPerWeek]);

  useEffect(() => {
    let active = true;
    setState("loading");
    setFeedback(null);
    const selectedStructureId = structureId === "all" ? undefined : structureId;
    const request = family !== null
      ? getAdminTrainingProgramTemplates(daysPerWeek, trainingLevel, selectedStructureId, family)
      : selectedStructureId === undefined
        ? getAdminTrainingProgramTemplates(daysPerWeek, trainingLevel)
        : getAdminTrainingProgramTemplates(daysPerWeek, trainingLevel, selectedStructureId);
    request
      .then((result) => {
        if (!active) return;
        setPage(result);
        setState("ready");
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => { active = false; };
  }, [daysPerWeek, family, retry, trainingLevel, structureId]);

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
          <div className="admin-hero-actions">
            <Link className="admin-secondary-link" to="/admin/training-program-structures">
              {t("admin.templates.structureLibraryLink")}
            </Link>
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
                    setFamily(null);
                    setStructureId("all");
                    setStructures([]);
                  }}
                  role="tab"
                  type="button"
                >
                  {t("admin.templates.days", { count: days })}
                </button>
              ))}
            </div>
          </div>
          {(structures.length > 0 || usesFamilyFilter) && (
            <div className="admin-template-filter-group">
              <span>{t("admin.templates.structureFilter")}</span>
              <div className={`admin-template-tabs admin-template-tabs--structures${usesFamilyFilter ? " admin-template-tabs--families" : ""}`} role="tablist" aria-label={t("admin.templates.structureFilter")}>
                <button
                  aria-selected={structureId === "all"}
                  onClick={() => {
                    setFamily(null);
                    setStructureId("all");
                  }}
                  role="tab"
                  type="button"
                >
                  {t("admin.templates.allStructures")}
                </button>
                {!usesFamilyFilter && structures.map((structure) => (
                  <button
                    aria-selected={structure.id === structureId}
                    key={structure.id}
                    onClick={() => setStructureId(structure.id)}
                    role="tab"
                    type="button"
                  >
                    {structureName(structure)}
                  </button>
                ))}
                {usesFamilyFilter && structureFamilies.map((value) => {
                  const expanded = family === value;
                  const familyStructures = structuresForFamily(value);
                  return (
                    <div className="admin-structure-family" key={value}>
                      <button
                        aria-expanded={expanded}
                        aria-pressed={expanded}
                        className="admin-structure-family__trigger"
                        onClick={() => {
                          setFamily(expanded ? null : value);
                          setStructureId("all");
                        }}
                        type="button"
                      >
                        <span>{familyLabel(value)}</span>
                        <span aria-hidden="true" className="admin-structure-family__chevron">⌄</span>
                      </button>
                      {expanded && (
                        <div className="admin-structure-family__options" role="list">
                          {familyStructures.length === 0 && (
                            <p className="admin-structure-family__empty">{t("admin.templates.noStructuresInFamily")}</p>
                          )}
                          {familyStructures.map((structure) => (
                            <button
                              aria-label={structureName(structure)}
                              aria-selected={structure.id === structureId}
                              className="admin-structure-option"
                              key={structure.id}
                              onClick={() => setStructureId(structure.id)}
                              type="button"
                            >
                              <span>{structureName(structure)}</span>
                              {structure.split_type !== null && (
                                <small>{t(`admin.templates.splitTypes.${structure.split_type}`)}</small>
                              )}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
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
        {feedback !== null && <p className="admin-status admin-status--success" role="status">{feedback}</p>}
        {state === "ready" && visibleTemplates.length === 0 && (
          <p className="admin-status">{t("admin.templates.empty")}</p>
        )}
        {state === "ready" && page !== null && visibleTemplates.length > 0 && (
          <section className="admin-template-list" role="tabpanel" aria-labelledby={`template-tab-${daysPerWeek}`}>
            {visibleTemplates.map((template) => {
              const name = english ? template.name_en : template.name_fa;
              const displayName = displayProgramTitle(
                name,
                template.days_per_week,
                english,
              );
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
                        <span className="admin-program-accordion-title">{displayName}</span>
                      </span>
                      <span className="admin-program-accordion-meta">
                        <span className="admin-template-levels">
                          {template.supported_levels.map((level) => (
                            <span className="admin-template-level" key={level}>
                              {level === "first_month"
                                ? t("admin.templates.firstMonth")
                                : t(`catalog.difficulty.${level}`)}
                            </span>
                          ))}
                        </span>
                        <span aria-hidden="true" className="admin-accordion-chevron">⌄</span>
                      </span>
                    </button>
                  </header>
                  {programExpanded && (
                    <div className="admin-program-accordion-panel" id={programPanelId}>
                      <p className="admin-program-accordion-description">{english ? template.description_en : template.description_fa}</p>
                      <div className="admin-template-tags" aria-label={t("admin.templates.labels")}>
                        {template.focus_tags.map((tag) => <span key={tag}>{t(`admin.templates.tags.${tag}`)}</span>)}
                        {template.intensity_methods.filter((method) => method !== "standard").map((method) => (
                          <span key={method}>{t(`admin.templates.methods.${method}`)}</span>
                        ))}
                      </div>
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
                                            <div className="admin-template-exercise-actions">
                                              <Link
                                                aria-label={t("admin.templates.exerciseDetailAria", { name: exerciseName })}
                                                className="admin-template-exercise-detail"
                                                to={`/exercises/${slot.exercise.slug}`}
                                              >
                                                <span aria-hidden="true">↗</span>
                                                {t("admin.templates.exerciseDetail")}
                                              </Link>
                                              <button
                                                aria-label={t("admin.templates.exerciseEditAria", { name: exerciseName })}
                                                className="admin-template-exercise-edit"
                                                onClick={() => setEditingSlot({
                                                  templateId: template.id,
                                                  dayId: day.id,
                                                  slot,
                                                  noviceDefaults: template.supported_levels.some(
                                                    (level) => level === "first_month" || level === "beginner",
                                                  ),
                                                })}
                                                type="button"
                                              >
                                                <span aria-hidden="true">✏️</span>
                                                {t("admin.templates.exerciseEdit")}
                                              </button>
                                            </div>
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
                    </div>
                  )}
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
        {editingSlot !== null && (
          <AdminTrainingTemplateSlotEditModal
            dayId={editingSlot.dayId}
            noviceDefaults={editingSlot.noviceDefaults}
            onClose={() => setEditingSlot(null)}
            onSaved={(updatedTemplate) => {
              setPage((current) => current === null
                ? current
                : { ...current, items: current.items.map((item) => item.id === updatedTemplate.id ? updatedTemplate : item) });
              setFeedback(t("admin.templates.exerciseSaved"));
              setEditingSlot(null);
            }}
            slot={editingSlot.slot}
            templateId={editingSlot.templateId}
          />
        )}
      </main>
    </div>
  );
}
