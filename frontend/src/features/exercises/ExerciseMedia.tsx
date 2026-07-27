import { useState } from "react";

import type { MediaType } from "./types";

const placeholderPath = "/exercises/exercise-placeholder.svg";

type ExerciseMediaProps = {
  path: string;
  name: string;
  mediaType: MediaType;
};

export function ExerciseMedia({ path, name, mediaType }: ExerciseMediaProps) {
  const [failed, setFailed] = useState(false);
  const alt = localizedAlt(name);

  if (mediaType === "placeholder" || failed || !path) {
    return <img src={placeholderPath} alt={alt} />;
  }

  if (mediaType === "video") {
    return (
      <video
        src={path}
        aria-label={alt}
        controls
        muted
        playsInline
        preload="metadata"
        onError={() => setFailed(true)}
      />
    );
  }

  return <img src={path} alt={alt} onError={() => setFailed(true)} />;
}

function localizedAlt(name: string): string {
  return /[\u0600-\u06ff]/.test(name)
    ? `نمایش حرکت ${name}`
    : `${name} demonstration`;
}
