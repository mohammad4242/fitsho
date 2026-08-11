import { useEffect, useState } from "react";

const reducedMotionRequested = () => typeof window.matchMedia === "function"
  && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function useSynchronizedProgress(durationMs = 900) {
  const [progress, setProgress] = useState(() => reducedMotionRequested() ? 1 : 0);

  useEffect(() => {
    if (reducedMotionRequested() || durationMs <= 0) {
      setProgress(1);
      return;
    }

    let frameId = 0;
    let startTime: number | null = null;

    const animate = (timestamp: number) => {
      startTime ??= timestamp;
      const linearProgress = Math.min(1, (timestamp - startTime) / durationMs);
      const easedProgress = 1 - (1 - linearProgress) ** 3;
      setProgress(linearProgress === 1 ? 1 : easedProgress);
      if (linearProgress < 1) frameId = requestAnimationFrame(animate);
    };

    frameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameId);
  }, [durationMs]);

  return progress;
}
