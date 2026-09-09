import type { components } from "@fitician/core";

import type { ExerciseDetail } from "./exerciseApi";

export type ExerciseMediaItem = {
  readonly key: string;
  readonly mediaAttribution: string | null;
  readonly mediaPath: string;
  readonly mediaType: components["schemas"]["MediaType"];
  readonly presentation: components["schemas"]["MediaPresentation"] | null;
  readonly sortOrder: number | null;
};

type ExerciseMediaSource = Pick<
  ExerciseDetail,
  "media_assets" | "media_attribution" | "media_path" | "media_type"
>;

export function buildExerciseMediaItems(exercise: ExerciseMediaSource): ExerciseMediaItem[] {
  const seenPaths = new Set<string>();
  const items: ExerciseMediaItem[] = [];
  const addItem = (item: ExerciseMediaItem) => {
    if (!item.mediaPath || seenPaths.has(item.mediaPath)) return;
    seenPaths.add(item.mediaPath);
    let key = item.key;
    let suffix = 2;
    while (items.some((existing) => existing.key === key)) {
      key = `${item.key}-${suffix}`;
      suffix += 1;
    }
    items.push({ ...item, key });
  };

  const assets = [...(exercise.media_assets ?? [])]
    .filter((asset) => asset.media_type !== "placeholder" && !asset.media_path.includes("placeholder"))
    .sort((left, right) => left.sort_order - right.sort_order);
  const primaryIndex = assets.findIndex((asset) => asset.media_path === exercise.media_path);
  if (primaryIndex > 0) {
    const [primary] = assets.splice(primaryIndex, 1);
    if (primary !== undefined) assets.unshift(primary);
  }

  for (const asset of assets) {
    addItem({
      key: `${asset.presentation}-${asset.role}-${asset.sort_order}`,
      mediaAttribution: asset.media_attribution,
      mediaPath: asset.media_path,
      mediaType: asset.media_type,
      presentation: asset.presentation,
      sortOrder: asset.sort_order,
    });
  }

  if (items.length === 0) {
    addItem({
      key: "legacy",
      mediaAttribution: exercise.media_attribution,
      mediaPath: exercise.media_path,
      mediaType: exercise.media_type,
      presentation: null,
      sortOrder: null,
    });
  }

  return items;
}

export function resolveExerciseMediaUrl(path: string, apiBaseUrl: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${apiBaseUrl.replace(/\/+$/u, "")}/${path.replace(/^\/+/, "")}`;
}

export function isExerciseMediaRenderable(
  path: string,
  mediaType: components["schemas"]["MediaType"],
): boolean {
  return path.trim() !== ""
    && mediaType !== "placeholder"
    && !path.toLowerCase().includes("placeholder");
}
