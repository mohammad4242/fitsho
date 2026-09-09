import type { ImageSourcePropType } from "react-native";

import type { BodyPhotoView } from "@fitician/core/body-photos";

export type BodyAssetSet = Record<BodyPhotoView, ImageSourcePropType>;

export const bodyAssets: Record<"female" | "male", BodyAssetSet> = {
  female: {
    back: require("../assets/body-analysis/female-back.jpg"),
    front: require("../assets/body-analysis/female-front.jpg"),
    side: require("../assets/body-analysis/female-side.jpg"),
  },
  male: {
    back: require("../assets/body-analysis/male-back.jpg"),
    front: require("../assets/body-analysis/male-front.jpg"),
    side: require("../assets/body-analysis/male-side.jpg"),
  },
};
