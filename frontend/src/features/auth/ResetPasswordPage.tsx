import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";

import { AuthShell } from "../../shared/AuthShell";
import { ApiError } from "../../shared/apiClient";
import * as api from "./api";
import { authErrorMessage } from "./authError";

export function ResetPasswordPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [busy, setBusy] = useState(false);
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const password = String(data.get("password") ?? "");
    const confirmation = String(data.get("confirmation") ?? "");
    if (password !== confirmation) {
      setError(t("errors.mismatch"));
      return;
    }
    setBusy(true);
    setError(null);
    void api
      .resetPassword(token, password)
      .then(() => setComplete(true))
      .catch((requestError: unknown) => {
        setError(
          requestError instanceof ApiError && requestError.status === 400
            ? t("passwordRecovery.invalidToken")
            : authErrorMessage(requestError, t),
        );
      })
      .finally(() => setBusy(false));
  }

  return (
    <AuthShell>
      <div className="form-heading">
        <p className="eyebrow eyebrow--accent">{t("passwordRecovery.eyebrow")}</p>
        <h2 className="fitsho-display">{t("passwordRecovery.resetTitle")}</h2>
        <p>{t("passwordRecovery.resetSubtitle")}</p>
      </div>
      {complete ? (
        <p className="form-success" role="status" aria-live="polite">
          {t("passwordRecovery.resetSuccess")}
        </p>
      ) : token ? (
        <form className="auth-form" onSubmit={handleSubmit}>
          <label htmlFor="new-password">{t("passwordRecovery.newPassword")}</label>
          <input
            id="new-password"
            name="password"
            type="password"
            autoComplete="new-password"
            minLength={8}
            maxLength={128}
            required
          />
          <label htmlFor="confirm-new-password">{t("passwordRecovery.confirmPassword")}</label>
          <input
            id="confirm-new-password"
            name="confirmation"
            type="password"
            autoComplete="new-password"
            minLength={8}
            maxLength={128}
            required
          />
          {error && (
            <p className="form-error" role="alert" aria-live="polite">
              {error}
            </p>
          )}
          <button className="primary-button" type="submit" disabled={busy}>
            <span>
              {t(busy ? "passwordRecovery.resetSubmitting" : "passwordRecovery.resetSubmit")}
            </span>
            <span aria-hidden="true">←</span>
          </button>
        </form>
      ) : (
        <p className="form-error" role="alert">
          {t("passwordRecovery.invalidToken")}
        </p>
      )}
      <p className="form-alternative">
        <Link to="/login">{t("passwordRecovery.backToLogin")}</Link>
      </p>
    </AuthShell>
  );
}
