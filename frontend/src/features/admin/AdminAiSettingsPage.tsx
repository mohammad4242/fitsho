import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getAdminAiTaskConfigs,
  getAdminAiTaskModels,
  refreshAdminAiModels,
  saveAdminAiTaskConfig,
  testAdminAiProvider,
} from "./api";
import { AiModelSelector } from "./AiModelSelector";
import type {
  AdminAiCatalogModel,
  AdminAiTaskConfig,
  AdminAiTaskConfigUpdate,
  AdminAiTaskType,
} from "./types";
import "./admin.css";

export function AdminAiSettingsPage() {
  const { t } = useTranslation();
  const [configs, setConfigs] = useState<AdminAiTaskConfig[]>([]);
  const [selectedTask, setSelectedTask] = useState<AdminAiTaskType>("body_photo_analysis");
  const [models, setModels] = useState<AdminAiCatalogModel[]>([]);
  const [search, setSearch] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const config = useMemo(
    () => configs.find((item) => item.task_type === selectedTask) ?? null,
    [configs, selectedTask],
  );

  useEffect(() => {
    void getAdminAiTaskConfigs()
      .then((items) => {
        setConfigs(items);
        if (!items.some((item) => item.task_type === selectedTask) && items[0]) {
          setSelectedTask(items[0].task_type);
        }
      })
      .catch(() => setError(t("admin.aiSettings.loadError")));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    void loadModels(selectedTask, search);
  }, [selectedTask]); // eslint-disable-line react-hooks/exhaustive-deps

  function loadModels(task: AdminAiTaskType, query: string) {
    return getAdminAiTaskModels(task, query)
      .then((response) => setModels(response.items))
      .catch(() => setError(t("admin.aiSettings.catalogError")));
  }

  function patchConfig(update: Partial<AdminAiTaskConfig>) {
    setConfigs((current) =>
      current.map((item) =>
        item.task_type === selectedTask ? { ...item, ...update } : item,
      ),
    );
  }

  function handleSave(event: FormEvent) {
    event.preventDefault();
    if (!config) return;
    persistConfig(config, apiKey);
  }

  function handleDisable() {
    if (!config) return;
    persistConfig({ ...config, enabled: false }, "");
  }

  function persistConfig(target: AdminAiTaskConfig, replacementKey: string) {
    setBusy("save");
    setMessage(null);
    setError(null);
    const payload: AdminAiTaskConfigUpdate = {
      provider: target.provider,
      enabled: target.enabled,
      primary_model_id: target.primary_model_id,
      fallback_model_ids: target.fallback_model_ids,
      temperature: target.temperature,
      max_output_tokens: target.max_output_tokens,
      timeout_seconds: target.timeout_seconds,
      minimum_confidence: target.minimum_confidence,
      max_cost_per_request: target.max_cost_per_request,
      routing_restrictions: target.routing_restrictions,
      replace_credential: replacementKey.length > 0,
      ...(replacementKey ? { api_key: replacementKey } : {}),
    };
    void saveAdminAiTaskConfig(selectedTask, payload)
      .then((saved) => {
        setConfigs((current) => current.map((item) => item.task_type === selectedTask ? saved : item));
        setApiKey("");
        setMessage(t("admin.aiSettings.saved"));
      })
      .catch(() => setError(t("admin.aiSettings.saveError")))
      .finally(() => setBusy(null));
  }

  function handleConnectionTest() {
    setBusy("test");
    setMessage(null);
    setError(null);
    void testAdminAiProvider(apiKey || undefined)
      .then((result) => result.ok
        ? setMessage(t("admin.aiSettings.connected"))
        : setError(result.safe_error_message ?? t("admin.aiSettings.connectionFailed")))
      .catch(() => setError(t("admin.aiSettings.connectionFailed")))
      .finally(() => setBusy(null));
  }

  function handleRefresh() {
    setBusy("refresh");
    setError(null);
    void refreshAdminAiModels()
      .then(() => loadModels(selectedTask, search))
      .then(() => setMessage(t("admin.aiSettings.refreshed")))
      .catch(() => setError(t("admin.aiSettings.refreshError")))
      .finally(() => setBusy(null));
  }

  if (!config) return <main className="admin-main"><p>{t("admin.aiSettings.loading")}</p></main>;

  return (
    <main className="admin-main admin-main--ai-settings">
      <header className="admin-page-heading">
        <div><p className="admin-kicker">{t("admin.aiSettings.eyebrow")}</p><h1>{t("admin.aiSettings.title")}</h1></div>
        <a href="/admin/ai-models">{t("admin.aiSettings.legacy")}</a>
      </header>

      <nav className="admin-ai-task-tabs" aria-label={t("admin.aiSettings.taskNav")}>
        {configs.map((item) => (
          <button
            key={item.task_type}
            type="button"
            aria-pressed={item.task_type === selectedTask}
            onClick={() => setSelectedTask(item.task_type)}
          >{t(`admin.aiSettings.tasks.${item.task_type}`)}</button>
        ))}
      </nav>

      <form className="admin-ai-settings-form" onSubmit={handleSave}>
        <section className="admin-panel">
          <h2>{t(`admin.aiSettings.tasks.${selectedTask}`)}</h2>
          <label className="admin-ai-setting-field"><span>{t("admin.aiSettings.provider")}</span><input value="OpenRouter" disabled /></label>
          <label className="admin-ai-setting-field" htmlFor="ai-api-key">
            <span>{t("admin.aiSettings.apiKey")}</span>
            <input
              id="ai-api-key"
              type="password"
              autoComplete="new-password"
              value={apiKey}
              placeholder={config.credential.masked ?? t("admin.aiSettings.apiKeyPlaceholder")}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </label>
          {config.credential.masked && <p className="admin-ai-secret-status">{config.credential.masked}</p>}
          <div className="admin-ai-settings-actions">
            <button type="button" disabled={busy !== null} onClick={handleConnectionTest}>{t("admin.aiSettings.test")}</button>
            <button type="button" disabled={busy !== null || !config.credential.configured} onClick={handleRefresh}>{t("admin.aiSettings.refresh")}</button>
          </div>
        </section>

        <section className="admin-panel">
          <label className="admin-ai-setting-field" htmlFor="model-search"><span>{t("admin.aiSettings.searchModels")}</span><input id="model-search" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <button type="button" onClick={() => void loadModels(selectedTask, search)}>{t("admin.aiSettings.search")}</button>
          <AiModelSelector id="primary-model" label={t("admin.aiSettings.primaryModel")} models={models} value={config.primary_model_id ?? ""} onChange={(value) => patchConfig({ primary_model_id: value || null })} />
          <AiModelSelector id="fallback-models" label={t("admin.aiSettings.fallbackModels")} models={models.filter((model) => model.model_id !== config.primary_model_id)} value="" onChange={() => undefined} multiple values={config.fallback_model_ids} onMultipleChange={(values) => patchConfig({ fallback_model_ids: values })} />
          <div className="admin-ai-capabilities" aria-label={t("admin.aiSettings.selectedCapabilities")}>
            {models.filter((model) => model.model_id === config.primary_model_id).map((model) => <div key={model.model_id}><span>{t("admin.aiSettings.imageInput")}: {model.supports_image_input ? t("admin.aiSettings.yes") : t("admin.aiSettings.no")}</span><span>{t("admin.aiSettings.structuredOutput")}: {model.supports_structured_output ? t("admin.aiSettings.yes") : t("admin.aiSettings.warningUnavailable")}</span><span>{t("admin.aiSettings.context")}: {model.context_length ?? t("admin.aiSettings.unknown")}</span><span>{t("admin.aiSettings.pricing")}: {model.input_price_per_token ?? "—"} / {model.output_price_per_token ?? "—"}</span></div>)}
          </div>
        </section>

        <section className="admin-panel admin-ai-settings-grid">
          <label><input type="checkbox" checked={config.enabled} onChange={(event) => patchConfig({ enabled: event.target.checked })} /> {t("admin.aiSettings.enabled")}</label>
          <NumberField label={t("admin.aiSettings.temperature")} value={config.temperature} step="0.1" onChange={(value) => patchConfig({ temperature: value })} />
          <NumberField label={t("admin.aiSettings.maxTokens")} value={config.max_output_tokens} onChange={(value) => patchConfig({ max_output_tokens: value })} />
          <NumberField label={t("admin.aiSettings.timeout")} value={config.timeout_seconds} onChange={(value) => patchConfig({ timeout_seconds: value })} />
          <NumberField label={t("admin.aiSettings.confidence")} value={config.minimum_confidence} step="0.01" onChange={(value) => patchConfig({ minimum_confidence: value })} />
          <label className="admin-ai-setting-field"><span>{t("admin.aiSettings.cost")}</span><input type="number" min="0" step="0.01" value={config.max_cost_per_request ?? ""} onChange={(event) => patchConfig({ max_cost_per_request: event.target.value || null })} /></label>
          <label className="admin-ai-setting-field"><span>{t("admin.aiSettings.restrictions")}</span><input value={config.routing_restrictions.join(", ")} onChange={(event) => patchConfig({ routing_restrictions: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} /></label>
        </section>

        {message && <p className="admin-ai-settings-message" role="status">{message}</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="admin-ai-settings-actions"><button type="submit" disabled={busy !== null}>{t("admin.aiSettings.save")}</button><button type="button" disabled={busy !== null} onClick={handleDisable}>{t("admin.aiSettings.disable")}</button></div>
      </form>
    </main>
  );
}

function NumberField({ label, value, step = "1", onChange }: { label: string; value: number; step?: string; onChange: (value: number) => void }) {
  return <label className="admin-ai-setting-field"><span>{label}</span><input type="number" step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}
