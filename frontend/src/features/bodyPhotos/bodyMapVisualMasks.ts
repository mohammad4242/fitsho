import type { BodyMapSex, BodyMapView } from "./bodyMapRegions";
import type { BodyAnalysisExperienceRegion } from "./types";

const rawMaskSources = import.meta.glob("../../assets/body-masks/**/*.svg", {
  eager: true,
  import: "default",
  query: "?raw",
}) as Record<string, string>;

export type BodyMapVisualMaskPath = {
  d: string;
  transform?: string;
};

export type BodyMapVisualMask = {
  file: string;
  paths: readonly BodyMapVisualMaskPath[];
};

type BodyMapArea = BodyAnalysisExperienceRegion["area"];
type BodyMapVisualMaskView = Partial<Record<BodyMapArea, BodyMapVisualMask>>;

function maskSource(file: string): string {
  const key = `../../assets/body-masks/${file}`;
  const source = rawMaskSources[key];
  if (source === undefined) throw new Error(`Missing body visual mask asset: ${file}`);
  return source;
}

function attributeValue(attributes: string, name: string): string | undefined {
  return new RegExp(`${name}="([^"]+)"`).exec(attributes)?.[1];
}

function maskPaths(file: string): readonly BodyMapVisualMaskPath[] {
  const paths = [...maskSource(file).matchAll(/<path\b([^>]*)\/?>(?:<\/path>)?/g)].map((match) => {
    const attributes = match[1] ?? "";
    const d = attributeValue(attributes, "d");
    if (d === undefined) throw new Error(`Body visual mask path is missing d: ${file}`);
    return {
      d,
      transform: attributeValue(attributes, "transform"),
    } satisfies BodyMapVisualMaskPath;
  });
  if (paths.length === 0) throw new Error(`Body visual mask has no paths: ${file}`);
  return paths;
}

const visualMask = (file: string): BodyMapVisualMask => ({ file, paths: maskPaths(file) });

const maleMasks: Record<BodyMapView, BodyMapVisualMaskView> = {
  front: {
    shoulders: visualMask("male-front/shoulders.svg"),
    chest: visualMask("male-front/chest.svg"),
    lats: visualMask("male-front/lats.svg"),
    arms: visualMask("male-front/arms.svg"),
    forearms: visualMask("male-front/forearms.svg"),
    waist_midsection: visualMask("male-front/waist_midsection.svg"),
    quads: visualMask("male-front/quads.svg"),
    calves: visualMask("male-front/calves.svg"),
  },
  back: {
    shoulders: visualMask("male-back/shoulders.svg"),
    back: visualMask("male-back/back.svg"),
    lats: visualMask("male-back/lats.svg"),
    arms: visualMask("male-back/arms.svg"),
    forearms: visualMask("male-back/forearms.svg"),
    waist_midsection: visualMask("male-back/waist_midsection.svg"),
    glutes: visualMask("male-back/glutes.svg"),
    hamstrings: visualMask("male-back/hamstrings.svg"),
    calves: visualMask("male-back/calves.svg"),
  },
};

const femaleMasks: Record<BodyMapView, BodyMapVisualMaskView> = {
  front: {
    shoulders: visualMask("female-front/shoulders.svg"),
    chest: visualMask("female-front/chest.svg"),
    lats: visualMask("female-front/lats.svg"),
    arms: visualMask("female-front/arms.svg"),
    forearms: visualMask("female-front/forearms.svg"),
    waist_midsection: visualMask("female-front/waist_midsection.svg"),
    quads: visualMask("female-front/quads.svg"),
    calves: visualMask("female-front/calves.svg"),
  },
  back: {
    shoulders: visualMask("female-back/shoulders.svg"),
    back: visualMask("female-back/back.svg"),
    lats: visualMask("female-back/lats.svg"),
    arms: visualMask("female-back/arms.svg"),
    forearms: visualMask("female-back/forearms.svg"),
    waist_midsection: visualMask("female-back/waist_midsection.svg"),
    glutes: visualMask("female-back/glutes.svg"),
    hamstrings: visualMask("female-back/hamstrings.svg"),
    calves: visualMask("female-back/calves.svg"),
  },
};

const visualMasks: Record<BodyMapSex, Record<BodyMapView, BodyMapVisualMaskView>> = {
  male: maleMasks,
  female: femaleMasks,
  neutral: maleMasks,
};

export function bodyMapVisualMask(
  sex: BodyMapSex,
  view: BodyMapView,
  area: BodyMapArea,
): BodyMapVisualMask | undefined {
  return visualMasks[sex][view][area];
}
