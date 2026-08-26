import { useState } from "react";
import { useTranslation } from "react-i18next";

import { muscleGroups, movementPatterns, type MuscleGroup } from "../exercises/types";
import { deleteAdminTrainingTemplateSlot, updateAdminTrainingTemplateSlot } from "./api";
import { ExerciseLibraryPickerModal } from "./ExerciseLibraryPickerModal";
import "./AdminTrainingTemplateSlotEditModal.css";
import type {
  AdminExercise,
  AdminTrainingProgramTemplate,
  AdminTrainingTemplateExercise,
  AdminTrainingTemplateSlot,
  AdminTrainingTemplateSlotWrite,
  TrainingTemplateMethod,
  TrainingTemplateSlotPriority,
} from "./types";

type PickerTarget = "primary" | "superset";

type SlotDraft = AdminTrainingTemplateSlotWrite & {
  exercise: AdminTrainingTemplateExercise | null;
  superset_exercise: AdminTrainingTemplateExercise | null;
};

export interface AdminTrainingTemplateSlotEditModalProps {
  templateId: string;
  dayId: string;
  slot: AdminTrainingTemplateSlot;
  onClose: () => void;
  onSaved: (template: AdminTrainingProgramTemplate) => void;
}

export function AdminTrainingTemplateSlotEditModal({
  templateId,
  dayId,
  slot,
  onClose,
  onSaved,
}: AdminTrainingTemplateSlotEditModalProps) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<SlotDraft>(() => slotToDraft(slot));
  const [pickerTarget, setPickerTarget] = useState<PickerTarget | null>(null);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const exercise = draft.exercise ?? slot.exercise;
  const exerciseName = draft.display_name_fa || draft.display_name_en || exercise?.name_fa || exercise?.name_en || slot.exercise_slug_hint;
  const supersetExercise = draft.superset_exercise ?? slot.superset_exercise;

  function patch(patchValue: Partial<SlotDraft>) {
    setDraft((current) => ({ ...current, ...patchValue }));
  }

  function selectExercise(selected: AdminExercise) {
    const selectedSummary = {
      id: selected.id,
      slug: selected.slug,
      name_en: selected.name_en,
      name_fa: selected.name_fa,
      needs_review: selected.needs_review,
    } satisfies AdminTrainingTemplateExercise;
    if (pickerTarget === "superset") {
      patch({ superset_exercise_id: selected.id, superset_exercise: selectedSummary });
    } else {
      patch({
        exercise_id: selected.id,
        exercise: selectedSummary,
        movement_pattern: selected.movement_pattern,
        target_muscles: exerciseTargetMuscles(selected, draft.target_muscles),
      });
    }
    setPickerTarget(null);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const saved = await updateAdminTrainingTemplateSlot(templateId, dayId, slot.id, toPayload(draft));
      onSaved(saved);
    } catch {
      setError(t("admin.templateEditor.slotSaveError"));
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!window.confirm(t("admin.templateEditor.slotDeleteConfirm", { name: exerciseName }))) return;
    setRemoving(true);
    setError(null);
    try {
      const saved = await deleteAdminTrainingTemplateSlot(templateId, dayId, slot.id);
      onSaved(saved);
    } catch {
      setError(t("admin.templateEditor.slotDeleteError"));
    } finally {
      setRemoving(false);
    }
  }

  return (
    <div
      className="admin-template-slot-modal-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        aria-label={t("admin.templateEditor.slotEditAria", { name: exerciseName })}
        aria-modal="true"
        className="admin-template-slot-modal"
        role="dialog"
      >
        <header className="admin-template-slot-modal__header">
          <div>
            <span className="eyebrow eyebrow--accent">{t("admin.templateEditor.slotEditEyebrow")}</span>
            <h2>{t("admin.templateEditor.slotEditTitle", { name: exerciseName })}</h2>
          </div>
          <button aria-label={t("admin.templateEditor.close")} className="admin-exercise-picker-close" onClick={onClose} type="button">✕</button>
        </header>

        <form className="admin-template-slot-modal__body" noValidate onSubmit={(event) => { event.preventDefault(); void save(); }}>
          {error !== null && <p className="admin-form-alert" role="alert">{error}</p>}
          <div className="admin-template-slot-modal__exercise">
            <div>
              <span className="admin-template-slot-modal__label">{t("admin.templateEditor.movement")}</span>
              <strong>{exercise?.name_fa || exercise?.name_en || slot.exercise_slug_hint}</strong>
              {exercise !== null && <small>{exercise.name_en} · {exercise.slug}</small>}
            </div>
            <button className="admin-slot-choose-btn" onClick={() => setPickerTarget("primary")} type="button">
              {t("admin.templateEditor.changeExerciseFromLibrary")}
            </button>
          </div>

          {draft.intensity_method === "superset" && (
            <div className="admin-template-slot-modal__exercise">
              <div>
                <span className="admin-template-slot-modal__label">{t("admin.templateEditor.movement2")}</span>
                <strong>{supersetExercise?.name_fa || supersetExercise?.name_en || t("admin.templateEditor.emptyMovement")}</strong>
                {supersetExercise !== null && <small>{supersetExercise.name_en} · {supersetExercise.slug}</small>}
              </div>
              <button className="admin-slot-choose-btn" onClick={() => setPickerTarget("superset")} type="button">
                {t("admin.templateEditor.chooseFromLibrary")}
              </button>
            </div>
          )}

          <div className="admin-template-editor-grid admin-template-editor-grid--slot">
            <TextInput dir="rtl" label={t("admin.templateEditor.displayNameFa")} value={draft.display_name_fa ?? ""} onChange={(value) => patch({ display_name_fa: value || null })} />
            <TextInput dir="ltr" label={t("admin.templateEditor.displayNameEn")} value={draft.display_name_en ?? ""} onChange={(value) => patch({ display_name_en: value || null })} />
            <NumberInput label={t("admin.templateEditor.sets")} value={draft.sets} onChange={(value) => patch({ sets: value })} />
            <NumberInput label={t("admin.templateEditor.repMin")} value={draft.rep_min} onChange={(value) => patch({ rep_min: value })} />
            <NumberInput label={t("admin.templateEditor.repMax")} value={draft.rep_max} onChange={(value) => patch({ rep_max: value })} />
            <NumberInput label={t("admin.templateEditor.rir")} value={draft.target_rir} onChange={(value) => patch({ target_rir: value })} />
            <NumberInput label={t("admin.templateEditor.rest")} value={draft.rest_seconds} onChange={(value) => patch({ rest_seconds: value })} />
            <SelectInput label={t("admin.templateEditor.priority")} value={draft.adaptation_priority} options={["core", "accessory", "optional"]} getLabel={(value) => t(`admin.templateEditor.priorities.${value}`)} onChange={(value) => patch({ adaptation_priority: value as TrainingTemplateSlotPriority })} />
            <SelectInput label={t("admin.templateEditor.movementPattern")} value={draft.movement_pattern} options={movementPatterns} getLabel={(value) => t(`admin.programming.movementPattern.${value}`, value)} onChange={(value) => patch({ movement_pattern: value as AdminTrainingTemplateSlotWrite["movement_pattern"] })} />
            <TextInput dir="ltr" label={t("admin.templateEditor.slotMuscles")} value={draft.target_muscles.join(", ")} onChange={(value) => patch({ target_muscles: parseMuscles(value) })} />
          </div>

          <label className="admin-field">
            <span>{t("admin.templateEditor.executionMethod")}</span>
            <select value={draft.intensity_method} onChange={(event) => {
              const method = event.target.value as TrainingTemplateMethod;
              patch({
                intensity_method: method,
                ...(method === "superset" ? {} : { superset_exercise_id: null, superset_exercise: null, superset_group: null }),
              });
            }}>
              <option value="standard">{t("admin.templates.methods.standard")}</option>
              <option value="superset">{t("admin.templates.methods.superset")}</option>
              <option value="drop_set">{t("admin.templates.methods.drop_set")}</option>
            </select>
          </label>

          {draft.intensity_method === "superset" && (
            <TextInput dir="ltr" label={t("admin.templateEditor.supersetGroup")} value={draft.superset_group ?? ""} onChange={(value) => patch({ superset_group: value || null })} />
          )}

          <footer className="admin-template-slot-modal__actions">
            <button className="admin-template-slot-modal__remove" disabled={saving || removing} onClick={() => { void remove(); }} type="button">
              {removing ? t("admin.templateEditor.slotDeleting") : t("admin.templateEditor.removeExercise")}
            </button>
            <div>
              <button className="admin-template-slot-modal__cancel" disabled={saving || removing} onClick={onClose} type="button">{t("admin.templateEditor.cancel")}</button>
              <button className="admin-primary-link" disabled={saving || removing} type="submit">{saving ? t("admin.templateEditor.slotSaving") : t("admin.templateEditor.slotSave")}</button>
            </div>
          </footer>
        </form>
      </section>

      <ExerciseLibraryPickerModal
        isOpen={pickerTarget !== null}
        onClose={() => setPickerTarget(null)}
        onSelect={selectExercise}
        title={t("admin.templateEditor.changeExerciseFromLibrary")}
      />
    </div>
  );
}

