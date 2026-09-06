import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getBodyProgressTimeline } from "./api";
import type { BodyProgressTimelineItem } from "./types";

interface BodyAnalysisProgressStripProps {
  currentSessionId?: string;
  initialItems?: BodyProgressTimelineItem[];
}

interface ScanPoint {
  id: string;
  dateStr: string;
  bodyFat: number | null;
  weight: number | null;
  isCurrent: boolean;
}

export function BodyAnalysisProgressStrip({
  currentSessionId,
  initialItems,
}: BodyAnalysisProgressStripProps) {
  const { t, i18n } = useTranslation();
  const [items, setItems] = useState<BodyProgressTimelineItem[]>(initialItems ?? []);
  const [loaded, setLoaded] = useState(initialItems !== undefined);

  useEffect(() => {
    if (initialItems !== undefined) {
      setItems(initialItems);
      setLoaded(true);
      return;
    }
    void getBodyProgressTimeline()
      .then((res) => {
        setItems(res.items);
        setLoaded(true);
      })
      .catch(() => {
        setLoaded(true);
      });
  }, [initialItems]);

  const locale = i18n.resolvedLanguage === "en" ? "en-US" : "fa-IR";

  // Filter for valid submitted sessions with snapshots
  const submittedItems = items.filter(
    (item) => item.session.submitted_at !== null && item.snapshot !== null,
  );

  // Take the most recent 4 scans, and order chronologically (oldest to newest)
  // items from timeline are newest first, so slice(0, 4).reverse()
  const recentItems = submittedItems.slice(0, 4).reverse();

  const scanPoints: ScanPoint[] = recentItems.map((item) => {
    const rawDate = item.session.submitted_at ?? item.session.created_at;
    const dateStr = new Intl.DateTimeFormat(locale, {
      month: "short",
      day: "numeric",
    }).format(new Date(rawDate));

    // Try experience body_composition first, else compute RFM
    let bf: number | null = item.analysis?.experience_result?.body_composition?.estimated_body_fat_percent ?? null;
    if (bf === null && item.snapshot && item.snapshot.waist_circumference_cm > 0 && item.snapshot.height_cm > 0) {
      const isMale = item.snapshot.sex === "male";
      const base = isMale ? 64.0 : 76.0;
      const rfm = base - 20.0 * (item.snapshot.height_cm / item.snapshot.waist_circumference_cm);
      if (rfm > 2.0 && rfm < 80.0) {
        bf = Math.round(rfm * 10) / 10;
      }
    }

    return {
      id: item.session.id,
      dateStr,
      bodyFat: bf,
      weight: item.snapshot?.weight_kg ?? null,
      isCurrent: item.session.id === currentSessionId,
    };
  });

  // Calculate changes between oldest and newest of recent scans
  let bfChange: number | null = null;
  let weightChange: number | null = null;

  if (scanPoints.length >= 2) {
    const first = scanPoints[0];
    const last = scanPoints[scanPoints.length - 1];
    if (first.bodyFat !== null && last.bodyFat !== null) {
      bfChange = Math.round((last.bodyFat - first.bodyFat) * 10) / 10;
    }
    if (first.weight !== null && last.weight !== null) {
      weightChange = Math.round((last.weight - first.weight) * 10) / 10;
    }
  }

  function formatChange(val: number | null, unit: string): string {
    if (val === null) return "—";
    if (val === 0) return t("bodyAnalysis.progressStrip.noChange");
    const sign = val > 0 ? "+" : "";
    return `${sign}${val} ${unit}`;
  }

  return (
    <section className="fitsho-progress-strip" aria-labelledby="fitsho-progress-title">
      <header className="fitsho-progress-strip__header">
        <div>
          <p className="eyebrow eyebrow--accent">{t("bodyAnalysis.progressStrip.subtitle")}</p>
          <h2 id="fitsho-progress-title">{t("bodyAnalysis.progressStrip.title")}</h2>
        </div>

        {scanPoints.length >= 2 && (
          <div className="fitsho-progress-strip__summary">
            {bfChange !== null && (
              <div className="fitsho-progress-strip__summary-item">
                <span className="fitsho-progress-strip__summary-label">
                  {t("bodyAnalysis.progressStrip.bodyFatChange")}
                </span>
                <strong
                  className={`fitsho-progress-strip__summary-val ${bfChange < 0 ? "fitsho-progress-strip__summary-val--pos" : ""}`}
                >
                  {formatChange(bfChange, "%")}
                </strong>
              </div>
            )}
            {weightChange !== null && (
              <div className="fitsho-progress-strip__summary-item">
                <span className="fitsho-progress-strip__summary-label">
                  {t("bodyAnalysis.progressStrip.weightChange")}
                </span>
                <strong className="fitsho-progress-strip__summary-val">
                  {formatChange(weightChange, "kg")}
                </strong>
              </div>
            )}
          </div>
        )}
      </header>

      {/* When only 1 scan exists */}
      {loaded && scanPoints.length <= 1 ? (
        <div className="fitsho-progress-strip__single-state">
          <div className="fitsho-progress-strip__single-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" />
            </svg>
          </div>
          <div>
            <h3>{t("bodyAnalysis.progressStrip.singleScanTitle")}</h3>
            <p>{t("bodyAnalysis.progressStrip.singleScanNotice")}</p>
          </div>
        </div>
      ) : (
        <div className="fitsho-progress-strip__timeline" role="list" aria-label={t("bodyAnalysis.progressStrip.recentScans")}>
          <div className="fitsho-progress-strip__line" aria-hidden="true" />
          <div className="fitsho-progress-strip__nodes">
            {scanPoints.map((pt) => (
              <article
                key={pt.id}
                className={`fitsho-progress-strip__node ${pt.isCurrent ? "fitsho-progress-strip__node--current" : ""}`}
                role="listitem"
              >
                <div className="fitsho-progress-strip__dot" aria-hidden="true">
                  {pt.isCurrent && <span className="fitsho-progress-strip__dot-pulse" />}
                </div>
                <time className="fitsho-progress-strip__date">{pt.dateStr}</time>
                <div className="fitsho-progress-strip__metrics">
                  <span className="fitsho-progress-strip__bf">
                    {pt.bodyFat !== null ? `${pt.bodyFat}% BF` : "—"}
                  </span>
                  <span className="fitsho-progress-strip__weight">
                    {pt.weight !== null ? `${pt.weight} kg` : "—"}
                  </span>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
