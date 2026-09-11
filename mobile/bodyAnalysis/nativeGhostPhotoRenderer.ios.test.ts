import { beforeEach, expect, it, vi } from "vitest";

const { createBlankImage, loadFromFileAsync } = vi.hoisted(() => ({
  createBlankImage: vi.fn(),
  loadFromFileAsync: vi.fn(),
}));

vi.mock("react-native", () => ({ Platform: { OS: "ios" } }));
vi.mock("react-native-nitro-image", () => ({
  Images: { createBlankImage, loadFromFileAsync },
}));

import { GHOST_EDITOR_DEFAULT_TRANSFORM } from "@fitician/core/body-ghost-editor";

import { renderNativeGhostPhoto } from "./nativeGhostPhotoRenderer";

function createImage(overrides: Record<string, unknown> = {}) {
  return {
    height: 2400,
    width: 1600,
    renderIntoAsync: vi.fn(async () => createImage({
      height: 1620,
      width: 1200,
    })),
    rotateAsync: vi.fn(async () => createImage()),
    saveToTemporaryFileAsync: vi.fn(async () => "/cache/body-photo-ios.jpg"),
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

it("passes destination width and height to Nitro Image on iOS", async () => {
  const source = createImage();
  const canvas = createImage({ height: 1620, width: 1200 });
  const rendered = createImage({ height: 1620, width: 1200 });
  canvas.renderIntoAsync = vi.fn(async () => rendered);
  loadFromFileAsync.mockResolvedValue(source);
  createBlankImage.mockReturnValue(canvas);

  await expect(renderNativeGhostPhoto({
    height: 2400,
    source: "camera",
    uri: "file:///cache/source-ios.jpg",
    width: 1600,
    transform: GHOST_EDITOR_DEFAULT_TRANSFORM,
    view: "front",
    ghostScale: 1,
    ghostVariant: "male",
  })).resolves.toMatchObject({
    mimeType: "image/jpeg",
    privacyCropApplied: true,
    source: "camera",
    uri: "file:///cache/body-photo-ios.jpg",
  });

  expect(canvas.renderIntoAsync).toHaveBeenCalledWith(
    source,
    0,
    -180,
    1200,
    1800,
  );
  expect(rendered.saveToTemporaryFileAsync).toHaveBeenCalledWith("jpg", 92);
});
