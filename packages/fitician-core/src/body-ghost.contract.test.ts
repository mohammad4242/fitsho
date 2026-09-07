import {
  GHOST_BACK_PRIVACY_CUT_RATIO,
  GHOST_PRIVACY_CUT_RATIO,
  GHOST_SCALE_MAX,
  GHOST_SCALE_MIN,
  getGhostGeometry,
  ghostPrivacyLineGeometry,
  isPointInZone,
  pointZoneDistance,
  transformGhostPoint,
} from "./body-ghost.js";
import type { BodyPhotoView } from "./body-photos.js";

const view: BodyPhotoView = "front";
const geometry = getGhostGeometry({ view, ghostScale: 1 });

void GHOST_BACK_PRIVACY_CUT_RATIO;
void GHOST_PRIVACY_CUT_RATIO;
void GHOST_SCALE_MAX;
void GHOST_SCALE_MIN;
void geometry;
void ghostPrivacyLineGeometry(view);
void isPointInZone({ x: 0.5, y: 0.5 }, geometry.bodyBounds);
void pointZoneDistance({ x: 0.5, y: 0.5 }, geometry.bodyBounds);
void transformGhostPoint({ x: 0.5, y: 0.5 }, 1);
