import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getProfile, updateProfile } from "../profile/api";
import {
  validateBodyAnalysisMeasurements,
} from "../profile/profileValidation";
import {
  MeasurementFields,
} from "../profile/ProfileFormFields";
import type {
  MeasurementField,
  MeasurementFormValues,
  Profile,
  ProfilePatch,
} from "../profile/types";
import "./bodyPhotos.css";

type BodyAnalysisRequirementsStepProps = {
  onConfirmed: () => void;
  onCancel: () => void;
};

const circumferenceFields: MeasurementField[] = [
  "shoulder_circumference_cm",
  "waist_circumference_cm",
  "hip_circumference_cm",
];

export function BodyAnalysisRequirementsStep({
  onConfirmed,
  onCancel,
}: BodyAnalysisRequirementsStepProps) {
  const { t } = useTranslation();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [values, setValues] = useState<MeasurementFormValues | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [saveError, setSaveError] = useState(false);

  useEffect(() => {
    let active = true;
    void getProfile()
      .then((loadedProfile) => {
        if (!active) return;
        if (loadedProfile === null) {
          setLoadError(true);
          return;
        }
        const nextValues = measurementValuesFromProfile(loadedProfile);
        setProfile(loadedProfile);
        setValues(nextValues);
      })
      .catch(() => {
        if (active) setLoadError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const validationErrors = useMemo(
    () => values === null ? {} : validateBodyAnalysisMeasurements(values),
    [values],
  );
  const canContinue = values !== null
    && Object.keys(validationErrors).length === 0
    && confirmed
    && !busy;

  function changeMeasurement(field: MeasurementField, value: string) {
    setValues((current) => current === null ? current : { ...current, [field]: value });
    setConfirmed(false);
    setSaveError(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (profile === null || values === null || !confirmed || busy) return;
    const nextErrors = validateBodyAnalysisMeasurements(values);
    if (Object.keys(nextErrors).length > 0) return;

    setBusy(true);
    setSaveError(false);
    try {
      const patch = measurementPatch(values, profile);
      if (Object.keys(patch).length > 0) {
        await updateProfile(patch);
      }
      onConfirmed();
    } catch {
      setSaveError(true);
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <section className="body-photo-wizard body-analysis-requirements" aria-labelledby="body-analysis-requirements-title">
        <p role="status">{t("bodyPhotos.measurements.loading")}</p>
      </section>
    );
  }

  if (loadError || values === null) {
    return (
      <section className="body-photo-wizard body-analysis-requirements" aria-labelledby="body-analysis-requirements-title">
        <p className="eyebrow eyebrow--accent">{t("bodyPhotos.measurements.eyebrow")}</p>
        <h1 id="body-analysis-requirements-title" className="fitsho-display">
          {t("bodyPhotos.measurements.title")}
        </h1>
        <p role="alert">{t("bodyPhotos.measurements.loadError")}</p>
        <button className="secondary-button" type="button" onClick={onCancel}>
          {t("bodyPhotos.measurements.back")}
        </button>
      </section>
    );
  }

  return (
    <section className="body-photo-wizard body-analysis-requirements" aria-labelledby="body-analysis-requirements-title">
      <p className="eyebrow eyebrow--accent">{t("bodyPhotos.measurements.eyebrow")}</p>
      <h1 id="body-analysis-requirements-title" className="fitsho-display">
        {t("bodyPhotos.measurements.title")}
      </h1>
      <p>{t("bodyPhotos.measurements.body")}</p>
      <form onSubmit={(event) => void submit(event)}>
        <fieldset className="profile-fieldset" disabled={busy}>
          <legend>{t("onboarding.steps.bodyGoal")}</legend>
          <MeasurementFields
            values={values}
            errors={validationErrors}
            onChange={changeMeasurement}
            requiredCircumferences
            idPrefix="body-analysis"
          />
        </fieldset>
        <p className="body-photo-muted">{t("bodyPhotos.measurements.snapshotNote")}</p>
        <label className="body-photo-consent">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
            disabled={busy}
          />
          <span>{t("bodyPhotos.measurements.confirmLabel")}</span>
        </label>
        {saveError && <p className="form-error" role="alert">{t("bodyPhotos.measurements.saveError")}</p>}
        <div className="body-analysis-requirements__actions">
          <button className="secondary-button" type="button" onClick={onCancel} disabled={busy}>
            {t("bodyPhotos.measurements.back")}
          </button>
          <button className="primary-button" type="submit" disabled={!canContinue}>
            {busy ? t("bodyPhotos.measurements.saving") : t("bodyPhotos.measurements.continue")}
          </button>
        </div>
      </form>
    </section>
  );
}

function measurementValuesFromProfile(profile: Profile): MeasurementFormValues {
  return {
    height_cm: String(profile.height_cm),
    current_weight_kg: String(profile.current_weight_kg),
    shoulder_circumference_cm: profile.shoulder_circumference_cm === null
      ? ""
      : String(profile.shoulder_circumference_cm),
    waist_circumference_cm: profile.waist_circumference_cm === null
      ? ""
      : String(profile.waist_circumference_cm),
    hip_circumference_cm: profile.hip_circumference_cm === null
      ? ""
      : String(profile.hip_circumference_cm),
  };
}

function measurementPatch(
  values: MeasurementFormValues,
  profile: Profile,
): ProfilePatch {
  const patch: ProfilePatch = {};
  const height = Number(values.height_cm.trim());
  const weight = Number(values.current_weight_kg.trim());
  if (height !== profile.height_cm) patch.height_cm = height;
  if (weight !== profile.current_weight_kg) patch.current_weight_kg = weight;

  for (const field of circumferenceFields) {
    const value = Number(values[field].trim());
    if (value !== profile[field]) patch[field] = value;
  }
  return patch;
}
