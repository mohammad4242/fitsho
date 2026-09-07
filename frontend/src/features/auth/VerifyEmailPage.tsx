import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";

import { AuthShell } from "../../shared/AuthShell";
import * as api from "./api";

type VerificationState = "checking" | "verified" | "invalid";

export function VerifyEmailPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [state, setState] = useState<VerificationState>("checking");

  useEffect(() => {
    let active = true;
    if (!token) {
      setState("invalid");
      return () => {
        active = false;
      };
    }

    void api
      .verifyEmail(token)
      .then(() => {
        if (active) setState("verified");
      })
      .catch(() => {
        if (active) setState("invalid");
      });

    return () => {
      active = false;
    };
  }, [token]);

  return (
    <AuthShell>
      <div className="form-heading">
        <p className="eyebrow eyebrow--accent">{t("emailVerification.eyebrow")}</p>
        <h2 className="fitsho-display">{t("emailVerification.title")}</h2>
        <p>{t("emailVerification.subtitle")}</p>
      </div>

      {state === "checking" && (
        <p className="form-success" role="status" aria-live="polite">
          {t("emailVerification.checking")}
        </p>
      )}
      {state === "verified" && (
        <p className="form-success" role="status" aria-live="polite">
          {t("emailVerification.success")}
        </p>
      )}
      {state === "invalid" && (
        <p className="form-error" role="alert" aria-live="polite">
          {t("emailVerification.invalidToken")}
        </p>
      )}

      <p className="form-alternative">
        <Link to="/login">{t("emailVerification.backToLogin")}</Link>
      </p>
    </AuthShell>
  );
}
