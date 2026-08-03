import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import appTrainingAccent from "../../assets/landing/app-training-accent.jpg";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
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
  const { i18n, t } = useTranslation();
  const [configs, setConfigs] = useState<AdminAiTaskConfig[]>([]);
  const [selectedTask, setSelectedTask] = useState<AdminAiTaskType>("body_photo_analysis");
  const [models, setModels] = useState<AdminAiCatalogModel[]>([]);
  const [catalogStale, setCatalogStale] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const modelRequestVersion = useRef(0);
  const operationVersion = useRef(0);
  const activeTask = useRef<AdminAiTaskType>(selectedTask);
  const taskEpoch = useRef(0);

  const config = useMemo(
    () => configs.find((item) => item.task_type === selectedTask) ?? null,
    [configs, selectedTask],
  );

  useEffect(() => {
    void getAdminAiTaskConfigs()
      .then((items) => {
        setConfigs(items);
        if (!items.some((item) => item.task_type === selectedTask) && items[0]) {
          activeTask.current = items[0].task_type;
          taskEpoch.current += 1;
          setSelectedTask(items[0].task_type);
        }
      })
      .catch(() => setError(t("admin.aiSettings.loadError")));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    void loadModels(selectedTask, "");
  }, [selectedTask]); // eslint-disable-line react-hooks/exhaustive-deps

  function loadModels(task: AdminAiTaskType, query: string, epoch = taskEpoch.current) {
    if (activeTask.current !== task || taskEpoch.current !== epoch) return Promise.resolve();
    const requestVersion = modelRequestVersion.current + 1;
    modelRequestVersion.current = requestVersion;
    return getAdminAiTaskModels(task, query)
      .then((response) => {
        if (
          requestVersion !== modelRequestVersion.current
          || activeTask.current !== task
          || taskEpoch.current !== epoch
        ) return;
        setModels(response.items);
        setCatalogStale(response.stale);
      })
      .catch(() => {
        if (
          requestVersion === modelRequestVersion.current
          && activeTask.current === task
          && taskEpoch.current === epoch
        ) {
          setError(t("admin.aiSettings.catalogError"));
        }
      });
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
    const taskAtStart = selectedTask;
    const epochAtStart = taskEpoch.current;
    const operation = beginOperation("save");
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
    void saveAdminAiTaskConfig(taskAtStart, payload)
      .then((saved) => {
        if (!isActiveOperation(taskAtStart, epochAtStart, operation)) return;
        setConfigs((current) => current.map((item) => item.task_type === taskAtStart ? saved : item));
        setApiKey("");
        setMessage(t("admin.aiSettings.saved"));
      })
      .catch(() => {
        if (isActiveOperation(taskAtStart, epochAtStart, operation)) {
          setError(t("admin.aiSettings.saveError"));
        }
      })
      .finally(() => finishOperation(taskAtStart, epochAtStart, operation));
  }

  function handleConnectionTest() {
    const taskAtStart = selectedTask;
    const epochAtStart = taskEpoch.current;
    const operation = beginOperation("test");
    setMessage(null);
    setError(null);
    void testAdminAiProvider(apiKey || undefined)
      .then((result) => {
        if (!isActiveOperation(taskAtStart, epochAtStart, operation)) return;
        if (result.ok) setMessage(t("admin.aiSettings.connected"));
        else setError(result.safe_error_message ?? t("admin.aiSettings.connectionFailed"));
      })
      .catch(() => {
        if (isActiveOperation(taskAtStart, epochAtStart, operation)) {
          setError(t("admin.aiSettings.connectionFailed"));
        }
      })
      .finally(() => finishOperation(taskAtStart, epochAtStart, operation));
  }

  function handleRefresh() {
    const taskAtStart = selectedTask;
    const epochAtStart = taskEpoch.current;
    const operation = beginOperation("refresh");
    setError(null);
    void refreshAdminAiModels()
      .then(() => {
        if (!isActiveOperation(taskAtStart, epochAtStart, operation)) return;
        return loadModels(taskAtStart, "", epochAtStart);
      })
      .then(() => {
        if (isActiveOperation(taskAtStart, epochAtStart, operation)) {
          setMessage(t("admin.aiSettings.refreshed"));
        }
      })
      .catch(() => {
        if (isActiveOperation(taskAtStart, epochAtStart, operation)) {
          setError(t("admin.aiSettings.refreshError"));
        }
      })
      .finally(() => finishOperation(taskAtStart, epochAtStart, operation));
  }

  function selectTask(task: AdminAiTaskType) {
    if (task !== activeTask.current) taskEpoch.current += 1;
    activeTask.current = task;
    setBusy(null);
    setMessage(null);
    setError(null);
    setSelectedTask(task);
  }

  function beginOperation(kind: string) {
    const operation = operationVersion.current + 1;
    operationVersion.current = operation;
    setBusy(kind);
    return operation;
  }

  function isActiveOperation(task: AdminAiTaskType, epoch: number, operation: number) {
    return (
      activeTask.current === task
      && taskEpoch.current === epoch
      && operationVersion.current === operation
    );
  }

  function finishOperation(task: AdminAiTaskType, epoch: number, operation: number) {
    if (isActiveOperation(task, epoch, operation)) setBusy(null);
  }

  const backLabel = i18n.resolvedLanguage === "en" ? "Return" : "بازگشت";

  if (!config) return <main className="admin-main"><p>{t("admin.aiSettings.loading")}</p></main>;

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={appTrainingAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--ai-settings">
      <header className="admin-page-heading">
        <div><p className="admin-kicker">{t("admin.aiSettings.eyebrow")}</p><h1>{t("admin.aiSettings.title")}</h1></div>
        <Link className="admin-ai-back" to="/admin/exercises" aria-label={backLabel}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14.5 5-7 7 7 7M8 12h9" /></svg>
          <span>{backLabel}</span>
        </Link>
      </header>

      <nav className="admin-ai-task-tabs" aria-label={t("admin.aiSettings.taskNav")}>
        {configs.map((item) => (
          <button
            key={item.task_type}
            type="button"
            aria-pressed={item.task_type === selectedTask}
            onClick={() => selectTask(item.task_type)}
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
          <dl className="admin-ai-observability">
            <div><dt>{t("admin.aiSettings.lastConnection")}</dt><dd>{config.last_successful_connection_test_at ?? "—"}</dd></div>
            <div><dt>{t("admin.aiSettings.lastCatalogRefresh")}</dt><dd>{config.last_model_catalog_refresh_at ?? "—"}</dd></div>
            <div><dt>{t("admin.aiSettings.lastError")}</dt><dd>{config.last_error_code ?? "—"}{config.last_error_message ? ` — ${config.last_error_message}` : ""}</dd></div>
          </dl>
          <div className="admin-ai-settings-actions">
            <button type="button" disabled={busy !== null} onClick={handleConnectionTest}>{t("admin.aiSettings.test")}</button>
            <button type="button" disabled={busy !== null || !config.credential.configured} onClick={handleRefresh}>{t("admin.aiSettings.refresh")}</button>
          </div>
        </section>

        <section className="admin-panel">
          {catalogStale && <p className="form-error" role="status">{t("admin.aiSettings.catalogStale")}</p>}
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
    </div>
  );
}

function NumberField({ label, value, step = "1", onChange }: { label: string; value: number; step?: string; onChange: (value: number) => void }) {
  return <label className="admin-ai-setting-field"><span>{label}</span><input type="number" step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}
