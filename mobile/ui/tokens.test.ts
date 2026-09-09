import { expect, it } from "vitest";

import { fiticianTokens } from "./tokens";

it("preserves the Fitsho dark petrol palette for native Fitician", () => {
  expect(fiticianTokens.colors).toMatchObject({
    amber: "#f2b85b",
    aqua: "#50dfce",
    canvas: "#020607",
    coral: "#f67859",
    ink: "#e8f4f1",
    muted: "#94aba5",
    petrol: "#091817",
    surface: "#081211",
    teal: "#0e201e",
  });
  expect(fiticianTokens.colors.line).toBe("rgba(232,244,241,0.12)");
  expect(fiticianTokens.colors.surfaceTranslucent).toBe("rgba(16,30,28,0.78)");
  expect(fiticianTokens.colors.mediaOverlay).toBe("rgba(2,6,7,0.72)");
  expect(fiticianTokens.colors.warningSurface).toBe("rgba(242,184,91,0.12)");
});

it("exposes typed native spacing, radii, typography, motion, and layout tokens", () => {
  expect(fiticianTokens.spacing).toEqual({
    1: 4,
    2: 8,
    3: 12,
    4: 16,
    5: 24,
    6: 32,
    7: 48,
    8: 72,
  });
  expect(fiticianTokens.radii.card).toBe(18);
  expect(fiticianTokens.radii.pill).toBe(999);
  expect(fiticianTokens.typography.fontFamily).toEqual({
    bodyEnglish: "Sora",
    bodyPersian: "Vazirmatn",
    displayEnglish: "Sora",
    displayPersian: "Lalezar",
  });
  expect(fiticianTokens.motion).toMatchObject({ fastMs: 160, mediumMs: 260 });
  expect(fiticianTokens.typography.fontSize.display).toBe(38);
  expect(fiticianTokens.iconSize).toMatchObject({ sm: 18, md: 22, lg: 28 });
  expect(fiticianTokens.layout.minimumTouchTarget).toBe(48);
});
