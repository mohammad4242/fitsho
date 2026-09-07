export const GHOST_SCALE_MIN = 0.75;
export const GHOST_SCALE_MAX = 1.15;
export const GHOST_SCALE_STEP = 0.05;

export const PHOTO_SCALE_MIN = 0.75;
export const PHOTO_SCALE_MAX = 2.5;
export const PHOTO_SCALE_STEP = 0.1;

export function stepGhostScale(current: number, delta: number): number {
  return Math.min(
    GHOST_SCALE_MAX,
    Math.max(GHOST_SCALE_MIN, Math.round((current + delta) * 100) / 100),
  );
}
