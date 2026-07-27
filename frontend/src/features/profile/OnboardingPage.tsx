import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { AuthShell } from "../../shared/AuthShell";
import {
  BodyGoalFields,
  ExperienceFields,
  PersonalFields,
} from "./ProfileFormFields";
import { useProfile } from "./ProfileContext";
import {
  toProfileInput,
  validateAll,
  validateStep,
  type ProfileValidationErrors,
} from "./profileValidation";
import type { ProfileFormValues } from "./types";
import "./profile.css";

type Step = 1 | 2 | 3;

const emptyValues: ProfileFormValues = {
  display_name: "",
  birth_date: "",
  sex: "",
  height_cm: "",
  current_weight_kg: "",
  fitness_goal: "",
  experience_level: "",
  training_days_per_week: "",
  physical_limitations: "",
};

const stepKeys = ["personal", "bodyGoal", "experience"] as const;

export function OnboardingPage() {
  const { i18n, t } = useTranslation();
  const navigate = useNavigate();
  const { createProfile } = useProfile();
  const [step, setStep] = useState<Step>(1);
  const [values, setValues] = useState<ProfileFormValues>(emptyValues);
  const [errors, setErrors] = useState<ProfileValidationErrors>({});
  const [submitError, setSubmitError] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const firstInvalidField = Object.keys(errors)[0];
    if (firstInvalidField !== undefined) {
      document
        .querySelector<HTMLElement>(`[name="${firstInvalidField}"]`)
        ?.focus();
    }
  }, [errors]);

  function updateValue(field: keyof ProfileFormValues, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => {
      if (current[field] === undefined) {
        return current;
      }
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  function handleBack() {
    if (step === 1 || busy) {
      return;
    }
    setErrors({});
    setSubmitError(false);
    setStep((step - 1) as Step);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) {
      return;
    }

    if (step < 3) {
      const stepErrors = validateStep(values, step, new Date());
      setErrors(stepErrors);
      if (Object.keys(stepErrors).length === 0) {
        setStep((step + 1) as Step);
      }
      return;
    }

    const allErrors = validateAll(values, new Date());
    setErrors(allErrors);
    if (Object.keys(allErrors).length > 0) {
      return;
    }

    setBusy(true);
    setSubmitError(false);
    void createProfile(toProfileInput(values))
      .then(() => navigate("/dashboard", { replace: true }))
      .catch(() => setSubmitError(true))
      .finally(() => setBusy(false));
  }

  const locale = i18n.resolvedLanguage === "en" ? "en" : "fa-IR";
  const numberFormat = new Intl.NumberFormat(locale);

  return (
    <AuthShell>
      <div className="onboarding-flow">
        <div className="form-heading">
          <p className="eyebrow eyebrow--accent">{t("onboarding.eyebrow")}</p>
          <h2>{t("onboarding.title")}</h2>
          <p>{t("onboarding.intro")}</p>
        </div>

        <nav className="profile-progress" aria-label={t("onboarding.progressLabel")}>
          <p className="profile-progress__count" aria-live="polite">
            {t("onboarding.stepCount", {
              current: numberFormat.format(step),
              total: numberFormat.format(3),
            })}
          </p>
          <ol aria-label={t("onboarding.progressLabel")}>
            {stepKeys.map((key, index) => {
              const stepNumber = (index + 1) as Step;
              return (
                <li
                  key={key}
                  className={stepNumber <= step ? "is-active" : undefined}
                  aria-current={stepNumber === step ? "step" : undefined}
                >
                  <span aria-hidden="true">{numberFormat.format(stepNumber)}</span>
                  <strong>{t(`onboarding.steps.${key}`)}</strong>
                </li>
              );
            })}
          </ol>
        </nav>

        <form className="profile-form" noValidate onSubmit={handleSubmit}>
          {step === 1 && (
            <PersonalFields
              values={values}
              errors={errors}
              disabled={busy}
              onChange={updateValue}
            />
          )}
          {step === 2 && (
            <BodyGoalFields
              values={values}
              errors={errors}
              disabled={busy}
              onChange={updateValue}
            />
          )}
          {step === 3 && (
            <ExperienceFields
              values={values}
              errors={errors}
              disabled={busy}
              onChange={updateValue}
            />
          )}

          {submitError && (
            <p className="form-error" role="alert" aria-live="polite">
              {t("errors.generic")}
            </p>
          )}

          <div className="profile-actions">
            {step > 1 && (
              <button
                className="secondary-button"
                type="button"
                disabled={busy}
                onClick={handleBack}
              >
                {t("onboarding.actions.back")}
              </button>
            )}
            <button className="primary-button" type="submit" disabled={busy}>
              <span>
                {step < 3
                  ? t("onboarding.actions.next")
                  : busy
                    ? t("onboarding.actions.saving")
                    : t("onboarding.actions.submit")}
              </span>
              <span aria-hidden="true">←</span>
            </button>
          </div>
        </form>
      </div>
    </AuthShell>
  );
}
