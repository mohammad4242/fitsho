import heroFallback from "../../assets/landing/hero-strength-fallback.jpg";
import heroVideo from "../../assets/landing/hero-strength.mp4";
import planFallback from "../../assets/landing/plan-focus-fallback.jpg";
import planVideo from "../../assets/landing/plan-focus.mp4";
import progressFallback from "../../assets/landing/progress-drive-fallback.jpg";
import progressVideo from "../../assets/landing/progress-drive.mp4";

export type LandingScene = {
  id: "strength" | "plan" | "progress";
  eyebrow: string;
  title: string;
  body: string;
  videoSrc: string;
  fallbackSrc: string;
  preload: "metadata" | "none";
};

export const landingScenes = [
  {
    id: "strength",
    eyebrow: "فیتشو، مسیر شخصی تو",
    title: "از امروز، قوی‌تر.",
    body: "برنامه‌ای روشن برای شروعی که واقعاً ادامه پیدا می‌کند.",
    videoSrc: heroVideo,
    fallbackSrc: heroFallback,
    preload: "metadata",
  },
  {
    id: "plan",
    eyebrow: "تمرین، متناسب با تو",
    title: "بدون حدس، با برنامه.",
    body: "هر جلسه با هدف، زمان و سطح آمادگی تو هماهنگ می‌شود.",
    videoSrc: planVideo,
    fallbackSrc: planFallback,
    preload: "none",
  },
  {
    id: "progress",
    eyebrow: "پیشرفت قابل دیدن",
    title: "هر تکرار، نزدیک‌تر.",
    body: "روندت را ببین، تمرینت را ادامه بده و نسخهٔ قوی‌تر خودت را بساز.",
    videoSrc: progressVideo,
    fallbackSrc: progressFallback,
    preload: "none",
  },
] as const satisfies readonly LandingScene[];
