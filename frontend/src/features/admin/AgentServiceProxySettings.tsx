import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../../shared/apiClient";
import {
  getAdminAiAgentServiceProxy,
  saveAdminAiAgentServiceProxy,
} from "./api";
import type {
  AdminAiAgentServiceProxy,
  AdminAiAgentServiceProxySource,
  AdminAiAgentServiceProxyUpdate,
} from "./types";

export function AgentServiceProxySettings() {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<AdminAiAgentServiceProxy | null>(null);
  const [enabled, setEnabled] = useState(true);
  const [source, setSource] = useState<AdminAiAgentServiceProxySource>("deployment_default");
  const [proxyUrl, setProxyUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void getAdminAiAgentServiceProxy()
      .then((next) => {
        if (!active) return;
        hydrate(next);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        setError(
          requestError instanceof ApiError
            ? requestError.message
            : t("admin.aiSettings.proxy.loadError"),
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [t]);

  function hydrate(next: AdminAiAgentServiceProxy) {
    setSettings(next);
    setEnabled(next.enabled);
    setSource(next.source);
    setProxyUrl("");
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (source === "custom" && enabled && !proxyUrl.trim()) {
      setError(t("admin.aiSettings.proxy.customRequired"));
      setMessage(null);
      return;
    }
    const payload: AdminAiAgentServiceProxyUpdate = {
      enabled,
      source,
      ...(source === "custom" && proxyUrl.trim()
        ? { proxy_url: proxyUrl.trim() }
        : {}),
    };
    setSaving(true);
    setMessage(null);
    setError(null);
    void saveAdminAiAgentServiceProxy(payload)
      .then((next) => {
        hydrate(next);
        if (next.applied) {
          setMessage(t("admin.aiSettings.proxy.saved"));
        } else {
          setError(next.last_apply_error ?? t("admin.aiSettings.proxy.pending"));
        }
      })
      .catch((requestError: unknown) => {
        setError(
          requestError instanceof ApiError
            ? requestError.message
            : t("admin.aiSettings.proxy.saveError"),
        );
      })
      .finally(() => setSaving(false));
  }

  const statusLabel = loading
    ? t("admin.aiSettings.proxy.loading")
    : settings?.agent_service_available === false
      ? t("admin.aiSettings.proxy.unavailable")
      : enabled
        ? t("admin.aiSettings.proxy.enabled")
        : t("admin.aiSettings.proxy.disabled");
  const deploymentProxy = source === "deployment_default"
    ? settings?.masked_proxy_url
    : null;
  const savedCustomProxy = source === "custom" ? settings?.masked_proxy_url : null;

  return (
    <section className="admin-panel admin-agent-proxy" aria-labelledby="agent-proxy-title">
      <header className="admin-agent-proxy__header">
        <div>
          <p className="admin-kicker">{t("admin.aiSettings.proxy.eyebrow")}</p>
          <h2 id="agent-proxy-title">{t("admin.aiSettings.proxy.title")}</h2>
          <p>{t("admin.aiSettings.proxy.subtitle")}</p>
        </div>
        <span
          className={`admin-agent-proxy__status${settings?.agent_service_available === false ? " is-unavailable" : ""}`}
          role="status"
        >
          {statusLabel}
        </span>
      </header>

      <form className="admin-agent-proxy__form" onSubmit={handleSubmit}>
        <label className="admin-agent-proxy__toggle">
          <input
            type="checkbox"
            aria-label={t("admin.aiSettings.proxy.useProxy")}
            checked={enabled}
            disabled={loading || saving}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          <span>
            <strong>{t("admin.aiSettings.proxy.useProxy")}</strong>
            <small>{t("admin.aiSettings.proxy.toggleHint")}</small>
          </span>
        </label>

        <fieldset className="admin-agent-proxy__sources" disabled={loading || saving}>
          <legend>{t("admin.aiSettings.proxy.source")}</legend>
          <label>
            <input
              type="radio"
              name="agent-service-proxy-source"
              value="deployment_default"
              checked={source === "deployment_default"}
              onChange={() => setSource("deployment_default")}
            />
            {t("admin.aiSettings.proxy.deploymentDefault")}
          </label>
          <label>
            <input
              type="radio"
              name="agent-service-proxy-source"
              value="custom"
              checked={source === "custom"}
              onChange={() => setSource("custom")}
            />
            {t("admin.aiSettings.proxy.custom")}
          </label>
        </fieldset>

        {source === "deployment_default" ? (
          <p className="admin-agent-proxy__current" role="status">
            {deploymentProxy
              ? t("admin.aiSettings.proxy.deploymentProxy", { proxy: deploymentProxy })
              : t("admin.aiSettings.proxy.defaultNotConfigured")}
          </p>
        ) : (
          <div className="admin-agent-proxy__custom">
            <label htmlFor="agent-service-custom-proxy">
              {t("admin.aiSettings.proxy.customUrl")}
            </label>
            <input
              id="agent-service-custom-proxy"
              type="text"
              autoComplete="off"
              placeholder={t("admin.aiSettings.proxy.customUrlPlaceholder")}
              value={proxyUrl}
              disabled={loading || saving}
              onChange={(event) => setProxyUrl(event.target.value)}
              aria-describedby="agent-service-proxy-hint"
            />
            <small id="agent-service-proxy-hint">
              {savedCustomProxy
                ? t("admin.aiSettings.proxy.savedProxy", { proxy: savedCustomProxy })
                : t("admin.aiSettings.proxy.customHint")}
            </small>
          </div>
        )}

        <div className="admin-agent-proxy__footer">
          <button
            type="submit"
            disabled={
              loading
              || saving
              || (source === "custom" && enabled && !proxyUrl.trim())
            }
          >
            {saving ? t("admin.aiSettings.proxy.saving") : t("admin.aiSettings.proxy.save")}
          </button>
          {message && <p className="admin-ai-settings-message" role="status">{message}</p>}
          {error && <p className="form-error" role="alert">{error}</p>}
        </div>
      </form>
    </section>
  );
}
