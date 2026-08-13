import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { AuthShell } from "../../shared/AuthShell";
import * as api from "./api";
import { authErrorMessage } from "./authError";

export function ForgotPasswordPage() {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    void api
      .forgotPassword(String(data.get("email") ?? ""))
      .then(() => setSent(true))
      .catch((requestError: unknown) => setError(authErrorMessage(requestError, t)))
      .finally(() => setBusy(false));
  }

  return (
    <AuthShell>
      <div className="form-heading">
        <p className="eyebrow eyebrow--accent">{t("passwordRecovery.eyebrow")}</p>
        <h2 className="fitsho-display">{t("passwordRecovery.forgotTitle")}</h2>
        <p>{t("passwordRecovery.forgotSubtitle")}</p>
      </div>
      {sent ? (
        <p className="form-success" role="status" aria-live="polite">
          {t("passwordRecovery.forgotSuccess")}
        </p>
      ) : (
        <form className="auth-form" onSubmit={handleSubmit}>
          <label htmlFor="recovery-email">{t("common.email")}</label>
          <input
            id="recovery-email"
            name="email"
            type="email"
            autoComplete="email"
            inputMode="email"
            required
          />
          {error && (
            <p className="form-error" role="alert" aria-live="polite">
              {error}
            </p>
          )}
          <button className="primary-button" type="submit" disabled={busy}>
            <span>
              {t(busy ? "passwordRecovery.forgotSubmitting" : "passwordRecovery.forgotSubmit")}
            </span>
            <span aria-hidden="true">←</span>
          </button>
        </form>
      )}
      <p className="form-alternative">
        <Link to="/login">{t("passwordRecovery.backToLogin")}</Link>
      </p>
    </AuthShell>
  );
}
