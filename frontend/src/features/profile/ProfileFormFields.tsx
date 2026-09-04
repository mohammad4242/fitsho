import { useTranslation } from "react-i18next";
import type { InputHTMLAttributes } from "react";

import { AppIcon, type IconName } from "../../shared/AppIcon";

import type {
  BodyAnalysisMeasurementErrors,
  ProfileValidationCode,
  ProfileValidationErrors,
} from "./profileValidation";
import {
  experienceLevels,
  fitnessGoals,
  planDurations,
  sessionDurations,
  sexes,
  trainingCautions,
  trainingIntensities,
  userSelectablePriorityMuscles,
  preferredWeekdays,
  availableEquipment,
  type TrainingCaution,
  type UserSelectablePriorityMuscle,
  type Equipment,
  type ProfileFormValue,
  type MeasurementField,
  type MeasurementFormValues,
  trainingLocations,
  type ProfileFormValues,
} from "./types";

type FieldGroupProps = {
  values: ProfileFormValues;
  errors: ProfileValidationErrors;
  disabled?: boolean;
  onChange: (
    field: keyof ProfileFormValues,
    value: ProfileFormValue,
  ) => void;
};

export function FieldLabel({
  htmlFor,
  icon,
  children,
}: {
  htmlFor?: string;
  icon?: IconName;
  children: React.ReactNode;
}) {
  return (
    <label htmlFor={htmlFor}>
      {icon && (
        <span className="profile-field__icon-badge" aria-hidden="true">
          <AppIcon name={icon} />
        </span>
      )}
      <span>{children}</span>
    </label>
  );
}

export function FieldLegend({
  icon,
  children,
}: {
  icon?: IconName;
  children: React.ReactNode;
}) {
  return (
    <legend>
      {icon && (
        <span className="profile-field__icon-badge" aria-hidden="true">
          <AppIcon name={icon} />
        </span>
      )}
      <span>{children}</span>
    </legend>
  );
}

