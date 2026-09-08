import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../shared/apiClient";
import { useAuth } from "../auth/AuthContext";
import { authPath } from "../auth/returnTo";
import {
  cancelAccountDeletion,
  getAccountDeletionStatus,
  requestAccountDeletion,
  type AccountDeletionStatusResponse,
} from "./api";
import { PublicPageFrame } from "./PublicPageFrame";
import "./publicAccount.css";

const DELETE_CONFIRMATION = "DELETE";

function isApiError(error: unknown, status: number, message: string): boolean {
  return error instanceof ApiError && error.status === status && error.message === message;
}

function formatDate(value: string | null, english: boolean): string | null {
  if (value === null) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(english ? "en-US" : "fa-IR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function AccountDeletionPage() {
  const { user, loading: authLoading, logout } = useAuth();
  const navigate = useNavigate();
  const [english, setEnglish] = useState(
    () => typeof document !== "undefined" && document.documentElement.lang === "en",
  );
  const [deletion, setDeletion] = useState<AccountDeletionStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [requiresReauthentication, setRequiresReauthentication] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [password, setPassword] = useState("");

  const l = useCallback((fa: string, en: string) => english ? en : fa, [english]);

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setEnglish(document.documentElement.lang === "en");
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (authLoading || user === null) return;
    let active = true;
    setLoading(true);
    setError(null);
    setUnavailable(false);
    void getAccountDeletionStatus()
      .then((response) => {
        if (active) setDeletion(response);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof ApiError && requestError.status === 503) {
          setUnavailable(true);
        } else {
          setError(l("وضعیت حذف حساب دریافت نشد. دوباره تلاش کن.", "Could not load deletion status. Try again."));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [authLoading, l, user]);

  if (authLoading) {
    return (
      <PublicPageFrame>
        <PublicState message={l("در حال بررسی حساب…", "Checking your account…")} />
      </PublicPageFrame>
    );
  }

  return (
    <PublicPageFrame>
      <section className="public-account-card" aria-labelledby="account-deletion-title">
        <p className="public-account-card__eyebrow">حساب / Account</p>
        <h1 id="account-deletion-title" className="fitsho-display">{l("حذف حساب فیتشو", "Delete your Fitsho account")}</h1>
        <p className="public-account-card__lead">
          {l(
            "درخواست حذف حساب را از همین صفحه ثبت کن. این مسیر برای اعضای فیتشو، خارج از اپلیکیشن هم در دسترس است.",
            "Submit your account deletion request here. This flow is available outside the app too.",
          )}
        </p>

        {user === null ? (
          <SignedOutState english={english} />
        ) : unavailable ? (
          <PublicState message={l("حذف حساب هنوز برای این محیط فعال نشده است.", "Account deletion is not enabled for this environment yet.")} />
        ) : loading || deletion === null ? (
          <PublicState message={l("در حال دریافت وضعیت حذف…", "Loading deletion status…")} />
        ) : deletion.status === "pending" ? (
          <PendingDeletionState
            deletion={deletion}
            english={english}
            busy={busy}
            onCancel={() => {
              setBusy(true);
              setError(null);
              void cancelAccountDeletion()
                .then(setDeletion)
                .catch(() => setError(l("لغو درخواست انجام نشد. دوباره تلاش کن.", "Could not cancel the request. Try again.")))
                .finally(() => setBusy(false));
            }}
          />
        ) : deletion.status === "completed" ? (
          <PublicState message={l("این حساب قبلاً حذف شده است.", "This account has already been deleted.")} />
        ) : (
          <>
            {deletion.status === "cancelled" && (
              <div className="public-account-state">
                <h2>{l("درخواست حذف لغو شد", "Deletion request cancelled")}</h2>
                <p>{l("اگر هنوز می‌خواهی حسابت حذف شود، می‌توانی درخواست تازه‌ای ثبت کنی.", "You can submit a new request if you still want to delete your account.")}</p>
              </div>
            )}
            <DeletionRequestForm
              confirmation={confirmation}
              password={password}
              busy={busy}
              requiresReauthentication={requiresReauthentication}
              english={english}
              onConfirmationChange={setConfirmation}
              onPasswordChange={setPassword}
              onReauthenticate={() => {
                setBusy(true);
                void logout()
                  .then(() => navigate(authPath("/login", "/delete-account"), { replace: true }))
                  .catch(() => {
                    setBusy(false);
                    setError(l("ورود دوباره شروع نشد. دوباره تلاش کن.", "Could not start reauthentication. Try again."));
                  });
              }}
              onSubmit={(event) => {
                event.preventDefault();
                if (confirmation.trim() !== DELETE_CONFIRMATION) {
                  setError(l("عبارت DELETE را دقیق وارد کن.", "Enter DELETE exactly to confirm."));
                  return;
                }
                setBusy(true);
                setError(null);
                setRequiresReauthentication(false);
                void requestAccountDeletion(password.trim() === "" ? undefined : password)
                  .then(setDeletion)
                  .catch((requestError: unknown) => {
                    if (isApiError(requestError, 403, "RECENT_AUTHENTICATION_REQUIRED")) {
                      setRequiresReauthentication(true);
                      setError(l("برای امنیت، ابتدا دوباره وارد حساب شو.", "For security, sign in again before deleting your account."));
                    } else if (isApiError(requestError, 403, "INVALID_REAUTHENTICATION")) {
                      setError(l("رمز عبور درست نیست.", "The password is not correct."));
                    } else {
                      setError(l("ثبت درخواست حذف انجام نشد. دوباره تلاش کن.", "Could not submit the deletion request. Try again."));
                    }
                  })
                  .finally(() => setBusy(false));
              }}
            />
          </>
        )}

        {error !== null && (
          <p className="public-account-card__error" role="alert">{error}</p>
        )}
      </section>
    </PublicPageFrame>
  );
}

function SignedOutState({ english }: { english: boolean }) {
  return (
    <div className="public-account-state">
      <p>{english ? "Sign in to manage or delete your account." : "برای مدیریت یا حذف حساب، ابتدا وارد شو."}</p>
      <Link className="public-account-button" to={authPath("/login", "/delete-account")}>
        {english ? "Sign in to continue" : "ورود برای ادامه"}
      </Link>
    </div>
  );
}

function PublicState({ message }: { message: string }) {
  return <div className="public-account-state"><p>{message}</p></div>;
}

function PendingDeletionState({
  deletion,
  english,
  busy,
  onCancel,
}: {
  deletion: AccountDeletionStatusResponse;
  english: boolean;
  busy: boolean;
  onCancel: () => void;
}) {
  const date = formatDate(deletion.grace_period_ends_at, english);
  return (
    <div className="public-account-state public-account-state--warning">
      <h2>{english ? "Account deletion is scheduled" : "حساب برای حذف زمان‌بندی شد"}</h2>
      <p>
        {english ? "You can cancel this request before:" : "تا پیش از این زمان می‌توانی درخواست را لغو کنی:"}{" "}
        {date === null ? "—" : <time dateTime={deletion.grace_period_ends_at ?? undefined}>{date}</time>}
      </p>
      <button className="public-account-button public-account-button--secondary" type="button" disabled={busy} onClick={onCancel}>
        {english ? "Cancel deletion request" : "لغو درخواست حذف"}
      </button>
    </div>
  );
}

function DeletionRequestForm({
  confirmation,
  password,
  busy,
  requiresReauthentication,
  english,
  onConfirmationChange,
  onPasswordChange,
  onReauthenticate,
  onSubmit,
}: {
  confirmation: string;
  password: string;
  busy: boolean;
  requiresReauthentication: boolean;
  english: boolean;
  onConfirmationChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onReauthenticate: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <form className="public-account-form" onSubmit={onSubmit}>
      <p>{english ? "Deletion starts after the grace period shown after submission." : "حذف پس از پایان مهلت بازگشت که بعد از ثبت نمایش داده می‌شود، اجرا خواهد شد."}</p>
      <label htmlFor="account-deletion-confirmation">{english ? "Type DELETE to confirm" : "تأیید حذف"}</label>
      <input
        id="account-deletion-confirmation"
        name="confirmation"
        type="text"
        autoComplete="off"
        dir="ltr"
        value={confirmation}
        onChange={(event) => onConfirmationChange(event.target.value)}
        required
      />
      <label htmlFor="account-deletion-password">{english ? "Password, if your account has one" : "رمز عبور، اگر حساب رمزدار است"}</label>
      <input
        id="account-deletion-password"
        name="password"
        type="password"
        autoComplete="current-password"
        minLength={8}
        maxLength={128}
        value={password}
        onChange={(event) => onPasswordChange(event.target.value)}
      />
      <button className="public-account-button" type="submit" disabled={busy}>
        {english ? "Submit deletion request" : "ثبت درخواست حذف"}
      </button>
      {requiresReauthentication && (
        <button className="public-account-text-button" type="button" disabled={busy} onClick={onReauthenticate}>
          {english ? "Sign in again to continue" : "ورود دوباره برای ادامه"}
        </button>
      )}
    </form>
  );
}
