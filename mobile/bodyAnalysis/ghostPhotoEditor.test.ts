import { expect, it } from "vitest";

import { GHOST_EDITOR_DEFAULT_TRANSFORM } from "@fitician/core/body-ghost-editor";

import {
  applyGhostPhotoDrag,
  applyGhostPhotoPinchGesture,
  createGhostPhotoPinchGesture,
  type GhostPhotoPoint,
  type GhostPhotoStageSize,
} from "./ghostPhotoEditor";

const stage: GhostPhotoStageSize = { height: 450, width: 300 };

it("moves the photo in normalized stage coordinates", () => {
  expect(applyGhostPhotoDrag(
    GHOST_EDITOR_DEFAULT_TRANSFORM,
    { x: 90, y: -225 },
    stage,
  )).toEqual({
    ...GHOST_EDITOR_DEFAULT_TRANSFORM,
    translateX: 0.3,
    translateY: -0.5,
  });
});

it("uses the two-finger midpoint, distance, and angle for one stable transform", () => {
  const initialFirst: GhostPhotoPoint = { x: 100, y: 100 };
  const initialSecond: GhostPhotoPoint = { x: 200, y: 100 };
  const gesture = createGhostPhotoPinchGesture(
    initialFirst,
    initialSecond,
    GHOST_EDITOR_DEFAULT_TRANSFORM,
    stage,
  );

  const next = applyGhostPhotoPinchGesture(
    gesture,
    { x: 90, y: 80 },
    { x: 230, y: 120 },
  );

  expect(next.translateX).toBeCloseTo(10 / 300);
  expect(next.translateY).toBeCloseTo(0);
  expect(next.scale).toBeCloseTo(Math.hypot(140, 40) / 100);
  expect(next.rotation).toBeCloseTo(Math.atan2(40, 140) * 180 / Math.PI);
});

it("clamps drag and pinch output to the shared editor contract", () => {
  const gesture = createGhostPhotoPinchGesture(
    { x: 0, y: 0 },
    { x: 100, y: 0 },
    GHOST_EDITOR_DEFAULT_TRANSFORM,
    stage,
  );

  expect(applyGhostPhotoDrag(
    { ...GHOST_EDITOR_DEFAULT_TRANSFORM, translateX: 0.4, translateY: -0.4 },
    { x: 1000, y: -1000 },
    stage,
  )).toMatchObject({ translateX: 0.5, translateY: -0.5 });
  expect(applyGhostPhotoPinchGesture(
    gesture,
    { x: 0, y: 0 },
    { x: 10000, y: 0 },
  )).toMatchObject({ scale: 2.5 });
});
