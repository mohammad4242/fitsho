import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { AuthShell } from "../../shared/AuthShell";
import * as api from "./api";
import { authErrorMessage } from "./authError";
import { useAuth } from "./AuthContext";

type LoginMode = "email" | "phone";
type PhoneStep = "request" | "verify";

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { login, loginWithPhone } = useAuth();
  const [mode, setMode] = useState<LoginMode>("email");
  const [phoneStep, setPhoneStep] = useState<PhoneStep>("request");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [countdown, setCountdown] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (countdown <= 0) return;
    const timer = window.setInterval(() => {
      setCountdown((seconds) => Math.max(0, seconds - 1));
    }, 1_000);
    return () => window.clearInterval(timer);
  }, [countdown]);

  function selectMode(nextMode: LoginMode) {
    setMode(nextMode);
    setError(null);
  }

  function handleEmailSubmit(event: FormEvent<HTMLFormElement>) {
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

  function sendOtp(number: string) {
    setBusy(true);
    setError(null);
    void api
      .sendPhoneOtp(number)
      .then((result) => {
        setPhoneNumber(number);
        setPhoneStep("verify");
        setCountdown(result.retry_after_seconds);
      })
      .catch((requestError: unknown) => setError(authErrorMessage(requestError, t)))
      .finally(() => setBusy(false));
  }

  function handlePhoneSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (phoneStep === "request") {
      sendOtp(String(data.get("phone_number") ?? ""));
      return;
    }
    setBusy(true);
    setError(null);
    void loginWithPhone(phoneNumber, String(data.get("code") ?? ""))
      .then(
        () => navigate("/dashboard", { replace: true }),
        () => setError(t("errors.invalidOtp")),
      )
      .finally(() => setBusy(false));
  }

  return (
    <AuthShell>
      <div className="form-heading">
        <p className="eyebrow eyebrow--accent">{t("login.eyebrow")}</p>
        <h2 className="fitsho-display">{t("login.title")}</h2>
        <p>{t(mode === "email" ? "login.subtitle" : "login.phoneSubtitle")}</p>
      </div>

      <div className="auth-tabs" role="tablist" aria-label={t("login.methodLabel")}>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "email"}
          onClick={() => selectMode("email")}
        >
          {t("login.emailTab")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "phone"}
          onClick={() => selectMode("phone")}
        >
          {t("login.phoneTab")}
        </button>
      </div>

      {mode === "email" ? (
        <form key="email-login" className="auth-form" onSubmit={handleEmailSubmit}>
          <label htmlFor="login-email">{t("common.email")}</label>
          <input
            id="login-email"
            name="email"
            type="email"
            autoComplete="email"
            inputMode="email"
            required
          />

          <div className="auth-field-heading">
            <label htmlFor="login-password">{t("common.password")}</label>
            <Link to="/forgot-password">{t("login.forgotPassword")}</Link>
          </div>
          <input
            id="login-password"
            name="password"
            type="password"
            autoComplete="current-password"
            minLength={8}
            maxLength={128}
            required
          />

          <FormError error={error} />

          <button className="primary-button" type="submit" disabled={busy}>
            <span>{busy ? t("login.submitting") : t("login.submit")}</span>
            <span aria-hidden="true">←</span>
          </button>
        </form>
      ) : (
        <form key="phone-login" className="auth-form" onSubmit={handlePhoneSubmit}>
          <label htmlFor="login-phone">{t("common.phoneNumber")}</label>
          <input
            id="login-phone"
            name="phone_number"
            type="tel"
            autoComplete="tel"
            inputMode="tel"
            dir="ltr"
            value={phoneNumber}
            onChange={(event) => setPhoneNumber(event.target.value)}
            disabled={phoneStep === "verify"}
            required
          />

          {phoneStep === "verify" && (
            <>
              <label htmlFor="login-otp">{t("common.otpCode")}</label>
              <input
                id="login-otp"
                name="code"
                type="text"
                autoComplete="one-time-code"
                inputMode="numeric"
                pattern="[0-9]{6}"
                minLength={6}
                maxLength={6}
                dir="ltr"
                required
              />
              <button
                className="auth-resend"
                type="button"
                disabled={busy || countdown > 0}
                onClick={() => sendOtp(phoneNumber)}
              >
                {countdown > 0
                  ? t("login.resendCountdown", {
                      seconds: countdown.toLocaleString("fa-IR"),
                    })
                  : t("login.resend")}
              </button>
            </>
          )}

          <FormError error={error} />

          <button className="primary-button" type="submit" disabled={busy}>
            <span>
              {busy
                ? t("login.phoneSubmitting")
                : t(phoneStep === "request" ? "login.sendOtp" : "login.verifyOtp")}
            </span>
            <span aria-hidden="true">←</span>
          </button>
        </form>
      )}

      <p className="form-alternative">
        {t("login.noAccount")}{" "}
        <Link to="/register">{t("login.registerLink")}</Link>
      </p>
    </AuthShell>
  );
}

function FormError({ error }: { error: string | null }) {
  if (error === null) return null;
  return (
    <p className="form-error" role="alert" aria-live="polite">
      {error}
    </p>
  );
}
