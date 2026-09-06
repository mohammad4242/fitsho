import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import * as api from "./api";
import type { SupplementOrder } from "./api";
import "./nutritionEstimate.css";

export function NutritionSupplementsPage() {
  const { i18n } = useTranslation();
  const fa = i18n.language === "fa";
  const l = (p: string, e: string) => (fa ? p : e);
  const navigate = useNavigate();
  const [orders, setOrders] = useState<SupplementOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");

  const statusLabels: Record<string, string> = {
    prescribed: l("تجویزشده", "Prescribed"),
    active: l("فعال", "Active"),
    completed: l("تمام‌شده", "Completed"),
    discontinued: l("قطع‌شده", "Discontinued"),
  };

  const load = () =>
    api
      .listSupplementOrders()
      .then((items) => {
        setOrders(items);
        setError(false);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));

  useEffect(() => {
    void load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const visibleOrders = orders.filter(
    (order) => statusFilter === "all" || order.status === statusFilter,
  );

  return (
    <main className="nutrition-estimate-page supplement-page-main" dir={fa ? "rtl" : "ltr"}>
      <div className="supplement-page-container">
        <header className="supplement-hero">
          <button
            className="secondary-button supplement-back-button"
            type="button"
            onClick={() => navigate(-1)}
          >
            <span className="supplement-back-button__icon" aria-hidden="true">‹</span>
            <span>{l("بازگشت", "Back")}</span>
          </button>
          <div className="supplement-hero__title-group">
            <h1>
              <span className="supplement-hero__pill-icon" aria-hidden="true">💊</span>
              <span>{l("مکمل‌های من", "My supplements")}</span>
            </h1>
            <p>
              {l(
                "فقط دستورهای ثبت‌شده توسط پزشک فیتشو اینجا نمایش داده می‌شوند.",
                "Only physician-managed Fitsho orders appear here.",
              )}
            </p>
          </div>
        </header>

        <section className="supplement-filter-bar" aria-label={l("فیلتر وضعیت", "Status filter")}>
          <div className="supplement-filter-bar__group">
            <label htmlFor="supplement-status-filter" className="supplement-filter-bar__label">
              {l("وضعیت", "Status")}
            </label>
            <div className="supplement-select-wrapper">
              <select
                id="supplement-status-filter"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
              >
                <option value="all">{l("همه", "All")}</option>
                <option value="prescribed">{l("تجویزشده", "Prescribed")}</option>
                <option value="active">{l("فعال", "Active")}</option>
                <option value="completed">{l("تمام‌شده", "Completed")}</option>
                <option value="discontinued">{l("قطع‌شده", "Discontinued")}</option>
              </select>
              <span className="supplement-select-chevron" aria-hidden="true">▾</span>
            </div>
          </div>
          <span className="supplement-filter-bar__count">
            {visibleOrders.length} {l("مورد", "items")}
          </span>
        </section>

        {loading && (
          <div className="supplement-state-card" role="status">
            <span className="supplement-state-card__spinner" aria-hidden="true" />
            <span>{l("در حال دریافت دستورها…", "Loading supplement orders…")}</span>
          </div>
        )}

        {error && (
          <div className="supplement-state-card supplement-state-card--error" role="alert">
            <span>{l("دستورهای مکمل دریافت نشد.", "Supplement orders could not be loaded.")}</span>
          </div>
        )}

        {!loading && visibleOrders.length === 0 ? (
          <div className="supplement-empty-card">
            <span className="supplement-empty-card__icon" aria-hidden="true">📋</span>
            <p className="nutrition-estimate-state">
              {l("هیچ دستور مکملی ثبت نشده است.", "No supplement order has been recorded.")}
            </p>
            <small>
              {l(
                "در صورت نیاز، پزشک پس از بررسی پرونده شما دستور مکمل را ثبت می‌کند.",
                "If necessary, your physician will prescribe supplements after reviewing your case.",
              )}
            </small>
          </div>
        ) : (
          <section className="supplement-orders-grid" aria-label={l("فهرست مکمل‌ها", "Supplements list")}>
            {visibleOrders.map((order) => {
              const statusClass = `supplement-status--${order.status}`;
              const localizedStatus = statusLabels[order.status] ?? order.status;
              return (
                <article className="supplement-card" key={order.id}>
                  <header className="supplement-card__header">
                    <div className="supplement-card__identity">
                      <span className="supplement-card__icon" aria-hidden="true">💊</span>
                      <div>
                        <strong className="supplement-card__name">{order.name}</strong>
                        <span className="supplement-card__dose">
                          {order.dose_amount} {order.dose_unit} — {order.frequency}
                        </span>
                      </div>
                    </div>
                    <span className={`supplement-card__status ${statusClass}`}>
                      <i aria-hidden="true" />
                      <b>{order.status}</b>
                      {fa && <span>({localizedStatus})</span>}
                    </span>
                  </header>

                  <div className="supplement-card__body">
                    <div className="supplement-card__duration">
                      <span className="supplement-card__meta-tag">
                        ⏱️ {order.duration_days} {l("روز", "days")}
                      </span>
                    </div>

                    <div className="supplement-card__instruction-box">
                      <span className="supplement-card__instruction-label">
                        {l("دستور مصرف:", "Instructions:")}
                      </span>
                      <p className="supplement-card__instruction-text">{order.instructions}</p>
                    </div>

                    {order.rationale && (
                      <div className="supplement-card__rationale">
                        <span className="supplement-card__rationale-label">
                          {l("علت تجویز پزشک:", "Physician rationale:")}
                        </span>
                        <p>{order.rationale}</p>
                      </div>
                    )}
                  </div>

                  <details className="supplement-card__breakdown">
                    <summary>
                      <span>{l("سهم تغذیه و مکمل", "Food and supplement contribution")}</span>
                      <span className="supplement-card__chevron" aria-hidden="true">▾</span>
                    </summary>
                    <div className="supplement-card__breakdown-content">
                      <small>
                        {l("سهم مکمل", "Supplement")}:{" "}
                        {Object.entries(order.supplement_nutrient_contribution)
                          .map(([code, value]) => `${code}: ${value}`)
                          .join(" · ") || "—"}
                      </small>
                      <small>
                        {l("کنترل مواجهه ترکیبی", "Combined exposure check")}:{" "}
                        {order.combined_exposure_safety.hard_blocks?.length
                          ? l("نیازمند بررسی", "Review required")
                          : l("بدون منع ثبت‌شده", "No recorded hard block")}
                      </small>
                    </div>
                  </details>

                  {!order.acknowledged_at && (
                    <footer className="supplement-card__footer">
                      <button
                        className="primary-button supplement-card__ack-button"
                        onClick={() => void api.acknowledgeSupplementOrder(order.id).then(load)}
                        type="button"
                      >
                        {l("دیدم", "Acknowledge")}
                      </button>
                    </footer>
                  )}
                </article>
              );
            })}
          </section>
        )}
      </div>
    </main>
  );
}
