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

export type PerformanceLaunchCohort = {
  readonly apiLevel: number;
  readonly appVersion: string;
  readonly buildProfile: string;
  readonly cleanLaunches: number;
  readonly commit: string;
  readonly crashes: number;
  readonly deviceModel: string;
};

export type PerformanceMetricSummary = {
  readonly budget: number;
  readonly p95: number;
  readonly passed: boolean;
  readonly sampleCount: number;
  readonly unit: PerformanceUnit;
};

export type MobilePerformanceReport = {
  readonly accepted: boolean;
  readonly launchCohort: PerformanceLaunchCohort & {
    readonly crashFreeRate: number;
    readonly passed: boolean;
  };
  readonly metrics: Partial<Record<PerformanceMetric, PerformanceMetricSummary>>;
  readonly missingMetrics: readonly PerformanceMetric[];
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

export function buildMobilePerformanceReport(
  samples: readonly PerformanceMeasurement[],
  launchCohort: PerformanceLaunchCohort,
): MobilePerformanceReport {
  const metrics: Partial<Record<PerformanceMetric, PerformanceMetricSummary>> = {};
  const missingMetrics: PerformanceMetric[] = [];

  for (const metric of Object.keys(MOBILE_PERFORMANCE_BUDGETS) as PerformanceMetric[]) {
    const values = samples
      .filter((sample) => sample.metric === metric)
      .map((sample) => sample.value)
      .sort((left, right) => left - right);
    if (values.length === 0) {
      missingMetrics.push(metric);
      continue;
    }
    const p95 = percentile95(values);
    const budget = MOBILE_PERFORMANCE_BUDGETS[metric];
    metrics[metric] = {
      budget: budget.max,
      p95,
      passed: values.every((value) => assessPerformance(metric, value).passed),
      sampleCount: values.length,
      unit: budget.unit,
    };
  }

  const cohortValid = isValidLaunchCohort(launchCohort);
  const crashFreeRate = cohortValid && launchCohort.cleanLaunches > 0
    ? (launchCohort.cleanLaunches - launchCohort.crashes) / launchCohort.cleanLaunches
    : 0;
  const launchCohortPassed = cohortValid
    && launchCohort.cleanLaunches >= 100
    && crashFreeRate >= 0.995;
  const metricSummaries = Object.values(metrics);

  return {
    accepted: missingMetrics.length === 0
      && metricSummaries.every((summary) => summary.passed)
      && launchCohortPassed,
    launchCohort: {
      ...launchCohort,
      crashFreeRate,
      passed: launchCohortPassed,
    },
    metrics,
    missingMetrics,
  };
}

function percentile95(sortedValues: readonly number[]): number {
  const index = Math.max(0, Math.ceil(sortedValues.length * 0.95) - 1);
  return sortedValues[index] ?? 0;
}

function isValidLaunchCohort(cohort: PerformanceLaunchCohort): boolean {
  return Number.isSafeInteger(cohort.apiLevel)
    && cohort.apiLevel > 0
    && Number.isSafeInteger(cohort.cleanLaunches)
    && cohort.cleanLaunches > 0
    && Number.isSafeInteger(cohort.crashes)
    && cohort.crashes >= 0
    && cohort.crashes <= cohort.cleanLaunches
    && cohort.appVersion.trim().length > 0
    && cohort.buildProfile.trim().length > 0
    && cohort.commit.trim().length > 0
    && cohort.deviceModel.trim().length > 0;
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
