import { useTranslation } from "react-i18next";

import {
  exerciseCautionTags,
  exerciseTypes,
  movementPatterns,
  type ExerciseCautionTag,
  type ExerciseType,
  type MovementPattern,
} from "../exercises/types";

export type ProgrammingMetadata = {
  movement_pattern: MovementPattern;
  exercise_type: ExerciseType;
  caution_tags: ExerciseCautionTag[];
  is_programmable: boolean;
};

type AdminExerciseFormProps = {
  value: ProgrammingMetadata;
  onChange: <K extends keyof ProgrammingMetadata>(
    key: K,
    value: ProgrammingMetadata[K],
  ) => void;
};

export function AdminExerciseForm({ value, onChange }: AdminExerciseFormProps) {
  const { t } = useTranslation();

  function toggleCautionTag(tag: ExerciseCautionTag) {
    const next = value.caution_tags.includes(tag)
      ? value.caution_tags.filter((current) => current !== tag)
      : [...value.caution_tags, tag];
    onChange("caution_tags", next);
  }

  return (
    <fieldset className="admin-form-section">
      <legend>{t("admin.sections.programming")}</legend>
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
      <label className="admin-active-toggle">
        <input
          type="checkbox"
          checked={value.is_programmable}
          onChange={(event) => onChange("is_programmable", event.target.checked)}
        />
        <span>{t("admin.fields.isProgrammable")}</span>
      </label>
    </fieldset>
  );
}
