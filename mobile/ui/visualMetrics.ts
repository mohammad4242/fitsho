export interface RingGeometry {
  readonly circumference: number;
  readonly dashOffset: number;
  readonly radius: number;
}

export function clampProgress(progress: number): number {
  if (!Number.isFinite(progress)) return 0;
  return Math.min(1, Math.max(0, progress));
}

export function calculateRingGeometry(size: number, strokeWidth: number, progress: number): RingGeometry {
  const radius = Math.max(0, (size - strokeWidth) / 2);
  const circumference = 2 * Math.PI * radius;
  return {
    circumference,
    dashOffset: circumference * (1 - clampProgress(progress)),
    radius,
  };
}
