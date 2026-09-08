import { fiticianTokens } from "./tokens";

export const ACCESSIBILITY_MIN_TOUCH_TARGET = fiticianTokens.layout.minimumTouchTarget;

export const ACCESSIBILITY_COLOR_PAIRS = [
  { background: fiticianTokens.colors.canvas, foreground: fiticianTokens.colors.ink },
  { background: fiticianTokens.colors.canvas, foreground: fiticianTokens.colors.muted },
  { background: fiticianTokens.colors.canvas, foreground: fiticianTokens.colors.aqua },
  { background: fiticianTokens.colors.canvas, foreground: fiticianTokens.colors.coral },
  { background: fiticianTokens.colors.canvas, foreground: fiticianTokens.colors.amber },
] as const;

function channel(value: string): number {
  const parsed = Number.parseInt(value, 16) / 255;
  return parsed <= 0.03928 ? parsed / 12.92 : ((parsed + 0.055) / 1.055) ** 2.4;
}

function relativeLuminance(color: string): number {
  const match = /^#([0-9a-f]{6})$/iu.exec(color);
  if (match === null) {
    throw new TypeError("Accessibility colors must be six-digit hexadecimal values");
  }
  const value = match[1];
  return 0.2126 * channel(value.slice(0, 2))
    + 0.7152 * channel(value.slice(2, 4))
    + 0.0722 * channel(value.slice(4, 6));
}

export function contrastRatio(foreground: string, background: string): number {
  const foregroundLuminance = relativeLuminance(foreground);
  const backgroundLuminance = relativeLuminance(background);
  const lighter = Math.max(foregroundLuminance, backgroundLuminance);
  const darker = Math.min(foregroundLuminance, backgroundLuminance);
  return (lighter + 0.05) / (darker + 0.05);
}

export function meetsContrast(
  foreground: string,
  background: string,
  minimumRatio = 4.5,
): boolean {
  if (!Number.isFinite(minimumRatio) || minimumRatio <= 0) {
    throw new RangeError("Accessibility contrast threshold must be positive");
  }
  return contrastRatio(foreground, background) >= minimumRatio;
}

export function meetsTouchTarget(width: number, height: number): boolean {
  return Number.isFinite(width)
    && Number.isFinite(height)
    && width >= ACCESSIBILITY_MIN_TOUCH_TARGET
    && height >= ACCESSIBILITY_MIN_TOUCH_TARGET;
}
