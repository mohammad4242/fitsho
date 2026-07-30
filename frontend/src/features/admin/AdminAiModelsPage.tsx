import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import appTrainingAccent from "../../assets/landing/app-training-accent.jpg";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import {
  createAdminAiModel,
  getAdminAiModels,
  syncAdminAiModels,
  testAdminAiModel,
  updateAdminAiModel,
  updateAdminAiRouting,
} from "./api";
import type {
  AdminAiModel,
  AdminAiModelCreate,
  AdminAiModelsResponse,
  BillingClass,
  RoutingMode,
  ZenApiKind,
} from "./types";
import "./admin.css";

type Filter = "free" | "paid" | "custom";

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
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [filter, setFilter] = useState<Filter>("free");
  const [message, setMessage] = useState<string | null>(null);
  const [customModel, setCustomModel] = useState<AdminAiModelCreate>(blankCustomModel);
  const [busy, setBusy] = useState<string | null>(null);

  function load() {
    setState("loading");
    setMessage(null);
    void getAdminAiModels()
      .then((result) => {
        setPage(result);
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

  function updatePageModel(model: AdminAiModel) {
    setPage((current) => current === null ? current : {
      ...current,
      models: current.models.map((item) => item.id === model.id ? model : item),
    });
  }

  function setRouting(mode: RoutingMode, manualModelId?: string) {
    setBusy("routing");
    setMessage(null);
    void updateAdminAiRouting(
      mode === "manual" ? { mode, manual_model_id: manualModelId } : { mode },
    )
      .then((routing) => setPage((current) => current === null ? current : { ...current, routing }))
      .catch(() => setMessage(t("admin.aiModels.updateError")))
      .finally(() => setBusy(null));
  }

  function updateModel(model: AdminAiModel, update: Parameters<typeof updateAdminAiModel>[1]) {
    setBusy(model.id);
    setMessage(null);
    void updateAdminAiModel(model.id, update)
      .then(updatePageModel)
      .catch(() => setMessage(t("admin.aiModels.updateError")))
      .finally(() => setBusy(null));
  }

  function moveAutomaticModel(model: AdminAiModel, direction: -1 | 1) {
    const index = automaticModels.findIndex((item) => item.id === model.id);
    const neighbor = automaticModels[index + direction];
    if (neighbor === undefined) return;
    setBusy(model.id);
    setMessage(null);
    void Promise.all([
      updateAdminAiModel(model.id, { priority: neighbor.priority }),
      updateAdminAiModel(neighbor.id, { priority: model.priority }),
    ])
      .then(([updated, adjacent]) => {
        updatePageModel(updated);
        updatePageModel(adjacent);
      })
      .catch(() => setMessage(t("admin.aiModels.updateError")))
      .finally(() => setBusy(null));
  }

  function syncModels() {
    setBusy("sync");
    setMessage(null);
    void syncAdminAiModels()
      .then((result) => {
        setMessage(result.needs_classification.length > 0
          ? t("admin.aiModels.syncNeedsClassification", { count: result.needs_classification.length })
          : t("admin.aiModels.syncSuccess"));
        load();
      })
      .catch(() => setMessage(t("admin.aiModels.syncError")))
      .finally(() => setBusy(null));
  }

  function checkModel(model: AdminAiModel) {
    setBusy(model.id);
    setMessage(null);
    void testAdminAiModel(model.id)
      .then((result) => {
        updatePageModel(result.model);
        setMessage(result.success ? t("admin.aiModels.testSuccess") : t("admin.aiModels.testFailure"));
      })
      .catch(() => setMessage(t("admin.aiModels.testFailure")))
      .finally(() => setBusy(null));
  }

  function createCustomModel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("create");
    setMessage(null);
    void createAdminAiModel(customModel)
      .then((model) => {
        setPage((current) => current === null ? current : { ...current, models: [...current.models, model] });
        setCustomModel(blankCustomModel);
        setFilter("custom");
        setMessage(t("admin.aiModels.createSuccess"));
      })
      .catch(() => setMessage(t("admin.aiModels.createError")))
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
        {message !== null && <p className="admin-status admin-status--success" role="status">{message}</p>}

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

            <form className="admin-form admin-ai-custom-form" onSubmit={createCustomModel}>
              <fieldset className="admin-form-section"><legend>{t("admin.aiModels.customTitle")}</legend><div className="admin-field-grid"><label className="admin-field"><span>{t("admin.aiModels.displayName")}</span><input required value={customModel.display_name} onChange={(event) => setCustomModel({ ...customModel, display_name: event.target.value })} /></label><label className="admin-field"><span>{t("admin.aiModels.modelId")}</span><input dir="ltr" required value={customModel.model_id} onChange={(event) => setCustomModel({ ...customModel, model_id: event.target.value })} /></label><label className="admin-field"><span>{t("admin.aiModels.apiKind")}</span><select value={customModel.api_kind} onChange={(event) => setCustomModel({ ...customModel, api_kind: event.target.value as ZenApiKind })}>{(["responses", "chat_completions", "messages", "gemini"] as const).map((value) => <option key={value} value={value}>{value}</option>)}</select></label><label className="admin-field"><span>{t("admin.aiModels.billing")}</span><select value={customModel.billing_class} onChange={(event) => setCustomModel({ ...customModel, billing_class: event.target.value as BillingClass })}><option value="free">{t("admin.aiModels.filters.free")}</option><option value="paid">{t("admin.aiModels.filters.paid")}</option></select></label></div><div className="admin-form-actions"><button className="admin-primary-link" type="submit" disabled={busy === "create"}>{busy === "create" ? t("admin.aiModels.creating") : t("admin.aiModels.create")}</button></div></fieldset>
            </form>
          </>
        )}
      </main>
    </div>
  );
}
