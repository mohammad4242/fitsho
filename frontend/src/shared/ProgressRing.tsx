import type { CSSProperties } from "react";

type Props = { value: number; max: number; label?: string };

export function ProgressRing({ value, max, label }: Props) {
  const percent = max > 0 ? Math.max(0, Math.min(100, Math.round(value / max * 100))) : 0;
  return (
    <div
      className="fitsho-progress-ring"
      role="progressbar"
      aria-label={label ?? `${percent}%`}
      aria-valuemin={0}
      aria-valuenow={value}
      aria-valuemax={Math.max(0, max)}
      style={{ "--ring-progress": `${percent * 3.6}deg` } as CSSProperties}
    >
      <strong>{percent}%</strong>
    </div>
  );
}
