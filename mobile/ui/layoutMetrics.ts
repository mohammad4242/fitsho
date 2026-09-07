import { fiticianTokens } from "./tokens";

export const TABLET_SHORTEST_SIDE = 600;

export interface ResponsiveLayout {
  readonly contentMaxWidth: number;
  readonly contentWidth: number;
  readonly height: number;
  readonly horizontalPadding: number;
  readonly isTablet: boolean;
  readonly readingMaxWidth: number;
  readonly readingWidth: number;
  readonly width: number;
}

export function getResponsiveLayout(width: number, height: number): ResponsiveLayout {
  const isTablet = Math.min(width, height) >= TABLET_SHORTEST_SIDE;
  const horizontalPadding = isTablet
    ? fiticianTokens.layout.tabletPadding
    : fiticianTokens.layout.screenPadding;
  const availableWidth = Math.max(0, width - horizontalPadding * 2);

  return {
    contentMaxWidth: fiticianTokens.layout.contentMaxWidth,
    contentWidth: Math.min(availableWidth, fiticianTokens.layout.contentMaxWidth),
    height,
    horizontalPadding,
    isTablet,
    readingMaxWidth: fiticianTokens.layout.readingMaxWidth,
    readingWidth: Math.min(availableWidth, fiticianTokens.layout.readingMaxWidth),
    width,
  };
}
