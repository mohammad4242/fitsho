import { describe, expect, it } from "vitest";

import {
  buildExerciseMediaItems,
  isExerciseMediaRenderable,
  resolveExerciseMediaUrl,
} from "./exerciseMedia";

describe("native exercise media", () => {
  it("preserves backend ordering and pins the backend primary asset", () => {
    const items = buildExerciseMediaItems({
      media_attribution: null,
      media_assets: [
        mediaAsset("/media/second.mp4", 1),
        mediaAsset("/media/primary.mp4", 4),
        mediaAsset("/media/first.mp4", 0),
      ],
      media_path: "/media/primary.mp4",
      media_type: "video",
    });

    expect(items.map((item) => item.mediaPath)).toEqual([
      "/media/primary.mp4",
      "/media/first.mp4",
      "/media/second.mp4",
    ]);
  });

  it("falls back to legacy media when assets are absent or placeholders", () => {
    expect(buildExerciseMediaItems({
      media_attribution: "legacy",
      media_assets: [],
      media_path: "/media/legacy.gif",
      media_type: "gif",
    })).toEqual([
      expect.objectContaining({ mediaPath: "/media/legacy.gif", presentation: null }),
    ]);

    expect(buildExerciseMediaItems({
      media_attribution: null,
      media_assets: [mediaAsset("/exercises/exercise-placeholder.svg", 0, "placeholder")],
      media_path: "/media/legacy.mp4",
      media_type: "video",
    })).toEqual([
      expect.objectContaining({ mediaPath: "/media/legacy.mp4", presentation: null }),
    ]);
  });

  it("deduplicates matching paths and resolves relative media against the API origin", () => {
    const items = buildExerciseMediaItems({
      media_attribution: null,
      media_assets: [mediaAsset("/media/primary.mp4", 0), mediaAsset("/media/other.mp4", 1)],
      media_path: "/media/primary.mp4",
      media_type: "video",
    });

    expect(items).toHaveLength(2);
    expect(resolveExerciseMediaUrl("/media/primary.mp4", "https://api.fitician.test/")).toBe(
      "https://api.fitician.test/media/primary.mp4",
    );
    expect(resolveExerciseMediaUrl("https://cdn.fitician.test/video.mp4", "https://api.fitician.test")).toBe(
      "https://cdn.fitician.test/video.mp4",
    );
  });

  it("accepts real GIF, image, and video media but rejects placeholders", () => {
    expect(isExerciseMediaRenderable("/media/row.gif", "gif")).toBe(true);
    expect(isExerciseMediaRenderable("/media/row.webp", "image")).toBe(true);
    expect(isExerciseMediaRenderable("/media/row.webp", "animated_webp")).toBe(true);
    expect(isExerciseMediaRenderable("/media/row.mp4", "video")).toBe(true);
    expect(isExerciseMediaRenderable("/exercises/exercise-placeholder.svg", "placeholder")).toBe(false);
    expect(isExerciseMediaRenderable("", "gif")).toBe(false);
  });
});

function mediaAsset(
  mediaPath: string,
  sortOrder: number,
  mediaType: "video" | "placeholder" = "video",
) {
  return {
    media_attribution: null,
    media_license: null,
    media_path: mediaPath,
    media_source_url: null,
    media_type: mediaType,
    presentation: "male" as const,
    role: "video" as const,
    sort_order: sortOrder,
  };
}
