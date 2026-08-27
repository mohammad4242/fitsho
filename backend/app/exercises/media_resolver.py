from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.exercises.enums import MediaPresentation, MediaType
from app.exercises.models import Exercise, ExerciseMediaAsset


@dataclass(frozen=True)
class ResolvedMedia:
    path: str
    media_type: MediaType


_PRESENTATION_ORDER = {
    MediaPresentation.UNSPECIFIED: 0,
    MediaPresentation.MALE: 1,
    MediaPresentation.FEMALE: 2,
}


def is_valid_media_asset(asset: ExerciseMediaAsset) -> bool:
    return (
        asset.media_type is not MediaType.PLACEHOLDER
        and "placeholder" not in asset.media_path.casefold()
        and bool(asset.media_path.strip())
    )


def valid_media_assets(exercise: Exercise) -> list[ExerciseMediaAsset]:
    return [asset for asset in exercise.media_assets if is_valid_media_asset(asset)]


def ordered_media_assets(
    assets: Iterable[ExerciseMediaAsset],
    preferred: MediaPresentation | None = None,
) -> list[ExerciseMediaAsset]:
    def key(asset: ExerciseMediaAsset) -> tuple[int, int, int, str]:
        preferred_rank = 0 if preferred is not None and asset.presentation is preferred else 1
        return (
            preferred_rank,
            _PRESENTATION_ORDER[asset.presentation],
            asset.sort_order,
            str(asset.id),
        )

    return sorted(assets, key=key)


def resolve_primary_media(
    exercise: Exercise,
    preferred: MediaPresentation | None = None,
) -> ResolvedMedia:
    assets = ordered_media_assets(valid_media_assets(exercise), preferred)
    if assets:
        asset = assets[0]
        return ResolvedMedia(path=asset.media_path, media_type=asset.media_type)
    return ResolvedMedia(path=exercise.media_path, media_type=exercise.media_type)
