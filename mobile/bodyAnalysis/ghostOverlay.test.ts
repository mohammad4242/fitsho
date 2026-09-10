import { expect, it } from "vitest";

import {
  getGhostOverlayLayout,
  resolveGhostOverlayVariant,
} from "./ghostOverlay";

it.each([
  ["male", "male"],
  ["female", "female"],
  [undefined, "neutral"],
  [null, "neutral"],
  ["other", "neutral"],
  ["prefer_not_to_say", "neutral"],
] as const)("resolves the %s Ghost asset variant", (sex, expected) => {
  expect(resolveGhostOverlayVariant(sex)).toBe(expected);
});

it("uses the shared front privacy-line golden vector", () => {
  const layout = getGhostOverlayLayout("front", 0.8);

  expect(layout).toMatchObject({ mirrored: false, scale: 0.8, view: "front" });
  expect(layout.privacyLine.anchor.x).toBeCloseTo(0.5);
  expect(layout.privacyLine.anchor.y).toBeCloseTo(0.164);
  expect(layout.privacyLine.start.x).toBeCloseTo(0.1);
  expect(layout.privacyLine.end.x).toBeCloseTo(0.9);
  expect(layout.privacyLine.start.y).toBeCloseTo(0.164);
  expect(layout.privacyLine.end.y).toBeCloseTo(0.164);
});

it("mirrors only the side Ghost for the left profile", () => {
  const layout = getGhostOverlayLayout("side", 0.95, "left");

  expect(layout.mirrored).toBe(true);
  expect(layout.privacyLine.anchor.x).toBe(0.5);
  expect(layout.privacyLine.start.x).toBeCloseTo(0.025);
  expect(layout.privacyLine.end.x).toBeCloseTo(0.975);
});

it.each([
  ["male", "front", 0.08],
  ["male", "side", 0.08],
  ["male", "back", 0.08],
  ["female", "front", 0.045],
  ["female", "side", 0.06],
  ["female", "back", 0.055],
] as const)("places the %s %s privacy line on the Ghost neck", (variant, view, expectedTop) => {
  const layout = getGhostOverlayLayout(view, 1, "right", variant);

  expect(layout.privacyLine.anchor.y).toBeCloseTo(expectedTop);
});

it("never turns the Ghost into a body-shape rejection gate", () => {
  expect(getGhostOverlayLayout("back", 10).scale).toBe(1.15);
  expect(getGhostOverlayLayout("back", Number.NaN).scale).toBe(1);
});
