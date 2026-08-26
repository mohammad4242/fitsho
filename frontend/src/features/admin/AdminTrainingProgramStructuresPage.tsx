import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import appTrainingAccent from "../../assets/landing/app-training-accent.jpg";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import {
  activateAdminTrainingProgramStructure,
  deactivateAdminTrainingProgramStructure,
  getAdminTrainingProgramStructures,
} from "./api";
import type {
  AdminTrainingProgramStructure,
  StructureFamily,
} from "./types";
import "./admin.css";

const trainingDays = [2, 3, 4, 5, 6] as const;
const familyFilters: Array<StructureFamily | "all"> = ["all", "upper_lower", "split"];

export function AdminTrainingProgramStructuresPage() {
  const { i18n, t } = useTranslation();
  const english = i18n.resolvedLanguage === "en";
  const [daysPerWeek, setDaysPerWeek] = useState<(typeof trainingDays)[number]>(2);
  const [family, setFamily] = useState<StructureFamily | "all">("all");
  const [structures, setStructures] = useState<AdminTrainingProgramStructure[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [retry, setRetry] = useState(0);
  const [actionId, setActionId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const visibleFamilyFilters = daysPerWeek <= 3 ? ["all" as const] : familyFilters;

  useEffect(() => {
    let active = true;
    setState("loading");
    getAdminTrainingProgramStructures(daysPerWeek, family === "all" ? undefined : family, true)
      .then((result) => {
        if (!active) return;
        setStructures(result.items);
        setState("ready");
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => { active = false; };
  }, [daysPerWeek, family, retry]);

  function familyLabel(value: StructureFamily | null) {
    if (value === "upper_lower") return t("admin.structureLibrary.upperLower");
    if (value === "split") return t("admin.structureLibrary.split");
    return t("admin.structureLibrary.direct");
  }

  function splitTypeLabel(value: AdminTrainingProgramStructure["split_type"]) {
    if (value === null) return null;
    return t(`admin.structureLibrary.splitTypes.${value}`);
  }

  async function toggleActive(structure: AdminTrainingProgramStructure) {
    setActionId(structure.id);
    setActionError(null);
    try {
      const updated = structure.is_active
        ? await deactivateAdminTrainingProgramStructure(structure.id)
        : await activateAdminTrainingProgramStructure(structure.id);
      setStructures((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch {
      setActionError(t("admin.structureLibrary.actionError"));
    } finally {
      setActionId(null);
    }
  }

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={appTrainingAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--templates">
        <header className="admin-hero admin-structure-hero">
          <div>
            <p className="eyebrow eyebrow--accent">{t("admin.structureLibrary.eyebrow")}</p>
            <h1 className="fitsho-display">{t("admin.structureLibrary.title")}</h1>
            <p>{t("admin.structureLibrary.intro")}</p>
          </div>
          <div className="admin-hero-actions">
            <Link className="admin-primary-link" to="/admin/training-program-structures/new">
              {t("admin.structureLibrary.add")}
            </Link>
            <Link className="admin-secondary-link" to="/admin/training-program-templates">
              {t("admin.structureLibrary.programLibrary")}
            </Link>
          </div>
        </header>

        <section className="admin-template-filters" aria-label={t("admin.structureLibrary.filters")}>
          <div className="admin-template-filter-group">
            <span>{t("admin.templates.dayFilter")}</span>
            <div className="admin-template-tabs" role="tablist" aria-label={t("admin.templates.dayFilter")}>
              {trainingDays.map((days) => (
                <button
                  aria-selected={days === daysPerWeek}
                  key={days}
                  onClick={() => {
                    setDaysPerWeek(days);
                    setFamily("all");
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
            <span>{t("admin.structureLibrary.familyFilter")}</span>
            <div className="admin-template-tabs" role="tablist" aria-label={t("admin.structureLibrary.familyFilter")}>
              {visibleFamilyFilters.map((value) => (
                <button
                  aria-selected={value === family}
                  key={value}
                  onClick={() => setFamily(value)}
                  role="tab"
                  type="button"
                >
                  {value === "all" ? t("admin.structureLibrary.allFamilies") : familyLabel(value)}
                </button>
              ))}
            </div>
          </div>
        </section>

        {state === "loading" && <p className="admin-status" role="status">{t("admin.structureLibrary.loading")}</p>}
        {state === "error" && (
          <div className="admin-status" role="alert">
            <p>{t("admin.structureLibrary.loadError")}</p>
            <button type="button" onClick={() => setRetry((value) => value + 1)}>{t("common.retry")}</button>
          </div>
        )}
        {actionError !== null && <p className="admin-status admin-status--error" role="alert">{actionError}</p>}
        {state === "ready" && structures.length === 0 && (
          <p className="admin-status">{t("admin.structureLibrary.empty")}</p>
        )}
        {state === "ready" && structures.length > 0 && (
          <section className="admin-structure-list" aria-label={t("admin.structureLibrary.list")}>
            {structures.map((structure) => {
              const name = english ? structure.name_en : structure.name_fa;
              const splitType = splitTypeLabel(structure.split_type);
              return (
                <article className="admin-structure-card" key={structure.id}>
                  <div className="admin-structure-card__header">
                    <div>
                      <p className="eyebrow">{t("admin.templates.days", { count: structure.days_per_week })}</p>
                      <h2>{name}</h2>
                    </div>
                    <span className={`admin-state ${structure.is_active ? "admin-state--active" : "admin-state--inactive"}`}>
                      {structure.is_active ? t("admin.structureLibrary.active") : t("admin.structureLibrary.inactive")}
                    </span>
                  </div>
                  <div className="admin-structure-card__meta">
                    <span>{familyLabel(structure.family)}</span>
                    {splitType !== null && <span>{splitType}</span>}
                    <code>{structure.slug}</code>
                  </div>
                  {(english ? structure.description_en : structure.description_fa) && (
                    <p className="admin-structure-card__description">{english ? structure.description_en : structure.description_fa}</p>
                  )}
                  <ol className="admin-structure-card__days">
                    {structure.structure_days.map((day) => (
                      <li key={day.id}>
                        <span>{day.day_number}</span>
                        <strong>{english ? day.label_en : day.label_fa}</strong>
                      </li>
                    ))}
                  </ol>
                  <footer className="admin-structure-card__actions">
                    <Link aria-label={t("admin.structureLibrary.editAria", { name })} to={`/admin/training-program-structures/${structure.id}/edit`}>
                      {t("admin.structureLibrary.edit")}
                    </Link>
                    <button
                      aria-label={t(`admin.structureLibrary.${structure.is_active ? "deactivate" : "activate"}Aria`, { name })}
                      disabled={actionId === structure.id}
                      onClick={() => void toggleActive(structure)}
                      type="button"
                    >
                      {structure.is_active ? t("admin.structureLibrary.deactivate") : t("admin.structureLibrary.activate")}
                    </button>
                  </footer>
                </article>
              );
            })}
          </section>
        )}
      </main>
    </div>
  );
}
