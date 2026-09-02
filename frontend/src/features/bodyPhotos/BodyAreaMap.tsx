import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  bodyMapArtwork,
  bodyMapRegions,
  type BodyMapSex,
  type BodyMapView,
  type BodyMapRegionLayout,
} from "./bodyMapRegions";
import { translateExperienceInsight } from "./experienceText";
import type { BodyAnalysisExperienceRegion } from "./types";

export function BodyAreaMap({ sex, regions }: { sex: BodyMapSex; regions: BodyAnalysisExperienceRegion[] }) {
  const { t } = useTranslation();
  const artworkRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<BodyMapView>("front");
  const [selectedArea, setSelectedArea] = useState<BodyAnalysisExperienceRegion["area"] | null>(
    regions[0]?.area ?? null,
  );
  const regionsByArea = useMemo(
    () => new Map(regions.map((region) => [region.area, region] as const)),
    [regions],
  );
  const selectedRegion = selectedArea === null ? undefined : regionsByArea.get(selectedArea);
  const areaLabel = useCallback((area: string) => t(`bodyPhotos.results.areas.${area}`), [t]);
  const classificationLabel = useCallback(
    (classification: BodyAnalysisExperienceRegion["display_classification"]) => (
      t(`bodyAnalysis.map.classifications.${classification}`)
    ),
    [t],
  );

  useEffect(() => {
    const svg = artworkRef.current?.querySelector("svg");
    if (svg === null || svg === undefined) return;

    const viewLabel = t(`bodyAnalysis.map.viewNames.${view}`);
    const sexLabel = t(`bodyAnalysis.map.sex.${sex}`);
    svg.setAttribute("role", "group");
    svg.setAttribute("aria-label", t("bodyAnalysis.map.artworkAlt", { sex: sexLabel, view: viewLabel }));
    const layoutsById = new Map<string, BodyMapRegionLayout>(
      bodyMapRegions.map((layout) => [layout.svgRegionId, layout]),
    );
    const paths = svg.querySelectorAll<SVGPathElement>("path[data-region-id]");

    paths.forEach((path) => {
      const layout = layoutsById.get(path.dataset.regionId ?? "");
      const region = layout === undefined ? undefined : regionsByArea.get(layout.area);
      const available = layout !== undefined && region !== undefined && layout.availableViews.includes(view);
      if (!available || layout === undefined || region === undefined) {
        path.setAttribute("aria-hidden", "true");
        path.setAttribute("tabindex", "-1");
        path.removeAttribute("role");
        path.style.display = "none";
        return;
      }

      path.style.display = "";
      path.removeAttribute("aria-hidden");
      path.setAttribute("role", "button");
      path.setAttribute("tabindex", "0");
      path.setAttribute("aria-label", t("bodyAnalysis.map.svgRegion", {
        area: areaLabel(region.area),
        classification: classificationLabel(region.display_classification),
      }));
      path.setAttribute("aria-pressed", String(selectedArea === region.area));
      path.dataset.classification = region.display_classification;
      path.classList.toggle("is-selected", selectedArea === region.area);
    });

    function selectPath(path: SVGPathElement) {
      const layout = layoutsById.get(path.dataset.regionId ?? "");
      if (layout === undefined || !layout.availableViews.includes(view) || !regionsByArea.has(layout.area)) return;
      setSelectedArea(layout.area);
    }

    function handleClick(event: Event) {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const path = target.closest<SVGPathElement>("path[data-region-id]");
      if (path !== null) selectPath(path);
    }

    function handleKeyDown(event: Event) {
      if (!(event instanceof globalThis.KeyboardEvent)) return;
      const keyboardEvent = event;
      if (keyboardEvent.key !== "Enter" && keyboardEvent.key !== " ") return;
      const target = keyboardEvent.target;
      if (!(target instanceof SVGPathElement)) return;
      keyboardEvent.preventDefault();
      selectPath(target);
    }

    svg.addEventListener("click", handleClick);
    svg.addEventListener("keydown", handleKeyDown);
    return () => {
      svg.removeEventListener("click", handleClick);
      svg.removeEventListener("keydown", handleKeyDown);
    };
  }, [areaLabel, classificationLabel, regions, regionsByArea, selectedArea, sex, t, view]);

  function changeView(nextView: BodyMapView) {
    setView(nextView);
    const nextRegion = bodyMapRegions.find((region) => (
      region.availableViews.includes(nextView) && regionsByArea.has(region.area)
    ));
    if (nextRegion !== undefined) setSelectedArea(nextRegion.area);
  }

  function handleViewKeyDown(event: ReactKeyboardEvent<HTMLButtonElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    changeView(view === "front" ? "back" : "front");
  }

  const selectedInsight = selectedRegion === undefined
    ? null
    : translateExperienceInsight(t, selectedRegion, areaLabel);

  return (
    <section className="body-area-map" aria-labelledby="body-area-map-title">
      <header className="body-area-map__header">
        <div>
          <p className="eyebrow eyebrow--accent">{t("bodyAnalysis.map.eyebrow")}</p>
          <h2 id="body-area-map-title">{t("bodyAnalysis.map.title")}</h2>
        </div>
        <p>{t("bodyAnalysis.map.selectionHint")}</p>
      </header>
      <div className="body-area-map__views" role="tablist" aria-label={t("bodyAnalysis.map.viewSelector")}>
        {(["front", "back"] as const).map((nextView) => (
          <button
            aria-controls="body-area-map-artwork"
            aria-selected={view === nextView}
            className="body-area-map__view-button"
            id={`body-area-map-tab-${nextView}`}
            key={nextView}
            role="tab"
            tabIndex={view === nextView ? 0 : -1}
            type="button"
            onClick={() => changeView(nextView)}
            onKeyDown={handleViewKeyDown}
          >
            {t(`bodyAnalysis.map.views.${nextView}`)}
          </button>
        ))}
      </div>
      <div
        aria-labelledby={`body-area-map-tab-${view}`}
        className="body-area-map__figure"
        id="body-area-map-artwork"
        role="tabpanel"
      >
        <div
          ref={artworkRef}
          className="body-area-map__svg"
          dangerouslySetInnerHTML={{ __html: bodyMapArtwork(sex, view) }}
        />
      </div>
      {selectedRegion !== undefined && (
        <div className="body-area-map__selection" aria-live="polite">
          <div>
            <p className="eyebrow eyebrow--accent">{t("bodyAnalysis.map.selectedEyebrow")}</p>
            <h3>{areaLabel(selectedRegion.area)}</h3>
          </div>
          <p className="body-area-map__classification" data-classification={selectedRegion.display_classification}>
            {classificationLabel(selectedRegion.display_classification)}
          </p>
          {selectedInsight !== null && <p>{selectedInsight}</p>}
          <small>{t("bodyAnalysis.map.supportedViews", { views: selectedRegion.supporting_views.map((item) => t(`bodyPhotos.views.${item}`)).join(" · ") })}</small>
        </div>
      )}
      <ul className="body-area-map__regions" aria-label={t("bodyAnalysis.map.regionListLabel")}>
        {regions.map((region, index) => {
          const label = areaLabel(region.area);
          const classification = classificationLabel(region.display_classification);
          return (
            <li key={region.area}>
              <button
                aria-label={`${label} — ${classification}`}
                aria-pressed={selectedArea === region.area}
                className={`body-area-map__region${selectedArea === region.area ? " is-selected" : ""}`}
                data-classification={region.display_classification}
                type="button"
                onClick={() => setSelectedArea(region.area)}
              >
                <span className="body-area-map__region-index" aria-hidden="true">{index + 1}</span>
                <span>
                  <strong>{label}</strong>
                  <small>{classification}</small>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
