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
    primary_path: str | None = None,
    *,
    preserve_input_order_if_unpinned: bool = False,
) -> list[ExerciseMediaAsset]:
    materialized = list(assets)
    if (
        preserve_input_order_if_unpinned
        and primary_path is not None
        and not any(
            asset.media_path == primary_path and is_valid_media_asset(asset)
            for asset in materialized
        )
    ):
        return materialized

    def key(asset: ExerciseMediaAsset) -> tuple[int, int, int, int, str]:
        primary_rank = (
            0
            if primary_path is not None
            and asset.media_path == primary_path
            and is_valid_media_asset(asset)
            else 1
        )
        preferred_rank = 0 if preferred is not None and asset.presentation is preferred else 1
        return (
            primary_rank,
            preferred_rank,
            _PRESENTATION_ORDER[asset.presentation],
            asset.sort_order,
            str(asset.id),
        )

    return sorted(materialized, key=key)


def resolve_primary_media(
    exercise: Exercise,
    preferred: MediaPresentation | None = None,
) -> ResolvedMedia:
    assets = ordered_media_assets(
        valid_media_assets(exercise),
        preferred,
        primary_path=exercise.media_path,
    )
    if assets:
        asset = assets[0]
        return ResolvedMedia(path=asset.media_path, media_type=asset.media_type)
    return ResolvedMedia(path=exercise.media_path, media_type=exercise.media_type)
