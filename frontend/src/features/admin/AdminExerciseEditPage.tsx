import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import appTrainingAccent from "../../assets/landing/app-training-accent.jpg";
import { ApiError } from "../../shared/apiClient";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import { getAdminExercise, updateAdminExercise } from "./api";
import { AdminExerciseForm, type ProgrammingMetadata } from "./AdminExerciseForm";
import { ExerciseMediaAssetsFields } from "./ExerciseMediaAssetsFields";
import { exerciseLibraryReturnPath, readExerciseLibraryReturn } from "./exerciseLibraryNavigation";
import type {
  AdminExercise,
  AdminExerciseForm as AdminExerciseFormState,
  AdminExerciseMediaFiles,
} from "./types";
import { adminExerciseToForm, toAdminExerciseCreate } from "./validation";
import "./admin.css";

export function AdminExerciseEditPage() {
  const { t } = useTranslation();
  const { exerciseId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = readExerciseLibraryReturn(searchParams);
  const [exercise, setExercise] = useState<AdminExercise | null>(null);
  const [form, setForm] = useState<AdminExerciseFormState | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "missing" | "error">("loading");
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const [reload, setReload] = useState(0);
  const [mediaAssets, setMediaAssets] = useState<AdminExerciseMediaFiles>([]);

  useEffect(() => {
    if (!exerciseId) {
      setState("missing");
      return;
    }
    let active = true;
    setState("loading");
    void getAdminExercise(exerciseId)
      .then((result) => {
        if (!active) return;
        setExercise(result);
        setForm(adminExerciseToForm(result));
        setState("ready");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setState(error instanceof ApiError && error.status === 404 ? "missing" : "error");
      });
    return () => { active = false; };
  }, [exerciseId, reload]);

  function setField<K extends keyof AdminExerciseFormState>(
    key: K,
    value: AdminExerciseFormState[K],
  ) {
    setForm((current) => current === null ? current : { ...current, [key]: value });
  }

  function setProgrammingField<K extends keyof ProgrammingMetadata>(key: K, value: ProgrammingMetadata[K]) {
    setField(key, value as AdminExerciseFormState[K]);
  }

  async function save() {
    if (!exerciseId || form === null) return;
    setBusy(true);
    setSaveError(false);
    try {
      const updated = await updateAdminExercise(
        exerciseId,
        toAdminExerciseCreate(form),
        null,
        mediaAssets,
      );
      navigate(
        exerciseLibraryReturnPath(
          returnTo,
          updated.body_region,
          updated.primary_muscle,
          updated.is_active,
          updated.needs_review,
        ),
        { replace: true },
      );
    } catch {
      setSaveError(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={appTrainingAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--form">
        <header className="admin-form-header">
          <div><p className="eyebrow eyebrow--accent">{t("admin.edit.eyebrow")}</p><h1>{t("admin.edit.title")}</h1><p>{t("admin.edit.intro")}</p></div>
          <Link to={returnTo}>{t("admin.edit.back")}</Link>
        </header>
        {state === "loading" && <p className="admin-status" role="status">{t("admin.edit.loading")}</p>}
        {state === "missing" && <p className="admin-status" role="alert">{t("admin.edit.missing")}</p>}
        {state === "error" && <div className="admin-status" role="alert"><p>{t("admin.edit.loadError")}</p><button type="button" onClick={() => setReload((value) => value + 1)}>{t("common.retry")}</button></div>}
        {state === "ready" && form !== null && exercise !== null && (
          <form className="admin-form" noValidate onSubmit={(event) => { event.preventDefault(); void save(); }}>
            {saveError && <div className="admin-form-alert" role="alert">{t("admin.errors.api")}</div>}
            <p className="admin-status" dir="ltr">{exercise.slug}</p>
            <AdminExerciseForm value={form} onChange={setProgrammingField} />
            <ExerciseMediaAssetsFields
              assets={form.media_assets}
              files={mediaAssets}
              onAssetsChange={(mediaAssetsInput) => setField("media_assets", mediaAssetsInput)}
              onFilesChange={setMediaAssets}
            />
            <div className="admin-form-actions"><button className="admin-primary-link" type="submit" disabled={busy}>{busy ? t("admin.actions.savingChanges") : t("admin.actions.saveChanges")}</button></div>
          </form>
        )}
      </main>
    </div>
  );
}
