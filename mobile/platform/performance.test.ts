import { expect, it } from "vitest";

import {
  MOBILE_PERFORMANCE_BUDGETS,
  MobilePerformanceRecorder,
  assessPerformance,
  recordBatteryDrain,
  recordMemoryPeak,
} from "./performance";

it("evaluates duration and resource measurements against explicit mobile budgets", () => {
  expect(assessPerformance("screen_transition", 300)).toEqual({
    budget: 300,
    metric: "screen_transition",
    passed: true,
    unit: "ms",
    value: 300,
  });
  expect(assessPerformance("screen_transition", 301).passed).toBe(false);
  expect(assessPerformance("memory_peak", 199).passed).toBe(true);
  expect(assessPerformance("battery_drain_per_hour", 8).passed).toBe(true);
  expect(MOBILE_PERFORMANCE_BUDGETS.large_list_render).toEqual({ max: 250, unit: "ms" });
});

it("records synchronous and asynchronous workloads without retaining payloads", async () => {
  let now = 1_000;
  const recorder = new MobilePerformanceRecorder(() => now);

  const value = recorder.measure("large_list_render", () => {
    now += 120;
    return "rendered";
  });
  await recorder.measureAsync("image_processing", async () => {
    now += 900;
    return { uri: "file:///private/body.jpg" };
  });

  expect(value).toBe("rendered");
  expect(recorder.getSamples()).toEqual([
    {
      budget: 250,
      metric: "large_list_render",
      passed: true,
      unit: "ms",
      value: 120,
    },
    {
      budget: 1_500,
      metric: "image_processing",
      passed: true,
      unit: "ms",
      value: 900,
    },
  ]);
  expect(JSON.stringify(recorder.getSamples())).not.toContain("body.jpg");
});

it("keeps only the bounded recent measurement window", () => {
  const recorder = new MobilePerformanceRecorder(() => 0, 2);

  recorder.record("video_cache_hit", 10);
  recorder.record("upload", 20);
  recorder.record("cold_start", 30);

  expect(recorder.getSamples().map((sample) => sample.metric)).toEqual([
    "upload",
    "cold_start",
  ]);
});

it("rejects invalid measurements before they reach the report", () => {
  expect(() => assessPerformance("memory_peak", -1)).toThrow("non-negative");
  expect(() => assessPerformance("memory_peak", Number.NaN)).toThrow("finite");
});

it("records resource measurements with the matching unit budget", () => {
  const recorder = new MobilePerformanceRecorder(() => 0);

  expect(recordMemoryPeak(128, recorder)).toEqual({
    budget: 200,
    metric: "memory_peak",
    passed: true,
    unit: "mb",
    value: 128,
  });
  expect(recordBatteryDrain(9, recorder)).toEqual({
    budget: 8,
    metric: "battery_drain_per_hour",
    passed: false,
    unit: "percent_per_hour",
    value: 9,
  });
});
