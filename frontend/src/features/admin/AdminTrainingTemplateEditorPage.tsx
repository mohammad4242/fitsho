import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { muscleGroups, movementPatterns } from "../exercises/types";
import { fitnessGoals, type ExperienceLevel } from "../profile/types";
import appTrainingAccent from "../../assets/landing/app-training-accent.jpg";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import {
  createAdminTrainingProgramTemplate,
  deleteAdminTrainingProgramTemplate,
  getAdminExercises,
  getAdminTrainingProgramTemplate,
  updateAdminTrainingProgramTemplate,
} from "./api";
import { AdminAccordionSection } from "./AdminAccordionSection";
import type {
  AdminExercise,
  AdminTrainingProgramTemplate,
  AdminTrainingProgramTemplateWrite,
  AdminTrainingTemplateDayWrite,
  AdminTrainingTemplateSlotWrite,
  TrainingTemplateMethod,
  TrainingTemplateSlotPriority,
} from "./types";
import "./admin.css";

type EditorState = "loading" | "ready" | "missing" | "error";
type EditorSectionId = "identity" | "reasons" | "days";

const levels: ExperienceLevel[] = ["first_month", "beginner", "intermediate", "advanced"];
const methods: TrainingTemplateMethod[] = ["standard", "superset", "drop_set"];
const priorities: TrainingTemplateSlotPriority[] = ["core", "accessory", "optional"];

