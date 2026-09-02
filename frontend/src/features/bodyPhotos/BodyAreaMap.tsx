import { useCallback, useMemo, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import { bodyMapHitRegions } from "./bodyMapHitRegions";
import {
  bodyMapArtwork,
  bodyMapRegions,
  type BodyMapSex,
  type BodyMapView,
} from "./bodyMapRegions";
import { translateExperienceInsight } from "./experienceText";
import type { BodyAnalysisExperienceRegion } from "./types";

export function BodyAreaMap({ sex, regions }: { sex: BodyMapSex; regions: BodyAnalysisExperienceRegion[] }) {
  const { t } = useTranslation();
  const [view, setView] = useState<BodyMapView>("front");
  const [selectedArea, setSelectedArea] = useState<BodyAnalysisExperienceRegion["area"] | null>(null);
  const regionsByArea = useMemo(
    () => new Map(regions.map((region) => [region.area, region] as const)),
    [regions],
  );
  const layoutsByArea = useMemo(
    () => new Map(bodyMapRegions.map((layout) => [layout.area, layout] as const)),
    [],
  );
  const hitRegions = useMemo(
    () => bodyMapHitRegions(sex, view).filter((hitRegion) => {
      const layout = layoutsByArea.get(hitRegion.area);
      return layout !== undefined
        && layout.availableViews.includes(view)
        && regionsByArea.has(hitRegion.area);
    }),
    [layoutsByArea, regionsByArea, sex, view],
  );
  const selectedRegion = selectedArea === null ? undefined : regionsByArea.get(selectedArea);
  const areaLabel = useCallback((area: string) => t(`bodyPhotos.results.areas.${area}`), [t]);
  const classificationLabel = useCallback(
    (classification: BodyAnalysisExperienceRegion["display_classification"]) => (
      t(`bodyAnalysis.map.classifications.${classification}`)
    ),
    [t],
  );
  const viewLabel = t(`bodyAnalysis.map.viewNames.${view}`);
  const sexLabel = t(`bodyAnalysis.map.sex.${sex}`);
  const selectedInsight = selectedRegion === undefined
    ? null
    : translateExperienceInsight(t, selectedRegion, areaLabel) ?? t("bodyAnalysis.unavailable");

  function changeView(nextView: BodyMapView) {
    setView(nextView);
    setSelectedArea(null);
  }

  function handleViewKeyDown(event: ReactKeyboardEvent<HTMLButtonElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    changeView(view === "front" ? "back" : "front");
  }

  function selectArea(area: BodyAnalysisExperienceRegion["area"]) {
    setSelectedArea(area);
  }

  function handleHitKeyDown(
    event: ReactKeyboardEvent<SVGPathElement>,
    area: BodyAnalysisExperienceRegion["area"],
  ) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    selectArea(area);
  }

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
        <div className="body-area-map__image-layer">
          <img
            className="body-area-map__image"
            src={bodyMapArtwork(sex, view)}
            alt={t("bodyAnalysis.map.imageAlt", { sex: sexLabel, view: viewLabel })}
          />
          <svg
            className="body-area-map__hit-map"
            viewBox="0 0 853 1280"
            role="group"
            aria-label={t("bodyAnalysis.map.artworkAlt", { sex: sexLabel, view: viewLabel })}
          >
            {hitRegions.map((hitRegion) => {
              const region = regionsByArea.get(hitRegion.area);
              if (region === undefined) return null;
              const selected = selectedArea === hitRegion.area;
              return (
                <path
                  aria-label={t("bodyAnalysis.map.svgRegion", {
                    area: areaLabel(region.area),
                    classification: classificationLabel(region.display_classification),
                  })}
                  aria-pressed={selected}
                  className={selected ? "is-selected" : undefined}
                  data-area={hitRegion.area}
                  data-classification={region.display_classification}
                  data-region-id={hitRegion.id}
                  d={hitRegion.d}
                  id={hitRegion.id}
                  key={hitRegion.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => selectArea(hitRegion.area)}
                  onKeyDown={(event) => handleHitKeyDown(event, hitRegion.area)}
                />
              );
            })}
          </svg>
        </div>
      </div>
      {selectedRegion !== undefined && selectedInsight !== null && (
        <div className="body-area-map__selection" aria-live="polite">
          <p className="eyebrow eyebrow--accent">{t("bodyAnalysis.map.selectedEyebrow")}</p>
          <h3>{areaLabel(selectedRegion.area)}</h3>
          <p>{selectedInsight}</p>
        </div>
      )}
    </section>
  );
}
