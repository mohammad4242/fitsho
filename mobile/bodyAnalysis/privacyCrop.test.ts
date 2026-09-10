import { expect, it } from "vitest";

import { GHOST_EDITOR_OUTPUT } from "@fitician/core/body-ghost-editor";

import {
  bodyPhotoPrivacyLine,
  createBodyPhotoPrivacyCropPlan,
} from "./privacyCrop";
import { getGhostOverlayLayout } from "./ghostOverlay";

const sourceSize = { height: 2400, width: 1600 };

it.each([
  ["front", 192],
  ["side", 192],
  ["back", 192],
] as const)("maps the visible %s line to the shared encoded crop", (view, expectedSourceY) => {
  const plan = createBodyPhotoPrivacyCropPlan({
    sourceSize,
    view,
  });

  expect(plan.sourceCropY).toBe(expectedSourceY);
  expect(plan.outputHeight).toBe(sourceSize.height - expectedSourceY);
  expect(plan.visibleLineDisplayY).toBeCloseTo(
    bodyPhotoPrivacyLine(view).anchor.y * GHOST_EDITOR_OUTPUT.height,
  );
});

it("uses the same line geometry for the native overlay and crop plan", () => {
  const overlay = getGhostOverlayLayout("front", 0.8);
  const plan = createBodyPhotoPrivacyCropPlan({
    ghostScale: 0.8,
    sourceSize,
    view: "front",
  });

  expect(plan.visibleLine.anchor).toEqual(overlay.privacyLine.anchor);
  expect(plan.visibleLine.start).toEqual(overlay.privacyLine.start);
  expect(plan.visibleLine.end).toEqual(overlay.privacyLine.end);
});

it("keeps a mirrored side guide on the same horizontal crop boundary", () => {
  const right = createBodyPhotoPrivacyCropPlan({
    sideProfile: "right",
    sourceSize,
    view: "side",
  });
  const left = createBodyPhotoPrivacyCropPlan({
    sideProfile: "left",
    sourceSize,
    view: "side",
  });

  expect(left.sourceCropY).toBe(right.sourceCropY);
  expect(left.visibleLine.anchor.y).toBe(right.visibleLine.anchor.y);
  expect(left.visibleLine.anchor.x).toBe(right.visibleLine.anchor.x);
});

it("uses the selected Ghost variant neck line for the encoded crop", () => {
  const plan = createBodyPhotoPrivacyCropPlan({
    ghostVariant: "female",
    sourceSize,
    view: "front",
  });

  expect(plan.visibleLine.anchor.y).toBeCloseTo(0.045);
  expect(plan.sourceCropY).toBe(108);
});

it("rejects invalid source dimensions before any crop can be encoded", () => {
  expect(() => createBodyPhotoPrivacyCropPlan({
    sourceSize: { height: 0, width: 1600 },
    view: "front",
  })).toThrow("positive");
});
