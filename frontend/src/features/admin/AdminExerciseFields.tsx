import { cloneElement, type ReactElement, useState } from "react";
import { useTranslation } from "react-i18next";

import { ExerciseMedia } from "../exercises/ExerciseMedia";
import {
  bodyRegions,
  difficulties,
  equipment,
  muscleFocusesByMuscle,
  type MuscleFocus,
  type MuscleGroup,
} from "../exercises/types";
import { AdminExerciseForm as ProgrammingMetadataForm, type ProgrammingMetadata } from "./AdminExerciseForm";
import { ExerciseMediaAssetsFields } from "./ExerciseMediaAssetsFields";
import type { AdminExerciseForm, AdminExerciseMediaFiles } from "./types";
import {
  musclesByRegion,
  slugifyExerciseName,
  type AdminValidationErrors,
} from "./validation";

type MediaType = "image" | "animated_webp" | "gif" | "video" | "placeholder";

type AdminExerciseFieldsProps = {
  value: AdminExerciseForm;
  errors: AdminValidationErrors;
  duplicateSlug?: boolean;
  suggestSlugFromName?: boolean;
  primaryMediaPath: string;
  primaryMediaType: MediaType;
  mediaFiles: AdminExerciseMediaFiles;
  onChange: <K extends keyof AdminExerciseForm>(key: K, value: AdminExerciseForm[K]) => void;
  onPrimaryMediaChange: (file: File | null) => void;
  onMediaFilesChange: (files: AdminExerciseMediaFiles) => void;
};

