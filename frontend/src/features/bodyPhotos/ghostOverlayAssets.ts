import maleFrontAsset from "../../../../bodyanalysis/photo_2026-09-02_13-27-40.jpg";
import maleSideAsset from "../../../../bodyanalysis/photo_2026-09-02_13-27-41 (2).jpg";
import maleBackAsset from "../../../../bodyanalysis/photo_2026-09-02_13-27-39.jpg";
import femaleFrontAsset from "../../../../bodyanalysis/photo_2026-09-02_13-54-09.jpg";
import femaleSideAsset from "../../../../bodyanalysis/photo_2026-09-02_13-27-41.jpg";
import femaleBackAsset from "../../../../bodyanalysis/photo_2026-09-02_13-27-42.jpg";

import type { Sex } from "../profile/types";
import type { BodyPhotoView } from "./types";

export type GhostOverlayVariant = "male" | "female" | "neutral";

export const ghostOverlayAssets: Record<GhostOverlayVariant, Record<BodyPhotoView, string>> = {
  male: {
    front: maleFrontAsset,
    side: maleSideAsset,
    back: maleBackAsset,
  },
  female: {
    front: femaleFrontAsset,
    side: femaleSideAsset,
    back: femaleBackAsset,
  },
  // The prepared directory has no neutral set; use the least sex-specific set
  // while preserving a visible guide for profiles without a binary sex value.
  neutral: {
    front: maleFrontAsset,
    side: maleSideAsset,
    back: maleBackAsset,
  },
};

export function resolveGhostOverlayVariant(sex: Sex | null | undefined): GhostOverlayVariant {
  if (sex === "male" || sex === "female") return sex;
  return "neutral";
}
