# Exercise media carousel design

## Scope

Add mobile swipe navigation for the media belonging to one exercise detail
page without changing `ExerciseMedia` from a simple media renderer or removing
the existing desktop selector.

## Behavior

- Build one deterministic media list from the legacy/default media followed by
  `media_assets` in their existing order.
- Deduplicate by `media_path`; the first occurrence wins.
- Start on the legacy/default item when it is unique, otherwise start on the
  first asset.
- On mobile, a clear physical left swipe advances and a physical right swipe
  goes back, regardless of document direction.
- Ignore vertical movement and short movement. Keep native video controls
  usable by ignoring gestures that begin in the video control strip.
- Show a position indicator only when the list has more than one item.
- Keep the desktop selector for lists with more than one item and hide it on
  mobile.

## Components and tests

`ExerciseMediaCarousel` owns the media list, selected index, and pointer
gesture handling. `ExerciseMedia` remains responsible only for rendering one
image or video. Tests cover list deduplication, legacy preservation, index
changes in both directions, single-item UI, and the existing desktop selector.
