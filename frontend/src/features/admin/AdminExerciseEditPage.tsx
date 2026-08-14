import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import appTrainingAccent from "../../assets/landing/app-training-accent.jpg";
import { ApiError } from "../../shared/apiClient";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import { getAdminExercise, updateAdminExercise } from "./api";
import { AdminExerciseFields } from "./AdminExerciseFields";
import { exerciseLibraryReturnPath, readExerciseLibraryReturn } from "./exerciseLibraryNavigation";
import type {
  AdminExercise,
  AdminExerciseForm,
  AdminExerciseMediaFiles,
} from "./types";
import {
  adminExerciseToForm,
  toAdminExerciseCreate,
  validateAdminExercise,
  type AdminValidationErrors,
} from "./validation";
import "./admin.css";

export function AdminExerciseEditPage() {
  const { t } = useTranslation();
  const { exerciseId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = readExerciseLibraryReturn(searchParams);
  const [exercise, setExercise] = useState<AdminExercise | null>(null);
  const [form, setForm] = useState<AdminExerciseForm | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "missing" | "error">("loading");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<AdminValidationErrors>({});
  const [requestError, setRequestError] = useState<"duplicate" | "api" | null>(null);
  const [reload, setReload] = useState(0);
  const [media, setMedia] = useState<File | null>(null);
  const [mediaAssets, setMediaAssets] = useState<AdminExerciseMediaFiles>([]);
  const [preview, setPreview] = useState<string | null>(null);

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
        setErrors({});
        setRequestError(null);
        setState("ready");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setState(error instanceof ApiError && error.status === 404 ? "missing" : "error");
      });
    return () => { active = false; };
  }, [exerciseId, reload]);

  useEffect(() => {
    if (media === null) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(media);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [media]);

  function setField<K extends keyof AdminExerciseForm>(key: K, value: AdminExerciseForm[K]) {
    setForm((current) => current === null ? current : { ...current, [key]: value });
    setErrors((current) => ({ ...current, [key]: undefined }));
  }

  async function save() {
    if (!exerciseId || form === null) return;
    const nextErrors = validateAdminExercise(form);
    setErrors(nextErrors);
    setRequestError(null);
    if (Object.keys(nextErrors).length > 0) return;
    setBusy(true);
    try {
      const updated = await updateAdminExercise(
        exerciseId,
        toAdminExerciseCreate(form),
        media,
        mediaAssets,
      );
      navigate(
        exerciseLibraryReturnPath(
          returnTo,
          updated.body_region,
          updated.primary_muscle,
          updated.muscle_focus,
          updated.is_active,
          updated.needs_review,
        ),
        { replace: true, state: { editedId: updated.id } },
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setRequestError("duplicate");
        setErrors((current) => ({ ...current, slug: "required" }));
      } else {
        setRequestError("api");
        if (error instanceof ApiError && error.details) {
          const field = error.details[0]?.loc?.at(-1);
          if (typeof field === "string" && field in form) {
            setErrors((current) => ({ ...current, [field]: "required" }));
          }
        }
      }
    } finally {
      setBusy(false);
    }
  }

  const previewType = media?.type.startsWith("video/")
    ? "video"
    : media
      ? "gif"
      : exercise?.media_type ?? "placeholder";

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={appTrainingAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--form">
        <header className="admin-form-header">
          <div>
            <p className="eyebrow eyebrow--accent">{t("admin.edit.eyebrow")}</p>
            <h1>{t("admin.edit.title")}</h1>
            <p>{t("admin.edit.intro")}</p>
          </div>
          <Link to={returnTo}>{t("admin.edit.back")}</Link>
        </header>
        {state === "loading" && <p className="admin-status" role="status">{t("admin.edit.loading")}</p>}
        {state === "missing" && <p className="admin-status" role="alert">{t("admin.edit.missing")}</p>}
        {state === "error" && (
          <div className="admin-status" role="alert">
            <p>{t("admin.edit.loadError")}</p>
            <button type="button" onClick={() => setReload((value) => value + 1)}>
              {t("common.retry")}
            </button>
          </div>
        )}
        {state === "ready" && form !== null && exercise !== null && (
          <form
            className="admin-form"
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            {(Object.keys(errors).length > 0 || requestError) && (
              <div className="admin-form-alert" role="alert">
                {requestError === "duplicate"
                  ? t("admin.errors.duplicate")
                  : requestError === "api"
                    ? t("admin.errors.api")
                    : t("admin.errors.validation")}
                {requestError === "api" && (
                  <button type="button" onClick={() => void save()}>{t("common.retry")}</button>
                )}
              </div>
            )}
            <AdminExerciseFields
              value={form}
              errors={errors}
              duplicateSlug={requestError === "duplicate"}
              primaryMediaPath={preview ?? exercise.media_path}
              primaryMediaType={previewType}
              mediaFiles={mediaAssets}
              onChange={setField}
              onPrimaryMediaChange={setMedia}
              onMediaFilesChange={setMediaAssets}
            />
            <div className="admin-form-actions">
              <button className="admin-primary-link" type="submit" disabled={busy}>
                {busy ? t("admin.actions.savingChanges") : t("admin.actions.saveChanges")}
              </button>
            </div>
          </form>
        )}
      </main>
    </div>
  );
}
