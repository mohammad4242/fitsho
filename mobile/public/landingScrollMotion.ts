export interface CinematicMotion {
  readonly cinema: number;
  readonly hero: number;
  readonly meal: number;
  readonly mealResult: number;
  readonly mealScan: number;
  readonly nutrition: number;
  readonly nutritionSeal: number;
  readonly training: number;
  readonly trainingSeal: number;
  readonly video: number;
}

export interface ProcessStepMotion {
  readonly connector: number;
  readonly copy: number;
  readonly ring: number;
}

export function clampProgress(value: number) {
  "worklet";
  return Math.min(1, Math.max(0, value));
}

export function progressBetween(value: number, start: number, end: number) {
  "worklet";
  return clampProgress((value - start) / Math.max(0.0001, end - start));
}

export function easedProgressBetween(value: number, start: number, end: number) {
  "worklet";
  const progress = progressBetween(value, start, end);
  return progress * progress * (3 - 2 * progress);
}

export function windowedProgress(
  value: number,
  enterStart: number,
  enterEnd: number,
  exitStart: number,
  exitEnd: number,
) {
  "worklet";
  return Math.min(
    easedProgressBetween(value, enterStart, enterEnd),
    1 - easedProgressBetween(value, exitStart, exitEnd),
  );
}

export function sectionProgress(
  offset: number,
  start: number,
  height: number,
  viewportHeight: number,
) {
  "worklet";
  return progressBetween(offset, start, start + Math.max(1, height - viewportHeight));
}

export function cinematicMotion(progress: number): CinematicMotion {
  "worklet";
  return {
    cinema: easedProgressBetween(progress, 0.06, 0.58),
    hero: 1 - easedProgressBetween(progress, 0.04, 0.16),
    meal: easedProgressBetween(progress, 0.64, 0.72),
    mealResult: easedProgressBetween(progress, 0.86, 0.94),
    mealScan: easedProgressBetween(progress, 0.73, 0.87),
    nutrition: windowedProgress(progress, 0.38, 0.46, 0.61, 0.72),
    nutritionSeal: easedProgressBetween(progress, 0.49, 0.57),
    training: windowedProgress(progress, 0.14, 0.21, 0.33, 0.44),
    trainingSeal: easedProgressBetween(progress, 0.23, 0.31),
    video: 1 - easedProgressBetween(progress, 0.76, 1),
  };
}

export function processStepMotion(progress: number, index: number): ProcessStepMotion {
  "worklet";
  const start = index * 0.25;
  return {
    connector: easedProgressBetween(progress, start + 0.18, start + 0.25),
    copy: easedProgressBetween(progress, start + 0.14, start + 0.18),
    ring: easedProgressBetween(progress, start, start + 0.14),
  };
}
