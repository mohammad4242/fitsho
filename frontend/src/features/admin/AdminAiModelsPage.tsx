import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import appTrainingAccent from "../../assets/landing/app-training-accent.jpg";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import {
  createAdminAiModel,
  getAdminAiGenerationFailures,
  getAdminAiModels,
  getAdminAiModelTestRuns,
  syncAdminAiModels,
  testAdminAiModel,
  updateAdminAiModel,
  updateAdminAiRouting,
} from "./api";
import type {
  AdminAiModel,
  AdminAiModelCreate,
  AdminAiGenerationFailure,
  AdminAiModelTestRun,
  AdminAiModelsResponse,
  BillingClass,
  RoutingMode,
  ZenApiKind,
} from "./types";
import "./admin.css";

type Filter = "free" | "paid" | "custom";
type Feedback = { text: string; tone: "success" | "error" };
type AiEvent = {
  id: string;
  modelId: string;
  createdAt: string;
  tone: "success" | "error";
  errorCode: string | null;
  message: string | null;
  diagnostics?: AdminAiGenerationFailure["validation_diagnostics"];
};

const blankCustomModel: AdminAiModelCreate = {
  model_id: "",
  display_name: "",
  api_kind: "chat_completions",
  billing_class: "free",
  is_enabled: true,
  priority: 1000,
};