export function AdminTrainingTemplateEditorPage() {
  const { t } = useTranslation();
  const { templateId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [form, setForm] = useState<AdminTrainingProgramTemplateWrite>(() =>
    emptyTemplate(defaultDays(searchParams.get("days")), defaultLevel(searchParams.get("level"))),
  );
  const [state, setState] = useState<EditorState>(templateId === undefined ? "ready" : "loading");
  const [openSections, setOpenSections] = useState<Set<EditorSectionId>>(() =>
    new Set<EditorSectionId>(templateId === undefined ? ["identity", "days"] : ["days"]),
  );
  const [expandedDays, setExpandedDays] = useState<Set<number>>(() => new Set<number>());
  const [pickerDay, setPickerDay] = useState<number | null>(null);
  const [exerciseSearch, setExerciseSearch] = useState("");
  const [exerciseResults, setExerciseResults] = useState<AdminExercise[]>([]);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (templateId === undefined) return;
    let active = true;
    void getAdminTrainingProgramTemplate(templateId)
      .then((template) => {
        if (!active) return;
        setForm(templateToForm(template));
        setState("ready");
      })
      .catch(() => {
        if (active) setState("missing");
      });
    return () => { active = false; };
  }, [templateId]);

  useEffect(() => {
    if (pickerDay === null || exerciseSearch.trim().length < 2) {
      setExerciseResults([]);
      return;
    }
    let active = true;
    void getAdminExercises({ search: exerciseSearch.trim(), is_active: true, page_size: 20 })
      .then((result) => {
        if (active) setExerciseResults(result.items);
      })
      .catch(() => {
        if (active) setExerciseResults([]);
      });
    return () => { active = false; };
  }, [exerciseSearch, pickerDay]);

  const slotCountProblems = useMemo(
    () => form.days.some((day) => day.slots.length < 5 || day.slots.length > 9),
    [form.days],
  );

  function toggleSection(sectionId: EditorSectionId) {
    setOpenSections((current) => {
      const next = new Set(current);
      if (next.has(sectionId)) next.delete(sectionId);
      else next.add(sectionId);
      return next;
    });
  }

  function toggleDay(dayIndex: number) {
    setExpandedDays((current) => {
      const next = new Set(current);
      if (next.has(dayIndex)) next.delete(dayIndex);
      else next.add(dayIndex);
      return next;
    });
  }

  function updateField<K extends keyof AdminTrainingProgramTemplateWrite>(
    key: K,
    value: AdminTrainingProgramTemplateWrite[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function setDaysPerWeek(daysPerWeek: number) {
    setForm((current) => ({
      ...current,
      days_per_week: daysPerWeek,
      days: resizeDays(current.days, daysPerWeek),
    }));
  }

  function toggleSupportedLevel(level: ExperienceLevel) {
    setForm((current) => {
      const selected = current.supported_levels.includes(level);
      if (selected && current.supported_levels.length === 1) return current;
      return {
        ...current,
        supported_levels: levels.filter((candidate) => (
          candidate === level ? !selected : current.supported_levels.includes(candidate)
        )),
      };
    });
  }

  function patchDay(dayIndex: number, patch: Partial<AdminTrainingTemplateDayWrite>) {
    setForm((current) => ({
      ...current,
      days: current.days.map((day, index) => index === dayIndex ? { ...day, ...patch } : day),
    }));
  }

  function patchSlot(
    dayIndex: number,
    slotIndex: number,
    patch: Partial<AdminTrainingTemplateSlotWrite>,
  ) {
    setForm((current) => ({
      ...current,
      days: current.days.map((day, index) => {
        if (index !== dayIndex) return day;
        return {
          ...day,
          slots: day.slots.map((slot, slotPosition) => (
            slotPosition === slotIndex ? { ...slot, ...patch } : slot
          )),
        };
      }),
    }));
  }

  function removeSlot(dayIndex: number, slotIndex: number) {
    setForm((current) => ({
      ...current,
      days: current.days.map((day, index) => (
        index === dayIndex
          ? { ...day, slots: day.slots.filter((_, position) => position !== slotIndex) }
          : day
      )),
    }));
  }

  function selectExercise(exercise: AdminExercise) {
    if (pickerDay === null) return;
    const muscles = exercise.primary_muscle === null
      ? exercise.secondary_muscles.slice(0, 1)
      : [exercise.primary_muscle, ...exercise.secondary_muscles];
    const slot: AdminTrainingTemplateSlotWrite = {
      exercise_id: exercise.id,
      display_name_en: exercise.name_en,
      display_name_fa: exercise.name_fa,
      target_muscles: muscles.length > 0 ? muscles : ["chest"],
      movement_pattern: exercise.movement_pattern,
      intensity_method: "standard",
      adaptation_priority: "core",
      superset_group: null,
      sets: 3,
      rep_min: 8,
      rep_max: 12,
      target_rir: 2,
      rest_seconds: 90,
    };
    setForm((current) => ({
      ...current,
      days: current.days.map((day, index) => (
        index === pickerDay ? { ...day, slots: [...day.slots, slot] } : day
      )),
    }));
    setExpandedDays((current) => new Set([...current, pickerDay]));
    setPickerDay(null);
    setExerciseSearch("");
  }

  async function save() {
    if (slotCountProblems) {
      setSaveError(t("admin.templateEditor.slotCountError"));
      return;
    }
    setSaving(true);
    setSaveError(null);
    const payload: AdminTrainingProgramTemplateWrite = {
      ...form,
      focus_tags: form.focus_tags.filter(Boolean),
      intensity_methods: uniqueMethods(form.days),
    };
    try {
      const saved = templateId === undefined
        ? await createAdminTrainingProgramTemplate(payload)
        : await updateAdminTrainingProgramTemplate(templateId, payload);
      navigate(`/admin/training-program-templates/${saved.id}/edit`, { replace: true });
    } catch {
      setSaveError(t("admin.templateEditor.saveError"));
    } finally {
      setSaving(false);
    }
  }

  async function removeTemplate() {
    if (templateId === undefined || !window.confirm(t("admin.templateEditor.deleteConfirm"))) {
      return;
    }
    setDeleting(true);
    setSaveError(null);
    try {
      await deleteAdminTrainingProgramTemplate(templateId);
      navigate("/admin/training-program-templates", { replace: true });
    } catch {
      setSaveError(t("admin.templateEditor.deleteError"));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={appTrainingAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--template-editor">
        <header className="admin-form-header">
          <div>
            <p className="eyebrow eyebrow--accent">{t("admin.templateEditor.eyebrow")}</p>
            <h1>{templateId === undefined ? t("admin.templateEditor.titleNew") : t("admin.templateEditor.titleEdit")}</h1>
            <p>{t("admin.templateEditor.intro")}</p>
          </div>
          <Link to="/admin/training-program-templates">{t("admin.templateEditor.back")}</Link>
        </header>

        {state === "loading" && <p className="admin-status" role="status">{t("admin.templateEditor.loading")}</p>}
        {state === "missing" && <p className="admin-status" role="alert">{t("admin.templateEditor.missing")}</p>}
        {state === "ready" && (
          <form className="admin-template-editor" noValidate onSubmit={(event) => { event.preventDefault(); void save(); }}>
            {saveError !== null && <p className="admin-form-alert" role="alert">{saveError}</p>}
            <AdminAccordionSection
              id="identity"
              isOpen={openSections.has("identity")}
              onToggle={() => toggleSection("identity")}
              title={t("admin.templateEditor.identity")}
            >
              <div className="admin-template-editor-grid">
                <TextInput label={t("admin.templateEditor.nameFa")} value={form.name_fa} onChange={(value) => updateField("name_fa", value)} />
                <TextInput label={t("admin.templateEditor.nameEn")} value={form.name_en} onChange={(value) => updateField("name_en", value)} />
                <TextArea label={t("admin.templateEditor.descriptionFa")} value={form.description_fa} onChange={(value) => updateField("description_fa", value)} />
                <TextArea label={t("admin.templateEditor.descriptionEn")} value={form.description_en} onChange={(value) => updateField("description_en", value)} />
                <label>{t("admin.templateEditor.daysPerWeek")}
                  <select aria-label={t("admin.templateEditor.daysPerWeek")} value={form.days_per_week} onChange={(event) => setDaysPerWeek(Number(event.target.value))}>
                    {[2, 3, 4, 5, 6].map((days) => <option key={days} value={days}>{t("admin.templates.days", { count: days })}</option>)}
                  </select>
                </label>
                <fieldset className="admin-template-level-selector">
                  <legend>{t("admin.templateEditor.supportedLevels")}</legend>
                  <p>{t("admin.templateEditor.supportedLevelsHint")}</p>
                  <div className="admin-template-level-options">
                    {levels.map((level) => (
                      <label className="admin-template-level-option" key={level}>
                        <input
                          checked={form.supported_levels.includes(level)}
                          onChange={() => toggleSupportedLevel(level)}
                          type="checkbox"
                        />
                        <span>{level === "first_month" ? t("admin.templates.firstMonth") : t(`catalog.difficulty.${level}`)}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
                <label>{t("admin.templateEditor.goal")}
                  <select value={form.fitness_goal} onChange={(event) => updateField("fitness_goal", event.target.value as AdminTrainingProgramTemplateWrite["fitness_goal"])}>
                    {fitnessGoals.map((goal) => <option key={goal} value={goal}>{t(`onboarding.fitnessGoal.${goal}`)}</option>)}
                  </select>
                </label>
                <TextInput label={t("admin.templateEditor.focusTags")} value={form.focus_tags.join(", ")} onChange={(value) => updateField("focus_tags", splitValues(value))} />
                <TextInput label={t("admin.templateEditor.sourceName")} value={form.source_name} onChange={(value) => updateField("source_name", value)} />
                <TextInput label={t("admin.templateEditor.sourceUrl")} value={form.source_url} onChange={(value) => updateField("source_url", value)} />
              </div>
            </AdminAccordionSection>

            <AdminAccordionSection
              id="program-reasons"
              isOpen={openSections.has("reasons")}
              onToggle={() => toggleSection("reasons")}
              title={t("admin.templateEditor.programReasons")}
            >
              <div className="admin-template-rationale-editor">
                {form.programming_rationale.map((reason, index) => (
                  <div key={index}>
                    <strong>{t("admin.templateEditor.reasonNumber", { number: index + 1 })}</strong>
                    <TextInput label={t("admin.templateEditor.reasonTitleFa")} value={reason.title_fa} onChange={(value) => updateReason(setForm, index, "title_fa", value)} />
                    <TextArea label={t("admin.templateEditor.reasonDetailFa")} value={reason.detail_fa} onChange={(value) => updateReason(setForm, index, "detail_fa", value)} />
                    <TextInput label={t("admin.templateEditor.reasonTitleEn")} value={reason.title_en} onChange={(value) => updateReason(setForm, index, "title_en", value)} />
                    <TextArea label={t("admin.templateEditor.reasonDetailEn")} value={reason.detail_en} onChange={(value) => updateReason(setForm, index, "detail_en", value)} />
                  </div>
                ))}
              </div>
            </AdminAccordionSection>

            <AdminAccordionSection
              id="training-days"
              isOpen={openSections.has("days")}
              onToggle={() => toggleSection("days")}
              title={t("admin.templateEditor.trainingDays")}
            >
              <div className="admin-template-editor-days">
                {form.days.map((day, dayIndex) => {
                  const isDayExpanded = expandedDays.has(dayIndex);
                  const dayPanelId = `admin-template-day-panel-${dayIndex}`;
                  const dayName = (day.title_fa || day.title_en || "").trim() || t("admin.templates.dayNumber", { number: dayIndex + 1 });
                  return (
                    <section
                      className="admin-template-editor-day"
                      data-expanded={isDayExpanded}
                      key={dayIndex}
                    >
                      <header className="admin-accordion-header">
                        <button
                          aria-controls={dayPanelId}
                          aria-expanded={isDayExpanded}
                          aria-label={t(`admin.templates.${isDayExpanded ? "collapseDayAria" : "expandDayAria"}`, {
                            name: dayName,
                            number: dayIndex + 1,
                          })}
                          className="admin-day-accordion-trigger admin-template-editor-day__trigger"
                          onClick={() => toggleDay(dayIndex)}
                          type="button"
                        >
                          <span className="admin-template-editor-day__meta">
                            <span className="admin-template-editor-day__badge">
                              {t("admin.templates.dayNumber", { number: dayIndex + 1 })}
                            </span>
                            <strong className="admin-template-editor-day__title">{dayName}</strong>
                            <small className="admin-template-editor-day__count">
                              {t("admin.templateEditor.slotCount", { count: day.slots.length })}
                            </small>
                          </span>
                          <span aria-hidden="true" className="admin-accordion-chevron">⌄</span>
                        </button>
                      </header>

                      {isDayExpanded && (
                        <div className="admin-day-accordion-panel admin-template-editor-day__panel" id={dayPanelId}>
                          <div className="admin-template-editor-grid">
                            <TextInput label={t("admin.templateEditor.dayNameFa")} value={day.title_fa} onChange={(value) => patchDay(dayIndex, { title_fa: value })} />
                            <TextInput label={t("admin.templateEditor.dayNameEn")} value={day.title_en} onChange={(value) => patchDay(dayIndex, { title_en: value })} />
                            <TextInput label={t("admin.templateEditor.structureFocus")} value={day.structure_focus} onChange={(value) => patchDay(dayIndex, { structure_focus: value })} />
                            <TextInput label={t("admin.templateEditor.targetMuscles")} value={day.direct_target_muscles.join(", ")} onChange={(value) => patchDay(dayIndex, { direct_target_muscles: parseMuscles(value) })} />
                          </div>
                          <ol>
                            {day.slots.map((slot, slotIndex) => (
                              <li className="admin-template-editor-slot" key={`${slot.exercise_id}-${slotIndex}`}>
                                <div className="admin-template-editor-slot__topline">
                                  <strong>{slot.display_name_fa ?? slot.display_name_en ?? t("admin.templateEditor.exercise")}</strong>
                                  <Link to={`/admin/exercises/${slot.exercise_id}/edit`}>{t("admin.templateEditor.exerciseDetails")}</Link>
                                  <button aria-label={t("admin.templateEditor.removeExerciseAria", { name: slot.display_name_fa ?? slot.display_name_en })} onClick={() => removeSlot(dayIndex, slotIndex)} type="button">{t("admin.templateEditor.removeExercise")}</button>
                                </div>
                                <div className="admin-template-editor-grid admin-template-editor-grid--slot">
                                  <TextInput label={t("admin.templateEditor.displayNameFa")} value={slot.display_name_fa ?? ""} onChange={(value) => patchSlot(dayIndex, slotIndex, { display_name_fa: value || null })} />
                                  <TextInput label={t("admin.templateEditor.displayNameEn")} value={slot.display_name_en ?? ""} onChange={(value) => patchSlot(dayIndex, slotIndex, { display_name_en: value || null })} />
                                  <NumberInput label={t("admin.templateEditor.sets")} value={slot.sets} onChange={(value) => patchSlot(dayIndex, slotIndex, { sets: value })} />
                                  <NumberInput label={t("admin.templateEditor.repMin")} value={slot.rep_min} onChange={(value) => patchSlot(dayIndex, slotIndex, { rep_min: value })} />
                                  <NumberInput label={t("admin.templateEditor.repMax")} value={slot.rep_max} onChange={(value) => patchSlot(dayIndex, slotIndex, { rep_max: value })} />
                                  <NumberInput label={t("admin.templateEditor.rir")} value={slot.target_rir} onChange={(value) => patchSlot(dayIndex, slotIndex, { target_rir: value })} />
                                  <NumberInput label={t("admin.templateEditor.rest")} value={slot.rest_seconds} onChange={(value) => patchSlot(dayIndex, slotIndex, { rest_seconds: value })} />
                                  <label>{t("admin.templateEditor.method")}<select value={slot.intensity_method} onChange={(event) => patchSlot(dayIndex, slotIndex, { intensity_method: event.target.value as TrainingTemplateMethod })}>{methods.map((method) => <option key={method} value={method}>{t(`admin.templates.methods.${method}`)}</option>)}</select></label>
                                  <label>{t("admin.templateEditor.priority")}<select value={slot.adaptation_priority} onChange={(event) => patchSlot(dayIndex, slotIndex, { adaptation_priority: event.target.value as TrainingTemplateSlotPriority })}>{priorities.map((priority) => <option key={priority} value={priority}>{t(`admin.templateEditor.priorities.${priority}`)}</option>)}</select></label>
                                  <label>{t("admin.templateEditor.movementPattern")}<select value={slot.movement_pattern} onChange={(event) => patchSlot(dayIndex, slotIndex, { movement_pattern: event.target.value as AdminTrainingTemplateSlotWrite["movement_pattern"] })}>{movementPatterns.map((pattern) => <option key={pattern} value={pattern}>{t(`admin.programming.movementPattern.${pattern}`)}</option>)}</select></label>
                                  <TextInput label={t("admin.templateEditor.slotMuscles")} value={slot.target_muscles.join(", ")} onChange={(value) => patchSlot(dayIndex, slotIndex, { target_muscles: parseMuscles(value) })} />
                                </div>
                              </li>
                            ))}
                          </ol>
                          <button className="admin-template-editor-add" onClick={() => setPickerDay(dayIndex)} type="button">{t("admin.templateEditor.addExercise")}</button>
                        </div>
                      )}
                    </section>
                  );
                })}
              </div>
            </AdminAccordionSection>

            {pickerDay !== null && (
              <section className="admin-template-exercise-picker" aria-label={t("admin.templateEditor.exercisePicker")}>
                <header><h2>{t("admin.templateEditor.exercisePicker")}</h2><button onClick={() => setPickerDay(null)} type="button">{t("admin.templateEditor.close")}</button></header>
                <input autoFocus onChange={(event) => setExerciseSearch(event.target.value)} placeholder={t("admin.templateEditor.searchPlaceholder")} value={exerciseSearch} />
                <div>{exerciseResults.map((exercise) => <button key={exercise.id} onClick={() => selectExercise(exercise)} type="button">{t("admin.templateEditor.selectExercise", { name: exercise.name_fa })}{exercise.needs_review ? ` · ${t("admin.templates.reviewMedia")}` : ""}</button>)}</div>
              </section>
            )}

            <footer className="admin-template-editor-actions">
              <span>{slotCountProblems && t("admin.templateEditor.slotCountHint")}</span>
              <div>
                {templateId !== undefined && (
                  <button className="admin-template-delete" disabled={deleting || saving} onClick={() => { void removeTemplate(); }} type="button">
                    {deleting ? t("admin.templateEditor.deleting") : t("admin.templateEditor.delete")}
                  </button>
                )}
                <button className="admin-primary-link" disabled={saving || deleting} type="submit">{saving ? t("admin.templateEditor.saving") : t("admin.templateEditor.save")}</button>
              </div>
            </footer>
          </form>
        )}
      </main>
    </div>
  );
}

function TextInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label>{label}<input aria-label={label} onChange={(event) => onChange(event.target.value)} value={value} /></label>;
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label>{label}<textarea aria-label={label} onChange={(event) => onChange(event.target.value)} value={value} /></label>;
}

function NumberInput({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <label>{label}<input aria-label={label} min="0" onChange={(event) => onChange(Number(event.target.value))} type="number" value={value} /></label>;
}

function defaultDays(value: string | null): number {
  const parsed = Number(value);
  return parsed >= 2 && parsed <= 6 ? parsed : 2;
}

function defaultLevel(value: string | null): ExperienceLevel {
  return levels.includes(value as ExperienceLevel) ? value as ExperienceLevel : "beginner";
}

function emptyTemplate(daysPerWeek: number, level: ExperienceLevel): AdminTrainingProgramTemplateWrite {
  return {
    name_en: "New Training Program",
    name_fa: "برنامه تمرینی جدید",
    description_en: "A new Fitsho training-program reference.",
    description_fa: "برنامه مرجع جدید فیتشو.",
    days_per_week: daysPerWeek,
    supported_levels: [level],
    fitness_goal: "build_muscle",
    focus_tags: ["full_body", "balanced"],
    intensity_methods: ["standard"],
    programming_rationale: Array.from({ length: 5 }, (_, index) => ({ title_en: `Reason ${index + 1}`, title_fa: `علت ${index + 1}`, detail_en: "Explain this program decision.", detail_fa: "دلیل این تصمیم برنامه‌نویسی را بنویس.", })),
    source_name: "Fitsho admin library",
    source_url: "https://fitsho.local/admin-library",
    days: Array.from({ length: daysPerWeek }, (_, index) => emptyDay(index + 1)),
  };
}

function emptyDay(dayNumber: number): AdminTrainingTemplateDayWrite {
  return { title_en: `Day ${dayNumber}`, title_fa: `روز ${dayNumber}`, structure_focus: "full_body", direct_target_muscles: ["chest"], slots: [] };
}

function resizeDays(days: AdminTrainingTemplateDayWrite[], target: number): AdminTrainingTemplateDayWrite[] {
  return Array.from({ length: target }, (_, index) => days[index] ?? emptyDay(index + 1));
}

function templateToForm(template: AdminTrainingProgramTemplate): AdminTrainingProgramTemplateWrite {
  return {
    ...template,
    days: template.days.map((day) => ({
      title_en: day.title_en,
      title_fa: day.title_fa,
      structure_focus: day.structure_focus,
      direct_target_muscles: day.direct_target_muscles,
      slots: day.slots.filter((slot) => slot.exercise !== null).map((slot) => ({
        exercise_id: slot.exercise!.id,
        display_name_en: slot.placeholder_name_en,
        display_name_fa: slot.placeholder_name_fa,
        target_muscles: slot.target_muscles,
        movement_pattern: slot.movement_pattern,
        intensity_method: slot.intensity_method,
        adaptation_priority: slot.adaptation_priority,
        superset_group: slot.superset_group,
        sets: slot.sets,
        rep_min: slot.rep_min,
        rep_max: slot.rep_max,
        target_rir: slot.target_rir,
        rest_seconds: slot.rest_seconds,
      })),
    })),
  };
}

function splitValues(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function parseMuscles(value: string): AdminTrainingTemplateDayWrite["direct_target_muscles"] {
  const values = splitValues(value).filter((item): item is AdminTrainingTemplateDayWrite["direct_target_muscles"][number] => muscleGroups.includes(item as AdminTrainingTemplateDayWrite["direct_target_muscles"][number]));
  return values.length > 0 ? values : ["chest"];
}

function uniqueMethods(days: AdminTrainingTemplateDayWrite[]): TrainingTemplateMethod[] {
  return Array.from(new Set(days.flatMap((day) => day.slots.map((slot) => slot.intensity_method))));
}

function updateReason(
  setForm: Dispatch<SetStateAction<AdminTrainingProgramTemplateWrite>>,
  index: number,
  key: keyof AdminTrainingProgramTemplateWrite["programming_rationale"][number],
  value: string,
) {
  setForm((current) => ({
    ...current,
    programming_rationale: current.programming_rationale.map((reason, reasonIndex) => (
      reasonIndex === index ? { ...reason, [key]: value } : reason
    )),
  }));
}
