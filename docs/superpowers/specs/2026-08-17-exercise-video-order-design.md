# Exercise video ordering design

## Goal

Allow an administrator to control the display order of multiple exercise videos independently for male and female users. The member exercise detail view selects the video group from the authenticated profile sex.

## Decisions

- Keep the existing `exercise_media_assets.sort_order` column and scope its order by presentation (`male` or `female`). No new ordering table or migration is needed.
- Add media asset IDs to the admin exercise response and use IDs when synchronizing existing assets. Reordering must preserve the existing media rows and files.
- The admin media editor keeps separate male and female tabs. Each visible item has accessible up/down controls. Moving an item renumbers only that tab from zero.
- The member exercise API filters returned media assets to the authenticated profile sex. The existing primary exercise media remains the fallback when no matching gendered asset exists.
- Existing asset metadata and uploaded files remain unchanged unless the administrator explicitly edits or replaces them.

## Backend

- Extend the admin media asset response with `id`.
- Make media synchronization ID-aware. Existing assets are temporarily moved to collision-free order values before their final presentation/order values are applied, allowing swaps without violating the unique constraint.
- Preserve the current multipart exercise create/update contract and upload validation.
- Load the completed profile for the exercise detail endpoint and return only matching gendered assets, ordered by `sort_order`.

## Frontend

- Carry the admin asset ID through the form conversion and payload serialization.
- Add up/down controls to `ExerciseMediaAssetsFields`; disable the first item's up control and the last item's down control.
- Renumber only the active male or female list after a move while preserving file upload indexes and metadata.
- Build member media from the filtered assets when present; otherwise use the legacy primary media. Multiple matching assets remain selectable/swipeable in their stored order.
- Add Persian and English labels for the ordering controls.

## Error handling

- Reject duplicate presentation/order values and invalid asset IDs through the existing validation path.
- Keep upload cleanup behavior unchanged on validation or database failure.
- If profile lookup cannot select a gendered asset, return the exercise normally with the legacy media fallback.

## Verification

- Backend tests cover ID-aware reorder swaps, independent male/female order, media-path preservation, admin response IDs, and member filtering/fallback.
- Frontend tests cover up/down controls, boundary disabling, independent tabs, preserved upload indexes, and member fallback/ordered display.
- Run focused backend/frontend tests, lint/type checks, frontend build, and the relevant live API smoke checks.