function slotToDraft(slot: AdminTrainingTemplateSlot): SlotDraft {
  return {
    exercise_id: slot.exercise?.id ?? "",
    display_name_en: slot.placeholder_name_en,
    display_name_fa: slot.placeholder_name_fa,
    target_muscles: slot.target_muscles,
    movement_pattern: slot.movement_pattern,
    intensity_method: slot.intensity_method,
    adaptation_priority: slot.adaptation_priority ?? "accessory",
    superset_group: slot.superset_group ?? null,
    superset_exercise_id: slot.superset_exercise_id ?? null,
    sets: slot.sets,
    rep_min: slot.rep_min,
    rep_max: slot.rep_max,
    target_rir: slot.target_rir,
    rest_seconds: slot.rest_seconds,
    exercise: slot.exercise,
    superset_exercise: slot.superset_exercise ?? null,
  };
}

function toPayload(draft: SlotDraft): AdminTrainingTemplateSlotWrite {
  return {
    exercise_id: draft.exercise_id,
    display_name_en: draft.display_name_en?.trim() || null,
    display_name_fa: draft.display_name_fa?.trim() || null,
    target_muscles: draft.target_muscles,
    movement_pattern: draft.movement_pattern,
    intensity_method: draft.intensity_method,
    adaptation_priority: draft.adaptation_priority,
    superset_group: draft.superset_group,
    superset_exercise_id: draft.superset_exercise_id,
    sets: draft.sets,
    rep_min: draft.rep_min,
    rep_max: draft.rep_max,
    target_rir: draft.target_rir,
    rest_seconds: draft.rest_seconds,
  };
}

