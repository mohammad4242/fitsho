import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import authTrainingAccent from "../../assets/landing/auth-training-accent.jpg";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import { NutritionOnboardingFlow } from "../nutrition/NutritionOnboardingFlow";
import * as profileApi from "./api";
import {
  BodyGoalFields,
  ExperienceFields,
  PersonalFields,
} from "./ProfileFormFields";
import { useProfile } from "./ProfileContext";
import {
  profileToFormValues,
  toProfilePatch,
  validateStep,
  type ProfileValidationErrors,
} from "./profileValidation";
import type {
  ProductMode,
  Profile,
  ProfileFormValues,
  ProfilePatch,
  SharedProfile,
  SharedProfileInput,
} from "./types";
import "./profile.css";

type SaveStatus = "idle" | "saved" | "unchanged";
type ProfileSection = "personal" | "training" | "nutrition";

const sections: ProfileSection[] = ["personal", "training", "nutrition"];
const personalFields = new Set<keyof ProfilePatch>([
  "display_name", "birth_date", "sex", "height_cm", "current_weight_kg",
  "shoulder_circumference_cm", "waist_circumference_cm", "hip_circumference_cm",
  "fitness_goal",
]);
const trainingFields = new Set<keyof ProfilePatch>([
  "experience_level", "training_days_per_week", "training_location",
  "home_training_setup", "session_duration_minutes", "physical_limitations",
  "training_cautions", "plan_duration_weeks", "workout_generation_method",
]);

export function ProfilePage() {
  const { createProfile, productMode, profile, retryProfile, updateProfile } = useProfile();

  if (profile === null) {
    if (productMode === "nutrition") {
      return (
        <NutritionOnlyProfileLoader
          productMode={productMode}
          createTrainingProfile={createProfile}
          onNutritionComplete={retryProfile}
        />
      );
    }
    return null;
  }

  return (
    <ReadyProfilePage
      initialProfile={profile}
      initialShared={sharedFromProfile(profile, productMode ?? "training")}
      updateProfile={updateProfile}
      productMode={productMode ?? "training"}
      createTrainingProfile={createProfile}
      onNutritionComplete={retryProfile}
    />
  );
}

function NutritionOnlyProfileLoader({
  productMode,
  createTrainingProfile,
  onNutritionComplete,
}: {
  productMode: ProductMode;
  createTrainingProfile: ReturnType<typeof useProfile>["createProfile"];
  onNutritionComplete: () => void;
}) {
  const { t } = useTranslation();
  const [shared, setShared] = useState<SharedProfile | null | undefined>(undefined);

  useEffect(() => {
    let active = true;
    void profileApi.getSharedProfile()
      .then((value) => { if (active) setShared(value); })
      .catch(() => { if (active) setShared(null); });
    return () => { active = false; };
  }, []);

  if (shared === undefined) return <ProfileLoadingShell message={t("common.loading")} />;
  if (shared === null) return <ProfileLoadingShell message={t("errors.network")} error />;

  return (
    <ReadyProfilePage
      initialProfile={null}
      initialShared={shared}
      updateProfile={async () => { throw new Error("Training profile is optional"); }}
      saveSharedProfile={async (input) => {
        const updated = await profileApi.saveSharedProfile(input);
        setShared(updated);
        return updated;
      }}
      productMode={productMode}
      createTrainingProfile={createTrainingProfile}
      onNutritionComplete={onNutritionComplete}
    />
  );
}

