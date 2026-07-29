import { useEffect, useRef, useState } from "react";

import type { LandingScene } from "./landingContent";

type LandingVideoProps = {
  scene: LandingScene;
  active: boolean;
  reducedMotion: boolean;
};

export function LandingVideo({ scene, active, reducedMotion }: LandingVideoProps) {
  const [hasVideoError, setHasVideoError] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const showFallback = reducedMotion || hasVideoError;

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (active && !showFallback) {
      void video.play().catch(() => setHasVideoError(true));
      return;
    }

    video.pause();
  }, [active, showFallback]);

  if (showFallback) {
    return <img className="landing-scene__media" src={scene.fallbackSrc} alt={scene.title} />;
  }

  return (
    <video
      ref={videoRef}
      className="landing-scene__media"
      data-testid={`landing-video-${scene.id}`}
      muted
      loop
      playsInline
      preload={scene.preload}
      poster={scene.fallbackSrc}
      onError={() => setHasVideoError(true)}
    >
      <source src={scene.videoSrc} type="video/mp4" />
    </video>
  );
}
