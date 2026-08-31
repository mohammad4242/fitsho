import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import appTrainingAccent from "../../assets/landing/app-training-accent.jpg";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import { ApiError } from "../../shared/apiClient";
import {
  getAdminAiTaskConfigs,
  getAdminAiTaskModels,
  getAdminAiAgentServiceCapabilities,
  refreshAdminAiModels,
  saveAdminAiTaskConfig,
  testAdminAiAgentService,
  testAdminAiProvider,
} from "./api";
import { AiModelSelector } from "./AiModelSelector";
import { AgentServicePanel } from "./AgentServicePanel";
import type {
  AdminAiCatalogModel,
  AdminAiAgentRunnerCapability,
  AdminAiTaskConfig,
  AdminAiTaskConfigUpdate,
  AdminAiTaskType,
} from "./types";
import "./admin.css";

type AiSettingsOperation = "save" | "test" | "refresh";

const agentTasks: AdminAiTaskType[] = [
  "workout_plan_generation",
  "body_photo_analysis",
  "food_photo_estimation",
];

export function AdminAiSettingsPage() {
  const { i18n, t } = useTranslation();
  const [configs, setConfigs] = useState<AdminAiTaskConfig[]>([]);
  const [selectedTask, setSelectedTask] = useState<AdminAiTaskType>("body_photo_analysis");
  const [models, setModels] = useState<AdminAiCatalogModel[]>([]);
  const [catalogStale, setCatalogStale] = useState(false);
  const [agentCapabilities, setAgentCapabilities] = useState<AdminAiAgentRunnerCapability[]>([]);
  const [agentCapabilitiesLoading, setAgentCapabilitiesLoading] = useState(false);
  const [agentCapabilitiesError, setAgentCapabilitiesError] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [configsLoading, setConfigsLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedbackOperation, setFeedbackOperation] = useState<AiSettingsOperation | null>(null);
  const modelRequestVersion = useRef(0);
  const operationVersion = useRef(0);
  const agentRequestVersion = useRef(0);
  const activeTask = useRef<AdminAiTaskType>(selectedTask);
  const taskEpoch = useRef(0);

  const config = useMemo(
    () => configs.find((item) => item.task_type === selectedTask) ?? null,
    [configs, selectedTask],
  );

  const agentMode = config?.execution_backend === "agent_service";
  const agentTaskSupported = agentTasks.includes(selectedTask);
  const selectedAgent = config?.agent_name
    ?? agentCapabilities.find((runner) => runner.installed)?.agent
    ?? "antigravity";
  const selectedRunner = agentCapabilities.find((runner) => runner.agent === selectedAgent) ?? null;
  const agentModels = useMemo(
    () => (selectedRunner ? toAgentCatalogModels(selectedRunner, selectedTask) : []),
    [selectedRunner, selectedTask],
  );
  const selectableModels = agentMode ? agentModels : models;

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
      .catch(() => setError(t("admin.aiSettings.loadError")))
      .finally(() => setConfigsLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!config) return;
    if (config?.execution_backend === "agent_service") {
      setModels([]);
      setCatalogStale(false);
      return;
    }
    void loadModels(selectedTask, "");
  }, [selectedTask, config?.execution_backend]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!agentMode || !agentTaskSupported) {
      setAgentCapabilitiesLoading(false);
      return;
    }
    const taskAtStart = selectedTask;
    const epochAtStart = taskEpoch.current;
    const requestVersion = agentRequestVersion.current + 1;
    agentRequestVersion.current = requestVersion;
    setAgentCapabilitiesLoading(true);
    setAgentCapabilitiesError(false);
    void getAdminAiAgentServiceCapabilities()
      .then((response) => {
        if (
          requestVersion !== agentRequestVersion.current
          || activeTask.current !== taskAtStart
          || taskEpoch.current !== epochAtStart
        ) return;
        setAgentCapabilities(response.runners);
      })
      .catch(() => {
        if (
          requestVersion === agentRequestVersion.current
          && activeTask.current === taskAtStart
          && taskEpoch.current === epochAtStart
        ) setAgentCapabilitiesError(true);
      })
      .finally(() => {
        if (
          requestVersion === agentRequestVersion.current
          && activeTask.current === taskAtStart
          && taskEpoch.current === epochAtStart
        ) setAgentCapabilitiesLoading(false);
      });
  }, [agentMode, agentTaskSupported, selectedTask]);

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
      execution_backend: target.execution_backend,
      agent_name: target.agent_name,
      agent_model_id: target.agent_model_id,
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
    const testRequest = agentMode && config !== null && targetAgentIsReady(config)
      ? testAdminAiAgentService(config.agent_name!, config.agent_model_id!)
      : agentMode
        ? Promise.resolve({
            ok: false,
            agent: selectedAgent,
            model_id: config?.agent_model_id ?? "",
            checked_at: new Date().toISOString(),
            duration_seconds: null,
            error_code: "invalid_request",
            safe_error_message: t("admin.aiSettings.agentTestRequiresSelection"),
          })
        : testAdminAiProvider(apiKey || undefined);
    void testRequest
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
    if (agentMode) return;
    const taskAtStart = selectedTask;
    const epochAtStart = taskEpoch.current;
    const operation = beginOperation("refresh");
    setMessage(null);
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
      .catch((requestError: unknown) => {
        if (isActiveOperation(taskAtStart, epochAtStart, operation)) {
          setError(
            requestError instanceof ApiError
              ? requestError.message
              : t("admin.aiSettings.refreshError"),
          );
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

  function beginOperation(kind: AiSettingsOperation) {
    const operation = operationVersion.current + 1;
    operationVersion.current = operation;
    setBusy(kind);
    setFeedbackOperation(kind);
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

  if (configsLoading) return <main className="admin-main"><p>{t("admin.aiSettings.loading")}</p></main>;
  if (!config) {
    return <main className="admin-main"><p className="form-error" role="alert">
      {error ?? t("admin.aiSettings.loadError")}
    </p></main>;
  }

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={appTrainingAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--ai-settings">
      <header className="admin-page-heading">
        <div><p className="admin-kicker">{t("admin.aiSettings.eyebrow")}</p><h1>{t("admin.aiSettings.title")}</h1></div>
        <Link className="admin-ai-back" to="/more" aria-label={backLabel}>
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
          <fieldset className="admin-ai-backend-switch">
            <legend>{t("admin.aiSettings.executionBackend")}</legend>
            <label>
              <input
                type="radio"
                name="execution-backend"
                value="api"
                checked={config.execution_backend === "api"}
                onChange={() => patchConfig({ execution_backend: "api" })}
              />
              {t("admin.aiSettings.apiBackend")}
            </label>
            <label className={!agentTaskSupported ? "is-disabled" : undefined}>
              <input
                type="radio"
                name="execution-backend"
                value="agent_service"
                checked={config.execution_backend === "agent_service"}
                disabled={!agentTaskSupported}
                onChange={() => patchConfig({ execution_backend: "agent_service" })}
              />
              {t("admin.aiSettings.agentServiceBackend")}
            </label>
            {!agentTaskSupported && <p className="admin-ai-inline-note">{t("admin.aiSettings.agentUnsupported")}</p>}
          </fieldset>
          {!agentMode && <>
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
          </>}
          {agentMode && <AgentServicePanel
            runners={agentCapabilities}
            loading={agentCapabilitiesLoading}
            unavailable={agentCapabilitiesError}
            selectedAgent={selectedAgent}
            selectedModelId={config.agent_model_id}
            onSelectAgent={(agent) => patchConfig({ agent_name: agent, agent_model_id: null })}
            onAuthenticate={() => undefined}
            onTest={handleConnectionTest}
            testDisabled={busy !== null || !targetAgentIsReady(config)}
          />}
          <dl className="admin-ai-observability">
            <div><dt>{t("admin.aiSettings.lastConnection")}</dt><dd>{config.last_successful_connection_test_at ?? "—"}</dd></div>
            <div><dt>{t("admin.aiSettings.lastCatalogRefresh")}</dt><dd>{config.last_model_catalog_refresh_at ?? "—"}</dd></div>
            <div><dt>{t("admin.aiSettings.lastError")}</dt><dd>{config.last_error_code ?? "—"}{config.last_error_message ? ` — ${config.last_error_message}` : ""}</dd></div>
          </dl>
          {!agentMode && <div className="admin-ai-settings-actions">
            <button type="button" disabled={busy !== null} onClick={handleConnectionTest}>{t("admin.aiSettings.test")}</button>
            <button type="button" disabled={busy !== null || !config.credential.configured} onClick={handleRefresh}>{t("admin.aiSettings.refresh")}</button>
          </div>}
          {feedbackOperation !== "save" && message && <p className="admin-ai-provider-feedback admin-ai-settings-message" role="status">{message}</p>}
          {feedbackOperation !== "save" && error && <p className="admin-ai-provider-feedback form-error" role="alert">{error}</p>}
        </section>

        <section className="admin-panel">
          {catalogStale && !agentMode && <p className="form-error" role="status">{t("admin.aiSettings.catalogStale")}</p>}
          <AiModelSelector
            id="primary-model"
            label={agentMode ? t("admin.aiSettings.agentModel") : t("admin.aiSettings.primaryModel")}
            models={selectableModels}
            value={agentMode ? (config.agent_model_id ?? "") : (config.primary_model_id ?? "")}
            onChange={(value) => patchConfig(agentMode ? { agent_name: config.agent_name ?? selectedAgent, agent_model_id: value || null } : { primary_model_id: value || null })}
          />
          {!agentMode && <AiModelSelector id="fallback-models" label={t("admin.aiSettings.fallbackModels")} models={models.filter((model) => model.model_id !== config.primary_model_id)} value="" onChange={() => undefined} multiple values={config.fallback_model_ids} onMultipleChange={(values) => patchConfig({ fallback_model_ids: values })} />}
          <div className="admin-ai-capabilities" aria-label={t("admin.aiSettings.selectedCapabilities")}>
            {selectableModels.filter((model) => model.model_id === (agentMode ? config.agent_model_id : config.primary_model_id)).map((model) => <div key={model.model_id}><span>{t("admin.aiSettings.imageInput")}: {model.supports_image_input ? t("admin.aiSettings.yes") : t("admin.aiSettings.no")}</span><span>{t("admin.aiSettings.structuredOutput")}: {model.supports_structured_output ? t("admin.aiSettings.yes") : t("admin.aiSettings.warningUnavailable")}</span><span>{t("admin.aiSettings.context")}: {model.context_length ?? t("admin.aiSettings.unknown")}</span><span>{t("admin.aiSettings.pricing")}: {model.input_price_per_token ?? "—"} / {model.output_price_per_token ?? "—"}</span></div>)}
          </div>
        </section>

        <section className="admin-panel admin-ai-settings-grid">
          <div className="admin-ai-enabled-field">
            <label htmlFor="ai-task-enabled"><input id="ai-task-enabled" type="checkbox" checked={config.enabled} onChange={(event) => patchConfig({ enabled: event.target.checked })} /> {t("admin.aiSettings.enabled")}</label>
            <SettingHelp label={t("admin.aiSettings.enabled")} guide={t("admin.aiSettings.guides.enabled")} />
          </div>
          <NumberField id="ai-temperature" label={t("admin.aiSettings.temperature")} guide={t("admin.aiSettings.guides.temperature")} value={config.temperature} step="0.1" disabled={agentMode} onChange={(value) => patchConfig({ temperature: value })} />
          <NumberField id="ai-max-tokens" label={t("admin.aiSettings.maxTokens")} guide={t("admin.aiSettings.guides.maxTokens")} value={config.max_output_tokens} disabled={agentMode} onChange={(value) => patchConfig({ max_output_tokens: value })} />
          {agentMode && <p className="admin-ai-inline-note" role="note">{t("admin.aiSettings.agentTuningUnsupported")}</p>}
          <NumberField id="ai-timeout" label={t("admin.aiSettings.timeout")} guide={t("admin.aiSettings.guides.timeout")} value={config.timeout_seconds} onChange={(value) => patchConfig({ timeout_seconds: value })} />
          <NumberField id="ai-confidence" label={t("admin.aiSettings.confidence")} guide={t("admin.aiSettings.guides.confidence")} value={config.minimum_confidence} step="0.01" onChange={(value) => patchConfig({ minimum_confidence: value })} />
          {!agentMode && <>
            <div className="admin-ai-setting-field"><SettingLabel htmlFor="ai-cost" label={t("admin.aiSettings.cost")} guide={t("admin.aiSettings.guides.cost")} /><input id="ai-cost" type="number" min="0" step="0.01" value={config.max_cost_per_request ?? ""} onChange={(event) => patchConfig({ max_cost_per_request: event.target.value || null })} /></div>
            <div className="admin-ai-setting-field"><SettingLabel htmlFor="ai-restrictions" label={t("admin.aiSettings.restrictions")} guide={t("admin.aiSettings.guides.restrictions")} /><input id="ai-restrictions" value={config.routing_restrictions.join(", ")} onChange={(event) => patchConfig({ routing_restrictions: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} /></div>
          </>}
        </section>

        {(feedbackOperation === "save" || feedbackOperation === null) && message && <p className="admin-ai-settings-message" role="status">{message}</p>}
        {(feedbackOperation === "save" || feedbackOperation === null) && error && <p className="form-error" role="alert">{error}</p>}
        <div className="admin-ai-settings-actions"><button type="submit" disabled={busy !== null}>{t("admin.aiSettings.save")}</button><button type="button" disabled={busy !== null} onClick={handleDisable}>{t("admin.aiSettings.disable")}</button></div>
      </form>
      </main>
    </div>
  );
}

function NumberField({ id, label, guide, value, step = "1", disabled = false, onChange }: { id: string; label: string; guide: string; value: number; step?: string; disabled?: boolean; onChange: (value: number) => void }) {
  return <div className="admin-ai-setting-field"><SettingLabel htmlFor={id} label={label} guide={guide} /><input id={id} type="number" step={step} value={value} disabled={disabled} onChange={(event) => onChange(Number(event.target.value))} /></div>;
}

function SettingLabel({ htmlFor, label, guide }: { htmlFor: string; label: string; guide: string }) {
  return <span className="admin-ai-setting-label"><label htmlFor={htmlFor}>{label}</label><SettingHelp label={label} guide={guide} /></span>;
}

function SettingHelp({ label, guide }: { label: string; guide: string }) {
  return (
    <details className="admin-ai-setting-help">
      <summary aria-label={`About ${label}`}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 10v6m0-9h.01" /></svg>
      </summary>
      <div role="note"><strong>{label}</strong><p>{guide}</p></div>
    </details>
  );
}

function targetAgentIsReady(config: AdminAiTaskConfig | null): config is AdminAiTaskConfig {
  return config?.execution_backend === "agent_service"
    && config.agent_name !== null
    && config.agent_model_id !== null
    && config.agent_model_id.trim().length > 0;
}

function toAgentCatalogModels(
  runner: AdminAiAgentRunnerCapability,
  task: AdminAiTaskType,
): AdminAiCatalogModel[] {
  return runner.models
    .filter((model) => {
      if (!runner.installed) return false;
      const needsImage = task === "body_photo_analysis" || task === "food_photo_estimation";
      return model.supports_structured_output
        && (needsImage ? model.supports_image_input : model.supports_text_input);
    })
    .map((model) => ({
      provider: `agent_service:${runner.agent}`,
      model_id: model.model_id,
      display_name: model.model_id,
      provider_family: runner.agent,
      supports_text_input: model.supports_text_input,
      supports_image_input: model.supports_image_input,
      supports_structured_output: model.supports_structured_output,
      context_length: null,
      input_price_per_token: null,
      output_price_per_token: null,
      available: true,
    }));
}
