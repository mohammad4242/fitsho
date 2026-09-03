import { describe, expect, it } from "vitest";

import {
  GHOST_EDITOR_DEFAULT_TRANSFORM,
  GHOST_EDITOR_OUTPUT,
  clampGhostPhotoTransform,
  createGhostPhotoRenderPlan,
  ghostPrivacyLineGeometry,
  ghostPhotoTransformStyle,
  isGhostFramingWithinTolerance,
  privacyCropSourceYForView,
  type GhostPhotoRenderPlan,
  type GhostPhotoTransform,
  type GhostPhotoCanvasRuntime,
} from "./ghostPhotoEditor";
import type { BodyPhotoView } from "./types";

const createGhostPhotoRenderPlanForView = createGhostPhotoRenderPlan as (
  sourceWidth: number,
  sourceHeight: number,
  transform: GhostPhotoTransform,
  view: BodyPhotoView,
) => GhostPhotoRenderPlan;

describe("ghost photo transform", () => {
  it("starts centered with a neutral transform", () => {
    expect(GHOST_EDITOR_DEFAULT_TRANSFORM).toEqual({
      scale: 1,
      translateX: 0,
      translateY: 0,
      rotation: 0,
    });
    expect(ghostPhotoTransformStyle(GHOST_EDITOR_DEFAULT_TRANSFORM)).toBe(
      "translate(0%, 0%) rotate(0deg) scale(1)",
    );
  });

  it("clamps unsafe transform values to the editor contract", () => {
    expect(clampGhostPhotoTransform({
      translateX: 9999,
      translateY: -9999,
      scale: 99,
      rotation: -999,
    })).toEqual({
      translateX: 0.5,
      translateY: -0.5,
      scale: 1.15,
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
      translateX: 0.15,
      translateY: 0.15,
    })).toBe(true);
    expect(isGhostFramingWithinTolerance({
      ...GHOST_EDITOR_DEFAULT_TRANSFORM,
      translateX: 0.16,
    })).toBe(false);
  });

  it("moves the privacy line with the Ghost translation", () => {
    const line = ghostPrivacyLineGeometry("front", {
      ...GHOST_EDITOR_DEFAULT_TRANSFORM,
      translateY: 0.12,
    });

    expect(line.anchor.y).toBeCloseTo(0.28, 6);
    expect(line.start.x).toBeCloseTo(0, 6);
    expect(line.end.x).toBeCloseTo(1, 6);
    expect(line.start.y).toBeCloseTo(line.anchor.y, 6);
    expect(line.end.y).toBeCloseTo(line.anchor.y, 6);
  });

  it("moves the privacy line horizontally with the Ghost", () => {
    const line = ghostPrivacyLineGeometry("front", {
      ...GHOST_EDITOR_DEFAULT_TRANSFORM,
      translateX: 0.12,
    });

    expect(line.anchor.x).toBeCloseTo(0.62, 6);
    expect(line.start.x).toBeCloseTo(0.12, 6);
    expect(line.end.x).toBeCloseTo(1.12, 6);
  });

  it("recomputes the privacy anchor when the Ghost is scaled", () => {
    const line = ghostPrivacyLineGeometry("front", {
      ...GHOST_EDITOR_DEFAULT_TRANSFORM,
      scale: 0.8,
    });

    expect(line.anchor.y).toBeCloseTo(0.228, 6);
  });

  it("uses rotation while calculating the transformed privacy anchor", () => {
    const line = ghostPrivacyLineGeometry("front", {
      ...GHOST_EDITOR_DEFAULT_TRANSFORM,
      rotation: 90,
    });

    expect(line.anchor.x).toBeCloseTo(0.84, 6);
    expect(line.anchor.y).toBeCloseTo(0.5, 6);
  });

  it("maps the visible line through responsive contain geometry to source pixels", () => {
    const sourceY = privacyCropSourceYForView(
      "front",
      GHOST_EDITOR_DEFAULT_TRANSFORM,
      { width: 320, height: 480 },
      { width: 900, height: 1200 },
    );

    expect(sourceY).toBeCloseTo(141, 0);
  });

  it("keeps the same crop mapping when the preview uses a different size", () => {
    expect(privacyCropSourceYForView(
      "front",
      GHOST_EDITOR_DEFAULT_TRANSFORM,
      { width: 390, height: 585 },
      { width: 1200, height: 1800 },
    )).toBeCloseTo(288, 6);
  });

  it("uses the transformed visible line for the encoded crop", () => {
    const transform = {
      ...GHOST_EDITOR_DEFAULT_TRANSFORM,
      scale: 0.8,
      translateY: 0.12,
    };
    const line = ghostPrivacyLineGeometry("front", transform);
    const sourceY = privacyCropSourceYForView(
      "front",
      transform,
      GHOST_EDITOR_OUTPUT,
      { width: 1600, height: 2400 },
    );

    expect(line.anchor.y * GHOST_EDITOR_OUTPUT.height).toBeCloseTo(626.4, 6);
    expect(sourceY).toBeCloseTo(835.2, 6);
    expect(Math.round(sourceY)).toBe(835);
  });

  it.each(["front", "side", "back"] as const)(
    "maps the visible %s privacy line to the source crop",
    (view) => {
      const expectedSourceY = view === "back" ? 192 : 384;

      expect(privacyCropSourceYForView(
        view,
        GHOST_EDITOR_DEFAULT_TRANSFORM,
        GHOST_EDITOR_OUTPUT,
        { width: 1600, height: 2400 },
      )).toBeCloseTo(expectedSourceY, 6);
    },
  );

  it("builds a deterministic clean render plan with the privacy crop", () => {
    expect(createGhostPhotoRenderPlan(1600, 2400, GHOST_EDITOR_DEFAULT_TRANSFORM)).toEqual({
      canvasWidth: 1200,
      canvasHeight: 1512,
      sourceWidth: 1600,
      sourceHeight: 2400,
      baseScale: 0.75,
      sourceCropY: 384,
      privacyCutPixels: 288,
      privacyLineDisplayY: 288,
      draw: {
        sourceX: 0,
        sourceY: 384,
        sourceWidth: 1600,
        sourceHeight: 2016,
        destinationX: 0,
        destinationY: 0,
        destinationWidth: 1200,
        destinationHeight: 1512,
      },
    });
  });

  it("raises the privacy boundary for the back render plan", () => {
    expect(createGhostPhotoRenderPlanForView(
      1600,
      2400,
      GHOST_EDITOR_DEFAULT_TRANSFORM,
      "back",
    )).toMatchObject({
      canvasHeight: 1656,
      sourceCropY: 192,
      privacyCutPixels: 144,
      privacyLineDisplayY: 144,
      draw: { sourceY: 192, sourceHeight: 2208 },
    });
  });
});

