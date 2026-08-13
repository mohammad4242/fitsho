import { useEffect, useState } from "react";

import "./MealThumbnail.css";

type Props = {
  imageUrl: string | null | undefined;
  alt: string;
  fallbackLabel: string;
  className?: string;
};

export function MealThumbnail({ imageUrl, alt, fallbackLabel, className = "" }: Props) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [imageUrl]);
  const classes = `meal-thumbnail ${className}`.trim();

  if (!imageUrl || failed) {
    return (
      <div aria-label={fallbackLabel} className={`${classes} meal-thumbnail--fallback`} role="img">
        <svg aria-hidden="true" viewBox="0 0 48 48">
          <circle cx="24" cy="25" r="12" />
          <circle cx="24" cy="25" r="6" />
          <path d="M9 10v11m4-11v11m-2-4h4M38 10v28" />
        </svg>
      </div>
    );
  }

  return <img alt={alt} className={classes} onError={() => setFailed(true)} src={imageUrl} />;
}
