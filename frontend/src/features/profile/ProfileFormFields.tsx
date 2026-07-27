import { useTranslation } from "react-i18next";

import type {
  ProfileValidationCode,
  ProfileValidationErrors,
} from "./profileValidation";
import {
  experienceLevels,
  fitnessGoals,
  sexes,
  type ProfileFormValues,
} from "./types";

type FieldGroupProps = {
  values: ProfileFormValues;
  errors: ProfileValidationErrors;
  disabled?: boolean;
  onChange: (field: keyof ProfileFormValues, value: string) => void;
};

function describedBy(
  field: keyof ProfileFormValues,
  error: ProfileValidationCode | undefined,
  hint = false,
) {
  return [hint ? `${field}-hint` : null, error ? `${field}-error` : null]
    .filter(Boolean)
    .join(" ") || undefined;
}

function FieldError({
  field,
  error,
}: {
  field: keyof ProfileFormValues;
  error: ProfileValidationCode | undefined;
}) {
  const { t } = useTranslation();
  if (error === undefined) {
    return null;
  }
  return (
    <p className="profile-field__error" id={`${field}-error`}>
      {t(`onboarding.validation.${error}`)}
    </p>
  );
}

export function PersonalFields({
  values,
  errors,
  disabled = false,
  onChange,
}: FieldGroupProps) {
  const { t } = useTranslation();
  return (
    <fieldset className="profile-fieldset" disabled={disabled}>
      <legend>{t("onboarding.steps.personal")}</legend>

      <div className="profile-field">
        <label htmlFor="profile-display-name">{t("onboarding.fields.displayName")}</label>
        <input
          id="profile-display-name"
          name="display_name"
          type="text"
          autoComplete="name"
          minLength={2}
          maxLength={80}
          required
          value={values.display_name}
          aria-invalid={errors.display_name !== undefined}
          aria-describedby={describedBy("display_name", errors.display_name)}
          onChange={(event) => onChange("display_name", event.target.value)}
        />
        <FieldError field="display_name" error={errors.display_name} />
      </div>

      <div className="profile-field">
        <label htmlFor="profile-birth-date">{t("onboarding.fields.birthDate")}</label>
        <input
          id="profile-birth-date"
          name="birth_date"
          type="date"
          autoComplete="bday"
          required
          value={values.birth_date}
          aria-invalid={errors.birth_date !== undefined}
          aria-describedby={describedBy("birth_date", errors.birth_date, true)}
          onChange={(event) => onChange("birth_date", event.target.value)}
        />
        <p className="profile-field__hint" id="birth_date-hint">
          {t("onboarding.hints.birthDate")}
        </p>
        <FieldError field="birth_date" error={errors.birth_date} />
      </div>

      <div className="profile-field">
        <label htmlFor="profile-sex">{t("onboarding.fields.sex")}</label>
        <select
          id="profile-sex"
          name="sex"
          autoComplete="sex"
          required
          value={values.sex}
          aria-invalid={errors.sex !== undefined}
          aria-describedby={describedBy("sex", errors.sex)}
          onChange={(event) => onChange("sex", event.target.value)}
        >
          <option value="" disabled>
            {t("onboarding.options.select")}
          </option>
          {sexes.map((sex) => (
            <option key={sex} value={sex}>
              {t(`onboarding.options.sex.${sex}`)}
            </option>
          ))}
        </select>
        <FieldError field="sex" error={errors.sex} />
      </div>
    </fieldset>
  );
}

