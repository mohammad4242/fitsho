import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import appTrainingAccent from "../../assets/landing/app-training-accent.jpg";
import { ApiError } from "../../shared/apiClient";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import { createAdminExercise } from "./api";
import { AdminExerciseFields } from "./AdminExerciseFields";
import {
  exerciseLibraryReturnPath,
  readExerciseCreateContext,
  readExerciseLibraryReturn,
} from "./exerciseLibraryNavigation";
import type { AdminExerciseForm, AdminExerciseMediaFiles } from "./types";
import {
  emptyAdminExerciseForm,
  toAdminExerciseCreate,
  validateAdminExercise,
  type AdminValidationErrors,
} from "./validation";
import "./admin.css";

export function AdminExerciseNewPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = readExerciseLibraryReturn(searchParams);
  const [form, setForm] = useState<AdminExerciseForm>(() => ({
    ...emptyAdminExerciseForm(),
    ...readExerciseCreateContext(searchParams),
  }));
  const [errors, setErrors] = useState<AdminValidationErrors>({});
  const [media, setMedia] = useState<File | null>(null);
  const [mediaAssets, setMediaAssets] = useState<AdminExerciseMediaFiles>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [requestError, setRequestError] = useState<"duplicate" | "api" | null>(null);

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
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  }

  async function submitForm() {
    const nextErrors = validateAdminExercise(form);
    setErrors(nextErrors);
    setRequestError(null);
    if (Object.keys(nextErrors).length > 0) return;
    setBusy(true);
    try {
      const created = await createAdminExercise(toAdminExerciseCreate(form), media, mediaAssets);
      navigate(
        exerciseLibraryReturnPath(
          returnTo,
          created.body_region,
          created.primary_muscle,
          created.muscle_focus,
          created.is_active,
          created.needs_review,
        ),
        { replace: true, state: { createdId: created.id } },
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

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void submitForm();
  }

  const previewType = media?.type.startsWith("video/") ? "video" : media ? "gif" : "placeholder";

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={appTrainingAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--form">
        <header className="admin-form-header">
          <div>
            <p className="eyebrow eyebrow--accent">{t("admin.new.eyebrow")}</p>
            <h1>{t("admin.new.title")}</h1>
            <p>{t("admin.new.intro")}</p>
          </div>
          <Link to={returnTo}>{t("admin.new.back")}</Link>
        </header>
        <form className="admin-form" noValidate onSubmit={handleSubmit}>
          {(Object.keys(errors).length > 0 || requestError) && (
            <div className="admin-form-alert" role="alert">
              {requestError === "duplicate"
                ? t("admin.errors.duplicate")
                : requestError === "api"
                  ? t("admin.errors.api")
                  : t("admin.errors.validation")}
              {requestError === "api" && (
                <button type="button" onClick={() => void submitForm()}>{t("common.retry")}</button>
              )}
            </div>
          )}
          <AdminExerciseFields
            value={form}
            errors={errors}
            duplicateSlug={requestError === "duplicate"}
            suggestSlugFromName
            primaryMediaPath={preview ?? ""}
            primaryMediaType={previewType}
            mediaFiles={mediaAssets}
            onChange={setField}
            onPrimaryMediaChange={setMedia}
            onMediaFilesChange={setMediaAssets}
          />
          <div className="admin-form-actions">
            <button className="admin-primary-link" type="submit" disabled={busy}>
              {busy ? t("admin.actions.saving") : t("admin.actions.save")}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
