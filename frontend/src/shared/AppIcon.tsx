import type { ReactNode } from "react";

export type IconName =
  | "home" | "dumbbell" | "nutrition" | "progress" | "more"
  | "arrow" | "profile" | "camera" | "catalogue" | "settings"
  | "body" | "target" | "language" | "logout" | "chevron"
  | "document" | "feedback";

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
  };

  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}
