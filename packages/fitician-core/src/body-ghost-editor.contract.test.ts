import {
  GHOST_EDITOR_DEFAULT_TRANSFORM,
  GHOST_EDITOR_OUTPUT,
  clampGhostPhotoTransform,
  containImageRect,
  createGhostPhotoRenderPlan,
  isGhostFramingWithinTolerance,
  privacyCropSourceYForView,
} from "./body-ghost-editor.js";

void GHOST_EDITOR_DEFAULT_TRANSFORM;
void GHOST_EDITOR_OUTPUT;
void clampGhostPhotoTransform(GHOST_EDITOR_DEFAULT_TRANSFORM);
void containImageRect({ width: 1, height: 1 }, { width: 1, height: 1 });
void createGhostPhotoRenderPlan(1200, 1800, GHOST_EDITOR_DEFAULT_TRANSFORM);
void isGhostFramingWithinTolerance(GHOST_EDITOR_DEFAULT_TRANSFORM);
void privacyCropSourceYForView(
  "front",
  1,
  GHOST_EDITOR_OUTPUT,
  GHOST_EDITOR_OUTPUT,
);
