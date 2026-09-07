import type { ImageSourcePropType } from "react-native";

import type { BodyPhotoView } from "@fitician/core/body-photos";

import type { GhostOverlayVariant } from "./ghostOverlay";

const maleFront = require("../assets/body-analysis/male-front.jpg") as ImageSourcePropType;
const maleSide = require("../assets/body-analysis/male-side.jpg") as ImageSourcePropType;
const maleBack = require("../assets/body-analysis/male-back.jpg") as ImageSourcePropType;
const femaleFront = require("../assets/body-analysis/female-front.jpg") as ImageSourcePropType;
const femaleSide = require("../assets/body-analysis/female-side.jpg") as ImageSourcePropType;
const femaleBack = require("../assets/body-analysis/female-back.jpg") as ImageSourcePropType;

export const ghostOverlayAssets: Record<GhostOverlayVariant, Record<BodyPhotoView, ImageSourcePropType>> = {
  female: {
    back: femaleBack,
    front: femaleFront,
    side: femaleSide,
  },
  male: {
    back: maleBack,
    front: maleFront,
    side: maleSide,
  },
  neutral: {
    back: maleBack,
    front: maleFront,
    side: maleSide,
  },
};
