export type PerformanceUnit = "mb" | "ms" | "percent_per_hour";

export type PerformanceBudget = {
  readonly max: number;
  readonly unit: PerformanceUnit;
};

export const MOBILE_PERFORMANCE_BUDGETS = {
  battery_drain_per_hour: { max: 8, unit: "percent_per_hour" },
  cold_start: { max: 3_000, unit: "ms" },
  image_processing: { max: 1_500, unit: "ms" },
  large_list_render: { max: 250, unit: "ms" },
  memory_peak: { max: 200, unit: "mb" },
  screen_transition: { max: 300, unit: "ms" },
  upload: { max: 30_000, unit: "ms" },
  video_cache_hit: { max: 150, unit: "ms" },
} as const satisfies Record<string, PerformanceBudget>;

export type PerformanceMetric = keyof typeof MOBILE_PERFORMANCE_BUDGETS;

export type PerformanceMeasurement = {
  readonly budget: number;
  readonly metric: PerformanceMetric;
  readonly passed: boolean;
  readonly unit: PerformanceUnit;
  readonly value: number;
};

export type PerformanceClock = () => number;

export function monotonicNow(): number {
  return typeof globalThis.performance?.now === "function"
    ? globalThis.performance.now()
    : Date.now();
}

export function assessPerformance(
  metric: PerformanceMetric,
  value: number,
): PerformanceMeasurement {
  if (!Number.isFinite(value)) {
    throw new TypeError("Performance measurements must be finite");
  }
  if (value < 0) {
    throw new RangeError("Performance measurements must be non-negative");
  }
  const budget = MOBILE_PERFORMANCE_BUDGETS[metric];
  return {
    budget: budget.max,
    metric,
    passed: value <= budget.max,
    unit: budget.unit,
    value,
  };
}

export class MobilePerformanceRecorder {
  private readonly samples: PerformanceMeasurement[] = [];

  constructor(
    private readonly now: PerformanceClock = monotonicNow,
    private readonly maxSamples = 100,
  ) {
    if (!Number.isSafeInteger(maxSamples) || maxSamples <= 0) {
      throw new RangeError("Performance sample limit must be a positive integer");
    }
  }

  record(metric: PerformanceMetric, value: number): PerformanceMeasurement {
    const measurement = assessPerformance(metric, value);
    this.samples.push(measurement);
    if (this.samples.length > this.maxSamples) {
      this.samples.splice(0, this.samples.length - this.maxSamples);
    }
    return measurement;
  }

  measure<T>(metric: PerformanceMetric, operation: () => T): T {
    const startedAt = this.now();
    try {
      return operation();
    } finally {
      this.record(metric, this.now() - startedAt);
    }
  }

  async measureAsync<T>(metric: PerformanceMetric, operation: () => Promise<T>): Promise<T> {
    const startedAt = this.now();
    try {
      return await operation();
    } finally {
      this.record(metric, this.now() - startedAt);
    }
  }

  start(metric: PerformanceMetric): () => PerformanceMeasurement {
    const startedAt = this.now();
    let completed = false;
    return () => {
      if (completed) {
        throw new Error(`Performance measurement already completed: ${metric}`);
      }
      completed = true;
      return this.record(metric, this.now() - startedAt);
    };
  }

  getSamples(): readonly PerformanceMeasurement[] {
    return this.samples.slice();
  }
}

export const mobilePerformanceRecorder = new MobilePerformanceRecorder();

export function recordMemoryPeak(
  megabytes: number,
  recorder: MobilePerformanceRecorder = mobilePerformanceRecorder,
): PerformanceMeasurement {
  return recorder.record("memory_peak", megabytes);
}

export function recordBatteryDrain(
  percentPerHour: number,
  recorder: MobilePerformanceRecorder = mobilePerformanceRecorder,
): PerformanceMeasurement {
  return recorder.record("battery_drain_per_hour", percentPerHour);
}

const completeColdStartMeasurement = mobilePerformanceRecorder.start("cold_start");
let coldStartMeasurement: PerformanceMeasurement | null = null;

export function completeMobileColdStart(): PerformanceMeasurement {
  coldStartMeasurement ??= completeColdStartMeasurement();
  return coldStartMeasurement;
}
