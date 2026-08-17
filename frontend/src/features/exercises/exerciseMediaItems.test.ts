import { describe, expect, it } from "vitest";

import { buildExerciseMediaItems } from "./exerciseMediaItems";

describe("buildExerciseMediaItems", () => {
  it("uses ordered gendered assets instead of legacy media when assets exist", () => {
    const items = buildExerciseMediaItems({
      media_path: "/media/legacy.mp4",
      media_type: "video",
      media_attribution: null,
      media_assets: [
        mediaAsset("/media/second.mp4", 1),
        mediaAsset("/media/first.mp4", 0),
      ],
    });

    expect(items.map((item) => item.media_path)).toEqual([
      "/media/first.mp4",
      "/media/second.mp4",
    ]);
  });

  it("uses legacy media when no gendered asset was returned", () => {
    const items = buildExerciseMediaItems({
      media_path: "/media/legacy.mp4",
      media_type: "video",
      media_attribution: null,
      media_assets: [],
    });

    expect(items.map((item) => item.media_path)).toEqual(["/media/legacy.mp4"]);
  });
});

function mediaAsset(media_path: string, sort_order: number) {
  return {
    presentation: "male" as const,
    role: "video" as const,
    sort_order,
    media_path,
    media_type: "video" as const,
    media_source_url: null,
    media_license: null,
    media_attribution: null,
  };
}
