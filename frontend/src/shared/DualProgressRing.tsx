import type { CSSProperties } from "react";

type Props = {
  primaryValue: number;
  secondaryValue: number;
  total: number;
  label?: string;
};

export function DualProgressRing({ primaryValue, secondaryValue, total, label }: Props) {
  const combined = primaryValue + secondaryValue;
  const percent = total > 0 ? Math.max(0, Math.min(100, Math.round((combined / total) * 100))) : 0;
  const primaryDeg = total > 0 ? Math.max(0, Math.min(360, (primaryValue / total) * 360)) : 0;
  const secondaryDeg = total > 0 ? Math.max(primaryDeg, Math.min(360, (combined / total) * 360)) : 0;

  return (
    <div
      className="fitsho-progress-ring fitsho-progress-ring--dual"
      role="progressbar"
      aria-label={label ?? `${percent}%`}
      aria-valuemin={0}
      aria-valuenow={Math.round(combined)}
      aria-valuemax={Math.max(0, Math.round(total))}
      style={
        {
          "--ring-deg-1": `${primaryDeg.toFixed(1)}deg`,
          "--ring-deg-2": `${secondaryDeg.toFixed(1)}deg`,
        } as CSSProperties
      }
    >
      <strong>{percent}%</strong>
    </div>
  );
}
