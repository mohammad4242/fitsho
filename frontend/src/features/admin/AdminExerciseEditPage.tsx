import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../shared/apiClient";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { getAdminExercise, updateAdminExercise } from "./api";
import { AdminExerciseForm, type ProgrammingMetadata } from "./AdminExerciseForm";
import type { AdminExercise, AdminExerciseForm as AdminExerciseFormState } from "./types";
import { adminExerciseToForm, toAdminExerciseCreate } from "./validation";
import "./admin.css";

export function AdminExerciseEditPage() {
  const { t } = useTranslation();
  const { exerciseId } = useParams();
  const navigate = useNavigate();
  const [exercise, setExercise] = useState<AdminExercise | null>(null);
  const [form, setForm] = useState<AdminExerciseFormState | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "missing" | "error">("loading");
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const [reload, setReload] = useState(0);

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
      await updateAdminExercise(exerciseId, toAdminExerciseCreate(form), null);
      navigate("/admin/exercises", { replace: true });
    } catch {
      setSaveError(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="admin-page">
      <AuthenticatedHeader />
      <main className="admin-main admin-main--form">
        <header className="admin-form-header">
          <div><p className="eyebrow eyebrow--accent">{t("admin.edit.eyebrow")}</p><h1>{t("admin.edit.title")}</h1><p>{t("admin.edit.intro")}</p></div>
          <Link to="/admin/exercises">{t("admin.edit.back")}</Link>
        </header>
        {state === "loading" && <p className="admin-status" role="status">{t("admin.edit.loading")}</p>}
        {state === "missing" && <p className="admin-status" role="alert">{t("admin.edit.missing")}</p>}
        {state === "error" && <div className="admin-status" role="alert"><p>{t("admin.edit.loadError")}</p><button type="button" onClick={() => setReload((value) => value + 1)}>{t("common.retry")}</button></div>}
        {state === "ready" && form !== null && exercise !== null && (
          <form className="admin-form" noValidate onSubmit={(event) => { event.preventDefault(); void save(); }}>
            {saveError && <div className="admin-form-alert" role="alert">{t("admin.errors.api")}</div>}
            <p className="admin-status" dir="ltr">{exercise.slug}</p>
            <AdminExerciseForm value={form} onChange={setProgrammingField} />
            <div className="admin-form-actions"><button className="admin-primary-link" type="submit" disabled={busy}>{busy ? t("admin.actions.savingChanges") : t("admin.actions.saveChanges")}</button></div>
          </form>
        )}
      </main>
    </div>
  );
}
