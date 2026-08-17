import type { ExerciseDetail, ExerciseMediaAsset, MediaPresentation, MediaType } from "./types";

export type ExerciseMediaItem = {
  key: string;
  presentation: MediaPresentation | null;
  sort_order: number | null;
  media_path: string;
  media_type: MediaType;
  media_attribution: string | null;
};

export function buildExerciseMediaItems(
  exercise: Pick<ExerciseDetail, "media_path" | "media_type" | "media_attribution" | "media_assets">,
): ExerciseMediaItem[] {
  const seenPaths = new Set<string>();
  const items: ExerciseMediaItem[] = [];

  function addItem(item: ExerciseMediaItem) {
    if (!item.media_path || seenPaths.has(item.media_path)) return;
    seenPaths.add(item.media_path);
    let key = item.key;
    let suffix = 2;
    while (items.some((existing) => existing.key === key)) {
      key = `${item.key}-${suffix}`;
      suffix += 1;
    }
    items.push({ ...item, key });
  }

  const assets = [...(exercise.media_assets ?? [])].sort((left, right) =>
    left.sort_order - right.sort_order,
  );
  if (assets.length === 0) {
    addItem({
      key: "legacy",
      presentation: null,
      sort_order: null,
      media_path: exercise.media_path,
      media_type: exercise.media_type,
      media_attribution: exercise.media_attribution,
    });
  }

  for (const asset of assets) {
    addItem(mediaAssetToItem(asset));
  }

  return items;
}

function mediaAssetToItem(asset: ExerciseMediaAsset): ExerciseMediaItem {
  return {
    key: `${asset.presentation}-${asset.role}-${asset.sort_order}`,
    presentation: asset.presentation,
    sort_order: asset.sort_order,
    media_path: asset.media_path,
    media_type: asset.media_type,
    media_attribution: asset.media_attribution,
  };
}