export function AdminExerciseFields({
  value,
  errors,
  duplicateSlug = false,
  suggestSlugFromName = false,
  primaryMediaPath,
  primaryMediaType,
  mediaFiles,
  onChange,
  onPrimaryMediaChange,
  onMediaFilesChange,
}: AdminExerciseFieldsProps) {
  const { t } = useTranslation();
  const [slugEdited, setSlugEdited] = useState(false);
  const availableMuscles = value.body_region ? musclesByRegion[value.body_region] : [];
  const availableFocuses = value.primary_muscle
    ? muscleFocusesByMuscle[value.primary_muscle]
    : [];
  const errorText = (key: keyof AdminExerciseForm) =>
    errors[key] ? t(`admin.validation.${errors[key]}`) : null;

  function toggleChoice<K extends "secondary_muscles" | "equipment">(
    key: K,
    choice: AdminExerciseForm[K][number],
  ) {
    const values = value[key] as Array<typeof choice>;
    onChange(
      key,
      (values.includes(choice)
        ? values.filter((item) => item !== choice)
        : [...values, choice]) as AdminExerciseForm[K],
    );
  }

  function changeList(
    key: "instructions_en" | "instructions_fa" | "safety_notes_en" | "safety_notes_fa",
    index: number,
    nextValue: string,
  ) {
    const next = [...value[key]];
    next[index] = nextValue;
    onChange(key, next);
  }

  function setProgrammingField<K extends keyof ProgrammingMetadata>(
    key: K,
    nextValue: ProgrammingMetadata[K],
  ) {
    onChange(key, nextValue as AdminExerciseForm[K]);
  }

  return (
    <>
      <fieldset className="admin-form-section">
        <legend>{t("admin.sections.identity")}</legend>
        <div className="admin-field-grid">
          <Field label={t("admin.fields.nameEn")} error={errorText("name_en")}>
            <input
              dir="ltr"
              value={value.name_en}
              onChange={(event) => {
                const name = event.target.value;
                onChange("name_en", name);
                if (suggestSlugFromName && !slugEdited) {
                  onChange("slug", slugifyExerciseName(name));
                }
              }}
            />
          </Field>
          <Field label={t("admin.fields.nameFa")} error={errorText("name_fa")}>
            <input
              dir="rtl"
              value={value.name_fa}
              onChange={(event) => onChange("name_fa", event.target.value)}
            />
          </Field>
          <Field
            label={t("admin.fields.slug")}
            error={duplicateSlug ? t("admin.errors.duplicate") : errorText("slug")}
          >
            <input
              dir="ltr"
              value={value.slug}
              onChange={(event) => {
                setSlugEdited(true);
                onChange("slug", event.target.value);
              }}
            />
          </Field>
          <Field label={t("admin.fields.difficulty")}>
            <select
              value={value.difficulty}
              onChange={(event) =>
                onChange("difficulty", event.target.value as AdminExerciseForm["difficulty"])
              }
            >
              {difficulties.map((difficulty) => (
                <option key={difficulty} value={difficulty}>
                  {t(`catalog.difficulty.${difficulty}`)}
                </option>
              ))}
            </select>
          </Field>
        </div>
      </fieldset>

      <fieldset className="admin-form-section">
        <legend>{t("admin.sections.target")}</legend>
        <div className="admin-field-grid">
          <Field label={t("admin.fields.bodyRegion")} error={errorText("body_region")}>
            <select
              value={value.body_region}
              disabled={value.needs_review}
              onChange={(event) => {
                onChange("body_region", event.target.value as AdminExerciseForm["body_region"]);
                onChange("primary_muscle", "");
                onChange("muscle_focus", "");
                onChange("secondary_muscles", []);
              }}
            >
              <option value="">{t("admin.fields.select")}</option>
              {bodyRegions.map((region) => (
                <option key={region} value={region}>{t(`catalog.bodyRegion.${region}`)}</option>
              ))}
            </select>
          </Field>
          <Field label={t("admin.fields.primaryMuscle")} error={errorText("primary_muscle")}>
            <select
              value={value.primary_muscle}
              disabled={!value.body_region || value.needs_review}
              onChange={(event) => {
                onChange("primary_muscle", event.target.value as MuscleGroup);
                onChange("muscle_focus", "");
              }}
            >
              <option value="">{t("admin.fields.select")}</option>
              {availableMuscles.map((muscle) => (
                <option key={muscle} value={muscle}>{t(`catalog.muscle.${muscle}`)}</option>
              ))}
            </select>
          </Field>
          <Field label={t("admin.fields.muscleFocus")} error={errorText("muscle_focus")}>
            <select
              value={value.muscle_focus}
              disabled={!value.primary_muscle || value.needs_review}
              onChange={(event) => onChange("muscle_focus", event.target.value as MuscleFocus)}
            >
              <option value="">{t("admin.fields.select")}</option>
              {availableFocuses.map((focus) => (
                <option key={focus} value={focus}>{t(`catalog.muscleFocus.${focus}`)}</option>
              ))}
            </select>
          </Field>
        </div>
        <ChoiceGroup
          legend={t("admin.fields.secondaryMuscles")}
          error={errorText("secondary_muscles")}
          values={availableMuscles}
          selected={value.secondary_muscles}
          label={(muscle) => `${t("admin.fields.secondaryPrefix")}: ${t(`catalog.muscle.${muscle}`)}`}
          onToggle={(muscle) => toggleChoice("secondary_muscles", muscle)}
        />
        <ChoiceGroup
          legend={t("admin.fields.equipment")}
          error={errorText("equipment")}
          values={equipment}
          selected={value.equipment}
          label={(item) => t(`catalog.equipment.${item}`)}
          onToggle={(item) => toggleChoice("equipment", item)}
        />
      </fieldset>

      <ProgrammingMetadataForm value={value} onChange={setProgrammingField} />

      <fieldset className="admin-form-section">
        <legend>{t("admin.sections.guidance")}</legend>
        <Repeater
          title={t("admin.fields.instructionsEn")}
          itemLabel={t("admin.fields.instructionEn")}
          addLabel={t("admin.actions.addInstructionEn")}
          values={value.instructions_en}
          error={errorText("instructions_en")}
          max={6}
          min={3}
          dir="ltr"
          onChange={(index, text) => changeList("instructions_en", index, text)}
          onAdd={() => onChange("instructions_en", [...value.instructions_en, ""])}
          onRemove={(index) =>
            onChange("instructions_en", value.instructions_en.filter((_, item) => item !== index))
          }
        />
        <Repeater
          title={t("admin.fields.instructionsFa")}
          itemLabel={t("admin.fields.instructionFa")}
          addLabel={t("admin.actions.addInstructionFa")}
          values={value.instructions_fa}
          error={errorText("instructions_fa")}
          max={6}
          min={3}
          dir="rtl"
          onChange={(index, text) => changeList("instructions_fa", index, text)}
          onAdd={() => onChange("instructions_fa", [...value.instructions_fa, ""])}
          onRemove={(index) =>
            onChange("instructions_fa", value.instructions_fa.filter((_, item) => item !== index))
          }
        />
        <Repeater
          title={t("admin.fields.safetyEn")}
          itemLabel={t("admin.fields.noteEn")}
          addLabel={t("admin.actions.addSafetyEn")}
          values={value.safety_notes_en}
          error={errorText("safety_notes_en")}
          max={8}
          min={1}
          dir="ltr"
          onChange={(index, text) => changeList("safety_notes_en", index, text)}
          onAdd={() => onChange("safety_notes_en", [...value.safety_notes_en, ""])}
          onRemove={(index) =>
            onChange("safety_notes_en", value.safety_notes_en.filter((_, item) => item !== index))
          }
        />
        <Repeater
          title={t("admin.fields.safetyFa")}
          itemLabel={t("admin.fields.noteFa")}
          addLabel={t("admin.actions.addSafetyFa")}
          values={value.safety_notes_fa}
          error={errorText("safety_notes_fa")}
          max={8}
          min={1}
          dir="rtl"
          onChange={(index, text) => changeList("safety_notes_fa", index, text)}
          onAdd={() => onChange("safety_notes_fa", [...value.safety_notes_fa, ""])}
          onRemove={(index) =>
            onChange("safety_notes_fa", value.safety_notes_fa.filter((_, item) => item !== index))
          }
        />
      </fieldset>

      <fieldset className="admin-form-section admin-media-section">
        <legend>{t("admin.sections.media")}</legend>
        <div className="admin-media-preview">
          <ExerciseMedia
            path={primaryMediaPath}
            mediaType={primaryMediaType}
            name={value.name_fa || value.name_en || t("admin.fields.previewName")}
          />
        </div>
        <div className="admin-field-grid">
          <Field label={t("admin.fields.mediaFile")}>
            <input
              type="file"
              accept="image/gif,video/mp4,video/webm"
              onChange={(event) => onPrimaryMediaChange(event.target.files?.[0] ?? null)}
            />
          </Field>
          <Field label={t("admin.fields.sourceUrl")} error={errorText("media_source_url")}>
            <input
              dir="ltr"
              type="url"
              value={value.media_source_url ?? ""}
              onChange={(event) => onChange("media_source_url", event.target.value)}
            />
          </Field>
          <Field label={t("admin.fields.license")}>
            <input
              value={value.media_license ?? ""}
              onChange={(event) => onChange("media_license", event.target.value)}
            />
          </Field>
          <Field label={t("admin.fields.attribution")}>
            <input
              value={value.media_attribution ?? ""}
              onChange={(event) => onChange("media_attribution", event.target.value)}
            />
          </Field>
        </div>
      </fieldset>

      <ExerciseMediaAssetsFields
        assets={value.media_assets}
        files={mediaFiles}
        onAssetsChange={(assets) => onChange("media_assets", assets)}
        onFilesChange={onMediaFilesChange}
      />

      <label className="admin-active-toggle">
        <input
          type="checkbox"
          checked={value.is_active}
          onChange={(event) => onChange("is_active", event.target.checked)}
        />
        <span>{t("admin.fields.active")}</span>
      </label>
    </>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string | null;
  children: ReactElement<{
    id?: string;
    "aria-invalid"?: boolean;
    "aria-describedby"?: string;
  }>;
}) {
  const id = `admin-${label.replace(/\s+/g, "-")}`;
  return (
    <div className="admin-field">
      <label htmlFor={id}>{label}</label>
      {cloneElement(children, {
        id,
        "aria-invalid": Boolean(error),
        "aria-describedby": error ? `${id}-error` : undefined,
      })}
      {error && <small id={`${id}-error`} role="status">{error}</small>}
    </div>
  );
}