function ProfileLoadingShell({ message, error = false }: { message: string; error?: boolean }) {
  return (
    <div className="profile-page-shell">
      <MemberHeaderMedia imageSrc={authTrainingAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="profile-page-main">
        <p className={error ? "form-error" : undefined} role={error ? "alert" : "status"}>{message}</p>
      </main>
    </div>
  );
}

function ReadyProfilePage({
  initialProfile,
  initialShared,
  updateProfile,
  saveSharedProfile,
  productMode,
  createTrainingProfile,
  onNutritionComplete,
}: {
  initialProfile: Profile | null;
  initialShared: SharedProfile;
  updateProfile: (patch: ProfilePatch) => Promise<Profile>;
  saveSharedProfile?: (input: SharedProfileInput) => Promise<SharedProfile>;
  productMode: ProductMode;
  createTrainingProfile: ReturnType<typeof useProfile>["createProfile"];
  onNutritionComplete: () => void;
}) {
  const { i18n, t } = useTranslation();
  const navigate = useNavigate();
  const language = i18n.resolvedLanguage === "en" ? "en" : "fa";
  const l = (fa: string, en: string) => language === "en" ? en : fa;
  const [baselineProfile, setBaselineProfile] = useState(initialProfile);
  const [baselineShared, setBaselineShared] = useState(initialShared);
  const [values, setValues] = useState(() => initialProfile === null
    ? sharedToFormValues(initialShared)
    : profileToFormValues(initialProfile));
  const [errors, setErrors] = useState<ProfileValidationErrors>({});
  const [status, setStatus] = useState<SaveStatus>("idle");
  const [saveError, setSaveError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [section, setSection] = useState<ProfileSection>("personal");

  useEffect(() => {
    const firstInvalidField = Object.keys(errors)[0];
    if (firstInvalidField !== undefined) {
      document.querySelector<HTMLElement>(`[name="${firstInvalidField}"]`)?.focus();
    }
  }, [errors]);

  function updateValue(
    field: keyof ProfileFormValues,
    value: string | ProfileFormValues["training_cautions"],
  ) {
    const clearsHomeSetup = field === "training_location" && value === "gym";
    setValues((current) => ({
      ...current,
      [field]: value,
      ...(clearsHomeSetup ? { home_training_setup: "" } : {}),
    }));
    setStatus("idle");
    setSaveError(false);
    setErrors((current) => {
      const next = { ...current };
      delete next[field];
      if (clearsHomeSetup) delete next.home_training_setup;
      return next;
    });
  }

  function currentErrors(): ProfileValidationErrors {
    if (section === "personal") {
      return {
        ...validateStep(values, 1, new Date()),
        ...validateStep(values, 2, new Date()),
      };
    }
    if (section === "training" && baselineProfile !== null) {
      return validateStep(values, 3, new Date());
    }
    return {};
  }

  function advance() {
    setErrors({});
    setStatus("idle");
    setSection(section === "personal" ? "training" : "nutrition");
  }

  async function persistCurrent(advanceAfterSave: boolean) {
    if (busy || section === "nutrition") return;
    const validationErrors = currentErrors();
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;

    if (section === "training" && baselineProfile === null) {
      if (advanceAfterSave) advance();
      return;
    }

    setBusy(true);
    setStatus("idle");
    setSaveError(false);
    try {
      if (baselineProfile === null) {
        const input = toSharedProfileInput(values);
        if (sameSharedProfile(input, baselineShared)) {
          setStatus("unchanged");
        } else if (saveSharedProfile !== undefined) {
          const updated = await saveSharedProfile(input);
          setBaselineShared(updated);
          setStatus("saved");
        }
      } else {
        const patch = filterProfilePatch(toProfilePatch(values, baselineProfile), section);
        if (Object.keys(patch).length === 0) {
          setStatus("unchanged");
        } else {
          const updated = await updateProfile(patch);
          setBaselineProfile(updated);
          setBaselineShared(sharedFromProfile(updated, productMode));
          setValues(profileToFormValues(updated));
          setStatus("saved");
        }
      }
      if (advanceAfterSave) advance();
    } catch {
      setSaveError(true);
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void persistCurrent(false);
  }

  function goBack() {
    setErrors({});
    setSaveError(false);
    setStatus("idle");
    if (section === "personal") navigate("/dashboard");
    else setSection(section === "nutrition" ? "training" : "personal");
  }

  const locale = language === "en" ? "en" : "fa-IR";
  const measuredWeight = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 })
    .format(baselineShared.current_weight_kg);
  const measuredAt = new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(baselineShared.weight_measured_at));

  return (
    <div className="profile-page-shell" dir={language === "fa" ? "rtl" : "ltr"}>
      <MemberHeaderMedia imageSrc={authTrainingAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="profile-page-main">
        <section className="profile-page-heading">
          <p className="eyebrow eyebrow--accent">{t("profile.eyebrow")}</p>
          <h1 className="fitsho-display">{t("profile.title")}</h1>
          <p>{t("profile.intro")}</p>
        </section>

        {section === "personal" && <>
          <aside className="measurement-card" aria-label={t("profile.measurementTitle")}>
            <p>{t("profile.measurementTitle")}</p>
            <strong>{t("profile.weightValue", { weight: measuredWeight })}</strong>
            <span>{t("profile.measuredAt", { date: measuredAt })}</span>
          </aside>
          <aside className="measurement-card" aria-label={t("bodyPhotos.progressTitle")}>
            <p>{t("bodyPhotos.progressTitle")}</p>
            <strong>{t("bodyPhotos.optionalIntro")}</strong>
            <Link className="secondary-button" to="/body-progress">{t("bodyPhotos.start")}</Link>
          </aside>
        </>}

        <section className="profile-wizard">
          <ProfileProgress section={section} language={language} />

          {section !== "nutrition" && (
            <form className="profile-form profile-edit-form profile-wizard__page" noValidate onSubmit={handleSubmit}>
              <h2 className="fitsho-display">{section === "personal"
                ? l("اطلاعات شخصی", "Personal information")
                : l("اطلاعات تمرینی", "Training information")}</h2>

              {section === "personal" && <>
                <PersonalFields values={values} errors={errors} disabled={busy} onChange={updateValue} />
                <BodyGoalFields
                  values={values}
                  errors={errors}
                  disabled={busy}
                  onChange={updateValue}
                  showCircumferences={baselineProfile !== null}
                />
              </>}

              {section === "training" && baselineProfile !== null && (
                <ExperienceFields values={values} errors={errors} disabled={busy} onChange={updateValue} />
              )}
              {section === "training" && baselineProfile === null && (
                <div className="profile-optional-state">
                  <p>{l("این بخش برای مسیر تغذیه اختیاری است.", "This section is optional for the nutrition path.")}</p>
                  <span>{l("هر زمان برنامه تمرینی خواستی، می‌توانی این بخش را کامل کنی.", "Complete it whenever you decide to add a training plan.")}</span>
                </div>
              )}

              {saveError && <p className="form-error profile-save-message" role="alert">{t("profile.saveError")}</p>}
              {status !== "idle" && (
                <p className="profile-save-message profile-save-message--success" role="status">
                  {status === "saved" ? t("profile.saved", { name: baselineShared.display_name }) : t("profile.unchanged")}
                </p>
              )}

              {baselineProfile !== null && (
                <button className="text-button profile-inline-save" type="submit" disabled={busy}>
                  {busy ? t("profile.saving") : t("profile.save")}
                </button>
              )}
              {baselineProfile === null && section === "personal" && (
                <button className="text-button profile-inline-save" type="submit" disabled={busy}>
                  {busy ? t("profile.saving") : t("profile.save")}
                </button>
              )}

              <div className="profile-actions profile-wizard__actions">
                <button className="secondary-button" type="button" disabled={busy} onClick={goBack}>{l("بازگشت", "Back")}</button>
                <button className="primary-button" type="button" disabled={busy} onClick={() => void persistCurrent(true)}>{l("بعدی", "Next")}</button>
              </div>
            </form>
          )}

          {section === "nutrition" && productMode !== "training" && (
            <div className="profile-wizard__page profile-wizard__nutrition">
              <NutritionOnboardingFlow
                productMode={productMode}
                editExisting
                trainingProfileExists={baselineProfile !== null}
                onBack={goBack}
                onCreateTrainingProfile={createTrainingProfile}
                onComplete={onNutritionComplete}
              />
            </div>
          )}

          {section === "nutrition" && productMode === "training" && (
            <section className="profile-wizard__page profile-optional-state">
              <h2 className="fitsho-display">{l("اطلاعات تغذیه‌ای", "Nutrition information")}</h2>
              <p>{l("پروفایل تغذیه برای مسیر فعلی اختیاری است.", "A nutrition profile is optional for your current path.")}</p>
              <div className="profile-actions profile-wizard__actions">
                <button className="secondary-button" type="button" onClick={goBack}>{l("بازگشت", "Back")}</button>
                <button className="primary-button" type="button" onClick={() => navigate("/dashboard")}>{l("بعدی", "Next")}</button>
              </div>
            </section>
          )}
        </section>
      </main>
    </div>
  );
}

function ProfileProgress({ section, language }: { section: ProfileSection; language: "fa" | "en" }) {
  const labels = language === "en"
    ? ["Personal", "Training", "Nutrition"]
    : ["شخصی", "تمرینی", "تغذیه‌ای"];
  const current = sections.indexOf(section);
  const localizedStep = language === "en" ? String(current + 1) : new Intl.NumberFormat("fa-IR").format(current + 1);
  const localizedTotal = language === "en" ? "3" : new Intl.NumberFormat("fa-IR").format(3);
  return (
    <nav className="profile-progress" aria-label={language === "en" ? "Profile progress" : "پیشرفت پروفایل"}>
      <p className="profile-progress__count">{language === "en" ? `Step ${localizedStep} of ${localizedTotal}` : `مرحله ${localizedStep} از ${localizedTotal}`}</p>
      <ol>
        {labels.map((label, index) => (
          <li className={index <= current ? "is-active" : undefined} aria-current={index === current ? "step" : undefined} key={label}>
            <span aria-hidden="true">{index + 1}</span>
            <strong>{label}</strong>
          </li>
        ))}
      </ol>
    </nav>
  );
}

function sharedFromProfile(profile: Profile, productMode: ProductMode): SharedProfile {
  return {
    user_id: profile.user_id,
    product_mode: productMode,
    display_name: profile.display_name,
    birth_date: profile.birth_date,
    sex: profile.sex,
    height_cm: profile.height_cm,
    current_weight_kg: profile.current_weight_kg,
    fitness_goal: profile.fitness_goal,
    weight_measured_at: profile.weight_measured_at,
  };
}

function sharedToFormValues(profile: SharedProfile): ProfileFormValues {
  return {
    display_name: profile.display_name,
    birth_date: profile.birth_date,
    sex: profile.sex,
    height_cm: String(profile.height_cm),
    current_weight_kg: String(profile.current_weight_kg),
    shoulder_circumference_cm: "",
    waist_circumference_cm: "",
    hip_circumference_cm: "",
    fitness_goal: profile.fitness_goal,
    experience_level: "",
    training_days_per_week: "",
    training_location: "",
    home_training_setup: "",
    session_duration_minutes: "",
    physical_limitations: "",
    training_cautions: null,
    plan_duration_weeks: "4",
  };
}

function toSharedProfileInput(values: ProfileFormValues): SharedProfileInput {
  return {
    display_name: values.display_name.trim(),
    birth_date: values.birth_date,
    sex: values.sex as SharedProfileInput["sex"],
    height_cm: Number(values.height_cm),
    current_weight_kg: Number(values.current_weight_kg),
    fitness_goal: values.fitness_goal as SharedProfileInput["fitness_goal"],
  };
}

function sameSharedProfile(input: SharedProfileInput, profile: SharedProfile): boolean {
  return input.display_name === profile.display_name
    && input.birth_date === profile.birth_date
    && input.sex === profile.sex
    && input.height_cm === profile.height_cm
    && input.current_weight_kg === profile.current_weight_kg
    && input.fitness_goal === profile.fitness_goal;
}

function filterProfilePatch(patch: ProfilePatch, section: Exclude<ProfileSection, "nutrition">): ProfilePatch {
  const allowed = section === "personal" ? personalFields : trainingFields;
  return Object.fromEntries(
    Object.entries(patch).filter(([field]) => allowed.has(field as keyof ProfilePatch)),
  ) as ProfilePatch;
}
