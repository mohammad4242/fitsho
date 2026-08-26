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
  getAdminTrainingProgramTemplate,
  updateAdminTrainingProgramTemplate,
} from "./api";
import { AdminAccordionSection } from "./AdminAccordionSection";
import { ExerciseLibraryPickerModal } from "./ExerciseLibraryPickerModal";
import { mapExerciseLibraryToTemplateFields } from "./trainingTemplateExerciseMapping";
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
type PickerTarget = {
  dayIndex: number;
  slotIndex: number | null;
  member?: "primary" | "superset";
};

type AdminTrainingTemplateSlotForm = Omit<AdminTrainingTemplateSlotWrite, "exercise_id"> & {
  exercise_id: string | null;
  exercise_name_fa?: string | null;
  exercise_name_en?: string | null;
  exercise_slug?: string | null;
  superset_exercise_name_fa?: string | null;
  superset_exercise_name_en?: string | null;
  superset_exercise_slug?: string | null;
};

type AdminTrainingTemplateDayForm = Omit<AdminTrainingTemplateDayWrite, "slots"> & {
  slots: AdminTrainingTemplateSlotForm[];
};

type AdminTrainingProgramTemplateForm = Omit<AdminTrainingProgramTemplateWrite, "days"> & {
  days: AdminTrainingTemplateDayForm[];
};

const levels: ExperienceLevel[] = ["first_month", "beginner", "intermediate", "advanced"];
const methods: TrainingTemplateMethod[] = ["standard", "superset", "drop_set"];
const priorities: TrainingTemplateSlotPriority[] = ["core", "accessory", "optional"];

