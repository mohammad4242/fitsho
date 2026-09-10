import { expect, it, vi } from "vitest";

const { createBlankImage, loadFromFileAsync } = vi.hoisted(() => ({
  createBlankImage: vi.fn(),
  loadFromFileAsync: vi.fn(),
}));

vi.mock("react-native", () => ({ Platform: { OS: "android" } }));
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
      height: 1656,
      width: 1200,
    })),
    resizeAsync: vi.fn(async () => createImage()),
    rotateAsync: vi.fn(async () => createImage()),
    saveToTemporaryFileAsync: vi.fn(async () => "/cache/body-photo.jpg"),
    ...overrides,
  };
}

it("renders the transformed photo into a private JPEG on Android", async () => {
  const source = createImage();
  const canvas = createImage({ height: 1656, width: 1200 });
  const rendered = createImage({ height: 1656, width: 1200 });
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
    height: 1656,
    mimeType: "image/jpeg",
    privacyCropApplied: true,
    source: "library",
    uri: "file:///cache/body-photo.jpg",
    width: 1200,
  });

  expect(loadFromFileAsync).toHaveBeenCalledWith("/cache/source.png");
  expect(createBlankImage).toHaveBeenCalledWith(
    1200,
    1656,
    false,
    { r: 160 / 255, g: 163 / 255, b: 161 / 255 },
  );
  expect(canvas.renderIntoAsync).toHaveBeenCalledWith(
    source,
    0,
    -144,
    1200,
    1656,
  );
  expect(rendered.saveToTemporaryFileAsync).toHaveBeenCalledWith("jpg", 92);
});

it("uses the female neck crop for the selected view", async () => {
  const source = createImage();
  const canvas = createImage({ height: 1701, width: 1200 });
  const rendered = createImage({ height: 1701, width: 1200 });
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
    1701,
    false,
    expect.any(Object),
  );
});
