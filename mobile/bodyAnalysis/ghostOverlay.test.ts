import { expect, it } from "vitest";
import { ghostAssetCalibrationForView } from "@fitician/core/body-ghost";

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
  expect(layout.privacyLine.anchor.y).toBeCloseTo(0.180025);
  expect(layout.privacyLine.start.x).toBeCloseTo(0.1);
  expect(layout.privacyLine.end.x).toBeCloseTo(0.9);
  expect(layout.privacyLine.start.y).toBeCloseTo(0.180025);
  expect(layout.privacyLine.end.y).toBeCloseTo(0.180025);
});

it("mirrors only the side Ghost for the left profile", () => {
  const layout = getGhostOverlayLayout("side", 0.95, "left");
  const right = getGhostOverlayLayout("side", 0.95, "right");

  expect(layout.mirrored).toBe(true);
  expect(layout.privacyLine.anchor.x).toBe(0.5);
  expect(layout.privacyLine.anchor.y).toBe(right.privacyLine.anchor.y);
  expect(layout.privacyLine.start.x).toBeCloseTo(0.025);
  expect(layout.privacyLine.end.x).toBeCloseTo(0.975);
  expect(layout.assetCalibration).toEqual(right.assetCalibration);
});

it.each([
  ["male", "front", 0.10003125],
  ["male", "side", 0.10425],
  ["male", "back", 0.0159375],
  ["female", "front", 0.1098125],
  ["female", "side", 0.1099296875],
  ["female", "back", 0.0228125],
] as const)("places the %s %s privacy line on the Ghost visible top", (variant, view, expectedTop) => {
  const layout = getGhostOverlayLayout(view, 1, "right", variant);

  expect(layout.privacyLine.anchor.y).toBeCloseTo(expectedTop);
});

it.each([
  ["male", "front", 0.87, -0.071],
  ["male", "side", 0.88, -0.063],
  ["male", "back", 0.91, -0.103],
  ["female", "front", 0.78, -0.027],
  ["female", "side", 0.83, -0.025],
  ["female", "back", 0.94, -0.11],
] as const)("matches the web artwork calibration for %s/%s", (variant, view, scale, translateYRatio) => {
  expect(ghostAssetCalibrationForView(view, variant)).toEqual({ scale, translateYRatio });
});

it("keeps fixed artwork calibration when the user changes Ghost size", () => {
  const smaller = getGhostOverlayLayout("front", 0.75, "right", "male");
  const larger = getGhostOverlayLayout("front", 1.15, "right", "male");

  expect(smaller.assetCalibration).toEqual({ scale: 0.87, translateYRatio: -0.071 });
  expect(larger.assetCalibration).toEqual(smaller.assetCalibration);
});

it("never turns the Ghost into a body-shape rejection gate", () => {
  expect(getGhostOverlayLayout("back", 10).scale).toBe(1.15);
  expect(getGhostOverlayLayout("back", Number.NaN).scale).toBe(1);
});
