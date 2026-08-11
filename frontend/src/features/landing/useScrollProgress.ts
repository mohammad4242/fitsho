import { useEffect, useRef } from "react";

type ScrollProgressTarget = "cinematic" | "process" | "body";

const clamp = (value: number) => Math.min(1, Math.max(0, value));
const range = (value: number, start: number, end: number) => clamp((value - start) / (end - start));
const windowed = (value: number, enterStart: number, enterEnd: number, exitStart: number, exitEnd: number) => (
  Math.min(range(value, enterStart, enterEnd), 1 - range(value, exitStart, exitEnd))
);

export function useScrollProgress<T extends HTMLElement>(
  target: ScrollProgressTarget,
  reducedMotion: boolean,
) {
  const ref = useRef<T>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    let frame = 0;
    const set = (name: string, value: number) => {
      element.style.setProperty(name, clamp(value).toFixed(4));
    };

    const render = () => {
      frame = 0;
      const rect = element.getBoundingClientRect();
      const distance = Math.max(1, element.offsetHeight - window.innerHeight);
      const progress = reducedMotion ? 1 : clamp(-rect.top / distance);

      if (target === "cinematic") {
        set("--hero-progress", 1 - range(progress, 0.04, 0.2));
        set("--cinema-progress", range(progress, 0.08, 0.54));
        set("--training-progress", windowed(progress, 0.18, 0.29, 0.45, 0.56));
        set("--training-seal", range(progress, 0.27, 0.41));
        set("--nutrition-progress", windowed(progress, 0.5, 0.62, 0.77, 0.87));
        set("--nutrition-seal", range(progress, 0.6, 0.74));
        set("--video-progress", 1 - range(progress, 0.82, 1));
      } else if (target === "process") {
        const starts = [0, 0.25, 0.5, 0.75];
        starts.forEach((start, index) => {
          set(`--step-${index}`, range(progress, start, start + 0.14));
          set(`--copy-${index}`, range(progress, start + 0.14, start + 0.18));
          if (index < 3) set(`--line-${index}`, range(progress, start + 0.18, start + 0.25));
        });
      } else {
        set("--body-depth", range(progress, 0, 1));
      }
    };

    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(render);
    };

    render();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [reducedMotion, target]);

  return ref;
}