describe("renderGhostPhoto", () => {
  it("renders the source from the visible privacy line into a clean JPEG", async () => {
    const calls: string[] = [];
    const canvas = {
      width: 0,
      height: 0,
      getContext: () => ({
        fillStyle: "",
        fillRect: () => calls.push("fillRect"),
        drawImage: (...args: unknown[]) => calls.push(`drawImage:${args.slice(1).join(",")}`),
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
      "front",
      runtime,
    );

    expect(output.type).toBe("image/jpeg");
    expect(output.name).toMatch(/^body-photo-edited-.*\.jpg$/);
    expect(canvas.width).toBe(1200);
    expect(canvas.height).toBe(1512);
    expect(calls).toEqual(["fillRect", "drawImage:0,384,1600,2016,0,0,1200,1512"]);
  });

  it("renders the higher back crop into a taller clean JPEG", async () => {
    const canvas = {
      width: 0,
      height: 0,
      getContext: () => ({
        fillStyle: "",
        fillRect: () => undefined,
        save: () => undefined,
        translate: () => undefined,
        rotate: () => undefined,
        scale: () => undefined,
        drawImage: () => undefined,
        restore: () => undefined,
      }),
    };
    const runtime: GhostPhotoCanvasRuntime = {
      decode: async () => ({ source: {} as unknown as CanvasImageSource, width: 1600, height: 2400, dispose: () => undefined }),
      createCanvas: () => canvas,
      toJpeg: async () => new Blob(["clean"], { type: "image/jpeg" }),
    };

    const { renderGhostPhoto } = await import("./ghostPhotoEditor");
    await renderGhostPhoto(
      new File(["source"], "back.png", { type: "image/png" }),
      GHOST_EDITOR_DEFAULT_TRANSFORM,
      "back",
      runtime,
    );

    expect(canvas.width).toBe(1200);
    expect(canvas.height).toBe(1656);
  });
});
