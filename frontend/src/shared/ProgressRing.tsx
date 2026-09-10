import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

type Props = {
  value: number;
  max: number;
  label?: string;
  color?: string;
  animateOnMount?: boolean;
};

export function ProgressRing({
  animateOnMount = false,
  color = "var(--fitsho-aqua)",
  value,
  max,
  label,
}: Props) {
  const percent = max > 0 ? Math.max(0, Math.min(100, Math.round(value / max * 100))) : 0;
  const [displayedPercent, setDisplayedPercent] = useState(animateOnMount ? 0 : percent);

  useEffect(() => {
    if (!animateOnMount) {
      setDisplayedPercent(percent);
      return;
    }
    const frame = requestAnimationFrame(() => setDisplayedPercent(percent));
    return () => cancelAnimationFrame(frame);
  }, [animateOnMount, percent]);

  return (
    <div
      className={`fitsho-progress-ring${animateOnMount ? " fitsho-progress-ring--mount-animated" : ""}`}
      role="progressbar"
      aria-label={label ?? `${percent}%`}
      aria-valuemin={0}
      aria-valuenow={value}
      aria-valuemax={Math.max(0, max)}
      style={{
        "--ring-color": color,
        "--ring-progress": `${displayedPercent * 3.6}deg`,
      } as CSSProperties}
    >
      <strong>{percent}%</strong>
    </div>
  );
}
