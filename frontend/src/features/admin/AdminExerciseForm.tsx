import { useTranslation } from "react-i18next";

import {
  exerciseCautionTags,
  exerciseLabels,
  exerciseTypes,
  movementPatterns,
  type ExerciseCautionTag,
  type ExerciseLabel,
  type ExerciseType,
  type MovementPattern,
} from "../exercises/types";
import {
  AdminAccordionSection,
  type AdminAccordionSectionControl,
} from "./AdminAccordionSection";

export type ProgrammingMetadata = {
  movement_pattern: MovementPattern;
  exercise_type: ExerciseType;
  caution_tags: ExerciseCautionTag[];
  labels: ExerciseLabel[];
  needs_review: boolean;
  is_programmable: boolean;
};

type AdminExerciseFormProps = {
  value: ProgrammingMetadata;
  accordion: AdminAccordionSectionControl;
  onChange: <K extends keyof ProgrammingMetadata>(
    key: K,
    value: ProgrammingMetadata[K],
  ) => void;
};

export function AdminExerciseForm({ value, accordion, onChange }: AdminExerciseFormProps) {
  const { t } = useTranslation();

  function toggleCautionTag(tag: ExerciseCautionTag) {
    const next = value.caution_tags.includes(tag)
      ? value.caution_tags.filter((current) => current !== tag)
      : [...value.caution_tags, tag];
    onChange("caution_tags", next);
  }

  function toggleLabel(label: ExerciseLabel) {
    const next = value.labels.includes(label)
      ? value.labels.filter((current) => current !== label)
      : [...value.labels, label];
    onChange("labels", next);
  }

  return (
    <AdminAccordionSection {...accordion}>
      <div className="admin-field-grid">
        <label className="admin-field">
          <span>{t("admin.fields.movementPattern")}</span>
          <select
            aria-label={t("admin.fields.movementPattern")}
            value={value.movement_pattern}
            onChange={(event) => onChange("movement_pattern", event.target.value as MovementPattern)}
          >
            {movementPatterns.map((pattern) => (
              <option key={pattern} value={pattern}>{t(`admin.programming.movementPattern.${pattern}`)}</option>
            ))}
          </select>
        </label>
        <label className="admin-field">
          <span>{t("admin.fields.exerciseType")}</span>
          <select
            aria-label={t("admin.fields.exerciseType")}
            value={value.exercise_type}
            onChange={(event) => onChange("exercise_type", event.target.value as ExerciseType)}
          >
            {exerciseTypes.map((type) => (
              <option key={type} value={type}>{t(`admin.programming.exerciseType.${type}`)}</option>
            ))}
          </select>
        </label>
      </div>
      <fieldset className="admin-choice-group">
        <legend>{t("admin.fields.cautionTags")}</legend>
        <div>
          {exerciseCautionTags.map((tag) => (
            <label key={tag}>
              <input
                type="checkbox"
                checked={value.caution_tags.includes(tag)}
                onChange={() => toggleCautionTag(tag)}
              />
              {t(`admin.programming.cautionTag.${tag}`)}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="admin-choice-group">
        <legend>{t("admin.fields.labels")}</legend>
        <div>
          {exerciseLabels.map((label) => (
            <label key={label}>
              <input
                type="checkbox"
                checked={value.labels.includes(label)}
                onChange={() => toggleLabel(label)}
              />
              {t(`catalog.label.${label}`)}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="admin-active-toggle">
        <input
          type="checkbox"
          checked={value.needs_review}
          onChange={(event) => onChange("needs_review", event.target.checked)}
        />
        <span>{t("admin.fields.needsReview")}</span>
      </label>
      <label className="admin-active-toggle">
        <input
          type="checkbox"
          checked={value.is_programmable}
          onChange={(event) => onChange("is_programmable", event.target.checked)}
        />
        <span>{t("admin.fields.isProgrammable")}</span>
      </label>
    </AdminAccordionSection>
  );
}
