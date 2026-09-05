import { describe, expect, it } from "vitest";

import {
  clampGhostScale,
  getGhostGeometry,
  ghostPrivacyLineGeometry,
  isPointInZone,
  pointZoneDistance,
  transformGhostPoint,
  transformGhostZone,
} from "./ghostGeometry";

describe("ghostGeometry", () => {
  it("clamps ghostScale safely within min and max bounds", () => {
    expect(clampGhostScale(0.5)).toBe(0.75);
    expect(clampGhostScale(1.5)).toBe(1.15);
    expect(clampGhostScale(1.0)).toBe(1.0);
    expect(clampGhostScale(Number.NaN)).toBe(1.0);
  });

  it("transforms a point around the center (0.5, 0.5) according to ghostScale", () => {
    const center = transformGhostPoint({ x: 0.5, y: 0.5 }, 1.1);
    expect(center.x).toBeCloseTo(0.5);
    expect(center.y).toBeCloseTo(0.5);

    const scaledTop = transformGhostPoint({ x: 0.5, y: 0.2 }, 0.8);
    // 0.5 + (0.2 - 0.5) * 0.8 = 0.5 - 0.24 = 0.26
    expect(scaledTop.y).toBeCloseTo(0.26);

    const scaledBottom = transformGhostPoint({ x: 0.5, y: 0.9 }, 1.1);
    // 0.5 + (0.9 - 0.5) * 1.1 = 0.5 + 0.44 = 0.94
    expect(scaledBottom.y).toBeCloseTo(0.94);
  });

  it("mirrors points horizontally when mirrored is true", () => {
    const leftPoint = transformGhostPoint({ x: 0.35, y: 0.4 }, 1, true);
    expect(leftPoint.x).toBeCloseTo(0.65);
    expect(leftPoint.y).toBeCloseTo(0.4);
  });

  it("transforms zones correctly with scale and mirroring", () => {
    const zone = { minX: 0.3, maxX: 0.4, minY: 0.2, maxY: 0.3 };
    const scaled = transformGhostZone(zone, 1.0, true);
    // Mirroring swaps minX and maxX
    expect(scaled.minX).toBeCloseTo(0.6);
    expect(scaled.maxX).toBeCloseTo(0.7);
    expect(scaled.minY).toBeCloseTo(0.2);
    expect(scaled.maxY).toBeCloseTo(0.3);
  });

  it("provides view geometry for front, side, and back views", () => {
    const front = getGhostGeometry({ view: "front", ghostScale: 1.0 });
    expect(front.view).toBe("front");
    expect(front.mirrored).toBe(false);
    expect(front.zones.shoulders.minY).toBeLessThan(front.zones.hips.minY);
    expect(front.zones.hips.minY).toBeLessThan(front.zones.knees.minY);
    expect(front.zones.knees.minY).toBeLessThan(front.zones.ankles.minY);

    const back = getGhostGeometry({ view: "back", ghostScale: 1.0 });
    expect(back.view).toBe("back");
    // Back privacy line is higher (0.08 vs 0.16)
    expect(back.privacyLine.anchor.y).toBeLessThan(front.privacyLine.anchor.y);

    const sideRight = getGhostGeometry({ view: "side", sideProfile: "right", ghostScale: 1.0 });
    expect(sideRight.mirrored).toBe(false);
    expect(sideRight.sideVisibleChain).toBeDefined();

    const sideLeft = getGhostGeometry({ view: "side", sideProfile: "left", ghostScale: 1.0 });
    expect(sideLeft.mirrored).toBe(true);
    expect(sideLeft.sideVisibleChain).toBeDefined();
  });

  it("adapts expected body span when ghostScale changes", () => {
    const smaller = getGhostGeometry({ view: "front", ghostScale: 0.8 });
    const larger = getGhostGeometry({ view: "front", ghostScale: 1.1 });

    expect(smaller.expectedBodySpan.target).toBeLessThan(larger.expectedBodySpan.target);
  });

  it("checks point inside zone and computes zone distances", () => {
    const zone = { minX: 0.4, maxX: 0.6, minY: 0.2, maxY: 0.4 };
    expect(isPointInZone({ x: 0.5, y: 0.3 }, zone)).toBe(true);
    expect(isPointInZone({ x: 0.39, y: 0.3 }, zone)).toBe(false);
    expect(isPointInZone({ x: 0.39, y: 0.3 }, zone, 0.02)).toBe(true);

    expect(pointZoneDistance({ x: 0.5, y: 0.3 }, zone)).toBe(0);
    expect(pointZoneDistance({ x: 0.35, y: 0.3 }, zone)).toBeCloseTo(0.05);
  });

  it("produces identical privacy line geometry to ghostPhotoEditor", () => {
    const frontLine = ghostPrivacyLineGeometry("front", 1.0, false);
    expect(frontLine.anchor.x).toBeCloseTo(0.5);
    expect(frontLine.anchor.y).toBeCloseTo(0.16);
    expect(frontLine.start.x).toBeCloseTo(0.0);
    expect(frontLine.end.x).toBeCloseTo(1.0);

    const mirroredSideLine = ghostPrivacyLineGeometry("side", 0.9, true);
    expect(mirroredSideLine.anchor.x).toBeCloseTo(0.5);
    expect(mirroredSideLine.start.x).toBeLessThan(mirroredSideLine.end.x);
  });
});