export function BodyGoalFields({
  values,
  errors,
  disabled = false,
  onChange,
}: FieldGroupProps) {
  const { t } = useTranslation();
  return (
    <fieldset className="profile-fieldset" disabled={disabled}>
      <legend>{t("onboarding.steps.bodyGoal")}</legend>

      <div className="profile-field profile-field--paired">
        <div>
          <label htmlFor="profile-height">{t("onboarding.fields.height")}</label>
          <input
            id="profile-height"
            name="height_cm"
            type="number"
            inputMode="numeric"
            autoComplete="off"
            min={100}
            max={250}
            step={1}
            required
            value={values.height_cm}
            aria-invalid={errors.height_cm !== undefined}
            aria-describedby={describedBy("height_cm", errors.height_cm)}
            onChange={(event) => onChange("height_cm", event.target.value)}
          />
          <FieldError field="height_cm" error={errors.height_cm} />
        </div>
        <div>
          <label htmlFor="profile-current-weight">{t("onboarding.fields.weight")}</label>
          <input
            id="profile-current-weight"
            name="current_weight_kg"
            type="number"
            inputMode="decimal"
            autoComplete="off"
            min={20}
            max={500}
            step={0.01}
            required
            value={values.current_weight_kg}
            aria-invalid={errors.current_weight_kg !== undefined}
            aria-describedby={describedBy(
              "current_weight_kg",
              errors.current_weight_kg,
            )}
            onChange={(event) => onChange("current_weight_kg", event.target.value)}
          />
          <FieldError field="current_weight_kg" error={errors.current_weight_kg} />
        </div>
      </div>

      <div className="profile-field">
        <label htmlFor="profile-fitness-goal">{t("onboarding.fields.fitnessGoal")}</label>
        <select
          id="profile-fitness-goal"
          name="fitness_goal"
          autoComplete="off"
          required
          value={values.fitness_goal}
          aria-invalid={errors.fitness_goal !== undefined}
          aria-describedby={describedBy("fitness_goal", errors.fitness_goal)}
          onChange={(event) => onChange("fitness_goal", event.target.value)}
        >
          <option value="" disabled>
            {t("onboarding.options.select")}
          </option>
          {fitnessGoals.map((goal) => (
            <option key={goal} value={goal}>
              {t(`onboarding.options.fitnessGoal.${goal}`)}
            </option>
          ))}
        </select>
        <FieldError field="fitness_goal" error={errors.fitness_goal} />
      </div>
    </fieldset>
  );
}

export function ExperienceFields({
  values,
  errors,
  disabled = false,
  onChange,
}: FieldGroupProps) {
  const { t } = useTranslation();
  return (
    <fieldset className="profile-fieldset" disabled={disabled}>
      <legend>{t("onboarding.steps.experience")}</legend>

      <div className="profile-field">
        <label htmlFor="profile-experience">{t("onboarding.fields.experience")}</label>
        <select
          id="profile-experience"
          name="experience_level"
          autoComplete="off"
          required
          value={values.experience_level}
          aria-invalid={errors.experience_level !== undefined}
          aria-describedby={describedBy(
            "experience_level",
            errors.experience_level,
          )}
          onChange={(event) => onChange("experience_level", event.target.value)}
        >
          <option value="" disabled>
            {t("onboarding.options.select")}
          </option>
          {experienceLevels.map((level) => (
            <option key={level} value={level}>
              {t(`onboarding.options.experience.${level}`)}
            </option>
          ))}
        </select>
        <FieldError field="experience_level" error={errors.experience_level} />
      </div>

      <div className="profile-field">
        <label htmlFor="profile-training-days">{t("onboarding.fields.trainingDays")}</label>
        <input
          id="profile-training-days"
          name="training_days_per_week"
          type="number"
          inputMode="numeric"
          autoComplete="off"
          min={1}
          max={7}
          step={1}
          required
          value={values.training_days_per_week}
          aria-invalid={errors.training_days_per_week !== undefined}
          aria-describedby={describedBy(
            "training_days_per_week",
            errors.training_days_per_week,
          )}
          onChange={(event) => onChange("training_days_per_week", event.target.value)}
        />
        <FieldError
          field="training_days_per_week"
          error={errors.training_days_per_week}
        />
      </div>

      <div className="profile-field">
        <label htmlFor="profile-limitations">{t("onboarding.fields.limitations")}</label>
        <textarea
          id="profile-limitations"
          name="physical_limitations"
          autoComplete="off"
          maxLength={1000}
          rows={4}
          value={values.physical_limitations}
          aria-invalid={errors.physical_limitations !== undefined}
          aria-describedby={describedBy(
            "physical_limitations",
            errors.physical_limitations,
            true,
          )}
          onChange={(event) => onChange("physical_limitations", event.target.value)}
        />
        <p className="profile-field__hint" id="physical_limitations-hint">
          {t("onboarding.hints.limitations")}
        </p>
        <FieldError
          field="physical_limitations"
          error={errors.physical_limitations}
        />
      </div>
    </fieldset>
  );
}