function ChoiceGroup<T extends string>({
  legend,
  error,
  values,
  selected,
  label,
  onToggle,
}: {
  legend: string;
  error?: string | null;
  values: readonly T[];
  selected: readonly T[];
  label: (value: T) => string;
  onToggle: (value: T) => void;
}) {
  return (
    <fieldset className="admin-choice-group">
      <legend>{legend}</legend>
      <div>
        {values.map((choice) => (
          <label key={choice}>
            <input
              type="checkbox"
              checked={selected.includes(choice)}
              onChange={() => onToggle(choice)}
            />
            {label(choice)}
          </label>
        ))}
      </div>
      {error && <small role="status">{error}</small>}
    </fieldset>
  );
}

function Repeater({
  title,
  itemLabel,
  addLabel,
  values,
  error,
  max,
  min,
  dir,
  onChange,
  onAdd,
  onRemove,
}: {
  title: string;
  itemLabel: string;
  addLabel: string;
  values: string[];
  error?: string | null;
  max: number;
  min: number;
  dir: "ltr" | "rtl";
  onChange: (index: number, value: string) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}) {
  return (
    <section className="admin-repeater">
      <h2>{title}</h2>
      {values.map((text, index) => {
        const number = localizedNumber(index + 1);
        return (
          <div key={index}>
            <label>
              <span>{itemLabel} {number}</span>
              <textarea
                dir={dir}
                value={text}
                onChange={(event) => onChange(index, event.target.value)}
              />
            </label>
            {values.length > min && (
              <button
                type="button"
                aria-label={`${removeLabel()} ${itemLabel} ${number}`}
                onClick={() => onRemove(index)}
              >
                ×
              </button>
            )}
          </div>
        );
      })}
      {error && <small role="status">{error}</small>}
      {values.length < max && <button type="button" onClick={onAdd}>{addLabel}</button>}
    </section>
  );
}

function removeLabel() {
  return document.documentElement.lang === "en" ? "Remove" : "حذف";
}

function localizedNumber(value: number) {
  return document.documentElement.lang === "en"
    ? String(value)
    : new Intl.NumberFormat("fa-IR", { useGrouping: false }).format(value);
}
