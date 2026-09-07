import { validatePoseWithGhost } from "./body-ghost-pose.js";
import type { NormalizedBodyLandmark } from "./body-ghost-pose.js";

const pose: NormalizedBodyLandmark[] = Array.from({ length: 33 }, () => ({
  x: 0.5,
  y: 0.5,
  z: 0,
  visibility: 1,
}));

void validatePoseWithGhost({ view: "front", poses: [pose] });