function describedBy(
  field: string,
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
  field: string;
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
      <FieldLegend icon="profile">{t("onboarding.steps.personal")}</FieldLegend>

      <div className="profile-field">
        <FieldLabel htmlFor="profile-display-name" icon="profile">
          {t("onboarding.fields.displayName")}
        </FieldLabel>
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
        <FieldLabel htmlFor="profile-birth-date" icon="calendar">
          {t("onboarding.fields.birthDate")}
        </FieldLabel>
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
        <FieldLabel htmlFor="profile-sex" icon="gender">
          {t("onboarding.fields.sex")}
        </FieldLabel>
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
  showCircumferences = true,
}: FieldGroupProps & { showCircumferences?: boolean }) {
  const { t } = useTranslation();
  return (
    <fieldset className="profile-fieldset" disabled={disabled}>
      <FieldLegend icon="target">{t("onboarding.steps.bodyGoal")}</FieldLegend>

      <MeasurementFields
        values={values}
        errors={errors}
        disabled={disabled}
        onChange={(field, value) => onChange(field, value)}
        showCircumferences={showCircumferences}
      />

      <div className="profile-field">
        <FieldLabel htmlFor="profile-fitness-goal" icon="target">
          {t("onboarding.fields.fitnessGoal")}
        </FieldLabel>
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

type MeasurementFieldsProps = {
  values: MeasurementFormValues;
  errors: BodyAnalysisMeasurementErrors;
  disabled?: boolean;
  onChange: (field: MeasurementField, value: string) => void;
  showPrimaryMeasurements?: boolean;
  showCircumferences?: boolean;
  requiredCircumferences?: boolean;
  showUnits?: boolean;
  idPrefix?: string;
};

export function MeasurementFields({
  values,
  errors,
  disabled = false,
  onChange,
  showPrimaryMeasurements = true,
  showCircumferences = true,
  requiredCircumferences = false,
  showUnits = false,
  idPrefix = "profile",
}: MeasurementFieldsProps) {
  const { t } = useTranslation();
  return (
    <>
      {showPrimaryMeasurements && (
        <div className="profile-field profile-field--paired">
          <div>
            <FieldLabel htmlFor={`${idPrefix}-height`} icon="ruler">
              {t("onboarding.fields.height")}
            </FieldLabel>
            <MeasurementInput
              unit={showUnits ? "cm" : undefined}
              id={`${idPrefix}-height`}
              name="height_cm"
              type="number"
              inputMode="numeric"
              autoComplete="off"
              min={120}
              max={230}
              step={1}
              required
              value={values.height_cm}
              aria-invalid={errors.height_cm !== undefined}
              aria-describedby={describedBy("height_cm", errors.height_cm)}
              onChange={(event) => onChange("height_cm", event.target.value)}
              disabled={disabled}
            />
            <FieldError field="height_cm" error={errors.height_cm} />
          </div>
          <div>
            <FieldLabel htmlFor={`${idPrefix}-current-weight`} icon="scale">
              {t("onboarding.fields.weight")}
            </FieldLabel>
            <MeasurementInput
              unit={showUnits ? "kg" : undefined}
              id={`${idPrefix}-current-weight`}
              name="current_weight_kg"
              type="number"
              inputMode="decimal"
              autoComplete="off"
              min={35}
              max={300}
              step={0.01}
              required
              value={values.current_weight_kg}
              aria-invalid={errors.current_weight_kg !== undefined}
              aria-describedby={describedBy("current_weight_kg", errors.current_weight_kg)}
              onChange={(event) => onChange("current_weight_kg", event.target.value)}
              disabled={disabled}
            />
            <FieldError field="current_weight_kg" error={errors.current_weight_kg} />
          </div>
        </div>
      )}

      {showCircumferences && (
        <div className="profile-field profile-field--measurements">
          {([
            ["shoulder_circumference_cm", "shoulderCircumference"],
            ["waist_circumference_cm", "waistCircumference"],
            ["hip_circumference_cm", "hipCircumference"],
          ] as const).map(([field, label]) => (
            <div key={field}>
              <FieldLabel htmlFor={`${idPrefix}-${field}`} icon="body">
                {requiredCircumferences
                  ? t(`bodyPhotos.measurements.fields.${label}`)
                  : t(`onboarding.fields.${label}`)}
              </FieldLabel>
              <MeasurementInput
                unit={showUnits ? "cm" : undefined}
                id={`${idPrefix}-${field}`}
                name={field}
                type="number"
                inputMode="decimal"
                autoComplete="off"
                min={40}
                max={250}
                step={0.01}
                required={requiredCircumferences}
                value={values[field]}
                aria-invalid={errors[field] !== undefined}
                aria-describedby={describedBy(field, errors[field], true)}
                onChange={(event) => onChange(field, event.target.value)}
                disabled={disabled}
              />
              <p className="profile-field__hint" id={`${field}-hint`}>
                {t("onboarding.hints.circumference")}
              </p>
              <FieldError field={field} error={errors[field]} />
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function MeasurementInput({
  unit,
  ...inputProps
}: InputHTMLAttributes<HTMLInputElement> & { unit?: string }) {
  if (unit === undefined) {
    return <input {...inputProps} />;
  }
  return (
    <div className="measurement-input">
      <input {...inputProps} />
      <span aria-hidden="true">{unit}</span>
    </div>
  );
}

export function ExperienceFields({
  values,
  errors,
  disabled = false,
  onChange,
}: FieldGroupProps) {
  const { t } = useTranslation();

  function toggleTrainingCaution(caution: TrainingCaution) {
    const selected = values.training_cautions ?? [];
    onChange(
      "training_cautions",
      selected.includes(caution)
        ? selected.filter((item) => item !== caution)
        : [...selected, caution],
    );
  }

  function toggleWeekday(day: number) {
    const selected = values.preferred_weekdays;
    onChange(
      "preferred_weekdays",
      selected.includes(day)
        ? selected.filter((item) => item !== day)
        : [...selected, day].sort((a, b) => a - b),
    );
  }

  function selectPriorityMuscle(muscle: UserSelectablePriorityMuscle | "") {
    onChange("priority_muscle", muscle);
  }

  function toggleEquipment(equipment: Equipment) {
    const selected = new Set(values.available_equipment ?? []);
    if (equipment === "bodyweight") {
      if (selected.has(equipment)) {
        selected.delete("bodyweight");
        selected.delete("pull_up_bar");
      } else {
        selected.add("bodyweight");
        selected.add("pull_up_bar");
      }
    } else if (equipment === "pull_up_bar") {
      if (selected.has(equipment)) {
        selected.delete("pull_up_bar");
      } else {
        selected.add("bodyweight");
        selected.add("pull_up_bar");
      }
    } else if (selected.has(equipment)) {
      selected.delete(equipment);
    } else {
      selected.add(equipment);
    }
    onChange("available_equipment", availableEquipment.filter((item) => selected.has(item)));
  }

  return (
    <fieldset className="profile-fieldset" disabled={disabled}>
      <FieldLegend icon="dumbbell">{t("onboarding.steps.experience")}</FieldLegend>

      <div className="profile-field">
        <FieldLabel htmlFor="profile-experience" icon="award">
          {t("onboarding.fields.experience")}
        </FieldLabel>
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
        <FieldLabel htmlFor="profile-training-days" icon="flame">
          {t("onboarding.fields.trainingDays")}
        </FieldLabel>
        <input
          id="profile-training-days"
          name="training_days_per_week"
          type="number"
          inputMode="numeric"
          autoComplete="off"
          min={2}
          max={6}
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
        <FieldLabel htmlFor="profile-training-age" icon="clock">
          {t("onboarding.fields.trainingAge")}
        </FieldLabel>
        <input
          id="profile-training-age"
          name="training_age_months"
          type="number"
          inputMode="numeric"
          autoComplete="off"
          min={0}
          max={900}
          step={1}
          value={values.training_age_months}
          aria-invalid={errors.training_age_months !== undefined}
          aria-describedby={describedBy("training_age_months", errors.training_age_months, true)}
          onChange={(event) => onChange("training_age_months", event.target.value)}
        />
        <p className="profile-field__hint" id="training_age_months-hint">
          {t("onboarding.hints.trainingAge")}
        </p>
        <FieldError field="training_age_months" error={errors.training_age_months} />
      </div>

      <fieldset className="profile-field" aria-describedby={describedBy("preferred_weekdays", errors.preferred_weekdays)}>
        <FieldLegend icon="calendar">{t("onboarding.fields.preferredWeekdays")}</FieldLegend>
        <p className="profile-field__hint">{t("onboarding.hints.preferredWeekdays")}</p>
        <div className="profile-checkboxes">
          {preferredWeekdays.map((day) => (
            <label key={day}>
              <input
                type="checkbox"
                name="preferred_weekdays"
                checked={values.preferred_weekdays.includes(day)}
                disabled={!values.preferred_weekdays.includes(day) && values.preferred_weekdays.length >= Number(values.training_days_per_week)}
                onChange={() => toggleWeekday(day)}
              />
              {t(`onboarding.options.weekday.${day}`)}
            </label>
          ))}
        </div>
        <FieldError field="preferred_weekdays" error={errors.preferred_weekdays} />
      </fieldset>

      <fieldset className="profile-field">
        <FieldLegend icon="body">{t("onboarding.fields.priorityMuscles")}</FieldLegend>
        <p className="profile-field__hint">{t("onboarding.hints.priorityMuscles")}</p>
        <div className="profile-checkboxes">
          <label>
            <input
              type="radio"
              name="priority_muscle"
              value=""
              checked={values.priority_muscle === ""}
              onChange={() => selectPriorityMuscle("")}
            />
            {t("onboarding.options.muscle.none")}
          </label>
          {userSelectablePriorityMuscles.map((muscle) => (
            <label key={muscle}>
              <input
                type="radio"
                name="priority_muscle"
                value={muscle}
                checked={values.priority_muscle === muscle}
                onChange={() => selectPriorityMuscle(muscle)}
              />
              {t(`onboarding.options.muscle.${muscle}`)}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="profile-field">
        <FieldLabel htmlFor="profile-training-location" icon="home">
          {t("onboarding.fields.trainingLocation")}
        </FieldLabel>
        <select
          id="profile-training-location"
          name="training_location"
          autoComplete="off"
          required
          value={values.training_location}
          aria-invalid={errors.training_location !== undefined}
          aria-describedby={describedBy(
            "training_location",
            errors.training_location,
          )}
          onChange={(event) => onChange("training_location", event.target.value)}
        >
          <option value="" disabled>
            {t("onboarding.options.select")}
          </option>
          {trainingLocations.map((location) => (
            <option key={location} value={location}>
              {t(`onboarding.options.trainingLocation.${location}`)}
            </option>
          ))}
        </select>
        <FieldError field="training_location" error={errors.training_location} />
      </div>

      {values.training_location === "home" && (
        <fieldset
          className="profile-field"
          aria-describedby={describedBy("available_equipment", errors.available_equipment)}
        >
          <FieldLegend icon="dumbbell">
            {t("onboarding.fields.homeTrainingSetup")}
          </FieldLegend>
          <p className="profile-field__hint">{t("onboarding.hints.homeTrainingSetup")}</p>
          <div className="profile-checkboxes">
            {availableEquipment.map((equipment) => (
              <label key={equipment}>
                <input
                  type="checkbox"
                  name="available_equipment"
                  checked={values.available_equipment?.includes(equipment) ?? false}
                  onChange={() => toggleEquipment(equipment)}
                />
                {t(`onboarding.options.equipment.${equipment}`)}
              </label>
            ))}
          </div>
          <FieldError
            field="available_equipment"
            error={errors.available_equipment}
          />
        </fieldset>
      )}

      <div className="profile-field">
        <FieldLabel htmlFor="profile-session-duration" icon="clock">
          {t("onboarding.fields.sessionDuration")}
        </FieldLabel>
        <select
          id="profile-session-duration"
          name="session_duration_minutes"
          autoComplete="off"
          required
          value={values.session_duration_minutes}
          aria-invalid={errors.session_duration_minutes !== undefined}
          aria-describedby={describedBy(
            "session_duration_minutes",
            errors.session_duration_minutes,
          )}
          onChange={(event) =>
            onChange("session_duration_minutes", event.target.value)
          }
        >
          <option value="" disabled>
            {t("onboarding.options.select")}
          </option>
          {sessionDurations.map((duration) => (
            <option key={duration} value={duration}>
              {t(`onboarding.options.sessionDuration.${duration}`)}
            </option>
          ))}
        </select>
        <FieldError
          field="session_duration_minutes"
          error={errors.session_duration_minutes}
        />
      </div>

      <div className="profile-field">
        <FieldLabel htmlFor="profile-training-intensity" icon="zap">
          {t("onboarding.fields.trainingIntensity")}
        </FieldLabel>
        <select
          id="profile-training-intensity"
          name="training_intensity"
          required
          value={values.training_intensity}
          aria-invalid={errors.training_intensity !== undefined}
          aria-describedby={describedBy("training_intensity", errors.training_intensity)}
          onChange={(event) => onChange("training_intensity", event.target.value)}
        >
          <option value="" disabled>{t("onboarding.options.select")}</option>
          {trainingIntensities.map((intensity) => (
            <option key={intensity} value={intensity}>{t(`onboarding.options.trainingIntensity.${intensity}`)}</option>
          ))}
        </select>
        <FieldError field="training_intensity" error={errors.training_intensity} />
      </div>

      <fieldset
        className="profile-field"
        aria-describedby={describedBy("training_cautions", errors.training_cautions)}
      >
        <FieldLegend icon="shield">{t("onboarding.fields.trainingCautions")}</FieldLegend>
        <div className="profile-checkboxes">
          <label>
            <input
              type="checkbox"
              name="training_cautions"
              checked={values.training_cautions !== null && values.training_cautions.length === 0}
              onChange={() => onChange("training_cautions", [])}
            />
            {t("onboarding.options.trainingCaution.none")}
          </label>
          {trainingCautions.map((caution) => (
            <label key={caution}>
              <input
                type="checkbox"
                checked={values.training_cautions?.includes(caution) ?? false}
                onChange={() => toggleTrainingCaution(caution)}
              />
              {t(`onboarding.options.trainingCaution.${caution}`)}
            </label>
          ))}
        </div>
        <FieldError field="training_cautions" error={errors.training_cautions} />
      </fieldset>

      <div className="profile-field">
        <FieldLabel htmlFor="profile-plan-duration" icon="sparkles">
          {t("onboarding.fields.planDuration")}
        </FieldLabel>
        <select
          id="profile-plan-duration"
          name="plan_duration_weeks"
          required
          value={values.plan_duration_weeks}
          aria-invalid={errors.plan_duration_weeks !== undefined}
          aria-describedby={describedBy("plan_duration_weeks", errors.plan_duration_weeks)}
          onChange={(event) => onChange("plan_duration_weeks", event.target.value)}
        >
          {planDurations.map((duration) => (
            <option key={duration} value={duration}>
              {t(`onboarding.options.planDuration.${duration}`)}
            </option>
          ))}
        </select>
        <FieldError field="plan_duration_weeks" error={errors.plan_duration_weeks} />
      </div>

    </fieldset>
  );
}
