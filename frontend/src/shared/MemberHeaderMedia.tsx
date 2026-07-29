import { useEffect, useRef, useState } from "react";

type MemberHeaderMediaProps = {
  imageSrc: string;
  videoSrc?: string;
  className?: string;
};

function getReducedMotionPreference() {
  return typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function MemberHeaderMedia({ imageSrc, videoSrc, className }: MemberHeaderMediaProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [reducedMotion, setReducedMotion] = useState(getReducedMotionPreference);
  const [visible, setVisible] = useState(false);
  const [videoError, setVideoError] = useState(false);
  const showVideo = Boolean(videoSrc) && !reducedMotion && !videoError;

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;

    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => setReducedMotion(query.matches);
    query.addEventListener?.("change", updatePreference);
    return () => query.removeEventListener?.("change", updatePreference);
  }, []);

  useEffect(() => {
    if (!showVideo || !containerRef.current) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.1 });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [showVideo]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (showVideo && visible) {
      void Promise.resolve(video.play()).catch(() => setVideoError(true));
      return;
    }

    video.pause();
  }, [showVideo, visible]);

  return (
    <div ref={containerRef} className={["member-header-media", className].filter(Boolean).join(" ")} aria-hidden="true">
      {showVideo ? (
        <video
          ref={videoRef}
          className="member-header-media__asset"
          data-testid="member-header-video"
          muted
          playsInline
          preload="metadata"
          poster={imageSrc}
          onError={() => setVideoError(true)}
        >
          <source src={videoSrc} type="video/mp4" />
        </video>
      ) : (
        <img className="member-header-media__asset" data-testid="member-header-image" src={imageSrc} alt="" />
      )}
      <div className="member-header-media__veil" />
    </div>
  );
}
