export const MEDIA_SWIPE_THRESHOLD = 48;
export const MEDIA_SWIPE_DIRECTION_RATIO = 1.2;

export function clampMediaIndex(index: number, itemCount: number): number {
  if (itemCount <= 0 || !Number.isFinite(index)) return 0;
  return Math.min(Math.max(Math.trunc(index), 0), itemCount - 1);
}

export function resolveMediaSwipeIndex(
  currentIndex: number,
  deltaX: number,
  deltaY: number,
  itemCount: number,
  startedInControls = false,
): number {
  const safeIndex = clampMediaIndex(currentIndex, itemCount);
  if (
    itemCount <= 1
    || startedInControls
    || !Number.isFinite(deltaX)
    || !Number.isFinite(deltaY)
    || Math.abs(deltaX) < MEDIA_SWIPE_THRESHOLD
    || Math.abs(deltaX) <= Math.abs(deltaY) * MEDIA_SWIPE_DIRECTION_RATIO
  ) {
    return safeIndex;
  }

  return clampMediaIndex(safeIndex + (deltaX < 0 ? 1 : -1), itemCount);
}
