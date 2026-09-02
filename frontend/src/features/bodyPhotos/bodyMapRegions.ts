import femaleBackArtwork from "../../assets/body1/female-back.jpg";
import femaleFrontArtwork from "../../assets/body1/female-front.jpg";
import maleBackArtwork from "../../assets/body1/male-back.jpg";
import maleFrontArtwork from "../../assets/body1/male-front.jpg";

import type { BodyAnalysisExperienceSex, BodyAnalysisExperienceRegion } from "./types";

export type BodyMapSex = "male" | "female" | "neutral";
export type BodyMapView = "front" | "back";

export type BodyMapRegionLayout = {
  area: BodyAnalysisExperienceRegion["area"];
  svgRegionId: `region-${BodyAnalysisExperienceRegion["area"]}`;
  availableViews: readonly BodyMapView[];
};

export const bodyMapRegions: readonly BodyMapRegionLayout[] = [
  {
    area: "shoulders",
    svgRegionId: "region-shoulders",
    availableViews: ["front", "back"],
  },
  {
    area: "chest",
    svgRegionId: "region-chest",
    availableViews: ["front"],
  },
  {
    area: "back",
    svgRegionId: "region-back",
    availableViews: ["back"],
  },
  {
    area: "lats",
    svgRegionId: "region-lats",
    availableViews: ["front", "back"],
  },
  {
    area: "arms",
    svgRegionId: "region-arms",
    availableViews: ["front", "back"],
  },
  {
    area: "forearms",
    svgRegionId: "region-forearms",
    availableViews: ["front", "back"],
  },
  {
    area: "waist_midsection",
    svgRegionId: "region-waist_midsection",
    availableViews: ["front", "back"],
  },
  {
    area: "glutes",
    svgRegionId: "region-glutes",
    availableViews: ["back"],
  },
  {
    area: "quads",
    svgRegionId: "region-quads",
    availableViews: ["front"],
  },
  {
    area: "hamstrings",
    svgRegionId: "region-hamstrings",
    availableViews: ["back"],
  },
  {
    area: "calves",
    svgRegionId: "region-calves",
    availableViews: ["front", "back"],
  },
];

const artworkBySex: Record<BodyMapSex, Record<BodyMapView, string>> = {
  male: { front: maleFrontArtwork, back: maleBackArtwork },
  female: { front: femaleFrontArtwork, back: femaleBackArtwork },
  // Neutral profiles use the male artwork as the stable existing fallback.
  neutral: { front: maleFrontArtwork, back: maleBackArtwork },
};

export function bodyMapSex(sex: BodyAnalysisExperienceSex): BodyMapSex {
  if (sex === "male" || sex === "female") return sex;
  return "neutral";
}

export function bodyMapArtwork(sex: BodyMapSex, view: BodyMapView): string {
  return artworkBySex[sex][view];
}
