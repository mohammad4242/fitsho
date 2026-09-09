import { expect, it } from "vitest";

import { getResponsiveLayout } from "./layoutMetrics";

it("uses compact gutters for phones", () => {
  expect(getResponsiveLayout(390, 844)).toMatchObject({
    horizontalPadding: 16,
    isTablet: false,
  });
});

it("keeps the compact phone gutter across the supported parity widths", () => {
  for (const width of [360, 390, 430]) {
    expect(getResponsiveLayout(width, 844)).toMatchObject({
      horizontalPadding: 16,
      isTablet: false,
    });
  }
});

it("uses tablet gutters and preserves the reading width on large screens", () => {
  expect(getResponsiveLayout(1024, 768)).toMatchObject({
    contentMaxWidth: 1312,
    horizontalPadding: 32,
    isTablet: true,
    readingMaxWidth: 1088,
  });
});

it("classifies a narrow landscape device by its shortest dimension", () => {
  expect(getResponsiveLayout(844, 390).isTablet).toBe(false);
});
