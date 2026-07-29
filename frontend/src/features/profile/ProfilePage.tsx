import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import authTrainingAccent from "../../assets/landing/auth-training-accent.jpg";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import {
  BodyGoalFields,
  ExperienceFields,
  PersonalFields,
} from "./ProfileFormFields";
import { useProfile } from "./ProfileContext";
import {
  profileToFormValues,
  toProfilePatch,
  validateAll,
  type ProfileValidationErrors,
} from "./profileValidation";
import type { Profile, ProfileFormValues, ProfilePatch } from "./types";
import "./profile.css";

type SaveStatus = "idle" | "saved" | "unchanged";

export function ProfilePage() {
  const { profile, updateProfile } = useProfile();

  if (profile === null) {
    return null;
  }

  return <ReadyProfilePage initialProfile={profile} updateProfile={updateProfile} />;
}

function ReadyProfilePage({
  initialProfile,
  updateProfile,
}: {
  initialProfile: Profile;
  updateProfile: (patch: ProfilePatch) => Promise<Profile>;
}) {
  const { i18n, t } = useTranslation();
  const [baseline, setBaseline] = useState(initialProfile);
  const [values, setValues] = useState(() => profileToFormValues(initialProfile));
  const [errors, setErrors] = useState<ProfileValidationErrors>({});
  const [status, setStatus] = useState<SaveStatus>("idle");
  const [saveError, setSaveError] = useState(false);
  const [busy, setBusy] = useState(false);

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

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) {
      return;
    }

    const validationErrors = validateAll(values, new Date());
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    const patch = toProfilePatch(values, baseline);
    if (Object.keys(patch).length === 0) {
      setStatus("unchanged");
      setSaveError(false);
      return;
    }

    setBusy(true);
    setStatus("idle");
    setSaveError(false);
    void updateProfile(patch)
      .then((updatedProfile) => {
        setBaseline(updatedProfile);
        setValues(profileToFormValues(updatedProfile));
        setStatus("saved");
      })
      .catch(() => setSaveError(true))
      .finally(() => setBusy(false));
  }

  const locale = i18n.resolvedLanguage === "en" ? "en" : "fa-IR";
  const measuredWeight = new Intl.NumberFormat(locale, {
    maximumFractionDigits: 2,
  }).format(baseline.current_weight_kg);
  const measuredAt = new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(baseline.weight_measured_at));

  return (
    <div className="profile-page-shell">
      <AuthenticatedHeader />
      <main className="profile-page-main">
        <section className="profile-page-heading">
          <MemberHeaderMedia imageSrc={authTrainingAccent} />
          <p className="eyebrow eyebrow--accent">{t("profile.eyebrow")}</p>
          <h1 className="fitsho-display">{t("profile.title")}</h1>
          <p>{t("profile.intro")}</p>
        </section>

        <aside className="measurement-card" aria-label={t("profile.measurementTitle")}>
          <p>{t("profile.measurementTitle")}</p>
          <strong>{t("profile.weightValue", { weight: measuredWeight })}</strong>
          <span>{t("profile.measuredAt", { date: measuredAt })}</span>
        </aside>

        <form className="profile-form profile-edit-form" noValidate onSubmit={handleSubmit}>
          <PersonalFields
            values={values}
            errors={errors}
            disabled={busy}
            onChange={updateValue}
          />
          <BodyGoalFields
            values={values}
            errors={errors}
            disabled={busy}
            onChange={updateValue}
          />
          <ExperienceFields
            values={values}
            errors={errors}
            disabled={busy}
            onChange={updateValue}
          />

          {saveError && (
            <p className="form-error profile-save-message" role="alert">
              {t("profile.saveError")}
            </p>
          )}
          {status !== "idle" && (
            <p className="profile-save-message profile-save-message--success" role="status">
              {status === "saved"
                ? t("profile.saved", { name: baseline.display_name })
                : t("profile.unchanged")}
            </p>
          )}

          <button className="primary-button profile-save-button" type="submit" disabled={busy}>
            <span>{busy ? t("profile.saving") : t("profile.save")}</span>
            <span aria-hidden="true">✓</span>
          </button>
        </form>
      </main>
    </div>
  );
}
