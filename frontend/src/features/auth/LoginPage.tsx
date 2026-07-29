import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { AuthShell } from "../../shared/AuthShell";
import { authErrorMessage } from "./authError";
import { useAuth } from "./AuthContext";

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    void login({
        email: String(data.get("email") ?? ""),
        password: String(data.get("password") ?? ""),
      })
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
        <p className="eyebrow eyebrow--accent">{t("login.eyebrow")}</p>
        <h2 className="fitsho-display">{t("login.title")}</h2>
        <p>{t("login.subtitle")}</p>
      </div>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label htmlFor="login-email">{t("common.email")}</label>
        <input
          id="login-email"
          name="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          required
        />

        <label htmlFor="login-password">{t("common.password")}</label>
        <input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
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
          <span>{busy ? t("login.submitting") : t("login.submit")}</span>
          <span aria-hidden="true">←</span>
        </button>
      </form>

      <p className="form-alternative">
        {t("login.noAccount")}{" "}
        <Link to="/register">{t("login.registerLink")}</Link>
      </p>
    </AuthShell>
  );
}