export function AdminAiModelsPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState<AdminAiModelsResponse | null>(null);
  const [failures, setFailures] = useState<AdminAiGenerationFailure[]>([]);
  const [modelTestRuns, setModelTestRuns] = useState<AdminAiModelTestRun[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [filter, setFilter] = useState<Filter>("free");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [customModel, setCustomModel] = useState<AdminAiModelCreate>(blankCustomModel);
  const [busy, setBusy] = useState<string | null>(null);

  function load() {
    setState("loading");
    setFeedback(null);
    void Promise.all([getAdminAiModels(), getAdminAiGenerationFailures(), getAdminAiModelTestRuns()])
      .then(([models, generationFailures, testRuns]) => {
        setPage(models);
        setFailures(generationFailures);
        setModelTestRuns(testRuns);
        setState("ready");
      })
      .catch(() => setState("error"));
  }

  useEffect(() => { load(); }, []);

  const selectableModels = useMemo(
    () => page?.models.filter((model) => model.is_enabled && !model.classification_required) ?? [],
    [page],
  );
  const automaticModels = useMemo(
    () => page?.models
      .filter((model) => model.is_enabled && !model.classification_required && model.billing_class === "free")
      .sort((left, right) => left.priority - right.priority || left.model_id.localeCompare(right.model_id)) ?? [],
    [page],
  );
  const displayedModels = useMemo(() => page?.models.filter((model) => {
    if (filter === "custom") return model.is_custom;
    return !model.is_custom && model.billing_class === filter;
  }) ?? [], [filter, page]);
  const events = useMemo<AiEvent[]>(() => [
    ...modelTestRuns.map((testRun) => ({
      id: `test-${testRun.id}`,
      modelId: testRun.model_id,
      createdAt: testRun.created_at,
      tone: testRun.outcome === "succeeded" ? "success" as const : "error" as const,
      errorCode: testRun.error_code,
      message: testRun.outcome === "succeeded"
        ? t("admin.aiModels.testSuccess")
        : testRun.safe_error_message,
    })),
    ...failures.map((failure) => ({
      id: `generation-${failure.id}`,
      modelId: failure.model_id,
      createdAt: failure.created_at,
      tone: "error" as const,
      errorCode: failure.error_code,
      message: failure.safe_error_message,
      diagnostics: failure.validation_diagnostics,
    })),
  ].sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()), [failures, modelTestRuns, t]);

  function updatePageModel(model: AdminAiModel) {
    setPage((current) => current === null ? current : {
      ...current,
      models: current.models.map((item) => item.id === model.id ? model : item),
    });
  }

  function setRouting(mode: RoutingMode, manualModelId?: string) {
    setBusy("routing");
    setFeedback(null);
    void updateAdminAiRouting(
      mode === "manual" ? { mode, manual_model_id: manualModelId } : { mode },
    )
      .then((routing) => setPage((current) => current === null ? current : { ...current, routing }))
      .catch(() => setFeedback({ text: t("admin.aiModels.updateError"), tone: "error" }))
      .finally(() => setBusy(null));
  }

  function updateModel(model: AdminAiModel, update: Parameters<typeof updateAdminAiModel>[1]) {
    setBusy(model.id);
    setFeedback(null);
    void updateAdminAiModel(model.id, update)
      .then(updatePageModel)
      .catch(() => setFeedback({ text: t("admin.aiModels.updateError"), tone: "error" }))
      .finally(() => setBusy(null));
  }

  function moveAutomaticModel(model: AdminAiModel, direction: -1 | 1) {
    const index = automaticModels.findIndex((item) => item.id === model.id);
    const neighbor = automaticModels[index + direction];
    if (neighbor === undefined) return;
    const reordered = [...automaticModels];
    reordered.splice(index, 1);
    reordered.splice(index + direction, 0, model);
    const updates = reordered
      .map((item, order) => ({ item, priority: (order + 1) * 10 }))
      .filter(({ item, priority }) => item.priority !== priority);
    setBusy(model.id);
    setFeedback(null);
    void Promise.all(
      updates.map(({ item, priority }) => updateAdminAiModel(item.id, { priority })),
    )
      .then((updatedModels) => {
        updatedModels.forEach(updatePageModel);
      })
      .catch(() => setFeedback({ text: t("admin.aiModels.updateError"), tone: "error" }))
      .finally(() => setBusy(null));
  }

  function syncModels() {
    setBusy("sync");
    setFeedback(null);
    void syncAdminAiModels()
      .then((result) => {
        setFeedback({
          text: result.needs_classification.length > 0
            ? t("admin.aiModels.syncNeedsClassification", { count: result.needs_classification.length })
            : t("admin.aiModels.syncSuccess"),
          tone: "success",
        });
        load();
      })
      .catch(() => setFeedback({ text: t("admin.aiModels.syncError"), tone: "error" }))
      .finally(() => setBusy(null));
  }

  function checkModel(model: AdminAiModel) {
    setBusy(model.id);
    setFeedback(null);
    void testAdminAiModel(model.id)
      .then((result) => {
        updatePageModel(result.model);
        setModelTestRuns((current) => [
          result.test_run,
          ...current.filter((testRun) => testRun.id !== result.test_run.id),
        ]);
      })
      .catch(() => setFeedback({ text: t("admin.aiModels.testFailure"), tone: "error" }))
      .finally(() => setBusy(null));
  }

  function createCustomModel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("create");
    setFeedback(null);
    void createAdminAiModel(customModel)
      .then((model) => {
        setPage((current) => current === null ? current : { ...current, models: [...current.models, model] });
        setCustomModel(blankCustomModel);
        setFilter("custom");
        setFeedback({ text: t("admin.aiModels.createSuccess"), tone: "success" });
      })
      .catch(() => setFeedback({ text: t("admin.aiModels.createError"), tone: "error" }))
      .finally(() => setBusy(null));
  }

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={appTrainingAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--ai-models">
        <header className="admin-hero admin-ai-hero">
          <div>
            <p className="eyebrow eyebrow--accent">{t("admin.aiModels.eyebrow")}</p>
            <h1 className="fitsho-display">{t("admin.aiModels.title")}</h1>
            <p>{t("admin.aiModels.intro")}</p>
          </div>
          <button className="admin-primary-link" type="button" onClick={syncModels} disabled={busy === "sync"}>
            {busy === "sync" ? t("admin.aiModels.syncing") : t("admin.aiModels.sync")}
          </button>
        </header>

        {state === "loading" && <p className="admin-status" role="status">{t("admin.aiModels.loading")}</p>}
        {state === "error" && <div className="admin-status" role="alert"><p>{t("admin.aiModels.loadError")}</p><button type="button" onClick={load}>{t("common.retry")}</button></div>}
        {feedback !== null && (
          <p
            className={`admin-status admin-status--${feedback.tone}`}
            role={feedback.tone === "error" ? "alert" : "status"}
          >
            {feedback.text}
          </p>
        )}

        {state === "ready" && page !== null && (
          <>
            <section className="admin-ai-routing admin-form-section" aria-labelledby="ai-routing-title">
              <div className="admin-section-heading"><div><p className="eyebrow">{t("admin.aiModels.routingEyebrow")}</p><h2 id="ai-routing-title">{t("admin.aiModels.routingTitle")}</h2></div><span className="admin-ai-route-pulse" aria-hidden="true" /></div>
              <fieldset className="admin-choice-group">
                <legend>{t("admin.aiModels.routingMode")}</legend>
                <div>
                  <label><input type="radio" name="routing" checked={page.routing.mode === "manual"} disabled={busy === "routing"} onChange={() => setRouting("manual", page.routing.manual_model_id ?? selectableModels[0]?.id)} />{t("admin.aiModels.manual")}</label>
                  <label><input type="radio" name="routing" checked={page.routing.mode === "automatic"} disabled={busy === "routing"} onChange={() => setRouting("automatic")} />{t("admin.aiModels.automatic")}</label>
                </div>
              </fieldset>
              {page.routing.mode === "manual" && <label className="admin-field"><span>{t("admin.aiModels.manualModel")}</span><select value={page.routing.manual_model_id ?? ""} onChange={(event) => setRouting("manual", event.target.value)} disabled={busy === "routing"}>{selectableModels.map((model) => <option key={model.id} value={model.id}>{model.display_name} — {model.model_id}</option>)}</select></label>}
              {page.routing.mode === "automatic" && <div className="admin-ai-priority-list" aria-label={t("admin.aiModels.priorityList")}>{automaticModels.map((model, index) => <article className="admin-ai-priority-row" data-testid="free-priority-row" key={model.id}><span>{index + 1}</span><div><strong>{model.display_name}</strong><code>{model.model_id}</code></div><div className="admin-ai-row-actions"><button type="button" disabled={index === 0 || busy === model.id} onClick={() => moveAutomaticModel(model, -1)}>{t("admin.aiModels.moveUp")}</button><button type="button" disabled={index === automaticModels.length - 1 || busy === model.id} onClick={() => moveAutomaticModel(model, 1)}>{t("admin.aiModels.moveDown")}</button></div></article>)}</div>}
            </section>

            <section className="admin-ai-catalog" aria-labelledby="ai-catalog-title">
              <div className="admin-section-heading"><div><p className="eyebrow">{t("admin.aiModels.catalogEyebrow")}</p><h2 id="ai-catalog-title">{t("admin.aiModels.catalogTitle")}</h2></div><div className="admin-ai-tabs" role="tablist" aria-label={t("admin.aiModels.filterLabel")}>{(["free", "paid", "custom"] as const).map((value) => <button type="button" key={value} role="tab" aria-selected={filter === value} onClick={() => setFilter(value)}>{t(`admin.aiModels.filters.${value}`)}</button>)}</div></div>
              <div className="admin-ai-model-list">{displayedModels.map((model) => <article className="admin-ai-model-row" key={model.id}><div className="admin-ai-model-row__identity"><div className="admin-ai-model-row__title"><h3>{model.display_name}</h3>{model.classification_required && <span className="admin-state admin-state--inactive">{t("admin.aiModels.needsClassification")}</span>}{!model.classification_required && <span className={`admin-state admin-state--${model.is_enabled ? "active" : "inactive"}`}>{t(`admin.aiModels.${model.is_enabled ? "enabled" : "disabled"}`)}</span>}</div><code>{model.model_id}</code></div><dl><div><dt>{t("admin.aiModels.apiKind")}</dt><dd>{model.api_kind ?? "—"}</dd></div><div><dt>{t("admin.aiModels.billing")}</dt><dd>{model.billing_class === null ? "—" : t(`admin.aiModels.filters.${model.billing_class}`)}</dd></div><div><dt>{t("admin.aiModels.priority")}</dt><dd>{model.priority}</dd></div></dl>{model.last_error_message !== null && <p className="admin-ai-model-error">{model.last_error_message}</p>}<div className="admin-ai-row-actions"><button type="button" disabled={busy === model.id} onClick={() => updateModel(model, { is_enabled: !model.is_enabled })}>{t(`admin.aiModels.${model.is_enabled ? "disable" : "enable"}`)}</button><button type="button" disabled={busy === model.id || model.classification_required} onClick={() => checkModel(model)}>{t("admin.aiModels.test")}</button></div></article>)}</div>
            </section>

            <section className="admin-ai-failures admin-form-section" aria-labelledby="ai-failures-title">
              <div className="admin-section-heading">
                <div>
                  <p className="eyebrow">{t("admin.aiModels.failuresEyebrow")}</p>
                  <h2 id="ai-failures-title">{t("admin.aiModels.failuresTitle")}</h2>
                </div>
              </div>
              {events.length === 0 && (
                <p className="admin-ai-failures__empty">{t("admin.aiModels.failuresEmpty")}</p>
              )}
              <div className="admin-ai-failure-list">
                {events.map((event) => (
                  <article className={`admin-ai-event admin-ai-event--${event.tone}`} key={event.id}>
                    <header>
                      <code>{event.modelId}</code>
                      <time dateTime={event.createdAt}>
                        {new Date(event.createdAt).toLocaleString()}
                      </time>
                    </header>
                    {event.errorCode !== null && <strong>{event.errorCode}</strong>}
                    {event.message !== null && <p>{event.message}</p>}
                    {event.diagnostics?.flatMap((diagnostic, diagnosticIndex) =>
                      diagnostic.problems.map((problem, problemIndex) => (
                        <div
                          className="admin-ai-diagnostic"
                          key={`${event.id}-${diagnosticIndex}-${problemIndex}`}
                        >
                          <span>{t("admin.aiModels.failurePhase")}: <code>{diagnostic.phase}</code></span>
                          <strong>{problem.code}</strong>
                          {problem.day_number !== undefined && (
                            <span>{t("admin.aiModels.failureDay")}: {problem.day_number}</span>
                          )}
                          {problem.exercise_id !== undefined && (
                            <span>
                              {t("admin.aiModels.failureExercise")}: <code>{problem.exercise_id}</code>
                            </span>
                          )}
                        </div>
                      )),
                    )}
                  </article>
                ))}
              </div>
            </section>

            <form className="admin-form admin-ai-custom-form" onSubmit={createCustomModel}>
              <fieldset className="admin-form-section"><legend>{t("admin.aiModels.customTitle")}</legend><div className="admin-field-grid"><label className="admin-field"><span>{t("admin.aiModels.displayName")}</span><input required value={customModel.display_name} onChange={(event) => setCustomModel({ ...customModel, display_name: event.target.value })} /></label><label className="admin-field"><span>{t("admin.aiModels.modelId")}</span><input dir="ltr" required value={customModel.model_id} onChange={(event) => setCustomModel({ ...customModel, model_id: event.target.value })} /></label><label className="admin-field"><span>{t("admin.aiModels.apiKind")}</span><select value={customModel.api_kind} onChange={(event) => setCustomModel({ ...customModel, api_kind: event.target.value as ZenApiKind })}>{(["responses", "chat_completions", "messages", "gemini"] as const).map((value) => <option key={value} value={value}>{value}</option>)}</select></label><label className="admin-field"><span>{t("admin.aiModels.billing")}</span><select value={customModel.billing_class} onChange={(event) => setCustomModel({ ...customModel, billing_class: event.target.value as BillingClass })}><option value="free">{t("admin.aiModels.filters.free")}</option><option value="paid">{t("admin.aiModels.filters.paid")}</option></select></label></div><div className="admin-form-actions"><button className="admin-primary-link" type="submit" disabled={busy === "create"}>{busy === "create" ? t("admin.aiModels.creating") : t("admin.aiModels.create")}</button></div></fieldset>
            </form>
          </>
        )}
      </main>
    </div>
  );
}