function exerciseTargetMuscles(exercise: AdminExercise, fallback: MuscleGroup[]): MuscleGroup[] {
  const muscles = exercise.primary_muscle === null
    ? exercise.secondary_muscles.slice(0, 1)
    : [exercise.primary_muscle, ...exercise.secondary_muscles];
  return muscles.length > 0 ? muscles : fallback;
}

function parseMuscles(value: string): MuscleGroup[] {
  const parsed = value
    .split(",")
    .map((item) => item.trim())
    .filter((item): item is MuscleGroup => muscleGroups.includes(item as MuscleGroup));
  return parsed.length > 0 ? parsed : ["chest"];
}

function TextInput({ label, value, onChange, dir }: { label: string; value: string; onChange: (value: string) => void; dir?: "rtl" | "ltr" | "auto" }) {
  return (
    <label className="admin-field">
      <span>{label}</span>
      <input aria-label={label} dir={dir} onChange={(event) => onChange(event.target.value)} value={value} />
    </label>
  );
}

function NumberInput({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="admin-field">
      <span>{label}</span>
      <input aria-label={label} dir="ltr" min={0} onChange={(event) => onChange(Number(event.target.value))} type="number" value={value} />
    </label>
  );
}

function SelectInput({ label, value, options, getLabel, onChange }: { label: string; value: string; options: readonly string[]; getLabel: (value: string) => string; onChange: (value: string) => void }) {
  return (
    <label className="admin-field">
      <span>{label}</span>
      <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option} value={option}>{getLabel(option)}</option>)}
      </select>
    </label>
  );
}
