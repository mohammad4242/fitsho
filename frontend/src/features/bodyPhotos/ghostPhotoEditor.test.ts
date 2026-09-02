import { describe, expect, it } from "vitest";

import {
  GHOST_EDITOR_DEFAULT_TRANSFORM,
  GHOST_EDITOR_OUTPUT,
  clampGhostPhotoTransform,
  createGhostPhotoRenderPlan,
  ghostPhotoTransformStyle,
  isGhostFramingWithinTolerance,
  type GhostPhotoCanvasRuntime,
} from "./ghostPhotoEditor";

describe("ghost photo transform", () => {
  it("starts centered with a neutral transform", () => {
    expect(GHOST_EDITOR_DEFAULT_TRANSFORM).toEqual({
      offsetX: 0,
      offsetY: 0,
      scale: 1,
      rotation: 0,
    });
    expect(ghostPhotoTransformStyle(GHOST_EDITOR_DEFAULT_TRANSFORM)).toBe(
      "translate(-50%, -50%) translate(0px, 0px) rotate(0deg) scale(1)",
    );
  });

  it("clamps unsafe transform values to the editor contract", () => {
    expect(clampGhostPhotoTransform({
      offsetX: 9999,
      offsetY: -9999,
      scale: 99,
      rotation: -999,
    })).toEqual({
      offsetX: 900,
      offsetY: -900,
      scale: 2.5,
      rotation: -180,
    });
  });

  it("allows a quarter-turn rotation for landscape and portrait photos", () => {
    expect(clampGhostPhotoTransform({
      ...GHOST_EDITOR_DEFAULT_TRANSFORM,
      rotation: 90,
    }).rotation).toBe(90);
    expect(clampGhostPhotoTransform({
      ...GHOST_EDITOR_DEFAULT_TRANSFORM,
      rotation: -90,
    }).rotation).toBe(-90);
  });

  it("reports a soft 15 percent framing tolerance without rejecting edits", () => {
    expect(isGhostFramingWithinTolerance(GHOST_EDITOR_DEFAULT_TRANSFORM)).toBe(true);
    expect(isGhostFramingWithinTolerance({
      ...GHOST_EDITOR_DEFAULT_TRANSFORM,
      offsetX: GHOST_EDITOR_OUTPUT.width * 0.15,
      offsetY: GHOST_EDITOR_OUTPUT.height * 0.15,
    })).toBe(true);
    expect(isGhostFramingWithinTolerance({
      ...GHOST_EDITOR_DEFAULT_TRANSFORM,
      offsetX: GHOST_EDITOR_OUTPUT.width * 0.16,
    })).toBe(false);
  });

  it("builds a deterministic clean render plan with the privacy crop", () => {
    expect(createGhostPhotoRenderPlan(1600, 2400, GHOST_EDITOR_DEFAULT_TRANSFORM)).toEqual({
      canvasWidth: 1200,
      canvasHeight: 1476,
      sourceWidth: 1600,
      sourceHeight: 2400,
      baseScale: 0.75,
      privacyCutPixels: 324,
      draw: {
        translateX: 600,
        translateY: 576,
        rotationRadians: 0,
        scale: 0.75,
      },
    });
  });
});

describe("renderGhostPhoto", () => {
  it("renders only the transformed source into a clean JPEG", async () => {
    const calls: string[] = [];
    const canvas = {
      width: 0,
      height: 0,
      getContext: () => ({
        fillStyle: "",
        fillRect: () => calls.push("fillRect"),
        save: () => calls.push("save"),
        translate: () => calls.push("translate"),
        rotate: () => calls.push("rotate"),
        scale: () => calls.push("scale"),
        drawImage: () => calls.push("drawImage"),
        restore: () => calls.push("restore"),
      }),
    };
    const runtime: GhostPhotoCanvasRuntime = {
      decode: async () => ({ source: {} as unknown as CanvasImageSource, width: 1600, height: 2400, dispose: () => undefined }),
      createCanvas: () => canvas,
      toJpeg: async () => new Blob(["clean"], { type: "image/jpeg" }),
    };

    const { renderGhostPhoto } = await import("./ghostPhotoEditor");
    const output = await renderGhostPhoto(
      new File(["source"], "front.png", { type: "image/png" }),
      GHOST_EDITOR_DEFAULT_TRANSFORM,
      runtime,
    );

    expect(output.type).toBe("image/jpeg");
    expect(output.name).toMatch(/^body-photo-edited-.*\.jpg$/);
    expect(canvas.width).toBe(1200);
    expect(canvas.height).toBe(1476);
    expect(calls).toEqual(["fillRect", "save", "translate", "rotate", "scale", "drawImage", "restore"]);
  });
});
