import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import appTrainingAccent from "../../assets/landing/app-training-accent.jpg";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import {
  createAdminTrainingProgramStructure,
  getAdminTrainingProgramStructure,
  updateAdminTrainingProgramStructure,
} from "./api";
import type {
  AdminTrainingProgramStructure,
  AdminTrainingProgramStructureDayWrite,
  AdminTrainingProgramStructureWrite,
  StructureFamily,
  StructureSplitType,
} from "./types";
import "./admin.css";

type EditorState = "loading" | "ready" | "missing";

const trainingDays = [2, 3, 4, 5, 6] as const;
const structureFamilies: StructureFamily[] = ["upper_lower", "split"];
const splitTypes: StructureSplitType[] = ["ppl", "body_part"];

function emptyDays(daysPerWeek: number): AdminTrainingProgramStructureDayWrite[] {
  return Array.from({ length: daysPerWeek }, (_, index) => ({
    day_number: index + 1,
    label_en: `Day ${index + 1}`,
    label_fa: `روز ${index + 1}`,
    day_type: null,
  }));
}

function emptyForm(daysPerWeek: number): AdminTrainingProgramStructureWrite {
  return {
    slug: "",
    name_en: "",
    name_fa: "",
    days_per_week: daysPerWeek,
    family: null,
    split_type: null,
    description_en: null,
    description_fa: null,
    days: emptyDays(daysPerWeek),
  };
}

function structureToForm(structure: AdminTrainingProgramStructure): AdminTrainingProgramStructureWrite {
  return {
    slug: structure.slug,
    name_en: structure.name_en,
    name_fa: structure.name_fa,
    days_per_week: structure.days_per_week,
    family: structure.family,
    split_type: structure.split_type,
    description_en: structure.description_en,
    description_fa: structure.description_fa,
    days: structure.structure_days.map((day) => ({
      day_number: day.day_number,
      label_en: day.label_en,
      label_fa: day.label_fa,
      day_type: day.day_type,
    })),
  };
}

export function AdminTrainingProgramStructureEditorPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { structureId } = useParams();
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState<AdminTrainingProgramStructureWrite>(() => (
    emptyForm(Number(searchParams.get("days")) || 2)
  ));
  const [state, setState] = useState<EditorState>(structureId === undefined ? "ready" : "loading");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (structureId === undefined) return;
    let active = true;
    getAdminTrainingProgramStructure(structureId)
      .then((structure) => {
        if (!active) return;
        setForm(structureToForm(structure));
        setState("ready");
      })
      .catch(() => {
        if (active) setState("missing");
      });
    return () => { active = false; };
  }, [structureId]);

  function setDaysPerWeek(daysPerWeek: number) {
    setForm((current) => ({
      ...current,
      days_per_week: daysPerWeek,
      family: daysPerWeek <= 3 ? null : current.family,
      split_type: daysPerWeek <= 3 || current.family !== "split" ? null : current.split_type,
      days: Array.from({ length: daysPerWeek }, (_, index) => current.days[index] ?? emptyDays(daysPerWeek)[index]),
    }));
  }

  function updateField<K extends keyof AdminTrainingProgramStructureWrite>(
    key: K,
    value: AdminTrainingProgramStructureWrite[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function updateDay(index: number, patch: Partial<AdminTrainingProgramStructureDayWrite>) {
    setForm((current) => ({
      ...current,
      days: current.days.map((day, dayIndex) => dayIndex === index ? { ...day, ...patch } : day),
    }));
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const saved = structureId === undefined
        ? await createAdminTrainingProgramStructure(form)
        : await updateAdminTrainingProgramStructure(structureId, form);
      navigate(`/admin/training-program-structures/${saved.id}/edit`, { replace: true });
    } catch {
      setError(t("admin.structureEditor.saveError"));
    } finally {
      setSaving(false);
    }
  }

  const title = structureId === undefined
    ? t("admin.structureEditor.titleNew")
    : t("admin.structureEditor.titleEdit");

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={appTrainingAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--form">
        <header className="admin-form-header">
          <div>
            <p className="eyebrow eyebrow--accent">{t("admin.structureEditor.eyebrow")}</p>
            <h1 className="fitsho-display">{title}</h1>
            <p>{t("admin.structureEditor.intro")}</p>
          </div>
          <Link to="/admin/training-program-structures">{t("admin.structureEditor.back")}</Link>
        </header>

        {state === "loading" && <p className="admin-status" role="status">{t("admin.structureEditor.loading")}</p>}
        {state === "missing" && <p className="admin-status admin-status--error">{t("admin.structureEditor.missing")}</p>}
        {state === "ready" && (
          <form className="admin-structure-editor" onSubmit={(event) => { event.preventDefault(); void save(); }}>
            <fieldset className="admin-form-section">
              <legend>{t("admin.structureEditor.identity")}</legend>
              <div className="admin-field-grid">
                <label className="admin-field">
                  {t("admin.structureEditor.nameFa")}
                  <input aria-label={t("admin.structureEditor.nameFa")} value={form.name_fa} onChange={(event) => updateField("name_fa", event.target.value)} required />
                </label>
                <label className="admin-field">
                  {t("admin.structureEditor.nameEn")}
                  <input aria-label={t("admin.structureEditor.nameEn")} value={form.name_en} onChange={(event) => updateField("name_en", event.target.value)} required />
                </label>
                <label className="admin-field">
                  {t("admin.structureEditor.slug")}
                  <input aria-label={t("admin.structureEditor.slug")} dir="ltr" value={form.slug} onChange={(event) => updateField("slug", event.target.value)} required />
                </label>
                <label className="admin-field">
                  {t("admin.structureEditor.daysPerWeek")}
                  <select aria-label={t("admin.structureEditor.daysPerWeek")} value={form.days_per_week} onChange={(event) => setDaysPerWeek(Number(event.target.value))}>
                    {trainingDays.map((days) => <option key={days} value={days}>{t("admin.templates.days", { count: days })}</option>)}
                  </select>
                </label>
                <label className="admin-field">
                  {t("admin.structureEditor.descriptionFa")}
                  <textarea value={form.description_fa ?? ""} onChange={(event) => updateField("description_fa", event.target.value || null)} />
                </label>
                <label className="admin-field">
                  {t("admin.structureEditor.descriptionEn")}
                  <textarea dir="ltr" value={form.description_en ?? ""} onChange={(event) => updateField("description_en", event.target.value || null)} />
                </label>
              </div>

              {form.days_per_week >= 4 && (
                <>
                  <label className="admin-field admin-structure-classification-field">
                    {t("admin.structureEditor.family")}
                    <select aria-label={t("admin.structureEditor.family")} value={form.family ?? ""} onChange={(event) => {
                      const nextFamily = (event.target.value || null) as StructureFamily | null;
                      updateField("family", nextFamily);
                      updateField("split_type", nextFamily === "split" ? form.split_type ?? "body_part" : null);
                    }} required>
                      <option value="">{t("admin.structureEditor.chooseFamily")}</option>
                      {structureFamilies.map((family) => (
                        <option key={family} value={family}>{family === "upper_lower" ? t("admin.structureEditor.upperLower") : t("admin.structureEditor.split")}</option>
                      ))}
                    </select>
                  </label>
                  {form.family === "split" && (
                    <label className="admin-field admin-structure-classification-field">
                      {t("admin.structureEditor.splitType")}
                      <select aria-label={t("admin.structureEditor.splitType")} value={form.split_type ?? ""} onChange={(event) => updateField("split_type", (event.target.value || null) as StructureSplitType | null)} required>
                        <option value="">{t("admin.structureEditor.chooseSplitType")}</option>
                        {splitTypes.map((splitType) => <option key={splitType} value={splitType}>{t(`admin.structureEditor.splitTypes.${splitType}`)}</option>)}
                      </select>
                    </label>
                  )}
                </>
              )}
            </fieldset>

            <fieldset className="admin-form-section">
              <legend>{t("admin.structureEditor.daysTitle")}</legend>
              <p className="admin-form-hint">{t("admin.structureEditor.daysHint")}</p>
              <div className="admin-structure-days">
                {form.days.map((day, index) => (
                  <article className="admin-structure-day-editor" key={day.day_number}>
                    <span className="admin-structure-day-editor__number">{day.day_number}</span>
                    <div className="admin-field-grid">
                      <label className="admin-field">
                        {t("admin.structureEditor.dayNameFa", { number: day.day_number })}
                        <input value={day.label_fa} onChange={(event) => updateDay(index, { label_fa: event.target.value })} required />
                      </label>
                      <label className="admin-field">
                        {t("admin.structureEditor.dayNameEn", { number: day.day_number })}
                        <input dir="ltr" value={day.label_en} onChange={(event) => updateDay(index, { label_en: event.target.value })} required />
                      </label>
                      <label className="admin-field admin-field--full-width">
                        {t("admin.structureEditor.dayType", { number: day.day_number })}
                        <input value={day.day_type ?? ""} onChange={(event) => updateDay(index, { day_type: event.target.value || null })} />
                      </label>
                    </div>
                  </article>
                ))}
              </div>
            </fieldset>

            {error !== null && <p className="admin-form-alert" role="alert">{error}</p>}
            <div className="admin-form-actions">
              <button className="admin-primary-link" disabled={saving} type="submit">
                {saving ? t("admin.structureEditor.saving") : t("admin.structureEditor.save")}
              </button>
            </div>
          </form>
        )}
      </main>
    </div>
  );
}
