import { type ReactNode, useEffect, useRef } from "react";

import {
  mobilePerformanceRecorder,
  monotonicNow,
  type MobilePerformanceRecorder,
  type PerformanceClock,
  type PerformanceMetric,
} from "./performance";

export interface PerformanceMeasuredCommitProps {
  readonly children: ReactNode;
  readonly metric: PerformanceMetric;
  readonly now?: PerformanceClock;
  readonly recorder?: MobilePerformanceRecorder;
}

export function PerformanceMeasuredCommit({
  children,
  metric,
  now = monotonicNow,
  recorder = mobilePerformanceRecorder,
}: PerformanceMeasuredCommitProps) {
  const startedAt = useRef(now());

  useEffect(() => {
    recorder.record(metric, now() - startedAt.current);
  }, [metric, now, recorder]);

  return children;
}
