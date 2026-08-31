import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../../shared/apiClient";
import {
  cancelAdminAiAgentAuthSession,
  getAdminAiAgentAuthSession,
  startAdminAiAgentAuth,
  submitAdminAiAgentAuthInput,
} from "./api";
import type {
  AdminAiAgentAuthSession,
  AdminAiAgentAuthStatus,
  AdminAiAgentName,
} from "./types";

const POLL_INTERVAL_MS = 2_000;
const terminalStatuses: ReadonlySet<AdminAiAgentAuthStatus> = new Set([
  "authenticated",
  "failed",
  "canceled",
  "expired",
]);
const authHosts: Record<AdminAiAgentName, string | null> = {
  antigravity: "accounts.google.com",
  codex: "auth.openai.com",
  claude: "claude.com",
};
const inputLabelKeys: Record<string, string> = {
  "authorization code": "authorizationCode",
  "verification code": "verificationCode",
  "device code": "deviceCode",
};
const errorKeys: Record<string, string> = {
  auth_in_progress: "inProgress",
  auth_session_not_found: "notFound",
  auth_session_expired: "expired",
  auth_input_not_expected: "invalidInput",
  auth_input_invalid: "invalidInput",
  auth_unavailable: "unavailable",
  auth_manual_only: "unavailable",
  "authentication failed": "failed",
  "authentication expired": "expired",
  "authentication was canceled": "canceled",
  "authentication is unavailable": "unavailable",
  "authentication input is invalid": "invalidInput",
  "authentication is already in progress": "inProgress",
  "authentication session was not found": "notFound",
};

export type AgentAuthDialogProps = {
  agent: AdminAiAgentName;
  onClose: () => void;
  onAuthenticated: () => void;
};

