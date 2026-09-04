import type { ReactNode } from "react";

export type IconName =
  | "home" | "dumbbell" | "nutrition" | "progress" | "more"
  | "arrow" | "profile" | "camera" | "catalogue" | "settings"
  | "body" | "target" | "language" | "logout" | "chevron"
  | "document" | "feedback" | "lock"
  | "calendar" | "scale" | "ruler" | "gender" | "flame"
  | "award" | "clock" | "zap" | "shield" | "sparkles";

type Props = {
  name: IconName;
  className?: string;
};

export function AppIcon({ name, className }: Props) {
  const paths: Record<IconName, ReactNode> = {
    home: <><path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9M9 20v-6h6v6"/></>,
    dumbbell: <><path d="M7 8v8M4.5 9.5v5M2.5 11v2M17 8v8M19.5 9.5v5M21.5 11v2M7 12h10"/></>,
    nutrition: <><path d="M12 21c5-3 7-7 7-11a7 7 0 0 0-14 0c0 4 2 8 7 11Z"/><path d="M8 12c3 0 5-2 5-5M12 21V11"/></>,
    progress: <><path d="M4 19V5M4 19h16"/><path d="m7 15 4-4 3 2 5-6"/></>,
    more: <><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></>,
    arrow: <><path d="m15 18-6-6 6-6"/></>,
    profile: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    camera: <><path d="M4 7h4l2-3h4l2 3h4v13H4Z"/><circle cx="12" cy="13" r="4"/></>,
    catalogue: <><path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/></>,
    body: <><circle cx="12" cy="5" r="2"/><path d="M8 9c1-1 2-2 4-2s3 1 4 2l-1 5 2 7M9 14 7 21M9 10l-3 5M15 10l3 5"/></>,
    target: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></>,
    language: <><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/></>,
    logout: <><path d="M10 5H5v14h5M14 8l4 4-4 4M8 12h10"/></>,
    chevron: <><path d="m9 18 6-6-6-6"/></>,
    document: <><path d="M6 3h8l4 4v14H6Z"/><path d="M14 3v5h4M9 13h6M9 17h4"/></>,
    feedback: <><path d="M4 5h16v12H9l-5 4Z"/><path d="m9 11 2 2 4-5"/></>,
    lock: <><rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></>,
    calendar: <><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></>,
    scale: <><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="12" cy="8" r="2.5"/><path d="m12 8 1.5-1.5"/></>,
    ruler: <><path d="m21.3 8.7-6-6a2 2 0 0 0-2.8 0L2.7 12.5a2 2 0 0 0 0 2.8l6 6a2 2 0 0 0 2.8 0l9.8-9.8a2 2 0 0 0 0-2.8Z"/><path d="m7.5 10.5 2 2M10.5 7.5 12 9M13.5 4.5 15 6M4.5 13.5 6 15"/></>,
    gender: <><circle cx="9" cy="9" r="4"/><path d="m12 6 6-3M15 3h3v3M9 13v7M6 17h6"/></>,
    flame: <><path d="M8.5 14.5A2.5 2.5 0 0 0 11 17c1.38 0 2.5-1.12 2.5-2.5 0-.61-.22-1.18-.6-1.61L12 11.8l-.9 1.09c-.38.43-.6 1-.6 1.61z"/><path d="M12 2c1 3 4 5.5 4 9.5a6 6 0 1 1-12 0c0-3.5 2.5-6.5 4.5-8 0 2 1.5 3.5 3.5 3.5.5-2 0-3.5 0-5z"/></>,
    award: <><circle cx="12" cy="8" r="5"/><path d="m8.21 13.89-1.21 7.11 5-3 5 3-1.21-7.11"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    zap: <><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></>,
    shield: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></>,
    sparkles: <><path d="m12 3-1.9 4.1L6 9l4.1 1.9L12 15l1.9-4.1L18 9l-4.1-1.9zM19 16l-.9 1.9L16 19l2.1.9.9 2.1.9-2.1L22 19l-2.1-.9z"/></>,
  };

  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}
