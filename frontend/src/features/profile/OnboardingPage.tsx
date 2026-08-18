import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { AuthShell } from "../../shared/AuthShell";
import { useAuth } from "../auth/AuthContext";
import { NutritionOnboardingFlow } from "../nutrition/NutritionOnboardingFlow";
import {
  clearPendingNutritionBasics,
  loadPendingNutritionSetup,
} from "../publicOnboarding/onboardingDraft";
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
import type { ProductMode, ProfileFormValue, ProfileFormValues } from "./types";
import "./profile.css";

type Step = 1 | 2 | 3;

const emptyValues: ProfileFormValues = {
  display_name: "",
  birth_date: "",
  sex: "",
  height_cm: "",
  current_weight_kg: "",
  shoulder_circumference_cm: "",
  waist_circumference_cm: "",
  hip_circumference_cm: "",
  fitness_goal: "",
  experience_level: "",
  training_age_months: "",
  training_days_per_week: "",
  preferred_weekdays: [],
  priority_muscles: [],
  training_location: "",
  home_training_setup: "",
  session_duration_minutes: "",
  training_intensity: "",
  physical_limitations: "",
  training_cautions: null,
  plan_duration_weeks: "4",
};

const stepKeys = ["personal", "bodyGoal", "experience"] as const;

export function OnboardingPage() {
  const { i18n, t } = useTranslation();
  const navigate = useNavigate();
  const { createProfile, profile, productMode, retryProfile, selectProductMode, status } = useProfile();
  const [step, setStep] = useState<Step>(1);
  const [values, setValues] = useState<ProfileFormValues>(emptyValues);
  const [errors, setErrors] = useState<ProfileValidationErrors>({});
  const [submitError, setSubmitError] = useState(false);
  const [busy, setBusy] = useState(false);

  function chooseMode(mode: ProductMode) {
    if (busy) return;
    setBusy(true);
    void selectProductMode(mode).catch(() => setSubmitError(true)).finally(() => setBusy(false));
  }

  useEffect(() => {
    const firstInvalidField = Object.keys(errors)[0];
    if (firstInvalidField !== undefined) {
      document
        .querySelector<HTMLElement>(`[name="${firstInvalidField}"]`)
        ?.focus();
    }
  }, [errors]);

  function updateValue(
    field: keyof ProfileFormValues,
    value: ProfileFormValue,
  ) {
    const clearsHomeSetup = field === "training_location" && value === "gym";
    setValues((current) => ({
      ...current,
      [field]: value,
      ...(clearsHomeSetup ? { home_training_setup: "" } : {}),
    }));
    setErrors((current) => {
      if (
        current[field] === undefined &&
        (!clearsHomeSetup || current.home_training_setup === undefined)
      ) {
        return current;
      }
      const next = { ...current };
      delete next[field];
      if (clearsHomeSetup) {
        delete next.home_training_setup;
      }
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
      .then(() => navigate("/body-progress/new", { replace: true }))
      .catch(() => setSubmitError(true))
      .finally(() => setBusy(false));
  }

  const locale = i18n.resolvedLanguage === "en" ? "en" : "fa-IR";
  const numberFormat = new Intl.NumberFormat(locale);
  const pendingNutritionSetup = loadPendingNutritionSetup();

  if (status === "missing") {
    return (
      <OnboardingShell>
        <main className="onboarding-flow product-mode-flow">
          <p className="eyebrow eyebrow--accent">شروع با مربی فیتشو</p>
          <h2 className="fitsho-display">بیشتر در چه زمینه‌ای به کمک نیاز داری؟</h2>
          <p>مسیرت را انتخاب کن؛ فقط همان سؤال‌هایی را می‌پرسیم که برای برنامه‌ات لازم است.</p>
          <div className="product-mode-cards" role="list">
            {([
              ["training", "تمرین", "برنامه شخصی براساس بدن، هدف، سطح، زمان و تجهیزات"],
              ["nutrition", "تغذیه", "برنامه غذایی متناسب با هدف، نیاز بدن، مواد در دسترس و بودجه"],
              ["both", "تمرین و تغذیه", "یک برنامه هماهنگ برای نتیجه بهتر"],
            ] as const).map(([mode, title, description]) => (
              <button key={mode} className={`product-mode-card ${mode === "both" ? "is-recommended" : ""}`}
                type="button" disabled={busy} onClick={() => chooseMode(mode)} role="listitem">
                {mode === "both" && <span>پیشنهاد فیتشو</span>}
                <strong>{title}</strong><small>{description}</small>
              </button>
            ))}
          </div>
          {submitError && <p className="form-error" role="alert">ارتباط با سرور برقرار نشد. دوباره تلاش کن.</p>}
        </main>
      </OnboardingShell>
    );
  }

  if (productMode === "nutrition" || productMode === "both") {
    return (
      <OnboardingShell>
        <main className="onboarding-flow">
          <NutritionOnboardingFlow
            productMode={productMode}
            trainingProfileExists={profile !== null}
            initialDraft={pendingNutritionSetup === null ? undefined : {
              mode: productMode,
              safety: pendingNutritionSetup.safety,
              structuredExercise: pendingNutritionSetup.structuredExercise,
            }}
            initialNutritionBasics={pendingNutritionSetup?.nutritionBasics}
            onCreateTrainingProfile={createProfile}
            onComplete={retryProfile}
            onNutritionComplete={clearPendingNutritionBasics}
            editExisting
          />
        </main>
      </OnboardingShell>
    );
  }

  return (
    <OnboardingShell>
      <div className="onboarding-flow">
        <div className="form-heading">
          <p className="eyebrow eyebrow--accent">{t("onboarding.eyebrow")}</p>
          <h2 className="fitsho-display">{t("onboarding.title")}</h2>
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
            <>
              <BodyGoalFields
                values={values}
                errors={errors}
                disabled={busy}
                onChange={updateValue}
              />
              <button className="text-button" type="button" onClick={() => {
                updateValue("shoulder_circumference_cm", "");
                updateValue("waist_circumference_cm", "");
                updateValue("hip_circumference_cm", "");
              }}>رد کردن اندازه‌گیری‌های اختیاری</button>
            </>
          )}
          {step === 3 && (
            <>
              <ExperienceFields
                values={values}
                errors={errors}
                disabled={busy}
                onChange={updateValue}
              />
              <button className="text-button" type="button" onClick={() => updateValue("physical_limitations", "")}>رد کردن توضیحات اختیاری</button>
            </>
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
    </OnboardingShell>
  );
}

function OnboardingShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  function handleLogout() {
    setBusy(true);
    setError(false);
    void logout()
      .then(() => navigate("/", { replace: true }))
      .catch(() => setError(true))
      .finally(() => setBusy(false));
  }

  return (
    <AuthShell>
      <div className="onboarding-session-actions">
        <button className="logout-button" type="button" disabled={busy} onClick={handleLogout}>
          {busy ? t("header.loggingOut") : t("header.logout")}
        </button>
        {error && <p className="form-error" role="alert">{t("errors.generic")}</p>}
      </div>
      {children}
    </AuthShell>
  );
}
