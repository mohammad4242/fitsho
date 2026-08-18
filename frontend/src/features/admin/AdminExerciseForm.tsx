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
  axialLoadingLevels,
  bodyPositions,
  impactLevels,
  lateralities,
  skillDemands,
  stabilityDemands,
  type AxialLoadingLevel,
  type BodyPosition,
  type ImpactLevel,
  type Laterality,
  type SkillDemand,
  type StabilityDemand,
} from "./types";
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
  body_position: BodyPosition | "";
  stability_demand: StabilityDemand | "";
  skill_demand: SkillDemand | "";
  impact_level: ImpactLevel | "";
  axial_loading_level: AxialLoadingLevel | "";
  fatigue_cost: number | null;
  setup_cost: number | null;
  laterality: Laterality | "";
  substitution_group: string;
  range_of_motion_profile: string;
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
      <div className="admin-field-grid">
        <OptionalSelect
          label={t("admin.fields.bodyPosition")}
          value={value.body_position}
          options={bodyPositions}
          labelKey="bodyPositionOption"
          onChange={(next) => onChange("body_position", next as BodyPosition | "")}
          t={t}
        />
        <OptionalSelect
          label={t("admin.fields.stabilityDemand")}
          value={value.stability_demand}
          options={stabilityDemands}
          labelKey="stabilityDemandOption"
          onChange={(next) => onChange("stability_demand", next as StabilityDemand | "")}
          t={t}
        />
        <OptionalSelect
          label={t("admin.fields.skillDemand")}
          value={value.skill_demand}
          options={skillDemands}
          labelKey="skillDemandOption"
          onChange={(next) => onChange("skill_demand", next as SkillDemand | "")}
          t={t}
        />
        <OptionalSelect
          label={t("admin.fields.impactLevel")}
          value={value.impact_level}
          options={impactLevels}
          labelKey="impactLevelOption"
          onChange={(next) => onChange("impact_level", next as ImpactLevel | "")}
          t={t}
        />
        <OptionalSelect
          label={t("admin.fields.axialLoadingLevel")}
          value={value.axial_loading_level}
          options={axialLoadingLevels}
          labelKey="axialLoadingLevelOption"
          onChange={(next) => onChange("axial_loading_level", next as AxialLoadingLevel | "")}
          t={t}
        />
        <OptionalSelect
          label={t("admin.fields.laterality")}
          value={value.laterality}
          options={lateralities}
          labelKey="lateralityOption"
          onChange={(next) => onChange("laterality", next as Laterality | "")}
          t={t}
        />
        <label className="admin-field">
          <span>{t("admin.fields.fatigueCost")}</span>
          <input
            aria-label={t("admin.fields.fatigueCost")}
            type="number"
            min={1}
            max={5}
            value={value.fatigue_cost ?? ""}
            onChange={(event) => onChange("fatigue_cost", event.target.value ? Number(event.target.value) : null)}
          />
        </label>
        <label className="admin-field">
          <span>{t("admin.fields.setupCost")}</span>
          <input
            aria-label={t("admin.fields.setupCost")}
            type="number"
            min={1}
            max={5}
            value={value.setup_cost ?? ""}
            onChange={(event) => onChange("setup_cost", event.target.value ? Number(event.target.value) : null)}
          />
        </label>
        <label className="admin-field">
          <span>{t("admin.fields.substitutionGroup")}</span>
          <input
            dir="ltr"
            aria-label={t("admin.fields.substitutionGroup")}
            value={value.substitution_group}
            onChange={(event) => onChange("substitution_group", event.target.value)}
          />
        </label>
        <label className="admin-field">
          <span>{t("admin.fields.rangeOfMotionProfile")}</span>
          <input
            dir="ltr"
            aria-label={t("admin.fields.rangeOfMotionProfile")}
            placeholder="deep_knee_flexion, supported"
            value={value.range_of_motion_profile}
            onChange={(event) => onChange("range_of_motion_profile", event.target.value)}
          />
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

type OptionalSelectProps = {
  label: string;
  value: string;
  options: readonly string[];
  labelKey: string;
  onChange: (value: string) => void;
  t: (key: string) => string;
};

function OptionalSelect({ label, value, options, labelKey, onChange, t }: OptionalSelectProps) {
  return (
    <label className="admin-field">
      <span>{label}</span>
      <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{t("admin.fields.notSet")}</option>
        {options.map((option) => (
          <option key={option} value={option}>{t(`admin.programming.${labelKey}.${option}`)}</option>
        ))}
      </select>
    </label>
  );
}