export function AdminTrainingTemplateEditorPage() {
  const { t, i18n } = useTranslation();
  const english = i18n.resolvedLanguage === "en";
  const { templateId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [form, setForm] = useState<AdminTrainingProgramTemplateForm>(() =>
    emptyTemplate(defaultDays(searchParams.get("days")), defaultLevel(searchParams.get("level")), searchParams.get("structure_id")),
  );
  const [state, setState] = useState<EditorState>(templateId === undefined ? "ready" : "loading");
  const [openSections, setOpenSections] = useState<Set<EditorSectionId>>(() =>
    new Set<EditorSectionId>(templateId === undefined ? ["identity", "days"] : ["days"]),
  );
  const [expandedDays, setExpandedDays] = useState<Set<number>>(() => new Set<number>());
  const [expandedSlots, setExpandedSlots] = useState<Set<string>>(() => new Set<string>());
  const [pickerTarget, setPickerTarget] = useState<PickerTarget | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [structures, setStructures] = useState<import("./types").AdminTrainingProgramStructure[]>([]);

  useEffect(() => {
    let active = true;
    import("./api").then(({ getAdminTrainingProgramStructures }) => {
      getAdminTrainingProgramStructures(form.days_per_week).then((res) => {
        if (!active) return;
        setStructures(res.items);
      }).catch(console.error);
    });
    return () => { active = false; };
  }, [form.days_per_week]);

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

  function toggleSlot(slotKey: string) {
    setExpandedSlots((current) => {
      const next = new Set(current);
      if (next.has(slotKey)) next.delete(slotKey);
      else next.add(slotKey);
      return next;
    });
  }

  function updateField<K extends keyof AdminTrainingProgramTemplateForm>(
    key: K,
    value: AdminTrainingProgramTemplateForm[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function setDaysPerWeek(daysPerWeek: number) {
    setForm((current) => ({
      ...current,
      days_per_week: daysPerWeek,
      structure_id: null,
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

  function patchDay(dayIndex: number, patch: Partial<AdminTrainingTemplateDayForm>) {
    setForm((current) => ({
      ...current,
      days: current.days.map((day, index) => index === dayIndex ? { ...day, ...patch } : day),
    }));
  }

  function patchSlot(
    dayIndex: number,
    slotIndex: number,
    patch: Partial<AdminTrainingTemplateSlotForm>,
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
    const slotKeyPrefix = `${dayIndex}-`;
    setForm((current) => ({
      ...current,
      days: current.days.map((day, index) => (
        index === dayIndex
          ? { ...day, slots: day.slots.filter((_, position) => position !== slotIndex) }
          : day
      )),
    }));
    setExpandedSlots((current) => {
      const next = new Set<string>();
      current.forEach((key) => {
        if (!key.startsWith(slotKeyPrefix)) {
          next.add(key);
        }
      });
      return next;
    });
  }

  function selectExercise(exercise: AdminExercise) {
    if (pickerTarget === null) return;
    const { dayIndex, slotIndex } = pickerTarget;
    const selected = mapExerciseLibraryToTemplateFields(exercise);

    if (slotIndex !== null) {
      if (pickerTarget.member === "superset") {
        patchSlot(dayIndex, slotIndex, {
          superset_exercise_id: selected.exercise_id,
          superset_exercise_name_fa: selected.exercise_name_fa,
          superset_exercise_name_en: selected.exercise_name_en,
          superset_exercise_slug: selected.exercise_slug,
        });
      } else {
        patchSlot(dayIndex, slotIndex, {
          exercise_id: selected.exercise_id,
          exercise_name_fa: selected.exercise_name_fa,
          exercise_name_en: selected.exercise_name_en,
          exercise_slug: selected.exercise_slug,
          movement_pattern: selected.movement_pattern,
          target_muscles: selected.target_muscles,
        });
      }
    } else {
      // Add new slot to day
      const existingSlotCount = form.days[dayIndex]?.slots.length ?? 0;
      const slot: AdminTrainingTemplateSlotForm = {
        exercise_id: selected.exercise_id,
        exercise_name_fa: selected.exercise_name_fa,
        exercise_name_en: selected.exercise_name_en,
        exercise_slug: selected.exercise_slug,
        superset_exercise_id: null,
        superset_exercise_name_fa: null,
        superset_exercise_name_en: null,
        superset_exercise_slug: null,
        display_name_en: null,
        display_name_fa: null,
        target_muscles: selected.target_muscles,
        movement_pattern: selected.movement_pattern,
        intensity_method: "standard",
        adaptation_priority: "core",
        superset_group: null,
        sets: 3,
        rep_min: 8,
        rep_max: 12,
        target_rir: 2,
        rest_seconds: 90,
      };
      const newSlotKey = `${dayIndex}-${existingSlotCount}`;
      setForm((current) => ({
        ...current,
        days: current.days.map((day, index) => (
          index === dayIndex ? { ...day, slots: [...day.slots, slot] } : day
        )),
      }));
      setExpandedDays((current) => new Set([...current, dayIndex]));
      setExpandedSlots((current) => new Set([...current, newSlotKey]));
    }
    setPickerTarget(null);
  }

  function addDraftSlot(dayIndex: number) {
    const existingSlotCount = form.days[dayIndex]?.slots.length ?? 0;
    const slot: AdminTrainingTemplateSlotForm = {
      exercise_id: null,
      exercise_name_fa: null,
      exercise_name_en: null,
      exercise_slug: null,
      superset_exercise_id: null,
      superset_exercise_name_fa: null,
      superset_exercise_name_en: null,
      superset_exercise_slug: null,
      display_name_en: null,
      display_name_fa: null,
      target_muscles: ["chest"],
      movement_pattern: "other",
      intensity_method: "standard",
      adaptation_priority: "accessory",
      superset_group: null,
      sets: 3,
      rep_min: 8,
      rep_max: 12,
      target_rir: 2,
      rest_seconds: 90,
    };
    const newSlotKey = `${dayIndex}-${existingSlotCount}`;
    setForm((current) => ({
      ...current,
      days: current.days.map((day, index) => (
        index === dayIndex ? { ...day, slots: [...day.slots, slot] } : day
      )),
    }));
    setExpandedDays((current) => new Set([...current, dayIndex]));
    setExpandedSlots((current) => new Set([...current, newSlotKey]));
  }

  async function save() {
    if (slotCountProblems) {
      setSaveError(t("admin.templateEditor.slotCountError"));
      return;
    }
    setSaving(true);
    setSaveError(null);
    const payload = formToPayload(form);
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
                <TextInput dir="rtl" label={t("admin.templateEditor.nameFa")} value={form.name_fa} onChange={(value) => updateField("name_fa", value)} />
                <TextInput dir="ltr" label={t("admin.templateEditor.nameEn")} value={form.name_en} onChange={(value) => updateField("name_en", value)} />
                <TextArea dir="rtl" label={t("admin.templateEditor.descriptionFa")} value={form.description_fa} onChange={(value) => updateField("description_fa", value)} />
                <TextArea dir="ltr" label={t("admin.templateEditor.descriptionEn")} value={form.description_en} onChange={(value) => updateField("description_en", value)} />
                <label className="admin-field">
                  <span>{t("admin.templateEditor.daysPerWeek")}</span>
                  <select aria-label={t("admin.templateEditor.daysPerWeek")} value={form.days_per_week} onChange={(event) => setDaysPerWeek(Number(event.target.value))}>
                    {[2, 3, 4, 5, 6].map((days) => <option key={days} value={days}>{t("admin.templates.days", { count: days })}</option>)}
                  </select>
                </label>
                {structures.length > 0 && (
                  <label className="admin-field">
                    <span>{t("admin.templateEditor.structure")}</span>
                    <select aria-label={t("admin.templateEditor.structure")} value={form.structure_id || ""} onChange={(event) => updateField("structure_id", event.target.value || null)}>
                      <option value="">{t("admin.templateEditor.noStructure")}</option>
                      {structures.map((s) => (
                        <option key={s.id} value={s.id}>
                          {english ? s.name_en : s.name_fa}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
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
                <label className="admin-field">
                  <span>{t("admin.templateEditor.goal")}</span>
                  <select value={form.fitness_goal} onChange={(event) => updateField("fitness_goal", event.target.value as AdminTrainingProgramTemplateWrite["fitness_goal"])}>
                    {fitnessGoals.map((goal) => <option key={goal} value={goal}>{t(`onboarding.fitnessGoal.${goal}`)}</option>)}
                  </select>
                </label>
                <TextInput dir="ltr" label={t("admin.templateEditor.focusTags")} value={form.focus_tags.join(", ")} onChange={(value) => updateField("focus_tags", splitValues(value))} />
                <TextInput dir="auto" label={t("admin.templateEditor.sourceName")} value={form.source_name} onChange={(value) => updateField("source_name", value)} />
                <TextInput dir="ltr" label={t("admin.templateEditor.sourceUrl")} value={form.source_url} onChange={(value) => updateField("source_url", value)} />
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
                  <article className="admin-template-reason-card" key={index}>
                    <header className="admin-template-reason-card__header">
                      <span className="admin-template-reason-card__badge">
                        {t("admin.templateEditor.reasonNumber", { number: index + 1 })}
                      </span>
                    </header>
                    <div className="admin-template-reason-card__body">
                      <div className="admin-template-reason-card__group" dir="rtl">
                        <TextInput dir="rtl" label={t("admin.templateEditor.reasonTitleFa")} value={reason.title_fa} onChange={(value) => updateReason(setForm, index, "title_fa", value)} />
                        <TextArea dir="rtl" label={t("admin.templateEditor.reasonDetailFa")} value={reason.detail_fa} onChange={(value) => updateReason(setForm, index, "detail_fa", value)} />
                      </div>
                      <div className="admin-template-reason-card__group" dir="ltr">
                        <TextInput dir="ltr" label={t("admin.templateEditor.reasonTitleEn")} value={reason.title_en} onChange={(value) => updateReason(setForm, index, "title_en", value)} />
                        <TextArea dir="ltr" label={t("admin.templateEditor.reasonDetailEn")} value={reason.detail_en} onChange={(value) => updateReason(setForm, index, "detail_en", value)} />
                      </div>
                    </div>
                  </article>
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
                            <TextInput dir="rtl" label={t("admin.templateEditor.dayNameFa")} value={day.title_fa} onChange={(value) => patchDay(dayIndex, { title_fa: value })} />
                            <TextInput dir="ltr" label={t("admin.templateEditor.dayNameEn")} value={day.title_en} onChange={(value) => patchDay(dayIndex, { title_en: value })} />
                            <TextInput dir="ltr" label={t("admin.templateEditor.structureFocus")} value={day.structure_focus} onChange={(value) => patchDay(dayIndex, { structure_focus: value })} />
                            <TextInput dir="ltr" label={t("admin.templateEditor.targetMuscles")} value={day.direct_target_muscles.join(", ")} onChange={(value) => patchDay(dayIndex, { direct_target_muscles: parseMuscles(value) })} />
                          </div>
                          <ol>
                            {day.slots.map((slot, slotIndex) => {
                              const slotKey = `${dayIndex}-${slotIndex}`;
                              const isSlotExpanded = expandedSlots.has(slotKey);
                              const slotPanelId = `admin-template-slot-panel-${dayIndex}-${slotIndex}`;
                              const baseNameFa = slot.exercise_name_fa?.trim() || "";
                              const baseNameEn = slot.exercise_name_en?.trim() || "";
                              const overrideFa = slot.display_name_fa?.trim() || "";
                              const overrideEn = slot.display_name_en?.trim() || "";
                              const slotName =
                                overrideFa ||
                                baseNameFa ||
                                overrideEn ||
                                baseNameEn ||
                                t("admin.templates.dayNumber", { number: slotIndex + 1 });
                              const prescriptionSummary = `${slot.sets} × ${slot.rep_min}–${slot.rep_max} · RIR ${slot.target_rir}`;

                              return (
                                <li
                                  className="admin-template-editor-slot"
                                  data-expanded={isSlotExpanded}
                                  key={`${slot.exercise_id}-${slotIndex}`}
                                >
                                  <header className="admin-accordion-header">
                                    <button
                                      aria-controls={slotPanelId}
                                      aria-expanded={isSlotExpanded}
                                      aria-label={t(`admin.templates.${isSlotExpanded ? "collapseSlotAria" : "expandSlotAria"}`, {
                                        name: slotName,
                                        number: slotIndex + 1,
                                      })}
                                      className="admin-slot-accordion-trigger admin-template-editor-slot__trigger"
                                      onClick={() => toggleSlot(slotKey)}
                                      type="button"
                                    >
                                      <span className="admin-template-editor-slot__meta">
                                        <span className="admin-template-editor-slot__index">{slotIndex + 1}</span>
                                        {slot.intensity_method === "superset" ? (
                                          <div className="admin-template-editor-slot__title">
                                            <span className="admin-badge admin-badge--superset">{t("admin.templates.methods.superset")}</span>
                                            <div>A. {slot.exercise_name_fa || "?"}</div>
                                            <div>B. {slot.superset_exercise_name_fa || "?"}</div>
                                          </div>
                                        ) : (
                                          <strong className="admin-template-editor-slot__title">
                                            {slot.intensity_method === "drop_set" && <span className="admin-badge admin-badge--drop-set">{t("admin.templates.methods.drop_set")} </span>}
                                            {slotName}
                                          </strong>
                                        )}
                                        <span className="admin-template-editor-slot__prescription" dir="ltr">
                                          {prescriptionSummary}
                                        </span>
                                      </span>
                                      <span aria-hidden="true" className="admin-accordion-chevron">⌄</span>
                                    </button>
                                  </header>

                                  {isSlotExpanded && (
                                    <div className="admin-slot-accordion-panel admin-template-editor-slot__panel" id={slotPanelId}>
                                      <div className="admin-template-editor-grid admin-template-editor-grid--slot">
                                        <div className="admin-field admin-field--full-width">
                                          <span>{t("admin.templateEditor.executionMethod")}</span>
                                          <div className="admin-method-selector">
                                            {methods.map((method) => (
                                              <label key={method}>
                                                <input
                                                  type="radio"
                                                  name={`method-${slotKey}`}
                                                  value={method}
                                                  checked={slot.intensity_method === method}
                                                  onChange={(e) => {
                                                    const newMethod = e.target.value as TrainingTemplateMethod;
                                                    if (newMethod === "standard" || newMethod === "drop_set") {
                                                      patchSlot(dayIndex, slotIndex, {
                                                        intensity_method: newMethod,
                                                        superset_exercise_id: null,
                                                        superset_exercise_name_fa: null,
                                                        superset_exercise_name_en: null,
                                                        superset_exercise_slug: null,
                                                      });
                                                    } else {
                                                      patchSlot(dayIndex, slotIndex, {
                                                        intensity_method: newMethod,
                                                      });
                                                    }
                                                  }}
                                                />
                                                {t(`admin.templates.methods.${method}`)}
                                              </label>
                                            ))}
                                          </div>
                                        </div>

                                        <div className="admin-field admin-field--full-width">
                                          <span>{slot.intensity_method === "superset" ? t("admin.templateEditor.movement1") : t("admin.templateEditor.movement")}</span>
                                          <div className="admin-slot-picker-group">
                                            <strong>{slot.exercise_name_fa || t("admin.templateEditor.emptyMovement")}</strong>
                                            <button type="button" onClick={() => setPickerTarget({ dayIndex, slotIndex, member: "primary" })}>
                                              {t("admin.templateEditor.chooseFromLibrary")}
                                            </button>
                                          </div>
                                        </div>

                                        {slot.intensity_method === "superset" && (
                                          <div className="admin-field admin-field--full-width">
                                            <span>{t("admin.templateEditor.movement2")}</span>
                                            <div className="admin-slot-picker-group">
                                              <strong>{slot.superset_exercise_name_fa || t("admin.templateEditor.emptyMovement")}</strong>
                                              <button type="button" onClick={() => setPickerTarget({ dayIndex, slotIndex, member: "superset" })}>
                                                {t("admin.templateEditor.chooseFromLibrary")}
                                              </button>
                                            </div>
                                          </div>
                                        )}

                                        <TextInput
                                          dir="rtl"
                                          label={t("admin.templateEditor.displayNameFa")}
                                          placeholder={baseNameFa || undefined}
                                          value={slot.display_name_fa ?? ""}
                                          onChange={(value) => patchSlot(dayIndex, slotIndex, { display_name_fa: value || null })}
                                        />
                                        <TextInput
                                          dir="ltr"
                                          label={t("admin.templateEditor.displayNameEn")}
                                          placeholder={baseNameEn || undefined}
                                          value={slot.display_name_en ?? ""}
                                          onChange={(value) => patchSlot(dayIndex, slotIndex, { display_name_en: value || null })}
                                        />
                                        <NumberInput label={t("admin.templateEditor.sets")} value={slot.sets} onChange={(value) => patchSlot(dayIndex, slotIndex, { sets: value })} />
                                        <NumberInput label={t("admin.templateEditor.repMin")} value={slot.rep_min} onChange={(value) => patchSlot(dayIndex, slotIndex, { rep_min: value })} />
                                        <NumberInput label={t("admin.templateEditor.repMax")} value={slot.rep_max} onChange={(value) => patchSlot(dayIndex, slotIndex, { rep_max: value })} />
                                        <NumberInput label={t("admin.templateEditor.rir")} value={slot.target_rir} onChange={(value) => patchSlot(dayIndex, slotIndex, { target_rir: value })} />
                                        <NumberInput label={t("admin.templateEditor.rest")} value={slot.rest_seconds} onChange={(value) => patchSlot(dayIndex, slotIndex, { rest_seconds: value })} />

                                        <label className="admin-field">
                                          <span>{t("admin.templateEditor.priority")}</span>
                                          <select value={slot.adaptation_priority} onChange={(event) => patchSlot(dayIndex, slotIndex, { adaptation_priority: event.target.value as TrainingTemplateSlotPriority })}>
                                            {priorities.map((priority) => <option key={priority} value={priority}>{t(`admin.templateEditor.priorities.${priority}`)}</option>)}
                                          </select>
                                        </label>
                                        <label className="admin-field">
                                          <span>{t("admin.templateEditor.movementPattern")}</span>
                                          <select value={slot.movement_pattern} onChange={(event) => patchSlot(dayIndex, slotIndex, { movement_pattern: event.target.value as AdminTrainingTemplateSlotWrite["movement_pattern"] })}>
                                            {movementPatterns.map((pattern) => <option key={pattern} value={pattern}>{t(`admin.programming.movementPattern.${pattern}`)}</option>)}
                                          </select>
                                        </label>
                                        <TextInput dir="ltr" label={t("admin.templateEditor.slotMuscles")} value={slot.target_muscles.join(", ")} onChange={(value) => patchSlot(dayIndex, slotIndex, { target_muscles: parseMuscles(value) })} />
                                      </div>
                                      <div className="admin-template-editor-slot__actions-footer">
                                        {slot.exercise_id && (
                                            <Link to={`/admin/exercises/${slot.exercise_id}/edit`}>
                                              {t("admin.templateEditor.exerciseDetails")} ↗
                                            </Link>
                                        )}
                                        <button
                                          aria-label={t("admin.templateEditor.removeExerciseAria", { name: slotName })}
                                          onClick={() => removeSlot(dayIndex, slotIndex)}
                                          type="button"
                                          className="admin-slot-remove-btn"
                                        >
                                          {t("admin.templateEditor.removeExercise")}
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                </li>
                              );
                            })}
                          </ol>
                          <button className="admin-template-editor-add" onClick={() => addDraftSlot(dayIndex)} type="button">{t("admin.templateEditor.addExercise")}</button>
                        </div>
                      )}
                    </section>
                  );
                })}
              </div>
            </AdminAccordionSection>

            <ExerciseLibraryPickerModal
              isOpen={pickerTarget !== null}
              onClose={() => setPickerTarget(null)}
              onSelect={selectExercise}
            />

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

function TextInput({
  label,
  value,
  onChange,
  dir,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  dir?: "rtl" | "ltr" | "auto";
  placeholder?: string;
}) {
  return (
    <label className="admin-field">
      <span>{label}</span>
      <input aria-label={label} dir={dir} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} value={value} />
    </label>
  );
}

function TextArea({
  label,
  value,
  onChange,
  dir,
  placeholder,
  rows = 3,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  dir?: "rtl" | "ltr" | "auto";
  placeholder?: string;
  rows?: number;
}) {
  return (
    <label className="admin-field">
      <span>{label}</span>
      <textarea aria-label={label} dir={dir} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} rows={rows} value={value} />
    </label>
  );
}

function NumberInput({
  label,
  value,
  onChange,
  min = 0,
  max,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <label className="admin-field">
      <span>{label}</span>
      <input aria-label={label} dir="ltr" max={max} min={min} onChange={(event) => onChange(Number(event.target.value))} step={step} type="number" value={value} />
    </label>
  );
}

function defaultDays(value: string | null): number {
  const parsed = Number(value);
  return parsed >= 2 && parsed <= 6 ? parsed : 2;
}

function defaultLevel(value: string | null): ExperienceLevel {
  return levels.includes(value as ExperienceLevel) ? value as ExperienceLevel : "beginner";
}

function emptyTemplate(daysPerWeek: number, level: ExperienceLevel, structureId: string | null): AdminTrainingProgramTemplateForm {
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
    structure_id: structureId,
  };
}

function emptyDay(dayNumber: number): AdminTrainingTemplateDayForm {
  return { title_en: `Day ${dayNumber}`, title_fa: `روز ${dayNumber}`, structure_focus: "full_body", direct_target_muscles: ["chest"], slots: [] };
}

function resizeDays(days: AdminTrainingTemplateDayForm[], target: number): AdminTrainingTemplateDayForm[] {
  return Array.from({ length: target }, (_, index) => days[index] ?? emptyDay(index + 1));
}

function templateToForm(template: AdminTrainingProgramTemplate): AdminTrainingProgramTemplateForm {
  return {
    ...template,
    days: template.days.map((day) => ({
      title_en: day.title_en,
      title_fa: day.title_fa,
      structure_focus: day.structure_focus,
      direct_target_muscles: day.direct_target_muscles,
      slots: day.slots.filter((slot) => slot.exercise !== null).map((slot) => ({
        exercise_id: slot.exercise!.id,
        exercise_name_en: slot.exercise!.name_en,
        exercise_name_fa: slot.exercise!.name_fa,
        exercise_slug: slot.exercise!.slug,
        superset_exercise_id: slot.superset_exercise ? slot.superset_exercise.id : null,
        superset_exercise_name_en: slot.superset_exercise ? slot.superset_exercise.name_en : null,
        superset_exercise_name_fa: slot.superset_exercise ? slot.superset_exercise.name_fa : null,
        superset_exercise_slug: slot.superset_exercise ? slot.superset_exercise.slug : null,
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

function formToPayload(form: AdminTrainingProgramTemplateForm): AdminTrainingProgramTemplateWrite {
  return {
    name_en: form.name_en,
    name_fa: form.name_fa,
    description_en: form.description_en,
    description_fa: form.description_fa,
    days_per_week: form.days_per_week,
    supported_levels: form.supported_levels,
    fitness_goal: form.fitness_goal,
    focus_tags: form.focus_tags.filter(Boolean),
    intensity_methods: uniqueMethods(form.days),
    programming_rationale: form.programming_rationale,
    source_name: form.source_name,
    source_url: form.source_url,
    structure_id: form.structure_id,
    days: form.days.map((day) => ({
      title_en: day.title_en,
      title_fa: day.title_fa,
      structure_focus: day.structure_focus,
      direct_target_muscles: day.direct_target_muscles,
      slots: day.slots.map((slot) => ({
        exercise_id: slot.exercise_id ?? "",
        superset_exercise_id: slot.superset_exercise_id ?? null,
        display_name_en: slot.display_name_en?.trim() ? slot.display_name_en.trim() : null,
        display_name_fa: slot.display_name_fa?.trim() ? slot.display_name_fa.trim() : null,
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

function uniqueMethods(days: AdminTrainingTemplateDayForm[]): TrainingTemplateMethod[] {
  return Array.from(new Set(days.flatMap((day) => day.slots.map((slot) => slot.intensity_method))));
}

function updateReason(
  setForm: Dispatch<SetStateAction<AdminTrainingProgramTemplateForm>>,
  index: number,
  key: keyof AdminTrainingProgramTemplateForm["programming_rationale"][number],
  value: string,
) {
  setForm((current) => ({
    ...current,
    programming_rationale: current.programming_rationale.map((reason, reasonIndex) => (
      reasonIndex === index ? { ...reason, [key]: value } : reason
    )),
  }));
}
