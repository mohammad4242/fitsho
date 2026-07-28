import { cloneElement, type FormEvent, type ReactElement, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../shared/apiClient";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { ExerciseMedia } from "../exercises/ExerciseMedia";
import { bodyRegions, difficulties, equipment, type MuscleGroup } from "../exercises/types";
import { createAdminExercise } from "./api";
import type { AdminExerciseForm } from "./types";
import {
  emptyAdminExerciseForm,
  musclesByRegion,
  slugifyExerciseName,
  toAdminExerciseCreate,
  validateAdminExercise,
  type AdminValidationErrors,
} from "./validation";
import "./admin.css";

export function AdminExerciseNewPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [form, setForm] = useState<AdminExerciseForm>(emptyAdminExerciseForm);
  const [slugEdited, setSlugEdited] = useState(false);
  const [errors, setErrors] = useState<AdminValidationErrors>({});
  const [media, setMedia] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [requestError, setRequestError] = useState<"duplicate" | "api" | null>(null);

  useEffect(() => {
    if (media === null) { setPreview(null); return; }
    const url = URL.createObjectURL(media);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [media]);

  function setField<K extends keyof AdminExerciseForm>(key: K, value: AdminExerciseForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  }

  function toggleChoice<K extends "secondary_muscles" | "equipment">(
    key: K,
    value: AdminExerciseForm[K][number],
  ) {
    const values = form[key] as Array<typeof value>;
    setField(key, (values.includes(value) ? values.filter((item) => item !== value) : [...values, value]) as AdminExerciseForm[K]);
  }

  function changeList(key: "instructions_en" | "instructions_fa" | "safety_notes_en" | "safety_notes_fa", index: number, value: string) {
    const next = [...form[key]];
    next[index] = value;
    setField(key, next);
  }

  async function submitForm() {
    const nextErrors = validateAdminExercise(form);
    setErrors(nextErrors);
    setRequestError(null);
    if (Object.keys(nextErrors).length > 0) return;
    setBusy(true);
    try {
      const created = await createAdminExercise(toAdminExerciseCreate(form), media);
      navigate("/admin/exercises", { replace: true, state: { createdId: created.id } });
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setRequestError("duplicate");
        setErrors((current) => ({ ...current, slug: "required" }));
      } else {
        setRequestError("api");
        if (error instanceof ApiError && error.details) {
          const field = error.details[0]?.loc?.at(-1);
          if (typeof field === "string" && field in form) {
            setErrors((current) => ({ ...current, [field]: "required" }));
          }
        }
      }
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void submitForm();
  }

  const availableMuscles = form.body_region ? musclesByRegion[form.body_region] : [];
  const previewType = media?.type.startsWith("video/") ? "video" : media ? "gif" : "placeholder";
  const errorText = (key: keyof AdminExerciseForm) => errors[key] ? t(`admin.validation.${errors[key]}`) : null;

  return (
    <div className="admin-page">
      <AuthenticatedHeader />
      <main className="admin-main admin-main--form">
        <header className="admin-form-header">
          <div><p className="eyebrow eyebrow--accent">{t("admin.new.eyebrow")}</p><h1>{t("admin.new.title")}</h1><p>{t("admin.new.intro")}</p></div>
          <Link to="/admin/exercises">{t("admin.new.back")}</Link>
        </header>
        <form className="admin-form" noValidate onSubmit={handleSubmit}>
          {(Object.keys(errors).length > 0 || requestError) && (
            <div className="admin-form-alert" role="alert">
              {requestError === "duplicate" ? t("admin.errors.duplicate") : requestError === "api" ? t("admin.errors.api") : t("admin.errors.validation")}
              {requestError === "api" && <button type="button" onClick={() => void submitForm()}>{t("common.retry")}</button>}
            </div>
          )}
          <fieldset className="admin-form-section"><legend>{t("admin.sections.identity")}</legend><div className="admin-field-grid">
            <Field label={t("admin.fields.nameEn")} error={errorText("name_en")}><input dir="ltr" value={form.name_en} onChange={(event) => { const value = event.target.value; setField("name_en", value); if (!slugEdited) setField("slug", slugifyExerciseName(value)); }} /></Field>
            <Field label={t("admin.fields.nameFa")} error={errorText("name_fa")}><input dir="rtl" value={form.name_fa} onChange={(event) => setField("name_fa", event.target.value)} /></Field>
            <Field label={t("admin.fields.slug")} error={requestError === "duplicate" ? t("admin.errors.duplicate") : errorText("slug")}><input dir="ltr" value={form.slug} onChange={(event) => { setSlugEdited(true); setField("slug", event.target.value); }} /></Field>
            <Field label={t("admin.fields.difficulty")}><select value={form.difficulty} onChange={(event) => setField("difficulty", event.target.value as AdminExerciseForm["difficulty"])}>{difficulties.map((value) => <option key={value} value={value}>{t(`catalog.difficulty.${value}`)}</option>)}</select></Field>
          </div></fieldset>
          <fieldset className="admin-form-section"><legend>{t("admin.sections.target")}</legend><div className="admin-field-grid">
            <Field label={t("admin.fields.bodyRegion")} error={errorText("body_region")}><select value={form.body_region} onChange={(event) => { setField("body_region", event.target.value as AdminExerciseForm["body_region"]); setField("primary_muscle", ""); setField("secondary_muscles", []); }}><option value="">{t("admin.fields.select")}</option>{bodyRegions.map((value) => <option key={value} value={value}>{t(`catalog.bodyRegion.${value}`)}</option>)}</select></Field>
            <Field label={t("admin.fields.primaryMuscle")} error={errorText("primary_muscle")}><select value={form.primary_muscle} disabled={!form.body_region} onChange={(event) => setField("primary_muscle", event.target.value as MuscleGroup)}><option value="">{t("admin.fields.select")}</option>{availableMuscles.map((value) => <option key={value} value={value}>{t(`catalog.muscle.${value}`)}</option>)}</select></Field>
          </div><ChoiceGroup legend={t("admin.fields.secondaryMuscles")} error={errorText("secondary_muscles")} values={availableMuscles} selected={form.secondary_muscles} label={(value) => `${t("admin.fields.secondaryPrefix")}: ${t(`catalog.muscle.${value}`)}`} onToggle={(value) => toggleChoice("secondary_muscles", value)} /><ChoiceGroup legend={t("admin.fields.equipment")} error={errorText("equipment")} values={equipment} selected={form.equipment} label={(value) => t(`catalog.equipment.${value}`)} onToggle={(value) => toggleChoice("equipment", value)} /></fieldset>
          <fieldset className="admin-form-section"><legend>{t("admin.sections.guidance")}</legend>
            <Repeater title={t("admin.fields.instructionsEn")} itemLabel={t("admin.fields.instructionEn")} addLabel={t("admin.actions.addInstructionEn")} values={form.instructions_en} error={errorText("instructions_en")} max={6} min={3} dir="ltr" onChange={(i,v) => changeList("instructions_en",i,v)} onAdd={() => setField("instructions_en", [...form.instructions_en, ""])} onRemove={(i) => setField("instructions_en", form.instructions_en.filter((_,x) => x !== i))} />
            <Repeater title={t("admin.fields.instructionsFa")} itemLabel={t("admin.fields.instructionFa")} addLabel={t("admin.actions.addInstructionFa")} values={form.instructions_fa} error={errorText("instructions_fa")} max={6} min={3} dir="rtl" onChange={(i,v) => changeList("instructions_fa",i,v)} onAdd={() => setField("instructions_fa", [...form.instructions_fa, ""])} onRemove={(i) => setField("instructions_fa", form.instructions_fa.filter((_,x) => x !== i))} />
            <Repeater title={t("admin.fields.safetyEn")} itemLabel={t("admin.fields.noteEn")} addLabel={t("admin.actions.addSafetyEn")} values={form.safety_notes_en} error={errorText("safety_notes_en")} max={8} min={1} dir="ltr" onChange={(i,v) => changeList("safety_notes_en",i,v)} onAdd={() => setField("safety_notes_en", [...form.safety_notes_en, ""])} onRemove={(i) => setField("safety_notes_en", form.safety_notes_en.filter((_,x) => x !== i))} />
            <Repeater title={t("admin.fields.safetyFa")} itemLabel={t("admin.fields.noteFa")} addLabel={t("admin.actions.addSafetyFa")} values={form.safety_notes_fa} error={errorText("safety_notes_fa")} max={8} min={1} dir="rtl" onChange={(i,v) => changeList("safety_notes_fa",i,v)} onAdd={() => setField("safety_notes_fa", [...form.safety_notes_fa, ""])} onRemove={(i) => setField("safety_notes_fa", form.safety_notes_fa.filter((_,x) => x !== i))} />
          </fieldset>
          <fieldset className="admin-form-section admin-media-section"><legend>{t("admin.sections.media")}</legend><div className="admin-media-preview"><ExerciseMedia path={preview ?? ""} mediaType={previewType} name={form.name_fa || form.name_en || t("admin.fields.previewName")} /></div><div className="admin-field-grid">
            <Field label={t("admin.fields.mediaFile")}><input type="file" accept="image/gif,video/mp4,video/webm" onChange={(event) => setMedia(event.target.files?.[0] ?? null)} /></Field>
            <Field label={t("admin.fields.sourceUrl")} error={errorText("media_source_url")}><input dir="ltr" type="url" value={form.media_source_url ?? ""} onChange={(event) => setField("media_source_url", event.target.value)} /></Field>
            <Field label={t("admin.fields.license")}><input value={form.media_license ?? ""} onChange={(event) => setField("media_license", event.target.value)} /></Field>
            <Field label={t("admin.fields.attribution")}><input value={form.media_attribution ?? ""} onChange={(event) => setField("media_attribution", event.target.value)} /></Field>
          </div></fieldset>
          <label className="admin-active-toggle"><input type="checkbox" checked={form.is_active} onChange={(event) => setField("is_active", event.target.checked)} /><span>{t("admin.fields.active")}</span></label>
          <div className="admin-form-actions"><button className="admin-primary-link" type="submit" disabled={busy}>{busy ? t("admin.actions.saving") : t("admin.actions.save")}</button></div>
        </form>
      </main>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string | null; children: ReactElement<{ id?: string; "aria-invalid"?: boolean; "aria-describedby"?: string }> }) { const id = `admin-${label.replace(/\s+/g,"-")}`; return <div className="admin-field"><label htmlFor={id}>{label}</label>{cloneElement(children, { id, "aria-invalid": Boolean(error), "aria-describedby": error ? `${id}-error` : undefined })}{error && <small id={`${id}-error`} role="status">{error}</small>}</div>; }
function ChoiceGroup<T extends string>({ legend, error, values, selected, label, onToggle }: { legend:string; error?:string|null; values:readonly T[]; selected:readonly T[]; label:(value:T)=>string; onToggle:(value:T)=>void }) { return <fieldset className="admin-choice-group"><legend>{legend}</legend><div>{values.map((value)=><label key={value}><input type="checkbox" checked={selected.includes(value)} onChange={()=>onToggle(value)} />{label(value)}</label>)}</div>{error && <small role="status">{error}</small>}</fieldset>; }
function Repeater({ title,itemLabel,addLabel,values,error,max,min,dir,onChange,onAdd,onRemove }:{ title:string; itemLabel:string; addLabel:string; values:string[]; error?:string|null; max:number; min:number; dir:"ltr"|"rtl"; onChange:(index:number,value:string)=>void; onAdd:()=>void; onRemove:(index:number)=>void }) { return <section className="admin-repeater"><h2>{title}</h2>{values.map((value,index)=>{ const number = localizedNumber(index + 1); return <div key={index}><label><span>{itemLabel} {number}</span><textarea dir={dir} value={value} onChange={(event)=>onChange(index,event.target.value)} /></label>{values.length>min && <button type="button" aria-label={`${tRemove()} ${itemLabel} ${number}`} onClick={()=>onRemove(index)}>×</button>}</div>; })}{error&&<small role="status">{error}</small>}{values.length<max&&<button type="button" onClick={onAdd}>{addLabel}</button>}</section>; }
function tRemove(){ return document.documentElement.lang === "en" ? "Remove" : "حذف"; }
function localizedNumber(value: number){ return document.documentElement.lang === "en" ? String(value) : new Intl.NumberFormat("fa-IR", { useGrouping: false }).format(value); }
