import type { ImageSourcePropType } from "react-native";

import type { BodyPhotoView } from "@fitician/core/body-photos";

export type BodyAssetSet = Record<BodyPhotoView, ImageSourcePropType>;
export type BodyMapAssetSet = Pick<BodyAssetSet, "back" | "front">;

export const bodyResultAssets: {
  readonly map: Record<"female" | "male", BodyMapAssetSet>;
  readonly overview: Record<"female" | "male", BodyAssetSet>;
} = {
  map: {
    female: {
      back: require("../assets/body-analysis/web/female-back.jpg"),
      front: require("../assets/body-analysis/web/female-front.jpg"),
    },
    male: {
      back: require("../assets/body-analysis/web/male-back.jpg"),
      front: require("../assets/body-analysis/web/male-front.jpg"),
    },
  },
  overview: {
    female: {
      back: require("../assets/body-analysis/web/female-back.png"),
      front: require("../assets/body-analysis/web/female-hero.png"),
      side: require("../assets/body-analysis/web/female-side.png"),
    },
    male: {
      back: require("../assets/body-analysis/web/male-back.png"),
      front: require("../assets/body-analysis/web/male-hero.png"),
      side: require("../assets/body-analysis/web/male-side.png"),
    },
  },
};
