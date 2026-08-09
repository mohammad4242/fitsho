import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import * as api from "./api";
import type { SupplementOrder } from "./api";
import "./nutritionEstimate.css";

export function NutritionSupplementsPage() {
  const { i18n } = useTranslation(); const fa = i18n.language === "fa";
  const l = (p: string, e: string) => fa ? p : e;
  const navigate = useNavigate();
  const [orders, setOrders] = useState<SupplementOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const load = () => api.listSupplementOrders().then((items) => { setOrders(items); setError(false); }).catch(() => setError(true)).finally(() => setLoading(false));
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const visibleOrders = orders.filter((order) => statusFilter === "all" || order.status === statusFilter);
  return <main className="nutrition-estimate-page" dir={fa ? "rtl" : "ltr"}>
    <section className="nutrition-estimate-hero"><button className="secondary-button" type="button" onClick={() => navigate(-1)}>{l("بازگشت", "Back")}</button><h1>{l("مکمل‌های من", "My supplements")}</h1><p>{l("فقط دستورهای ثبت‌شده توسط پزشک فیتشو اینجا نمایش داده می‌شوند.", "Only physician-managed Fitsho orders appear here.")}</p></section>
    {loading && <p role="status">{l("در حال دریافت دستورها…", "Loading supplement orders…")}</p>}
    {error && <p role="alert">{l("دستورهای مکمل دریافت نشد.", "Supplement orders could not be loaded.")}</p>}
    <label>{l("وضعیت", "Status")} <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">{l("همه", "All")}</option><option value="prescribed">{l("تجویزشده", "Prescribed")}</option><option value="active">{l("فعال", "Active")}</option><option value="completed">{l("تمام‌شده", "Completed")}</option><option value="discontinued">{l("قطع‌شده", "Discontinued")}</option></select></label>
    {!loading && visibleOrders.length === 0 ? <p className="nutrition-estimate-state">{l("هیچ دستور مکملی ثبت نشده است.", "No supplement order has been recorded.")}</p> : <section className="nutrition-target-grid">{visibleOrders.map((order) => <article className="nutrition-target-card" key={order.id}><strong>{order.name}</strong><span>{order.dose_amount} {order.dose_unit} — {order.frequency}</span><small>{order.duration_days} {l("روز", "days")} · {order.instructions}</small>{order.rationale && <p>{order.rationale}</p>}<b>{order.status}</b><details><summary>{l("سهم تغذیه و مکمل", "Food and supplement contribution")}</summary><small>{l("سهم مکمل", "Supplement")}: {Object.entries(order.supplement_nutrient_contribution).map(([code, value]) => `${code}: ${value}`).join(" · ") || "—"}</small><small>{l("کنترل مواجهه ترکیبی", "Combined exposure check")}: {order.combined_exposure_safety.hard_blocks?.length ? l("نیازمند بررسی", "Review required") : l("بدون منع ثبت‌شده", "No recorded hard block")}</small></details>{!order.acknowledged_at && <button onClick={() => void api.acknowledgeSupplementOrder(order.id).then(load)}>{l("دیدم", "Acknowledge")}</button>}</article>)}</section>}
  </main>;
}
