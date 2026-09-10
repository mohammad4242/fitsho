import { beforeEach, expect, it, vi } from "vitest";

const { createBlankImage, loadFromFileAsync } = vi.hoisted(() => ({
  createBlankImage: vi.fn(),
  loadFromFileAsync: vi.fn(),
}));

vi.mock("react-native", () => ({ Platform: { OS: "android" } }));
vi.mock("react-native-nitro-image", () => ({
  Images: { createBlankImage, loadFromFileAsync },
}));

import { ghostPrivacyLineGeometry } from "@fitician/core/body-ghost";
import { GHOST_EDITOR_DEFAULT_TRANSFORM } from "@fitician/core/body-ghost-editor";

import { renderNativeGhostPhoto } from "./nativeGhostPhotoRenderer";

const savedMarkerImages = new Map<string, MarkerImage>();

type Marker = "above" | "boundary" | "below";

class MarkerImage {
  readonly height: number;
  readonly width: number;
  private readonly markerSource: MarkerImage | null;
  private readonly originY: number;
  private readonly drawHeight: number;
  private readonly boundarySourceY: number;

  constructor(
    width: number,
    height: number,
    options: {
      boundarySourceY?: number;
      drawHeight?: number;
      markerSource?: MarkerImage | null;
      originY?: number;
    } = {},
  ) {
    this.width = width;
    this.height = height;
    this.boundarySourceY = options.boundarySourceY ?? 0;
    this.drawHeight = options.drawHeight ?? height;
    this.markerSource = options.markerSource ?? null;
    this.originY = options.originY ?? 0;
  }

  async renderIntoAsync(
    source: MarkerImage,
    x: number,
    y: number,
    right: number,
    bottom: number,
  ): Promise<MarkerImage> {
    return new MarkerImage(right - x, bottom - y, {
      boundarySourceY: source.boundarySourceY,
      drawHeight: bottom - y,
      markerSource: source,
      originY: y,
    });
  }

  async saveToTemporaryFileAsync(): Promise<string> {
    const path = `/cache/body-photo-marker-${savedMarkerImages.size}.jpg`;
    savedMarkerImages.set(path, this);
    return path;
  }

  markerAt(outputY: number): Marker {
    if (this.markerSource === null) return "above";
    const sourceY = Math.floor(
      ((outputY - this.originY) * this.markerSource.height) / this.drawHeight,
    );
    if (sourceY < this.boundarySourceY - 2) return "above";
    if (sourceY <= this.boundarySourceY + 2) return "boundary";
    return "below";
  }
}

function createImage(overrides: Record<string, unknown> = {}) {
  return {
    height: 2400,
    width: 1600,
    renderIntoAsync: vi.fn(async () => createImage({
      height: 1656,
      width: 1200,
    })),
    resizeAsync: vi.fn(async () => createImage()),
    rotateAsync: vi.fn(async () => createImage()),
    saveToTemporaryFileAsync: vi.fn(async () => "/cache/body-photo.jpg"),
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  savedMarkerImages.clear();
});

it("renders the transformed photo into a private JPEG on Android", async () => {
  const source = createImage();
  const canvas = createImage({ height: 1620, width: 1200 });
  const rendered = createImage({ height: 1620, width: 1200 });
  source.renderIntoAsync = vi.fn(async () => rendered);
  canvas.renderIntoAsync = vi.fn(async () => rendered);
  loadFromFileAsync.mockResolvedValue(source);
  createBlankImage.mockReturnValue(canvas);

  await expect(renderNativeGhostPhoto({
    height: 2400,
    source: "library",
    uri: "file:///cache/source.png",
    width: 1600,
    transform: GHOST_EDITOR_DEFAULT_TRANSFORM,
    view: "front",
    ghostScale: 1,
    ghostVariant: "male",
  })).resolves.toEqual({
    height: 1620,
    mimeType: "image/jpeg",
    privacyCropApplied: true,
    source: "library",
    uri: "file:///cache/body-photo.jpg",
    width: 1200,
  });

  expect(loadFromFileAsync).toHaveBeenCalledWith("/cache/source.png");
  expect(createBlankImage).toHaveBeenCalledWith(
    1200,
    1620,
    false,
    { r: 160 / 255, g: 163 / 255, b: 161 / 255 },
  );
  expect(canvas.renderIntoAsync).toHaveBeenCalledWith(
    source,
    0,
    -180,
    1200,
    1620,
  );
  expect(rendered.saveToTemporaryFileAsync).toHaveBeenCalledWith("jpg", 92);
});

it("uses the female Ghost top crop for the selected view", async () => {
  const source = createImage();
  const canvas = createImage({ height: 1759, width: 1200 });
  const rendered = createImage({ height: 1759, width: 1200 });
  canvas.renderIntoAsync = vi.fn(async () => rendered);
  loadFromFileAsync.mockResolvedValue(source);
  createBlankImage.mockReturnValue(canvas);

  await renderNativeGhostPhoto({
    height: 2400,
    source: "camera",
    uri: "file:///cache/source.jpg",
    width: 1600,
    transform: GHOST_EDITOR_DEFAULT_TRANSFORM,
    view: "back",
    ghostScale: 1,
    ghostVariant: "female",
  });

  expect(createBlankImage).toHaveBeenCalledWith(
    1200,
    1759,
    false,
    expect.any(Object),
  );
});

it.each([
  ["male", "front", 1, false, 240, 1620],
  ["male", "side", 1, false, 250, 1612],
  ["male", "back", 1, false, 38, 1771],
  ["female", "front", 1, false, 264, 1602],
  ["female", "side", 1, false, 264, 1602],
  ["female", "back", 1, false, 55, 1759],
  ["male", "side", 1.1, true, 155, 1684],
] as const)("keeps the privacy boundary as the first native JPEG row for %s/%s scale %s", async (
  variant,
  view,
  ghostScale,
  mirrored,
  boundarySourceY,
  expectedHeight,
) => {
  const source = new MarkerImage(1600, 2400, { boundarySourceY });
  const canvas = new MarkerImage(1200, expectedHeight);
  loadFromFileAsync.mockResolvedValue(source);
  createBlankImage.mockReturnValue(canvas);

  const rightLine = ghostPrivacyLineGeometry(view, ghostScale, false, variant);
  const visibleLine = ghostPrivacyLineGeometry(view, ghostScale, mirrored, variant);
  expect(visibleLine.anchor.y).toBe(rightLine.anchor.y);

  const output = await renderNativeGhostPhoto({
    height: 2400,
    source: "library",
    uri: "file:///cache/source-marker.jpg",
    width: 1600,
    transform: GHOST_EDITOR_DEFAULT_TRANSFORM,
    view,
    ghostScale,
    ghostVariant: variant,
  });
  const rendered = savedMarkerImages.get(output.uri.replace("file://", ""));

  expect(rendered).toBeDefined();
  expect(rendered?.markerAt(0)).toBe("boundary");
  expect(rendered?.markerAt(4)).toBe("below");
  for (let row = 0; row < output.height; row += 1) {
    expect(rendered?.markerAt(row)).not.toBe("above");
  }
});