export function AgentAuthDialog({ agent, onClose, onAuthenticated }: AgentAuthDialogProps) {
  const { t } = useTranslation();
  const [session, setSession] = useState<AdminAiAgentAuthSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const runVersion = useRef(0);
  const requestVersion = useRef(0);
  const latestResponseVersion = useRef(0);
  const timer = useRef<number | null>(null);
  const pollInFlight = useRef(false);
  const activeSession = useRef<AdminAiAgentAuthSession | null>(null);
  const authenticatedNotified = useRef(false);
  const cancelRequested = useRef(false);
  const onAuthenticatedRef = useRef(onAuthenticated);
  onAuthenticatedRef.current = onAuthenticated;

  const clearTimer = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const applySession = useCallback((next: AdminAiAgentAuthSession, runId: number, responseId: number) => {
    if (runVersion.current !== runId || responseId < latestResponseVersion.current) return false;
    latestResponseVersion.current = responseId;
    activeSession.current = next;
    setSession(next);
    if (terminalStatuses.has(next.status)) clearTimer();
    if (next.status === "authenticated" && !authenticatedNotified.current) {
      authenticatedNotified.current = true;
      onAuthenticatedRef.current();
    }
    return true;
  }, [clearTimer]);

  useEffect(() => {
    const runId = runVersion.current + 1;
    runVersion.current = runId;
    requestVersion.current = 0;
    latestResponseVersion.current = 0;
    activeSession.current = null;
    authenticatedNotified.current = false;
    cancelRequested.current = false;
    pollInFlight.current = false;
    clearTimer();
    setSession(null);
    setLoading(true);
    setSubmitting(false);
    setCanceling(false);
    setInputValue("");
    setError(null);
    setCopyFeedback(null);
    let disposed = false;

    const isCurrent = () => !disposed && runVersion.current === runId;
    const schedulePoll = () => {
      const current = activeSession.current;
      if (!isCurrent() || !current || terminalStatuses.has(current.status)) return;
      clearTimer();
      timer.current = window.setTimeout(() => void poll(), POLL_INTERVAL_MS);
    };
    const poll = async () => {
      const current = activeSession.current;
      if (!isCurrent() || !current || pollInFlight.current) return;
      pollInFlight.current = true;
      const responseId = ++requestVersion.current;
      try {
        const next = await getAdminAiAgentAuthSession(current.session_id);
        if (isCurrent()) {
          applySession(next, runId, responseId);
          setLoading(false);
          schedulePoll();
        }
      } catch (requestError: unknown) {
        if (isCurrent()) {
          setError(toSafeAuthError(requestError, t));
          setLoading(false);
          schedulePoll();
        }
      } finally {
        pollInFlight.current = false;
      }
    };
    const start = async () => {
      const responseId = ++requestVersion.current;
      try {
        const next = await startAdminAiAgentAuth(agent);
        if (!isCurrent()) {
          void cancelAdminAiAgentAuthSession(next.session_id).catch(() => undefined);
          return;
        }
        applySession(next, runId, responseId);
        setLoading(false);
        schedulePoll();
      } catch (requestError: unknown) {
        if (isCurrent()) {
          setLoading(false);
          setError(toSafeAuthError(requestError, t));
        }
      }
    };

    queueMicrotask(() => {
      if (isCurrent()) void start();
    });
    return () => {
      disposed = true;
      runVersion.current += 1;
      clearTimer();
      const current = activeSession.current;
      if (current && !terminalStatuses.has(current.status) && !cancelRequested.current) {
        cancelRequested.current = true;
        void cancelAdminAiAgentAuthSession(current.session_id).catch(() => undefined);
      }
    };
  }, [agent, applySession, clearTimer, t]);

  const safeUrl = session ? getSafeVerificationUrl(agent, session.verification_url) : null;
  const status = session?.status ?? null;
  const canSubmitInput = status === "waiting_for_input" && inputValue.trim().length > 0;

  function handleOpenAuthenticationPage() {
    if (!safeUrl) return;
    window.open(safeUrl, "_blank", "noopener,noreferrer");
  }

  function handleCopy(value: string, feedbackKey: string) {
    void copyText(value)
      .then(() => setCopyFeedback(t(`admin.aiSettings.agentAuth.${feedbackKey}`)))
      .catch(() => setError(t("admin.aiSettings.agentAuth.errors.copyFailed")));
  }

  async function handleSubmitInput(event: FormEvent) {
    event.preventDefault();
    const current = activeSession.current;
    if (!current || current.status !== "waiting_for_input" || !canSubmitInput || submitting) return;
    const value = inputValue;
    const runId = runVersion.current;
    const responseId = ++requestVersion.current;
    setInputValue("");
    setSubmitting(true);
    setError(null);
    try {
      const next = await submitAdminAiAgentAuthInput(current.session_id, value);
      applySession(next, runId, responseId);
    } catch (requestError: unknown) {
      if (runVersion.current === runId) setError(toSafeAuthError(requestError, t));
    } finally {
      if (runVersion.current === runId) setSubmitting(false);
    }
  }

  async function handleCancel() {
    const current = activeSession.current;
    if (!current || terminalStatuses.has(current.status)) {
      onClose();
      return;
    }
    const runId = runVersion.current;
    cancelRequested.current = true;
    setCanceling(true);
    try {
      await cancelAdminAiAgentAuthSession(current.session_id);
      if (runVersion.current === runId) onClose();
    } catch (requestError: unknown) {
      if (runVersion.current === runId) {
        cancelRequested.current = false;
        setCanceling(false);
        setError(toSafeAuthError(requestError, t));
      }
    }
  }

  return (
    <div className="admin-agent-auth-backdrop">
      <section
        className="admin-agent-auth-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="agent-auth-dialog-title"
      >
        <header className="admin-agent-auth-dialog__header">
          <div>
            <p className="admin-kicker">{t("admin.aiSettings.agentAuth.eyebrow")}</p>
            <h2 id="agent-auth-dialog-title">
              {t("admin.aiSettings.agentAuth.title", { agent: t(`admin.aiSettings.agents.${agent}`) })}
            </h2>
          </div>
          <button type="button" onClick={() => void handleCancel()} disabled={canceling}>
            {t("admin.aiSettings.agentAuth.close")}
          </button>
        </header>

        {loading && <p role="status">{t("admin.aiSettings.agentAuth.starting")}</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
        {copyFeedback && <p role="status">{copyFeedback}</p>}

        {session && <div className="admin-agent-auth-dialog__content">
          <p className="admin-agent-auth-dialog__status" role="status">
            {status ? t(`admin.aiSettings.agentAuth.status.${status}`) : t("admin.aiSettings.agentAuth.starting")}
          </p>
          {(status === "waiting_for_user" || status === "waiting_for_input") && <>
            {status === "waiting_for_user" && <p>{t("admin.aiSettings.agentAuth.waitingForUser")}</p>}
            {safeUrl && <div className="admin-agent-auth-dialog__url">
              <code dir="ltr">{safeUrl}</code>
              <div>
                <button type="button" onClick={handleOpenAuthenticationPage}>
                  {t("admin.aiSettings.agentAuth.openAuthenticationPage")}
                </button>
                <button type="button" onClick={() => handleCopy(safeUrl, "copiedLink")}>
                  {t("admin.aiSettings.agentAuth.copyLink")}
                </button>
              </div>
            </div>}
            {session.user_code && isSafeDisplayText(session.user_code, 256) && <div className="admin-agent-auth-dialog__code">
              <span>{t("admin.aiSettings.agentAuth.userCode")}</span>
              <code dir="ltr">{session.user_code}</code>
              <button type="button" onClick={() => handleCopy(session.user_code!, "copiedCode")}>
                {t("admin.aiSettings.agentAuth.copyCode")}
              </button>
            </div>}
            {status === "waiting_for_input" && <form onSubmit={handleSubmitInput} className="admin-agent-auth-dialog__input-form">
            <label htmlFor="agent-auth-input">
              {getInputLabel(session.input_label, t)}
              <input
                id="agent-auth-input"
                value={inputValue}
                autoComplete="off"
                onChange={(event) => setInputValue(event.target.value)}
                disabled={submitting || canceling}
              />
            </label>
            <button type="submit" disabled={!canSubmitInput || submitting || canceling}>
              {t("admin.aiSettings.agentAuth.continue")}
            </button>
            </form>}
          </>}
          {status === "authenticated" && <p className="admin-ai-settings-message">{t("admin.aiSettings.agentAuth.success")}</p>}
        </div>}

        <footer className="admin-agent-auth-dialog__footer">
          {session?.expires_at && <small>{t("admin.aiSettings.agentAuth.expiresAt", { value: session.expires_at })}</small>}
          <button type="button" onClick={() => void handleCancel()} disabled={canceling}>
            {t("admin.aiSettings.agentAuth.cancel")}
          </button>
        </footer>
      </section>
    </div>
  );
}

function getSafeVerificationUrl(agent: AdminAiAgentName, value: string | null): string | null {
  const expectedHost = authHosts[agent];
  if (!value || !expectedHost || value.length > 2048 || !isSafeDisplayText(value, 2048)) return null;
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "https:" || parsed.hostname !== expectedHost || parsed.username || parsed.password) return null;
  } catch {
    return null;
  }
  return value;
}

function isSafeDisplayText(value: string, maxLength: number): boolean {
  return value.length <= maxLength && value.trim().length > 0 && value.split("").every((char) => {
    const code = char.codePointAt(0) ?? 0;
    return code >= 0x20 && code !== 0x7f;
  });
}

function getInputLabel(value: string | null, t: (key: string) => string): string {
  const key = value ? inputLabelKeys[value] : undefined;
  return key ? t(`admin.aiSettings.agentAuth.inputLabels.${key}`) : t("admin.aiSettings.agentAuth.input");
}

function toSafeAuthError(error: unknown, t: (key: string) => string): string {
  const key = error instanceof ApiError
    ? errorKeys[error.code ?? ""]
    : undefined;
  return t(`admin.aiSettings.agentAuth.errors.${key ?? "unavailable"}`);
}

async function copyText(value: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("copy failed");
}
