import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { AuthShell } from "../../shared/AuthShell";
import { authErrorMessage } from "./authError";
import { useAuth } from "./AuthContext";

export function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { register } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") ?? "");
    const password = String(data.get("password") ?? "");
    const confirmation = String(data.get("confirmation") ?? "");

    if (password !== confirmation) {
      setError(t("errors.mismatch"));
      return;
    }

    setBusy(true);
    setError(null);
    void register({ email, password })
      .then(
        () => navigate("/dashboard", { replace: true }),
        (requestError: unknown) => {
          setError(authErrorMessage(requestError, t));
        },
      )
      .finally(() => setBusy(false));
  }

  return (
    <AuthShell>
      <div className="form-heading">
        <p className="eyebrow eyebrow--accent">{t("register.eyebrow")}</p>
        <h2>{t("register.title")}</h2>
        <p>{t("register.subtitle")}</p>
      </div>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label htmlFor="register-email">{t("common.email")}</label>
        <input
          id="register-email"
          name="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          required
        />

        <div className="label-row">
          <label htmlFor="register-password">{t("common.password")}</label>
          <span>{t("register.passwordHint")}</span>
        </div>
        <input
          id="register-password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          maxLength={128}
          required
        />

        <label htmlFor="register-confirmation">
          {t("register.confirmPassword")}
        </label>
        <input
          id="register-confirmation"
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
          <span>{busy ? t("register.submitting") : t("register.submit")}</span>
          <span aria-hidden="true">←</span>
        </button>
      </form>

      <p className="form-alternative">
        {t("register.hasAccount")} <Link to="/login">{t("register.loginLink")}</Link>
      </p>
    </AuthShell>
  );
}
