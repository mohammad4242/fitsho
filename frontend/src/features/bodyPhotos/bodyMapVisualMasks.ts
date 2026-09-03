import femaleBackArms from "../../assets/body-masks/female-back/arms.svg";
import femaleBack from "../../assets/body-masks/female-back/back.svg";
import femaleBackCalves from "../../assets/body-masks/female-back/calves.svg";
import femaleBackForearms from "../../assets/body-masks/female-back/forearms.svg";
import femaleBackGlutes from "../../assets/body-masks/female-back/glutes.svg";
import femaleBackHamstrings from "../../assets/body-masks/female-back/hamstrings.svg";
import femaleBackLats from "../../assets/body-masks/female-back/lats.svg";
import femaleBackShoulders from "../../assets/body-masks/female-back/shoulders.svg";
import femaleBackWaist from "../../assets/body-masks/female-back/waist_midsection.svg";
import femaleFrontArms from "../../assets/body-masks/female-front/arms.svg";
import femaleFrontCalves from "../../assets/body-masks/female-front/calves.svg";
import femaleFrontChest from "../../assets/body-masks/female-front/chest.svg";
import femaleFrontForearms from "../../assets/body-masks/female-front/forearms.svg";
import femaleFrontLats from "../../assets/body-masks/female-front/lats.svg";
import femaleFrontQuads from "../../assets/body-masks/female-front/quads.svg";
import femaleFrontShoulders from "../../assets/body-masks/female-front/shoulders.svg";
import femaleFrontWaist from "../../assets/body-masks/female-front/waist_midsection.svg";
import maleBackArms from "../../assets/body-masks/male-back/arms.svg";
import maleBack from "../../assets/body-masks/male-back/back.svg";
import maleBackCalves from "../../assets/body-masks/male-back/calves.svg";
import maleBackForearms from "../../assets/body-masks/male-back/forearms.svg";
import maleBackGlutes from "../../assets/body-masks/male-back/glutes.svg";
import maleBackHamstrings from "../../assets/body-masks/male-back/hamstrings.svg";
import maleBackLats from "../../assets/body-masks/male-back/lats.svg";
import maleBackShoulders from "../../assets/body-masks/male-back/shoulders.svg";
import maleBackWaist from "../../assets/body-masks/male-back/waist_midsection.svg";
import maleFrontArms from "../../assets/body-masks/male-front/arms.svg";
import maleFrontCalves from "../../assets/body-masks/male-front/calves.svg";
import maleFrontChest from "../../assets/body-masks/male-front/chest.svg";
import maleFrontForearms from "../../assets/body-masks/male-front/forearms.svg";
import maleFrontLats from "../../assets/body-masks/male-front/lats.svg";
import maleFrontQuads from "../../assets/body-masks/male-front/quads.svg";
import maleFrontShoulders from "../../assets/body-masks/male-front/shoulders.svg";
import maleFrontWaist from "../../assets/body-masks/male-front/waist_midsection.svg";

import type { BodyMapSex, BodyMapView } from "./bodyMapRegions";
import type { BodyAnalysisExperienceRegion } from "./types";

export type BodyMapVisualMask = {
  file: string;
  url: string;
};

type BodyMapArea = BodyAnalysisExperienceRegion["area"];
type BodyMapVisualMaskView = Partial<Record<BodyMapArea, BodyMapVisualMask>>;

const visualMask = (file: string, url: string): BodyMapVisualMask => ({ file, url });

const maleMasks: Record<BodyMapView, BodyMapVisualMaskView> = {
  front: {
    shoulders: visualMask("male-front/shoulders.svg", maleFrontShoulders),
    chest: visualMask("male-front/chest.svg", maleFrontChest),
    lats: visualMask("male-front/lats.svg", maleFrontLats),
    arms: visualMask("male-front/arms.svg", maleFrontArms),
    forearms: visualMask("male-front/forearms.svg", maleFrontForearms),
    waist_midsection: visualMask("male-front/waist_midsection.svg", maleFrontWaist),
    quads: visualMask("male-front/quads.svg", maleFrontQuads),
    calves: visualMask("male-front/calves.svg", maleFrontCalves),
  },
  back: {
    shoulders: visualMask("male-back/shoulders.svg", maleBackShoulders),
    back: visualMask("male-back/back.svg", maleBack),
    lats: visualMask("male-back/lats.svg", maleBackLats),
    arms: visualMask("male-back/arms.svg", maleBackArms),
    forearms: visualMask("male-back/forearms.svg", maleBackForearms),
    waist_midsection: visualMask("male-back/waist_midsection.svg", maleBackWaist),
    glutes: visualMask("male-back/glutes.svg", maleBackGlutes),
    hamstrings: visualMask("male-back/hamstrings.svg", maleBackHamstrings),
    calves: visualMask("male-back/calves.svg", maleBackCalves),
  },
};

const femaleMasks: Record<BodyMapView, BodyMapVisualMaskView> = {
  front: {
    shoulders: visualMask("female-front/shoulders.svg", femaleFrontShoulders),
    chest: visualMask("female-front/chest.svg", femaleFrontChest),
    lats: visualMask("female-front/lats.svg", femaleFrontLats),
    arms: visualMask("female-front/arms.svg", femaleFrontArms),
    forearms: visualMask("female-front/forearms.svg", femaleFrontForearms),
    waist_midsection: visualMask("female-front/waist_midsection.svg", femaleFrontWaist),
    quads: visualMask("female-front/quads.svg", femaleFrontQuads),
    calves: visualMask("female-front/calves.svg", femaleFrontCalves),
  },
  back: {
    shoulders: visualMask("female-back/shoulders.svg", femaleBackShoulders),
    back: visualMask("female-back/back.svg", femaleBack),
    lats: visualMask("female-back/lats.svg", femaleBackLats),
    arms: visualMask("female-back/arms.svg", femaleBackArms),
    forearms: visualMask("female-back/forearms.svg", femaleBackForearms),
    waist_midsection: visualMask("female-back/waist_midsection.svg", femaleBackWaist),
    glutes: visualMask("female-back/glutes.svg", femaleBackGlutes),
    hamstrings: visualMask("female-back/hamstrings.svg", femaleBackHamstrings),
    calves: visualMask("female-back/calves.svg", femaleBackCalves),
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
